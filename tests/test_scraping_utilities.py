"""
Unit tests for scraping utilities with mocked responses.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock
from urllib.parse import urlparse

from src.scraping.robots_checker import RobotsChecker
from src.scraping.rate_limiter import RateLimiter, RateLimitConfig
from src.scraping.header_randomizer import HeaderRandomizer
from src.scraping.retry_handler import RetryHandler, RetryConfig, RetryableError, NonRetryableError


class TestRobotsChecker:
    """Test cases for RobotsChecker."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.robots_checker = RobotsChecker()
    
    @patch('urllib.robotparser.RobotFileParser')
    def test_can_fetch_allowed_url(self, mock_robot_parser):
        """Test that allowed URLs return True."""
        # Mock robots.txt parser
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_robot_parser.return_value = mock_parser
        
        result = self.robots_checker.can_fetch("https://example.com/allowed-page")
        
        assert result is True
        mock_parser.can_fetch.assert_called_once()
    
    @patch('urllib.robotparser.RobotFileParser')
    def test_can_fetch_disallowed_url(self, mock_robot_parser):
        """Test that disallowed URLs return False."""
        # Mock robots.txt parser
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = False
        mock_robot_parser.return_value = mock_parser
        
        result = self.robots_checker.can_fetch("https://example.com/disallowed-page")
        
        assert result is False
        mock_parser.can_fetch.assert_called_once()
    
    @patch('urllib.robotparser.RobotFileParser')
    def test_can_fetch_with_custom_user_agent(self, mock_robot_parser):
        """Test can_fetch with custom user agent."""
        mock_parser = Mock()
        mock_parser.can_fetch.return_value = True
        mock_robot_parser.return_value = mock_parser
        
        result = self.robots_checker.can_fetch(
            "https://example.com/page", 
            user_agent="CustomBot/1.0"
        )
        
        assert result is True
        mock_parser.can_fetch.assert_called_with("CustomBot/1.0", "https://example.com/page")
    
    @patch('urllib.robotparser.RobotFileParser')
    def test_get_crawl_delay(self, mock_robot_parser):
        """Test getting crawl delay from robots.txt."""
        mock_parser = Mock()
        mock_parser.crawl_delay.return_value = 5.0
        mock_robot_parser.return_value = mock_parser
        
        delay = self.robots_checker.get_crawl_delay("https://example.com/page")
        
        assert delay == 5.0
        mock_parser.crawl_delay.assert_called_once()
    
    @patch('urllib.robotparser.RobotFileParser')
    def test_robots_txt_fetch_failure(self, mock_robot_parser):
        """Test handling of robots.txt fetch failures."""
        # Mock parser that raises exception on read()
        mock_parser = Mock()
        mock_parser.read.side_effect = Exception("Network error")
        mock_robot_parser.return_value = mock_parser
        
        # Should return True (permissive) when robots.txt can't be fetched
        result = self.robots_checker.can_fetch("https://example.com/page")
        
        assert result is True
    
    def test_cache_functionality(self):
        """Test that robots.txt responses are cached."""
        with patch('urllib.robotparser.RobotFileParser') as mock_robot_parser:
            mock_parser = Mock()
            mock_parser.can_fetch.return_value = True
            mock_robot_parser.return_value = mock_parser
            
            # First call
            self.robots_checker.can_fetch("https://example.com/page1")
            # Second call to same domain
            self.robots_checker.can_fetch("https://example.com/page2")
            
            # Should only create one parser instance (cached)
            assert mock_robot_parser.call_count == 1
    
    def test_clear_cache(self):
        """Test cache clearing functionality."""
        with patch('urllib.robotparser.RobotFileParser') as mock_robot_parser:
            mock_parser = Mock()
            mock_parser.can_fetch.return_value = True
            mock_robot_parser.return_value = mock_parser
            
            # Make a call to populate cache
            self.robots_checker.can_fetch("https://example.com/page")
            
            # Clear cache
            self.robots_checker.clear_cache()
            
            # Make another call - should create new parser
            self.robots_checker.can_fetch("https://example.com/page")
            
            assert mock_robot_parser.call_count == 2


class TestRateLimiter:
    """Test cases for RateLimiter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config = RateLimitConfig(base_delay=0.1, jitter=False)  # Fast tests
        self.rate_limiter = RateLimiter(config)
    
    @pytest.mark.asyncio
    async def test_basic_rate_limiting(self):
        """Test basic rate limiting functionality."""
        domain = "example.com"
        
        start_time = time.time()
        
        # First request should not wait
        await self.rate_limiter.wait_if_needed(domain)
        first_request_time = time.time()
        
        # Second request should wait
        await self.rate_limiter.wait_if_needed(domain)
        second_request_time = time.time()
        
        # Should have waited at least the base delay
        elapsed = second_request_time - first_request_time
        assert elapsed >= 0.1  # base_delay
    
    @pytest.mark.asyncio
    async def test_per_domain_rate_limiting(self):
        """Test that rate limiting is per-domain."""
        domain1 = "example.com"
        domain2 = "another.com"
        
        # Make request to first domain
        await self.rate_limiter.wait_if_needed(domain1)
        
        start_time = time.time()
        # Request to second domain should not wait
        await self.rate_limiter.wait_if_needed(domain2)
        elapsed = time.time() - start_time
        
        # Should not have waited significantly
        assert elapsed < 0.05
    
    def test_record_success_resets_failures(self):
        """Test that recording success resets failure count."""
        domain = "example.com"
        
        # Record some failures
        self.rate_limiter.record_failure(domain)
        self.rate_limiter.record_failure(domain)
        
        # Check that delay is increased
        delay_with_failures = self.rate_limiter.get_current_delay(domain)
        assert delay_with_failures > self.rate_limiter.config.base_delay
        
        # Record success
        self.rate_limiter.record_success(domain)
        
        # Delay should be back to base
        delay_after_success = self.rate_limiter.get_current_delay(domain)
        assert delay_after_success == self.rate_limiter.config.base_delay
    
    def test_exponential_backoff(self):
        """Test exponential backoff on failures."""
        domain = "example.com"
        
        base_delay = self.rate_limiter.config.base_delay
        
        # No failures - base delay
        assert self.rate_limiter.get_current_delay(domain) == base_delay
        
        # One failure - 2x base delay
        self.rate_limiter.record_failure(domain)
        assert self.rate_limiter.get_current_delay(domain) == base_delay * 2
        
        # Two failures - 4x base delay
        self.rate_limiter.record_failure(domain)
        assert self.rate_limiter.get_current_delay(domain) == base_delay * 4
    
    def test_should_retry_logic(self):
        """Test retry logic based on failure count."""
        domain = "example.com"
        
        # Should retry initially
        assert self.rate_limiter.should_retry(domain) is True
        
        # Record failures up to max retries
        for _ in range(self.rate_limiter.config.max_retries):
            self.rate_limiter.record_failure(domain)
        
        # Should not retry after max failures
        assert self.rate_limiter.should_retry(domain) is False
    
    @pytest.mark.asyncio
    async def test_robots_delay_respected(self):
        """Test that robots.txt crawl delay is respected."""
        domain = "example.com"
        robots_delay = 0.2  # Higher than base delay
        
        start_time = time.time()
        await self.rate_limiter.wait_if_needed(domain, respect_robots_delay=robots_delay)
        first_time = time.time()
        
        await self.rate_limiter.wait_if_needed(domain, respect_robots_delay=robots_delay)
        second_time = time.time()
        
        elapsed = second_time - first_time
        assert elapsed >= robots_delay
    
    def test_get_stats(self):
        """Test statistics collection."""
        domain = "example.com"
        
        self.rate_limiter.record_failure(domain)
        stats = self.rate_limiter.get_stats()
        
        assert domain in stats
        assert stats[domain]['failure_count'] == 1
        assert stats[domain]['current_delay'] > self.rate_limiter.config.base_delay


class TestHeaderRandomizer:
    """Test cases for HeaderRandomizer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.header_randomizer = HeaderRandomizer()
    
    def test_get_random_headers_structure(self):
        """Test that random headers have expected structure."""
        headers = self.header_randomizer.get_random_headers()
        
        # Check required headers are present
        required_headers = [
            'User-Agent', 'Accept', 'Accept-Language', 
            'Accept-Encoding', 'Connection'
        ]
        
        for header in required_headers:
            assert header in headers
            assert headers[header]  # Not empty
    
    def test_user_agent_randomization(self):
        """Test that user agents are randomized."""
        user_agents = set()
        
        # Generate multiple headers and collect user agents
        for _ in range(20):
            headers = self.header_randomizer.get_random_headers()
            user_agents.add(headers['User-Agent'])
        
        # Should have some variety (at least 2 different user agents)
        assert len(user_agents) >= 2
    
    def test_get_random_user_agent(self):
        """Test getting random user agent directly."""
        user_agent = self.header_randomizer.get_random_user_agent()
        
        assert user_agent in self.header_randomizer.user_agents
        assert len(user_agent) > 0
    
    def test_custom_user_agents(self):
        """Test adding custom user agents."""
        custom_ua = "CustomBot/1.0"
        
        self.header_randomizer.add_custom_user_agent(custom_ua)
        
        assert custom_ua in self.header_randomizer.user_agents
        
        # Should be able to get the custom user agent
        user_agents = set()
        for _ in range(50):  # Try many times to increase chance
            ua = self.header_randomizer.get_random_user_agent()
            user_agents.add(ua)
        
        assert custom_ua in user_agents
    
    def test_remove_user_agent(self):
        """Test removing user agents."""
        # Add a custom user agent
        custom_ua = "TestBot/1.0"
        self.header_randomizer.add_custom_user_agent(custom_ua)
        
        # Verify it's there
        assert custom_ua in self.header_randomizer.user_agents
        
        # Remove it
        self.header_randomizer.remove_user_agent(custom_ua)
        
        # Verify it's gone
        assert custom_ua not in self.header_randomizer.user_agents
    
    def test_headers_for_domain_spacex(self):
        """Test domain-specific header optimization for SpaceX."""
        headers = self.header_randomizer.get_headers_for_domain("spacex.com")
        
        # Should prefer Chrome user agents for SpaceX
        assert 'Chrome' in headers['User-Agent']
        assert 'Edg' not in headers['User-Agent']  # Not Edge
    
    def test_referer_header(self):
        """Test referer header inclusion."""
        referer_url = "https://example.com/previous-page"
        
        headers = self.header_randomizer.get_random_headers(
            include_referer=True,
            referer_url=referer_url
        )
        
        assert 'Referer' in headers
        assert headers['Referer'] == referer_url
    
    def test_base_headers_preserved(self):
        """Test that base headers are preserved and extended."""
        base_headers = {
            'Authorization': 'Bearer token123',
            'Custom-Header': 'custom-value'
        }
        
        headers = self.header_randomizer.get_random_headers(base_headers)
        
        # Base headers should be preserved
        assert headers['Authorization'] == 'Bearer token123'
        assert headers['Custom-Header'] == 'custom-value'
        
        # Random headers should be added
        assert 'User-Agent' in headers
        assert 'Accept' in headers
    
    def test_get_stats(self):
        """Test statistics collection."""
        stats = self.header_randomizer.get_stats()
        
        assert 'total_user_agents' in stats
        assert 'chrome_agents' in stats
        assert 'firefox_agents' in stats
        assert 'safari_agents' in stats
        assert 'edge_agents' in stats
        
        assert stats['total_user_agents'] > 0
        assert stats['chrome_agents'] > 0


class TestRetryHandler:
    """Test cases for RetryHandler."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config = RetryConfig(max_retries=2, base_delay=0.01, jitter=False)  # Fast tests
        self.retry_handler = RetryHandler(config)
    
    @pytest.mark.asyncio
    async def test_successful_function_no_retry(self):
        """Test that successful functions don't trigger retries."""
        async def successful_function():
            return "success"
        
        result = await self.retry_handler.retry_async(successful_function)
        
        assert result == "success"
        stats = self.retry_handler.get_stats()
        assert stats['total_retries'] == 0
    
    @pytest.mark.asyncio
    async def test_retryable_error_with_eventual_success(self):
        """Test retry on retryable error with eventual success."""
        call_count = 0
        
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("Temporary failure")
            return "success"
        
        result = await self.retry_handler.retry_async(flaky_function)
        
        assert result == "success"
        assert call_count == 2
        stats = self.retry_handler.get_stats()
        assert stats['total_retries'] == 1
        assert stats['successful_retries'] == 1
    
    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        async def failing_function():
            raise NonRetryableError("Permanent failure")
        
        with pytest.raises(NonRetryableError):
            await self.retry_handler.retry_async(failing_function)
        
        stats = self.retry_handler.get_stats()
        assert stats['total_retries'] == 0
    
    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Test behavior when max retries are exhausted."""
        async def always_failing_function():
            raise RetryableError("Always fails")
        
        with pytest.raises(RetryableError):
            await self.retry_handler.retry_async(always_failing_function)
        
        stats = self.retry_handler.get_stats()
        assert stats['total_retries'] == self.retry_handler.config.max_retries
        assert stats['failed_after_retries'] == 1
    
    def test_sync_retry_functionality(self):
        """Test synchronous retry functionality."""
        call_count = 0
        
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("Temporary failure")
            return "success"
        
        result = self.retry_handler.retry_sync(flaky_function)
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_custom_retry_exceptions(self):
        """Test retry with custom exception types."""
        class CustomError(Exception):
            pass
        
        call_count = 0
        
        async def function_with_custom_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise CustomError("Custom error")
            return "success"
        
        result = await self.retry_handler.retry_async(
            function_with_custom_error,
            retry_on=[CustomError]
        )
        
        assert result == "success"
        assert call_count == 2
    
    def test_http_status_code_handling(self):
        """Test retry behavior based on HTTP status codes."""
        class HTTPError(Exception):
            def __init__(self, status_code):
                self.status_code = status_code
        
        # Test retryable status code (500)
        call_count = 0
        
        def function_with_500_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise HTTPError(500)
            return "success"
        
        result = self.retry_handler.retry_sync(
            function_with_500_error,
            retry_on=[HTTPError]
        )
        
        assert result == "success"
        assert call_count == 2
    
    def test_exponential_backoff_timing(self):
        """Test that exponential backoff timing works correctly."""
        delays = []
        
        for attempt in range(3):
            delay = self.retry_handler._calculate_delay(attempt)
            delays.append(delay)
        
        # Each delay should be larger than the previous (exponential)
        assert delays[1] > delays[0]
        assert delays[2] > delays[1]
        
        # Should respect base delay
        assert delays[0] == self.retry_handler.config.base_delay
    
    def test_retry_reason_classification(self):
        """Test that retry reasons are classified correctly."""
        from src.scraping.retry_handler import RetryReason
        
        # Test timeout
        reason = self.retry_handler._get_retry_reason(asyncio.TimeoutError())
        assert reason == RetryReason.TIMEOUT
        
        # Test connection error
        reason = self.retry_handler._get_retry_reason(ConnectionError())
        assert reason == RetryReason.NETWORK_ERROR
        
        # Test HTTP 429 (rate limited)
        class HTTPError(Exception):
            def __init__(self, status_code):
                self.status_code = status_code
        
        reason = self.retry_handler._get_retry_reason(HTTPError(429))
        assert reason == RetryReason.RATE_LIMITED
        
        # Test HTTP 500 (server error)
        reason = self.retry_handler._get_retry_reason(HTTPError(500))
        assert reason == RetryReason.SERVER_ERROR
    
    def test_stats_collection(self):
        """Test comprehensive statistics collection."""
        # Make some successful calls
        self.retry_handler.retry_sync(lambda: "success")
        
        # Make some calls that retry and succeed
        call_count = 0
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("Temporary failure")
            return "success"
        
        self.retry_handler.retry_sync(flaky_function)
        
        stats = self.retry_handler.get_stats()
        
        assert stats['total_attempts'] == 3  # 1 + 2 attempts
        assert stats['total_retries'] == 1
        assert stats['successful_retries'] == 1
        assert stats['success_rate'] > 0
        assert stats['retry_rate'] > 0
        assert 'temporary_failure' in stats['reasons']
    
    def test_reset_stats(self):
        """Test statistics reset functionality."""
        # Generate some stats
        self.retry_handler.retry_sync(lambda: "success")
        
        # Verify stats exist
        stats = self.retry_handler.get_stats()
        assert stats['total_attempts'] > 0
        
        # Reset stats
        self.retry_handler.reset_stats()
        
        # Verify stats are reset
        stats = self.retry_handler.get_stats()
        assert stats['total_attempts'] == 0
        assert stats['total_retries'] == 0