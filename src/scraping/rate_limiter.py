"""
Rate limiting mechanism with configurable delays and backoff strategies.
"""

import asyncio
import time
from typing import Dict, Optional
from dataclasses import dataclass
import logging
import random

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    base_delay: float = 1.0  # Base delay between requests in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    backoff_factor: float = 2.0  # Exponential backoff multiplier
    jitter: bool = True  # Add random jitter to delays
    max_retries: int = 3  # Maximum number of retries for rate limited requests


class RateLimiter:
    """
    Rate limiter with configurable delays and exponential backoff.
    Supports per-domain rate limiting to be respectful to different sites.
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize the rate limiter.
        
        Args:
            config: Rate limiting configuration
        """
        self.config = config or RateLimitConfig()
        self._last_request_time: Dict[str, float] = {}
        self._failure_count: Dict[str, int] = {}
        self._lock = asyncio.Lock()
    
    async def wait_if_needed(self, domain: str, respect_robots_delay: Optional[float] = None):
        """
        Wait if needed to respect rate limits for the given domain.
        
        Args:
            domain: Domain to check rate limits for
            respect_robots_delay: Crawl delay from robots.txt to respect
        """
        async with self._lock:
            now = time.time()
            last_request = self._last_request_time.get(domain, 0)
            
            # Calculate required delay
            base_delay = max(
                self.config.base_delay,
                respect_robots_delay or 0
            )
            
            # Apply exponential backoff if there have been failures
            failure_count = self._failure_count.get(domain, 0)
            if failure_count > 0:
                backoff_delay = base_delay * (self.config.backoff_factor ** failure_count)
                delay = min(backoff_delay, self.config.max_delay)
            else:
                delay = base_delay
            
            # Add jitter to avoid thundering herd
            if self.config.jitter:
                jitter_amount = delay * 0.1  # 10% jitter
                delay += random.uniform(-jitter_amount, jitter_amount)
            
            # Calculate time to wait
            elapsed = now - last_request
            wait_time = max(0, delay - elapsed)
            
            if wait_time > 0:
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s for {domain}")
                await asyncio.sleep(wait_time)
            
            # Update last request time
            self._last_request_time[domain] = time.time()
    
    def record_success(self, domain: str):
        """
        Record a successful request for the domain.
        
        Args:
            domain: Domain that had a successful request
        """
        # Reset failure count on success
        if domain in self._failure_count:
            logger.debug(f"Resetting failure count for {domain}")
            del self._failure_count[domain]
    
    def record_failure(self, domain: str):
        """
        Record a failed request for the domain.
        
        Args:
            domain: Domain that had a failed request
        """
        current_failures = self._failure_count.get(domain, 0)
        self._failure_count[domain] = min(
            current_failures + 1,
            self.config.max_retries
        )
        logger.warning(f"Recorded failure for {domain}, count: {self._failure_count[domain]}")
    
    def get_current_delay(self, domain: str) -> float:
        """
        Get the current delay that would be applied for the domain.
        
        Args:
            domain: Domain to check delay for
            
        Returns:
            Current delay in seconds
        """
        failure_count = self._failure_count.get(domain, 0)
        if failure_count > 0:
            backoff_delay = self.config.base_delay * (self.config.backoff_factor ** failure_count)
            return min(backoff_delay, self.config.max_delay)
        return self.config.base_delay
    
    def should_retry(self, domain: str) -> bool:
        """
        Check if we should retry requests for the given domain.
        
        Args:
            domain: Domain to check
            
        Returns:
            True if we should retry, False if max retries exceeded
        """
        failure_count = self._failure_count.get(domain, 0)
        return failure_count < self.config.max_retries
    
    def reset_domain(self, domain: str):
        """
        Reset rate limiting state for a domain.
        
        Args:
            domain: Domain to reset
        """
        self._last_request_time.pop(domain, None)
        self._failure_count.pop(domain, None)
        logger.info(f"Reset rate limiting state for {domain}")
    
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Get rate limiting statistics.
        
        Returns:
            Dictionary with stats per domain
        """
        stats = {}
        for domain in set(list(self._last_request_time.keys()) + list(self._failure_count.keys())):
            stats[domain] = {
                'last_request': self._last_request_time.get(domain, 0),
                'failure_count': self._failure_count.get(domain, 0),
                'current_delay': self.get_current_delay(domain)
            }
        return stats