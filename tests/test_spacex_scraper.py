"""
Integration tests for SpaceX scraper with sample HTML content.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from bs4 import BeautifulSoup

from src.scraping.spacex_scraper import SpaceXScraper, SpaceXScraperError
from src.scraping.ethical_scraper import EthicalScraper
from src.models.schemas import LaunchData, LaunchStatus


# Sample HTML content for testing
SAMPLE_SPACEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>SpaceX Launches</title>
</head>
<body>
    <div class="launches-container">
        <article class="launch-card">
            <h2>Starlink 6-30</h2>
            <time datetime="2024-01-15T10:30:00Z">January 15, 2024</time>
            <p class="vehicle">Falcon 9</p>
            <p class="description">Starlink mission to deploy 23 satellites to low Earth orbit.</p>
            <img src="/images/starlink-patch.jpg" alt="Mission patch">
            <a href="https://youtube.com/watch?v=abc123">Watch Live</a>
            <span class="status">Success</span>
        </article>
        
        <article class="launch-card">
            <h3>Crew-8</h3>
            <time datetime="2024-02-20T15:45:00Z">February 20, 2024</time>
            <p class="vehicle">Falcon 9</p>
            <p class="description">NASA Commercial Crew mission to the International Space Station.</p>
            <img src="/images/crew8-patch.jpg" alt="Crew-8 patch">
            <span class="status">Upcoming</span>
        </article>
        
        <div data-testid="launch-mission-card">
            <h4>NROL-146</h4>
            <div class="launch-date">March 5, 2024</div>
            <div class="vehicle-info">Falcon Heavy</div>
            <div class="mission-details">National Reconnaissance Office mission</div>
            <div class="launch-status">Upcoming</div>
        </div>
    </div>
</body>
</html>
"""

MINIMAL_HTML = """
<html>
<body>
    <div class="grid">
        <div class="launch-item">
            <h2>Test Mission</h2>
            <p>Falcon 9 launch</p>
        </div>
    </div>
</body>
</html>
"""

EMPTY_HTML = """
<html>
<body>
    <div>No launch content here</div>
</body>
</html>
"""


class TestSpaceXScraper:
    """Test cases for SpaceXScraper."""
    
    @pytest.fixture
    def mock_ethical_scraper(self):
        """Create a mock ethical scraper."""
        mock_scraper = Mock(spec=EthicalScraper)
        mock_scraper.prepare_request = AsyncMock(return_value={
            'User-Agent': 'Mozilla/5.0 (Test Browser)',
            'Accept': 'text/html,application/xhtml+xml'
        })
        return mock_scraper
    
    @pytest.fixture
    def scraper(self, mock_ethical_scraper):
        """Create a SpaceXScraper instance with mocked dependencies."""
        return SpaceXScraper(ethical_scraper=mock_ethical_scraper)
    
    @pytest.fixture
    def mock_page(self):
        """Create a mock Playwright page."""
        page = Mock()
        page.goto = AsyncMock()
        page.content = AsyncMock(return_value=SAMPLE_SPACEX_HTML)
        page.set_extra_http_headers = AsyncMock()
        page.wait_for_selector = AsyncMock()
        page.close = AsyncMock()
        return page
    
    @pytest.fixture
    def mock_browser(self, mock_page):
        """Create a mock Playwright browser."""
        browser = Mock()
        browser.new_page = AsyncMock(return_value=mock_page)
        browser.close = AsyncMock()
        return browser
    
    @pytest.fixture
    def mock_playwright(self, mock_browser):
        """Create a mock Playwright instance."""
        playwright = Mock()
        playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        playwright.stop = AsyncMock()
        return playwright
    
    @pytest.mark.asyncio
    async def test_scraper_initialization(self, mock_ethical_scraper):
        """Test scraper initialization."""
        scraper = SpaceXScraper(ethical_scraper=mock_ethical_scraper)
        assert scraper.ethical_scraper == mock_ethical_scraper
        assert scraper.browser is None
        assert scraper.page is None
    
    @pytest.mark.asyncio
    async def test_scraper_context_manager(self, scraper):
        """Test scraper as async context manager."""
        with patch('src.scraping.spacex_scraper.async_playwright') as mock_playwright_func:
            mock_playwright = Mock()
            mock_browser = Mock()
            mock_page = Mock()
            
            mock_playwright_func.return_value.start = AsyncMock(return_value=mock_playwright)
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_page.close = AsyncMock()
            mock_browser.close = AsyncMock()
            mock_playwright.stop = AsyncMock()
            
            async with scraper:
                assert scraper.browser == mock_browser
                assert scraper.page == mock_page
            
            mock_page.close.assert_called_once()
            mock_browser.close.assert_called_once()
            mock_playwright.stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_parse_launches_from_sample_html(self, scraper):
        """Test parsing launches from sample HTML content."""
        launches = await scraper._parse_launches_from_html(SAMPLE_SPACEX_HTML)
        
        assert len(launches) >= 2  # Should find at least 2 launches
        
        # Check first launch (Starlink)
        starlink_launch = next((l for l in launches if 'Starlink' in l.mission_name), None)
        assert starlink_launch is not None
        assert starlink_launch.slug == 'starlink-6-30'
        assert starlink_launch.vehicle_type == 'Falcon 9'
        assert starlink_launch.status == LaunchStatus.SUCCESS
        assert 'satellites' in starlink_launch.details.lower()
        
        # Check second launch (Crew)
        crew_launch = next((l for l in launches if 'Crew' in l.mission_name), None)
        assert crew_launch is not None
        assert crew_launch.vehicle_type == 'Falcon 9'
        assert crew_launch.status == LaunchStatus.UPCOMING
    
    @pytest.mark.asyncio
    async def test_parse_strategy_data_testid(self, scraper):
        """Test parsing strategy using data-testid attributes."""
        soup = BeautifulSoup(SAMPLE_SPACEX_HTML, 'html.parser')
        launches = scraper._parse_strategy_data_testid(soup)
        
        assert len(launches) >= 1
        nrol_launch = next((l for l in launches if 'NROL' in l.mission_name), None)
        assert nrol_launch is not None
        assert nrol_launch.vehicle_type == 'Falcon Heavy'
    
    @pytest.mark.asyncio
    async def test_parse_strategy_launch_cards(self, scraper):
        """Test parsing strategy using launch card classes."""
        soup = BeautifulSoup(SAMPLE_SPACEX_HTML, 'html.parser')
        launches = scraper._parse_strategy_launch_cards(soup)
        
        assert len(launches) >= 2
        mission_names = [l.mission_name for l in launches]
        assert any('Starlink' in name for name in mission_names)
        assert any('Crew' in name for name in mission_names)
    
    @pytest.mark.asyncio
    async def test_parse_strategy_articles(self, scraper):
        """Test parsing strategy using article elements."""
        soup = BeautifulSoup(SAMPLE_SPACEX_HTML, 'html.parser')
        launches = scraper._parse_strategy_articles(soup)
        
        assert len(launches) >= 2
        # Should find launches from article elements
        assert any(l.vehicle_type == 'Falcon 9' for l in launches)
    
    @pytest.mark.asyncio
    async def test_extract_mission_name(self, scraper):
        """Test mission name extraction."""
        soup = BeautifulSoup('<div><h2>Starlink 6-30</h2></div>', 'html.parser')
        element = soup.find('div')
        
        mission_name = scraper._extract_mission_name(element, element.get_text())
        assert mission_name == 'Starlink 6-30'
    
    @pytest.mark.asyncio
    async def test_extract_launch_date(self, scraper):
        """Test launch date extraction."""
        soup = BeautifulSoup('<div><time datetime="2024-01-15T10:30:00Z">Jan 15</time></div>', 'html.parser')
        element = soup.find('div')
        
        launch_date = scraper._extract_launch_date(element, element.get_text())
        assert launch_date is not None
        assert launch_date.year == 2024
        assert launch_date.month == 1
        assert launch_date.day == 15
    
    @pytest.mark.asyncio
    async def test_extract_vehicle_type(self, scraper):
        """Test vehicle type extraction."""
        test_cases = [
            ('Falcon 9 launch today', 'Falcon 9'),
            ('Falcon Heavy mission', 'Falcon Heavy'),
            ('Starship test flight', 'Starship'),
            ('Dragon capsule', 'Dragon'),
            ('No vehicle mentioned', None)
        ]
        
        for text, expected in test_cases:
            soup = BeautifulSoup(f'<div>{text}</div>', 'html.parser')
            element = soup.find('div')
            
            vehicle_type = scraper._extract_vehicle_type(element, text)
            assert vehicle_type == expected
    
    @pytest.mark.asyncio
    async def test_extract_launch_status(self, scraper):
        """Test launch status extraction."""
        test_cases = [
            ('Mission was successful', None, LaunchStatus.SUCCESS),
            ('Launch failed', None, LaunchStatus.FAILURE),
            ('Mission aborted', None, LaunchStatus.ABORTED),
            ('Currently in flight', None, LaunchStatus.IN_FLIGHT),
            ('Upcoming launch', datetime(2025, 1, 1, tzinfo=timezone.utc), LaunchStatus.UPCOMING),
            ('Past launch', datetime(2020, 1, 1, tzinfo=timezone.utc), LaunchStatus.SUCCESS),
            ('No status info', None, LaunchStatus.UPCOMING)
        ]
        
        for text, launch_date, expected in test_cases:
            soup = BeautifulSoup(f'<div>{text}</div>', 'html.parser')
            element = soup.find('div')
            
            status = scraper._extract_launch_status(element, text, launch_date)
            assert status == expected
    
    @pytest.mark.asyncio
    async def test_extract_mission_patch_url(self, scraper):
        """Test mission patch URL extraction."""
        html = '<div><img src="/images/patch.jpg" alt="Mission patch"></div>'
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('div')
        
        patch_url = scraper._extract_mission_patch_url(element)
        assert patch_url == 'https://www.spacex.com/images/patch.jpg'
    
    @pytest.mark.asyncio
    async def test_extract_webcast_url(self, scraper):
        """Test webcast URL extraction."""
        html = '<div><a href="https://youtube.com/watch?v=abc123">Watch Live</a></div>'
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('div')
        
        webcast_url = scraper._extract_webcast_url(element)
        assert webcast_url == 'https://youtube.com/watch?v=abc123'
    
    @pytest.mark.asyncio
    async def test_create_slug(self, scraper):
        """Test slug creation from mission names."""
        test_cases = [
            ('Starlink 6-30', 'starlink-6-30'),
            ('Crew-8 Mission', 'crew-8-mission'),
            ('NROL-146', 'nrol-146'),
            ('Test Mission!@#', 'test-mission'),
            ('Multiple   Spaces', 'multiple-spaces'),
            ('', 'mission-'),  # Will be handled by hash fallback
        ]
        
        for mission_name, expected_prefix in test_cases:
            slug = scraper._create_slug(mission_name)
            if expected_prefix.endswith('-') and not mission_name:
                # For empty names, expect hash-based slug
                assert slug.startswith('mission-')
                assert slug != 'mission-'
            else:
                assert slug == expected_prefix
    
    @pytest.mark.asyncio
    async def test_looks_like_launch_content(self, scraper):
        """Test launch content detection."""
        test_cases = [
            ('<div>Falcon 9 launch today</div>', True),
            ('<div>Starlink mission details</div>', True),
            ('<div>Dragon capsule docking</div>', True),
            ('<div>Random website content</div>', False),
            ('<div>About our company</div>', False),
        ]
        
        for html, expected in test_cases:
            soup = BeautifulSoup(html, 'html.parser')
            element = soup.find('div')
            
            result = scraper._looks_like_launch_content(element)
            assert result == expected
    
    @pytest.mark.asyncio
    async def test_parse_minimal_html(self, scraper):
        """Test parsing with minimal HTML content."""
        launches = await scraper._parse_launches_from_html(MINIMAL_HTML)
        
        # Should still find at least one launch
        assert len(launches) >= 1
        test_launch = launches[0]
        assert test_launch.mission_name == 'Test Mission'
        assert test_launch.vehicle_type == 'Falcon 9'
    
    @pytest.mark.asyncio
    async def test_parse_empty_html(self, scraper):
        """Test parsing with HTML that contains no launch content."""
        launches = await scraper._parse_launches_from_html(EMPTY_HTML)
        
        # Should return empty list or handle gracefully
        assert isinstance(launches, list)
        # May be empty or contain fallback results
    
    @pytest.mark.asyncio
    async def test_scrape_launches_integration(self, scraper):
        """Test full scrape_launches method with mocked browser."""
        with patch('src.scraping.spacex_scraper.async_playwright') as mock_playwright_func:
            # Setup mocks
            mock_playwright = Mock()
            mock_browser = Mock()
            mock_page = Mock()
            
            mock_playwright_func.return_value.start = AsyncMock(return_value=mock_playwright)
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock()
            mock_page.content = AsyncMock(return_value=SAMPLE_SPACEX_HTML)
            mock_page.set_extra_http_headers = AsyncMock()
            mock_page.wait_for_selector = AsyncMock()
            mock_page.close = AsyncMock()
            mock_browser.close = AsyncMock()
            mock_playwright.stop = AsyncMock()
            
            # Start browser and scrape
            await scraper.start_browser()
            launches = await scraper.scrape_launches()
            await scraper.close_browser()
            
            # Verify results
            assert len(launches) >= 2
            assert any('Starlink' in l.mission_name for l in launches)
            assert any('Crew' in l.mission_name for l in launches)
            
            # Verify mocks were called
            mock_page.goto.assert_called_once()
            mock_page.content.assert_called_once()
            scraper.ethical_scraper.prepare_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_scrape_launches_without_browser(self, scraper):
        """Test scrape_launches raises error when browser not initialized."""
        with pytest.raises(SpaceXScraperError, match="Browser not initialized"):
            await scraper.scrape_launches()
    
    @pytest.mark.asyncio
    async def test_scrape_launches_timeout_error(self, scraper):
        """Test scrape_launches handles timeout errors."""
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from src.scraping.retry_handler import RetryableError
        
        with patch('src.scraping.spacex_scraper.async_playwright') as mock_playwright_func:
            # Setup mocks
            mock_playwright = Mock()
            mock_browser = Mock()
            mock_page = Mock()
            
            mock_playwright_func.return_value.start = AsyncMock(return_value=mock_playwright)
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout"))
            mock_page.set_extra_http_headers = AsyncMock()
            mock_page.close = AsyncMock()
            mock_browser.close = AsyncMock()
            mock_playwright.stop = AsyncMock()
            
            await scraper.start_browser()
            
            with pytest.raises(RetryableError, match="SpaceX scraping timeout"):
                await scraper.scrape_launches()
            
            await scraper.close_browser()
    
    @pytest.mark.asyncio
    async def test_get_source_data(self, scraper):
        """Test source data generation."""
        source_data = await scraper.get_source_data()
        
        assert source_data.source_name == "SpaceX Official Website"
        assert source_data.source_url == "https://www.spacex.com/launches"
        assert source_data.data_quality_score == 0.9
        assert isinstance(source_data.scraped_at, datetime)
    
    @pytest.mark.asyncio
    async def test_wait_for_launch_content(self, scraper):
        """Test waiting for launch content to load."""
        mock_page = Mock()
        mock_page.wait_for_selector = AsyncMock()
        scraper.page = mock_page
        
        await scraper._wait_for_launch_content()
        
        # Should have tried to wait for at least one selector
        assert mock_page.wait_for_selector.called
    
    @pytest.mark.asyncio
    async def test_wait_for_launch_content_fallback(self, scraper):
        """Test waiting for launch content with fallback when selectors fail."""
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        
        mock_page = Mock()
        mock_page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeoutError("No selector found"))
        scraper.page = mock_page
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await scraper._wait_for_launch_content()
            
            # Should fall back to sleep
            mock_sleep.assert_called_once_with(3)


class TestSpaceXScraperErrorHandling:
    """Test error handling in SpaceXScraper."""
    
    @pytest.fixture
    def scraper(self):
        """Create a basic scraper for error testing."""
        return SpaceXScraper()
    
    @pytest.mark.asyncio
    async def test_browser_start_failure(self, scraper):
        """Test handling of browser startup failures."""
        with patch('src.scraping.spacex_scraper.async_playwright') as mock_playwright_func:
            mock_playwright_func.return_value.start = AsyncMock(side_effect=Exception("Browser failed"))
            
            with pytest.raises(SpaceXScraperError, match="Browser initialization failed"):
                await scraper.start_browser()
    
    @pytest.mark.asyncio
    async def test_extract_launch_from_invalid_element(self, scraper):
        """Test extraction from invalid HTML elements."""
        # Test with empty element
        soup = BeautifulSoup('<div></div>', 'html.parser')
        element = soup.find('div')
        
        result = scraper._extract_launch_from_element(element)
        assert result is None
        
        # Test with element containing only whitespace
        soup = BeautifulSoup('<div>   \n\t   </div>', 'html.parser')
        element = soup.find('div')
        
        result = scraper._extract_launch_from_element(element)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])