"""
Cache manager for handling launch data caching and invalidation.
"""
import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta

from src.cache.redis_client import RedisClient, get_redis_client
from src.cache.cache_keys import CacheKeys
from src.models.schemas import LaunchResponse

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching operations for launch data."""
    
    def __init__(self, redis_client: Optional[RedisClient] = None):
        """Initialize cache manager with Redis client."""
        self.redis = redis_client or get_redis_client()
        self.enabled = self.redis.is_connected()
        
        if not self.enabled:
            logger.warning("Cache manager initialized but Redis is not connected")
    
    def is_enabled(self) -> bool:
        """Check if caching is enabled and Redis is connected."""
        return self.enabled and self.redis.is_connected()
    
    # Launch detail caching
    def get_launch_detail(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get cached launch detail by slug."""
        if not self.is_enabled():
            return None
        
        key = CacheKeys.launch_detail(slug)
        return self.redis.get(key)
    
    def set_launch_detail(self, slug: str, launch_data: Dict[str, Any]) -> bool:
        """Cache launch detail data."""
        if not self.is_enabled():
            return False
        
        key = CacheKeys.launch_detail(slug)
        return self.redis.set(key, launch_data, ttl=CacheKeys.LAUNCH_TTL)
    
    def invalidate_launch_detail(self, slug: str) -> bool:
        """Invalidate cached launch detail."""
        if not self.is_enabled():
            return False
        
        key = CacheKeys.launch_detail(slug)
        return bool(self.redis.delete(key))
    
    # Launches list caching
    def get_launches_list(
        self,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        vehicle_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached launches list."""
        if not self.is_enabled():
            return None
        
        key = CacheKeys.launches_list(skip, limit, status, vehicle_type, search)
        return self.redis.get(key)
    
    def set_launches_list(
        self,
        launches_data: Dict[str, Any],
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        vehicle_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> bool:
        """Cache launches list data."""
        if not self.is_enabled():
            return False
        
        key = CacheKeys.launches_list(skip, limit, status, vehicle_type, search)
        return self.redis.set(key, launches_data, ttl=CacheKeys.LAUNCHES_LIST_TTL)
    
    # Upcoming launches caching
    def get_upcoming_launches(self, limit: int = 50) -> Optional[List[Dict[str, Any]]]:
        """Get cached upcoming launches."""
        if not self.is_enabled():
            return None
        
        key = CacheKeys.upcoming_launches(limit)
        return self.redis.get(key)
    
    def set_upcoming_launches(self, launches_data: List[Dict[str, Any]], limit: int = 50) -> bool:
        """Cache upcoming launches data."""
        if not self.is_enabled():
            return False
        
        key = CacheKeys.upcoming_launches(limit)
        return self.redis.set(key, launches_data, ttl=CacheKeys.UPCOMING_LAUNCHES_TTL)
    
    # Historical launches caching
    def get_historical_launches(
        self,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        vehicle_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached historical launches."""
        if not self.is_enabled():
            return None
        
        key = CacheKeys.historical_launches(skip, limit, status, vehicle_type)
        return self.redis.get(key)
    
    def set_historical_launches(
        self,
        launches_data: Dict[str, Any],
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        vehicle_type: Optional[str] = None
    ) -> bool:
        """Cache historical launches data."""
        if not self.is_enabled():
            return False
        
        key = CacheKeys.historical_launches(skip, limit, status, vehicle_type)
        return self.redis.set(key, launches_data, ttl=CacheKeys.LAUNCHES_LIST_TTL)
    
    # System stats and health caching
    def get_system_stats(self) -> Optional[Dict[str, Any]]:
        """Get cached system statistics."""
        if not self.is_enabled():
            return None
        
        key = CacheKeys.system_stats()
        return self.redis.get(key)
    
    def set_system_stats(self, stats_data: Dict[str, Any]) -> bool:
        """Cache system statistics."""
        if not self.is_enabled():
            return False
        
        key = CacheKeys.system_stats()
        return self.redis.set(key, stats_data, ttl=CacheKeys.STATS_TTL)
    
    def get_system_health(self) -> Optional[Dict[str, Any]]:
        """Get cached system health."""
        if not self.is_enabled():
            return None
        
        key = CacheKeys.system_health()
        return self.redis.get(key)
    
    def set_system_health(self, health_data: Dict[str, Any]) -> bool:
        """Cache system health data."""
        if not self.is_enabled():
            return False
        
        key = CacheKeys.system_health()
        return self.redis.set(key, health_data, ttl=CacheKeys.HEALTH_TTL)
    
    def get_data_conflicts(self, resolved: bool = False) -> Optional[Dict[str, Any]]:
        """Get cached data conflicts."""
        if not self.is_enabled():
            return None
        
        key = CacheKeys.data_conflicts(resolved)
        return self.redis.get(key)
    
    def set_data_conflicts(self, conflicts_data: Dict[str, Any], resolved: bool = False) -> bool:
        """Cache data conflicts."""
        if not self.is_enabled():
            return False
        
        key = CacheKeys.data_conflicts(resolved)
        return self.redis.set(key, conflicts_data, ttl=CacheKeys.STATS_TTL)
    
    # Cache invalidation methods
    def invalidate_all_launches(self) -> int:
        """Invalidate all launch-related cache entries."""
        if not self.is_enabled():
            return 0
        
        deleted_count = 0
        patterns = CacheKeys.get_launch_patterns()
        
        for pattern in patterns:
            keys = self.redis.keys(pattern)
            if keys:
                deleted_count += self.redis.delete(*keys)
        
        logger.info(f"Invalidated {deleted_count} launch cache entries")
        return deleted_count
    
    def invalidate_stats_cache(self) -> int:
        """Invalidate all stats and health cache entries."""
        if not self.is_enabled():
            return 0
        
        deleted_count = 0
        patterns = CacheKeys.get_stats_patterns()
        
        for pattern in patterns:
            keys = self.redis.keys(pattern)
            if keys:
                deleted_count += self.redis.delete(*keys)
        
        logger.info(f"Invalidated {deleted_count} stats cache entries")
        return deleted_count
    
    def invalidate_all_cache(self) -> int:
        """Invalidate all cache entries (use with caution)."""
        if not self.is_enabled():
            return 0
        
        # Get all keys except rate limiting
        all_keys = []
        for prefix in [CacheKeys.LAUNCH_PREFIX, CacheKeys.LAUNCHES_PREFIX, 
                      CacheKeys.STATS_PREFIX, CacheKeys.HEALTH_PREFIX]:
            pattern = CacheKeys.get_pattern_for_prefix(prefix)
            all_keys.extend(self.redis.keys(pattern))
        
        if all_keys:
            deleted_count = self.redis.delete(*all_keys)
            logger.info(f"Invalidated {deleted_count} total cache entries")
            return deleted_count
        
        return 0
    
    # Cache warming methods
    def warm_upcoming_launches_cache(self, launches_data: List[Dict[str, Any]]) -> bool:
        """Warm cache with upcoming launches data."""
        if not self.is_enabled():
            return False
        
        # Cache different limits of upcoming launches
        limits = [10, 25, 50]
        success_count = 0
        
        for limit in limits:
            limited_data = launches_data[:limit]
            if self.set_upcoming_launches(limited_data, limit):
                success_count += 1
        
        logger.info(f"Warmed upcoming launches cache for {success_count}/{len(limits)} limits")
        return success_count > 0
    
    def get_cache_warming_status(self) -> Optional[Dict[str, Any]]:
        """Get cache warming status."""
        if not self.is_enabled():
            return None
        
        key = CacheKeys.cache_warming_status()
        return self.redis.get(key)
    
    def set_cache_warming_status(self, status_data: Dict[str, Any]) -> bool:
        """Set cache warming status."""
        if not self.is_enabled():
            return False
        
        key = CacheKeys.cache_warming_status()
        return self.redis.set(key, status_data, ttl=3600)  # 1 hour TTL
    
    # Cache monitoring and debugging
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information and statistics."""
        if not self.is_enabled():
            return {"enabled": False, "error": "Redis not connected"}
        
        try:
            redis_info = self.redis.info()
            
            # Count cache entries by type
            launch_keys = len(self.redis.keys(CacheKeys.get_pattern_for_prefix(CacheKeys.LAUNCH_PREFIX)))
            launches_keys = len(self.redis.keys(CacheKeys.get_pattern_for_prefix(CacheKeys.LAUNCHES_PREFIX)))
            stats_keys = len(self.redis.keys(CacheKeys.get_pattern_for_prefix(CacheKeys.STATS_PREFIX)))
            health_keys = len(self.redis.keys(CacheKeys.get_pattern_for_prefix(CacheKeys.HEALTH_PREFIX)))
            
            return {
                "enabled": True,
                "connected": True,
                "redis_info": {
                    "used_memory": redis_info.get("used_memory_human", "unknown"),
                    "connected_clients": redis_info.get("connected_clients", 0),
                    "total_commands_processed": redis_info.get("total_commands_processed", 0),
                    "keyspace_hits": redis_info.get("keyspace_hits", 0),
                    "keyspace_misses": redis_info.get("keyspace_misses", 0),
                },
                "cache_entries": {
                    "launch_details": launch_keys,
                    "launch_lists": launches_keys,
                    "stats": stats_keys,
                    "health": health_keys,
                    "total": launch_keys + launches_keys + stats_keys + health_keys
                },
                "hit_rate": self._calculate_hit_rate(redis_info)
            }
        except Exception as e:
            logger.error(f"Error getting cache info: {e}")
            return {"enabled": True, "connected": False, "error": str(e)}
    
    def _calculate_hit_rate(self, redis_info: Dict[str, Any]) -> float:
        """Calculate cache hit rate from Redis info."""
        hits = redis_info.get("keyspace_hits", 0)
        misses = redis_info.get("keyspace_misses", 0)
        total = hits + misses
        
        if total == 0:
            return 0.0
        
        return round((hits / total) * 100, 2)


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def close_cache_manager() -> None:
    """Close global cache manager."""
    global _cache_manager
    if _cache_manager:
        _cache_manager = None