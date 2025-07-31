"""
Cache decorators for automatic caching of function results.
"""
import functools
import logging
from typing import Callable, Any, Optional, Union, Dict
from datetime import datetime

from src.cache.cache_manager import get_cache_manager
from src.cache.cache_keys import CacheKeys

logger = logging.getLogger(__name__)


def cached(
    key_func: Optional[Callable[..., str]] = None,
    ttl: int = 3600,
    enabled: bool = True
):
    """
    Decorator for caching function results.
    
    Args:
        key_func: Function to generate cache key from function arguments
        ttl: Time to live in seconds
        enabled: Whether caching is enabled
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not enabled:
                return func(*args, **kwargs)
            
            cache_manager = get_cache_manager()
            if not cache_manager.is_enabled():
                return func(*args, **kwargs)
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                func_name = f"{func.__module__}.{func.__name__}"
                args_str = "_".join(str(arg) for arg in args)
                kwargs_str = "_".join(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                cache_key = f"func:{func_name}:{args_str}:{kwargs_str}"
            
            # Try to get from cache
            cached_result = cache_manager.redis.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            logger.debug(f"Cache miss for key: {cache_key}")
            result = func(*args, **kwargs)
            
            # Cache the result
            cache_manager.redis.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator


def cache_invalidate(
    key_func: Optional[Callable[..., str]] = None,
    pattern: Optional[str] = None
):
    """
    Decorator for invalidating cache entries after function execution.
    
    Args:
        key_func: Function to generate cache key to invalidate
        pattern: Redis key pattern to invalidate multiple keys
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Execute the function first
            result = func(*args, **kwargs)
            
            cache_manager = get_cache_manager()
            if not cache_manager.is_enabled():
                return result
            
            try:
                if key_func:
                    # Invalidate specific key
                    cache_key = key_func(*args, **kwargs)
                    cache_manager.redis.delete(cache_key)
                    logger.debug(f"Invalidated cache key: {cache_key}")
                
                if pattern:
                    # Invalidate keys matching pattern
                    keys = cache_manager.redis.keys(pattern)
                    if keys:
                        cache_manager.redis.delete(*keys)
                        logger.debug(f"Invalidated {len(keys)} keys matching pattern: {pattern}")
            
            except Exception as e:
                logger.error(f"Error invalidating cache: {e}")
            
            return result
        
        return wrapper
    return decorator


# Specific cache decorators for launch data
def cache_launch_detail(ttl: int = CacheKeys.LAUNCH_TTL):
    """Cache decorator for launch detail functions."""
    def key_func(*args, **kwargs):
        # Assume first argument or 'slug' kwarg is the slug
        slug = args[0] if args else kwargs.get('slug')
        return CacheKeys.launch_detail(slug)
    
    return cached(key_func=key_func, ttl=ttl)


def cache_launches_list(ttl: int = CacheKeys.LAUNCHES_LIST_TTL):
    """Cache decorator for launches list functions."""
    def key_func(*args, **kwargs):
        skip = kwargs.get('skip', 0)
        limit = kwargs.get('limit', 50)
        status = kwargs.get('status')
        vehicle_type = kwargs.get('vehicle_type')
        search = kwargs.get('search')
        return CacheKeys.launches_list(skip, limit, status, vehicle_type, search)
    
    return cached(key_func=key_func, ttl=ttl)


def cache_upcoming_launches(ttl: int = CacheKeys.UPCOMING_LAUNCHES_TTL):
    """Cache decorator for upcoming launches functions."""
    def key_func(*args, **kwargs):
        limit = kwargs.get('limit', 50)
        return CacheKeys.upcoming_launches(limit)
    
    return cached(key_func=key_func, ttl=ttl)


def cache_system_stats(ttl: int = CacheKeys.STATS_TTL):
    """Cache decorator for system stats functions."""
    def key_func(*args, **kwargs):
        return CacheKeys.system_stats()
    
    return cached(key_func=key_func, ttl=ttl)


def cache_system_health(ttl: int = CacheKeys.HEALTH_TTL):
    """Cache decorator for system health functions."""
    def key_func(*args, **kwargs):
        return CacheKeys.system_health()
    
    return cached(key_func=key_func, ttl=ttl)


def invalidate_launch_cache():
    """Decorator to invalidate all launch-related cache."""
    return cache_invalidate(pattern=CacheKeys.get_pattern_for_prefix(CacheKeys.LAUNCH_PREFIX))


def invalidate_launches_cache():
    """Decorator to invalidate launches list cache."""
    return cache_invalidate(pattern=CacheKeys.get_pattern_for_prefix(CacheKeys.LAUNCHES_PREFIX))


def invalidate_stats_cache():
    """Decorator to invalidate stats cache."""
    return cache_invalidate(pattern=CacheKeys.get_pattern_for_prefix(CacheKeys.STATS_PREFIX))