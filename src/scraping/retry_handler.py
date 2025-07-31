"""
Retry logic with exponential backoff for failed requests.
"""

import asyncio
import random
import time
from typing import Callable, Any, Optional, Union, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """Base class for errors that should trigger a retry."""
    pass


class NonRetryableError(Exception):
    """Base class for errors that should not trigger a retry."""
    pass


class RetryReason(Enum):
    """Reasons for retrying a request."""
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    TEMPORARY_FAILURE = "temporary_failure"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    retryable_status_codes: List[int] = None
    non_retryable_status_codes: List[int] = None
    
    def __post_init__(self):
        if self.retryable_status_codes is None:
            # Common retryable HTTP status codes
            self.retryable_status_codes = [
                408,  # Request Timeout
                429,  # Too Many Requests
                500,  # Internal Server Error
                502,  # Bad Gateway
                503,  # Service Unavailable
                504,  # Gateway Timeout
                520,  # Unknown Error (Cloudflare)
                521,  # Web Server Is Down (Cloudflare)
                522,  # Connection Timed Out (Cloudflare)
                523,  # Origin Is Unreachable (Cloudflare)
                524,  # A Timeout Occurred (Cloudflare)
            ]
        
        if self.non_retryable_status_codes is None:
            # Status codes that should not be retried
            self.non_retryable_status_codes = [
                400,  # Bad Request
                401,  # Unauthorized
                403,  # Forbidden
                404,  # Not Found
                405,  # Method Not Allowed
                406,  # Not Acceptable
                410,  # Gone
                422,  # Unprocessable Entity
            ]


class RetryHandler:
    """
    Handles retry logic with exponential backoff for failed requests.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize the retry handler.
        
        Args:
            config: Retry configuration
        """
        self.config = config or RetryConfig()
        self._retry_stats = {
            'total_attempts': 0,
            'total_retries': 0,
            'successful_retries': 0,
            'failed_after_retries': 0,
            'reasons': {}
        }
    
    async def retry_async(self, 
                         func: Callable,
                         *args,
                         retry_on: Optional[List[Union[Exception, type]]] = None,
                         **kwargs) -> Any:
        """
        Retry an async function with exponential backoff.
        
        Args:
            func: Async function to retry
            *args: Arguments to pass to the function
            retry_on: List of exceptions that should trigger a retry
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Result of the function call
            
        Raises:
            The last exception if all retries are exhausted
        """
        retry_on = retry_on or [RetryableError, asyncio.TimeoutError, ConnectionError]
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            self._retry_stats['total_attempts'] += 1
            
            try:
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    self._retry_stats['successful_retries'] += 1
                    logger.info(f"Function succeeded after {attempt} retries")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if this exception should trigger a retry
                should_retry = self._should_retry_exception(e, retry_on)
                
                if not should_retry or attempt >= self.config.max_retries:
                    if attempt > 0:
                        self._retry_stats['failed_after_retries'] += 1
                    
                    logger.error(f"Function failed after {attempt} retries: {e}")
                    raise e
                
                # Calculate delay for next attempt
                delay = self._calculate_delay(attempt)
                reason = self._get_retry_reason(e)
                
                self._retry_stats['total_retries'] += 1
                self._retry_stats['reasons'][reason.value] = self._retry_stats['reasons'].get(reason.value, 0) + 1
                
                logger.warning(f"Attempt {attempt + 1} failed ({reason.value}), retrying in {delay:.2f}s: {e}")
                await asyncio.sleep(delay)
        
        # This should never be reached, but just in case
        raise last_exception
    
    def retry_sync(self, 
                   func: Callable,
                   *args,
                   retry_on: Optional[List[Union[Exception, type]]] = None,
                   **kwargs) -> Any:
        """
        Retry a synchronous function with exponential backoff.
        
        Args:
            func: Function to retry
            *args: Arguments to pass to the function
            retry_on: List of exceptions that should trigger a retry
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Result of the function call
            
        Raises:
            The last exception if all retries are exhausted
        """
        retry_on = retry_on or [RetryableError, ConnectionError]
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            self._retry_stats['total_attempts'] += 1
            
            try:
                result = func(*args, **kwargs)
                
                if attempt > 0:
                    self._retry_stats['successful_retries'] += 1
                    logger.info(f"Function succeeded after {attempt} retries")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if this exception should trigger a retry
                should_retry = self._should_retry_exception(e, retry_on)
                
                if not should_retry or attempt >= self.config.max_retries:
                    if attempt > 0:
                        self._retry_stats['failed_after_retries'] += 1
                    
                    logger.error(f"Function failed after {attempt} retries: {e}")
                    raise e
                
                # Calculate delay for next attempt
                delay = self._calculate_delay(attempt)
                reason = self._get_retry_reason(e)
                
                self._retry_stats['total_retries'] += 1
                self._retry_stats['reasons'][reason.value] = self._retry_stats['reasons'].get(reason.value, 0) + 1
                
                logger.warning(f"Attempt {attempt + 1} failed ({reason.value}), retrying in {delay:.2f}s: {e}")
                time.sleep(delay)
        
        # This should never be reached, but just in case
        raise last_exception
    
    def _should_retry_exception(self, exception: Exception, retry_on: List[Union[Exception, type]]) -> bool:
        """
        Check if an exception should trigger a retry.
        
        Args:
            exception: The exception that occurred
            retry_on: List of exceptions that should trigger a retry
            
        Returns:
            True if the exception should trigger a retry
        """
        # Check if it's explicitly marked as non-retryable
        if isinstance(exception, NonRetryableError):
            return False
        
        # Check if it's in the retry_on list
        for retry_exception in retry_on:
            if isinstance(retry_exception, type):
                if isinstance(exception, retry_exception):
                    return True
            else:
                if type(exception) == type(retry_exception):
                    return True
        
        # Check HTTP status codes if it's an HTTP error
        if hasattr(exception, 'status_code'):
            status_code = exception.status_code
            if status_code in self.config.non_retryable_status_codes:
                return False
            if status_code in self.config.retryable_status_codes:
                return True
        
        return False
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate the delay for the next retry attempt.
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = self.config.base_delay * (self.config.backoff_factor ** attempt)
        delay = min(delay, self.config.max_delay)
        
        # Add jitter to avoid thundering herd
        if self.config.jitter:
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)
    
    def _get_retry_reason(self, exception: Exception) -> RetryReason:
        """
        Determine the reason for retrying based on the exception.
        
        Args:
            exception: The exception that occurred
            
        Returns:
            RetryReason enum value
        """
        if isinstance(exception, asyncio.TimeoutError):
            return RetryReason.TIMEOUT
        elif isinstance(exception, ConnectionError):
            return RetryReason.NETWORK_ERROR
        elif hasattr(exception, 'status_code'):
            if exception.status_code == 429:
                return RetryReason.RATE_LIMITED
            elif 500 <= exception.status_code < 600:
                return RetryReason.SERVER_ERROR
        
        return RetryReason.TEMPORARY_FAILURE
    
    def get_stats(self) -> dict:
        """
        Get retry statistics.
        
        Returns:
            Dictionary with retry statistics
        """
        stats = self._retry_stats.copy()
        if stats['total_attempts'] > 0:
            stats['success_rate'] = (stats['total_attempts'] - stats['failed_after_retries']) / stats['total_attempts']
            stats['retry_rate'] = stats['total_retries'] / stats['total_attempts']
        else:
            stats['success_rate'] = 0.0
            stats['retry_rate'] = 0.0
        
        return stats
    
    def reset_stats(self):
        """Reset retry statistics."""
        self._retry_stats = {
            'total_attempts': 0,
            'total_retries': 0,
            'successful_retries': 0,
            'failed_after_retries': 0,
            'reasons': {}
        }