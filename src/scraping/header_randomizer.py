"""
Request header randomization system with realistic user agents.
"""

import random
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class HeaderRandomizer:
    """
    Randomizes HTTP headers to make requests appear more natural and avoid detection.
    """
    
    # Realistic user agents from popular browsers
    USER_AGENTS = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        
        # Chrome on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
        
        # Firefox on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:119.0) Gecko/20100101 Firefox/119.0",
        
        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    ]
    
    # Common accept headers
    ACCEPT_HEADERS = [
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    ]
    
    # Accept-Language headers
    ACCEPT_LANGUAGE_HEADERS = [
        "en-US,en;q=0.9",
        "en-US,en;q=0.8",
        "en-US,en;q=0.9,es;q=0.8",
        "en-US,en;q=0.9,fr;q=0.8",
        "en-GB,en;q=0.9",
        "en-US,en;q=0.5",
    ]
    
    # Accept-Encoding headers
    ACCEPT_ENCODING_HEADERS = [
        "gzip, deflate, br",
        "gzip, deflate",
        "gzip, deflate, br, zstd",
    ]
    
    # Connection headers
    CONNECTION_HEADERS = [
        "keep-alive",
        "close",
    ]
    
    def __init__(self, custom_user_agents: Optional[List[str]] = None):
        """
        Initialize the header randomizer.
        
        Args:
            custom_user_agents: Optional list of custom user agents to use instead of defaults
        """
        self.user_agents = custom_user_agents or self.USER_AGENTS
        logger.info(f"HeaderRandomizer initialized with {len(self.user_agents)} user agents")
    
    def get_random_headers(self, 
                          base_headers: Optional[Dict[str, str]] = None,
                          include_referer: bool = True,
                          referer_url: Optional[str] = None) -> Dict[str, str]:
        """
        Generate a set of randomized HTTP headers.
        
        Args:
            base_headers: Base headers to start with
            include_referer: Whether to include a referer header
            referer_url: Specific referer URL to use
            
        Returns:
            Dictionary of HTTP headers
        """
        headers = base_headers.copy() if base_headers else {}
        
        # Always randomize these core headers
        headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Accept': random.choice(self.ACCEPT_HEADERS),
            'Accept-Language': random.choice(self.ACCEPT_LANGUAGE_HEADERS),
            'Accept-Encoding': random.choice(self.ACCEPT_ENCODING_HEADERS),
            'Connection': random.choice(self.CONNECTION_HEADERS),
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none' if not include_referer else 'same-origin',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
        
        # Add referer if requested
        if include_referer and referer_url:
            headers['Referer'] = referer_url
        
        # Randomly add some optional headers
        if random.random() < 0.7:  # 70% chance
            headers['DNT'] = '1'
        
        if random.random() < 0.5:  # 50% chance
            headers['Sec-GPC'] = '1'
        
        logger.debug(f"Generated headers with User-Agent: {headers['User-Agent'][:50]}...")
        return headers
    
    def get_random_user_agent(self) -> str:
        """
        Get a random user agent string.
        
        Returns:
            Random user agent string
        """
        return random.choice(self.user_agents)
    
    def add_custom_user_agent(self, user_agent: str):
        """
        Add a custom user agent to the pool.
        
        Args:
            user_agent: User agent string to add
        """
        if user_agent not in self.user_agents:
            self.user_agents.append(user_agent)
            logger.info(f"Added custom user agent: {user_agent[:50]}...")
    
    def remove_user_agent(self, user_agent: str):
        """
        Remove a user agent from the pool.
        
        Args:
            user_agent: User agent string to remove
        """
        if user_agent in self.user_agents:
            self.user_agents.remove(user_agent)
            logger.info(f"Removed user agent: {user_agent[:50]}...")
    
    def get_headers_for_domain(self, domain: str, 
                              base_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Get headers optimized for a specific domain.
        
        Args:
            domain: Domain to optimize headers for
            base_headers: Base headers to start with
            
        Returns:
            Dictionary of HTTP headers optimized for the domain
        """
        headers = self.get_random_headers(base_headers)
        
        # Domain-specific optimizations
        if 'spacex.com' in domain.lower():
            # SpaceX site works well with modern Chrome
            chrome_agents = [ua for ua in self.user_agents if 'Chrome' in ua and 'Edg' not in ua]
            if chrome_agents:
                headers['User-Agent'] = random.choice(chrome_agents)
        
        elif 'nasa.gov' in domain.lower():
            # NASA site is generally compatible with all browsers
            pass
        
        elif 'wikipedia.org' in domain.lower():
            # Wikipedia prefers standard headers
            headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        
        return headers
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about the header randomizer.
        
        Returns:
            Dictionary with statistics
        """
        return {
            'total_user_agents': len(self.user_agents),
            'chrome_agents': len([ua for ua in self.user_agents if 'Chrome' in ua]),
            'firefox_agents': len([ua for ua in self.user_agents if 'Firefox' in ua]),
            'safari_agents': len([ua for ua in self.user_agents if 'Safari' in ua and 'Chrome' not in ua]),
            'edge_agents': len([ua for ua in self.user_agents if 'Edg' in ua]),
        }