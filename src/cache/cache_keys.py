"""
Cache key definitions and utilities for consistent key naming.
"""
from typing import Optional, Dict, Any
from datetime import datetime


class CacheKeys:
    """Cache key definitions and utilities."""
    
    # Key prefixes
    LAUNCH_PREFIX = "launch"
    LAUNCHES_PREFIX = "launches"
    STATS_PREFIX = "stats"
    HEALTH_PREFIX = "health"
    RATE_LIMIT_PREFIX = "rate_limit"
    
    # TTL values (in seconds)
    LAUNCH_TTL = 3600  # 1 hour
    LAUNCHES_LIST_TTL = 1800  # 30 minutes
    UPCOMING_LAUNCHES_TTL = 900  # 15 minutes
    STATS_TTL = 1800  # 30 minutes
    HEALTH_TTL = 300  # 5 minutes
    RATE_LIMIT_TTL = 3600  # 1 hour
    
    @staticmethod
    def launch_detail(slug: str) -> str:
        """Generate cache key for individual launch details."""
        return f"{CacheKeys.LAUNCH_PREFIX}:detail:{slug}"
    
    @staticmethod
    def launches_list(
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        vehicle_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> str:
        """Generate cache key for launches list with filters."""
        key_parts = [CacheKeys.LAUNCHES_PREFIX, "list"]
        
        # Add pagination
        key_parts.extend([f"skip:{skip}", f"limit:{limit}"])
        
        # Add filters
        if status:
            key_parts.append(f"status:{status}")
        if vehicle_type:
            key_parts.append(f"vehicle:{vehicle_type}")
        if search:
            # Use hash of search term to avoid special characters
            search_hash = str(hash(search))
            key_parts.append(f"search:{search_hash}")
        
        return ":".join(key_parts)
    
    @staticmethod
    def upcoming_launches(limit: int = 50) -> str:
        """Generate cache key for upcoming launches."""
        return f"{CacheKeys.LAUNCHES_PREFIX}:upcoming:limit:{limit}"
    
    @staticmethod
    def historical_launches(
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        vehicle_type: Optional[str] = None
    ) -> str:
        """Generate cache key for historical launches."""
        key_parts = [CacheKeys.LAUNCHES_PREFIX, "historical"]
        
        # Add pagination
        key_parts.extend([f"skip:{skip}", f"limit:{limit}"])
        
        # Add filters
        if status:
            key_parts.append(f"status:{status}")
        if vehicle_type:
            key_parts.append(f"vehicle:{vehicle_type}")
        
        return ":".join(key_parts)
    
    @staticmethod
    def system_stats() -> str:
        """Generate cache key for system statistics."""
        return f"{CacheKeys.STATS_PREFIX}:system"
    
    @staticmethod
    def system_health() -> str:
        """Generate cache key for system health."""
        return f"{CacheKeys.HEALTH_PREFIX}:system"
    
    @staticmethod
    def data_conflicts(resolved: bool = False) -> str:
        """Generate cache key for data conflicts."""
        return f"{CacheKeys.STATS_PREFIX}:conflicts:resolved:{resolved}"
    
    @staticmethod
    def rate_limit_key(identifier: str, endpoint: str) -> str:
        """Generate cache key for rate limiting."""
        return f"{CacheKeys.RATE_LIMIT_PREFIX}:{endpoint}:{identifier}"
    
    @staticmethod
    def cache_warming_status() -> str:
        """Generate cache key for cache warming status."""
        return f"{CacheKeys.STATS_PREFIX}:cache_warming"
    
    @staticmethod
    def get_pattern_for_prefix(prefix: str) -> str:
        """Get Redis key pattern for a prefix."""
        return f"{prefix}:*"
    
    @staticmethod
    def get_launch_patterns() -> list:
        """Get all launch-related cache key patterns."""
        return [
            CacheKeys.get_pattern_for_prefix(CacheKeys.LAUNCH_PREFIX),
            CacheKeys.get_pattern_for_prefix(CacheKeys.LAUNCHES_PREFIX)
        ]
    
    @staticmethod
    def get_stats_patterns() -> list:
        """Get all stats-related cache key patterns."""
        return [
            CacheKeys.get_pattern_for_prefix(CacheKeys.STATS_PREFIX),
            CacheKeys.get_pattern_for_prefix(CacheKeys.HEALTH_PREFIX)
        ]
    
    @staticmethod
    def build_cache_metadata(
        key: str,
        ttl: int,
        created_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Build cache metadata for debugging and monitoring."""
        return {
            "key": key,
            "ttl": ttl,
            "created_at": (created_at or datetime.utcnow()).isoformat(),
            "expires_at": (
                (created_at or datetime.utcnow()).timestamp() + ttl
            )
        }