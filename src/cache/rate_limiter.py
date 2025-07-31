"""
Rate limiting implementation using sliding window algorithm with Redis.
"""
import time
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta

from src.cache.redis_client import RedisClient, get_redis_client
from src.cache.cache_keys import CacheKeys

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding window rate limiter using Redis."""
    
    def __init__(self, redis_client: Optional[RedisClient] = None):
        """Initialize rate limiter with Redis client."""
        self.redis = redis_client or get_redis_client()
        self.enabled = self.redis.is_connected()
        
        if not self.enabled:
            logger.warning("Rate limiter initialized but Redis is not connected")
    
    def is_enabled(self) -> bool:
        """Check if rate limiting is enabled."""
        return self.enabled and self.redis.is_connected()
    
    def check_rate_limit(
        self,
        identifier: str,
        endpoint: str,
        limit: int,
        window_seconds: int = 3600
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit using sliding window.
        
        Args:
            identifier: Unique identifier (IP, user ID, API key)
            endpoint: API endpoint being accessed
            limit: Maximum requests allowed in window
            window_seconds: Time window in seconds
        
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        if not self.is_enabled():
            # If Redis is not available, allow all requests
            return True, {
                "allowed": True,
                "limit": limit,
                "remaining": limit,
                "reset_time": int(time.time() + window_seconds),
                "retry_after": None
            }
        
        current_time = time.time()
        window_start = current_time - window_seconds
        
        # Generate cache key
        cache_key = CacheKeys.rate_limit_key(identifier, endpoint)
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = self.redis.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(cache_key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(cache_key)
            
            # Add current request timestamp
            pipe.zadd(cache_key, {str(current_time): current_time})
            
            # Set expiry for the key
            pipe.expire(cache_key, window_seconds + 60)  # Extra buffer
            
            # Execute pipeline
            results = pipe.execute()
            current_count = results[1]  # Count after removing expired entries
            
            # Check if limit exceeded
            if current_count >= limit:
                # Remove the request we just added since it's not allowed
                self.redis.client.zrem(cache_key, str(current_time))
                
                # Calculate retry after time
                oldest_request = self.redis.client.zrange(cache_key, 0, 0, withscores=True)
                if oldest_request:
                    oldest_time = oldest_request[0][1]
                    retry_after = int(oldest_time + window_seconds - current_time)
                else:
                    retry_after = window_seconds
                
                return False, {
                    "allowed": False,
                    "limit": limit,
                    "remaining": 0,
                    "reset_time": int(current_time + retry_after),
                    "retry_after": max(retry_after, 1)
                }
            
            # Request allowed
            remaining = max(0, limit - current_count - 1)  # -1 for current request
            
            return True, {
                "allowed": True,
                "limit": limit,
                "remaining": remaining,
                "reset_time": int(current_time + window_seconds),
                "retry_after": None
            }
            
        except Exception as e:
            logger.error(f"Rate limit check error for {identifier}:{endpoint}: {e}")
            # On error, allow the request
            return True, {
                "allowed": True,
                "limit": limit,
                "remaining": limit,
                "reset_time": int(current_time + window_seconds),
                "retry_after": None,
                "error": str(e)
            }
    
    def get_rate_limit_info(
        self,
        identifier: str,
        endpoint: str,
        limit: int,
        window_seconds: int = 3600
    ) -> Dict[str, Any]:
        """Get current rate limit information without making a request."""
        if not self.is_enabled():
            return {
                "limit": limit,
                "remaining": limit,
                "reset_time": int(time.time() + window_seconds),
                "used": 0
            }
        
        current_time = time.time()
        window_start = current_time - window_seconds
        cache_key = CacheKeys.rate_limit_key(identifier, endpoint)
        
        try:
            # Clean up expired entries and count current requests
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(cache_key, 0, window_start)
            pipe.zcard(cache_key)
            results = pipe.execute()
            
            current_count = results[1]
            remaining = max(0, limit - current_count)
            
            return {
                "limit": limit,
                "remaining": remaining,
                "reset_time": int(current_time + window_seconds),
                "used": current_count
            }
            
        except Exception as e:
            logger.error(f"Rate limit info error for {identifier}:{endpoint}: {e}")
            return {
                "limit": limit,
                "remaining": limit,
                "reset_time": int(current_time + window_seconds),
                "used": 0,
                "error": str(e)
            }
    
    def reset_rate_limit(self, identifier: str, endpoint: str) -> bool:
        """Reset rate limit for a specific identifier and endpoint."""
        if not self.is_enabled():
            return True
        
        cache_key = CacheKeys.rate_limit_key(identifier, endpoint)
        
        try:
            deleted = self.redis.delete(cache_key)
            logger.info(f"Reset rate limit for {identifier}:{endpoint}")
            return bool(deleted)
        except Exception as e:
            logger.error(f"Rate limit reset error for {identifier}:{endpoint}: {e}")
            return False
    
    def get_all_rate_limits(self) -> Dict[str, Any]:
        """Get information about all active rate limits."""
        if not self.is_enabled():
            return {"active_limits": [], "total": 0}
        
        try:
            pattern = CacheKeys.get_pattern_for_prefix(CacheKeys.RATE_LIMIT_PREFIX)
            keys = self.redis.keys(pattern)
            
            active_limits = []
            for key in keys:
                # Parse key to extract identifier and endpoint
                key_parts = key.split(":")
                if len(key_parts) >= 3:
                    endpoint = key_parts[1]
                    identifier = ":".join(key_parts[2:])
                    
                    # Get request count
                    count = self.redis.client.zcard(key)
                    ttl = self.redis.ttl(key)
                    
                    active_limits.append({
                        "identifier": identifier,
                        "endpoint": endpoint,
                        "current_requests": count,
                        "ttl": ttl,
                        "key": key
                    })
            
            return {
                "active_limits": active_limits,
                "total": len(active_limits)
            }
            
        except Exception as e:
            logger.error(f"Error getting all rate limits: {e}")
            return {"active_limits": [], "total": 0, "error": str(e)}


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter