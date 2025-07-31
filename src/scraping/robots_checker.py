"""
Robots.txt checker utility to respect site policies.
"""

import urllib.robotparser
from urllib.parse import urljoin, urlparse
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class RobotsChecker:
    """
    Utility class to check robots.txt compliance for ethical web scraping.
    """
    
    def __init__(self, user_agent: str = "*"):
        """
        Initialize the robots checker.
        
        Args:
            user_agent: User agent string to check permissions for
        """
        self.user_agent = user_agent
        self._robots_cache: Dict[str, urllib.robotparser.RobotFileParser] = {}
    
    def can_fetch(self, url: str, user_agent: Optional[str] = None) -> bool:
        """
        Check if the given URL can be fetched according to robots.txt.
        
        Args:
            url: The URL to check
            user_agent: User agent to check for (defaults to instance user_agent)
            
        Returns:
            True if the URL can be fetched, False otherwise
        """
        try:
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # Get or create robots parser for this domain
            rp = self._get_robots_parser(base_url)
            
            if rp is None:
                # If we can't fetch robots.txt, assume we can fetch (be permissive)
                logger.warning(f"Could not fetch robots.txt for {base_url}, assuming allowed")
                return True
            
            agent = user_agent or self.user_agent
            can_fetch = rp.can_fetch(agent, url)
            
            logger.debug(f"Robots.txt check for {url} with agent '{agent}': {can_fetch}")
            return can_fetch
            
        except Exception as e:
            logger.error(f"Error checking robots.txt for {url}: {e}")
            # Be permissive on errors
            return True
    
    def get_crawl_delay(self, url: str, user_agent: Optional[str] = None) -> Optional[float]:
        """
        Get the crawl delay specified in robots.txt for the given URL.
        
        Args:
            url: The URL to check
            user_agent: User agent to check for (defaults to instance user_agent)
            
        Returns:
            Crawl delay in seconds, or None if not specified
        """
        try:
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            rp = self._get_robots_parser(base_url)
            if rp is None:
                return None
            
            agent = user_agent or self.user_agent
            delay = rp.crawl_delay(agent)
            
            logger.debug(f"Crawl delay for {base_url} with agent '{agent}': {delay}")
            return delay
            
        except Exception as e:
            logger.error(f"Error getting crawl delay for {url}: {e}")
            return None
    
    def _get_robots_parser(self, base_url: str) -> Optional[urllib.robotparser.RobotFileParser]:
        """
        Get or create a robots.txt parser for the given base URL.
        
        Args:
            base_url: Base URL of the site
            
        Returns:
            RobotFileParser instance or None if robots.txt couldn't be fetched
        """
        if base_url in self._robots_cache:
            return self._robots_cache[base_url]
        
        try:
            robots_url = urljoin(base_url, '/robots.txt')
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            self._robots_cache[base_url] = rp
            logger.info(f"Successfully loaded robots.txt from {robots_url}")
            return rp
            
        except Exception as e:
            logger.warning(f"Could not load robots.txt from {base_url}: {e}")
            # Cache None to avoid repeated failed attempts
            self._robots_cache[base_url] = None
            return None
    
    def clear_cache(self):
        """Clear the robots.txt cache."""
        self._robots_cache.clear()
        logger.info("Robots.txt cache cleared")