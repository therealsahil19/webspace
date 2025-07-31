"""
Ethical scraper that combines all scraping utilities.
"""

import asyncio
import logging
from urllib.parse import urlparse
from typing import Optional, Dict, Any

from .robots_checker import RobotsChecker
from .rate_limiter import RateLimiter, RateLimitConfig
from .header_randomizer import HeaderRandomizer
from .retry_handler import RetryHandler, RetryConfig, RetryableError

logger = logging.getLogger(__name__)


class EthicalScraper:
    """
    Ethical web scraper that combines robots.txt compliance, rate limiting,
    header randomization, and retry logic.
    """
    
    def __init__(self, 
                 rate_limit_config: Optional[RateLimitConfig] = None,
                 retry_config: Optional[RetryConfig] = None,
                 user_agent: str = "*"):
        """
        Initialize the ethical scraper.
        
        Args:
            rate_limit_config: Configuration for rate limiting
            retry_config: Configuration for retry logic
            user_agent: User agent for robots.txt checking
        """
        self.robots_checker = RobotsChecker(user_agent)
        self.rate_limiter = RateLimiter(rate_limit_config)
        self.header_randomizer = HeaderRandomizer()
        self.retry_handler = RetryHandler(retry_config)
        
        logger.info("EthicalScraper initialized")
    
    async def can_scrape_url(self, url: str) -> bool:
        """
        Check if a URL can be scraped according to robots.txt.
        
        Args:
            url: URL to check
            
        Returns:
            True if the URL can be scraped
        """
        return self.robots_checker.can_fetch(url)
    
    async def prepare_request(self, url: str, 
                            base_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Prepare headers and handle rate limiting for a request.
        
        Args:
            url: URL to request
            base_headers: Base headers to include
            
        Returns:
            Dictionary of headers to use for the request
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        # Check robots.txt compliance
        if not await self.can_scrape_url(url):
            raise ValueError(f"URL {url} is disallowed by robots.txt")
        
        # Get crawl delay from robots.txt
        robots_delay = self.robots_checker.get_crawl_delay(url)
        
        # Apply rate limiting
        await self.rate_limiter.wait_if_needed(domain, robots_delay)
        
        # Generate appropriate headers
        headers = self.header_randomizer.get_headers_for_domain(domain, base_headers)
        
        logger.debug(f"Prepared request for {url} with {len(headers)} headers")
        return headers
    
    async def scrape_with_retry(self, 
                               scrape_function,
                               url: str,
                               *args,
                               **kwargs) -> Any:
        """
        Execute a scraping function with retry logic and ethical practices.
        
        Args:
            scrape_function: Async function to execute for scraping
            url: URL being scraped
            *args: Arguments to pass to scrape_function
            **kwargs: Keyword arguments to pass to scrape_function
            
        Returns:
            Result from scrape_function
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        async def wrapped_scrape():
            try:
                # Prepare the request
                headers = await self.prepare_request(url, kwargs.get('headers'))
                kwargs['headers'] = headers
                
                # Execute the scraping function
                result = await scrape_function(url, *args, **kwargs)
                
                # Record success for rate limiting
                self.rate_limiter.record_success(domain)
                
                return result
                
            except Exception as e:
                # Record failure for rate limiting
                self.rate_limiter.record_failure(domain)
                
                # Re-raise as retryable error for retry handler
                raise RetryableError(f"Scraping failed for {url}: {e}") from e
        
        # Use retry handler to execute with retries
        return await self.retry_handler.retry_async(wrapped_scrape)
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics from all components.
        
        Returns:
            Dictionary with statistics from all scraping utilities
        """
        return {
            'rate_limiter': self.rate_limiter.get_stats(),
            'header_randomizer': self.header_randomizer.get_stats(),
            'retry_handler': self.retry_handler.get_stats(),
            'robots_cache_size': len(self.robots_checker._robots_cache)
        }
    
    def reset_all_stats(self):
        """Reset statistics for all components."""
        self.rate_limiter = RateLimiter(self.rate_limiter.config)
        self.retry_handler.reset_stats()
        self.robots_checker.clear_cache()
        logger.info("All scraping statistics reset")


# Example usage function
async def example_usage():
    """
    Example of how to use the EthicalScraper.
    """
    # Configure scraper with custom settings
    rate_config = RateLimitConfig(
        base_delay=2.0,  # 2 second base delay
        max_delay=30.0,  # Max 30 second delay
        backoff_factor=1.5  # Gentler backoff
    )
    
    retry_config = RetryConfig(
        max_retries=3,
        base_delay=1.0
    )
    
    scraper = EthicalScraper(rate_config, retry_config)
    
    # Example scraping function (you would implement this)
    async def mock_scrape_function(url: str, headers: Dict[str, str]) -> str:
        """Mock scraping function for demonstration."""
        logger.info(f"Scraping {url} with headers: {list(headers.keys())}")
        # In real implementation, this would use aiohttp, playwright, etc.
        await asyncio.sleep(0.1)  # Simulate network request
        return f"Content from {url}"
    
    # URLs to scrape
    urls = [
        "https://www.spacex.com/launches",
        "https://www.nasa.gov/news/releases",
        "https://en.wikipedia.org/wiki/List_of_Falcon_9_and_Falcon_Heavy_launches"
    ]
    
    # Scrape each URL ethically
    results = []
    for url in urls:
        try:
            result = await scraper.scrape_with_retry(mock_scrape_function, url)
            results.append(result)
            logger.info(f"Successfully scraped: {url}")
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
    
    # Print statistics
    stats = scraper.get_comprehensive_stats()
    logger.info(f"Scraping statistics: {stats}")
    
    return results


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run example
    asyncio.run(example_usage())