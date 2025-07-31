"""
Redis client configuration and connection management.
"""
import os
import json
import logging
from typing import Optional, Any, Union, Dict, List
from datetime import datetime, timedelta
import redis
from redis.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client wrapper with connection management and error handling."""
    
    def __init__(self, redis_url: Optional[str] = None):
        """Initialize Redis client with connection pooling."""
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/1')
        self._client: Optional[redis.Redis] = None
        self._pool: Optional[ConnectionPool] = None
        self._setup_connection()
    
    def _setup_connection(self) -> None:
        """Set up Redis connection with pooling."""
        try:
            # Create connection pool
            self._pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=20,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )
            
            # Create Redis client
            self._client = redis.Redis(
                connection_pool=self._pool,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Test connection
            self._client.ping()
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._client = None
            self._pool = None
    
    @property
    def client(self) -> Optional[redis.Redis]:
        """Get Redis client instance."""
        if self._client is None:
            self._setup_connection()
        return self._client
    
    def is_connected(self) -> bool:
        """Check if Redis is connected and responsive."""
        try:
            if self._client is None:
                return False
            self._client.ping()
            return True
        except (RedisError, ConnectionError):
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis with JSON deserialization."""
        try:
            if not self.is_connected():
                logger.warning("Redis not connected, returning None")
                return None
            
            value = self._client.get(key)
            if value is None:
                return None
            
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Return as string if not JSON
                return value
                
        except Exception as e:
            logger.error(f"Redis GET error for key '{key}': {e}")
            return None
    
    def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """Set value in Redis with JSON serialization."""
        try:
            if not self.is_connected():
                logger.warning("Redis not connected, skipping SET")
                return False
            
            # Serialize value to JSON if it's not a string
            if isinstance(value, (dict, list, tuple, bool, int, float)):
                serialized_value = json.dumps(value, default=str)
            else:
                serialized_value = str(value)
            
            # Set with optional TTL and conditions
            result = self._client.set(
                key, 
                serialized_value, 
                ex=ttl,
                nx=nx,
                xx=xx
            )
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Redis SET error for key '{key}': {e}")
            return False
    
    def delete(self, *keys: str) -> int:
        """Delete one or more keys from Redis."""
        try:
            if not self.is_connected():
                logger.warning("Redis not connected, skipping DELETE")
                return 0
            
            return self._client.delete(*keys)
            
        except Exception as e:
            logger.error(f"Redis DELETE error for keys {keys}: {e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        try:
            if not self.is_connected():
                return False
            
            return bool(self._client.exists(key))
            
        except Exception as e:
            logger.error(f"Redis EXISTS error for key '{key}': {e}")
            return False
    
    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key."""
        try:
            if not self.is_connected():
                return False
            
            return bool(self._client.expire(key, ttl))
            
        except Exception as e:
            logger.error(f"Redis EXPIRE error for key '{key}': {e}")
            return False
    
    def ttl(self, key: str) -> int:
        """Get TTL for key (-1 if no expiry, -2 if key doesn't exist)."""
        try:
            if not self.is_connected():
                return -2
            
            return self._client.ttl(key)
            
        except Exception as e:
            logger.error(f"Redis TTL error for key '{key}': {e}")
            return -2
    
    def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern."""
        try:
            if not self.is_connected():
                return []
            
            return self._client.keys(pattern)
            
        except Exception as e:
            logger.error(f"Redis KEYS error for pattern '{pattern}': {e}")
            return []
    
    def flushdb(self) -> bool:
        """Flush current database (use with caution)."""
        try:
            if not self.is_connected():
                return False
            
            self._client.flushdb()
            return True
            
        except Exception as e:
            logger.error(f"Redis FLUSHDB error: {e}")
            return False
    
    def info(self) -> Dict[str, Any]:
        """Get Redis server information."""
        try:
            if not self.is_connected():
                return {}
            
            return self._client.info()
            
        except Exception as e:
            logger.error(f"Redis INFO error: {e}")
            return {}
    
    def pipeline(self):
        """Create Redis pipeline for batch operations."""
        try:
            if not self.is_connected():
                return None
            
            return self._client.pipeline()
            
        except Exception as e:
            logger.error(f"Redis PIPELINE error: {e}")
            return None
    
    def close(self) -> None:
        """Close Redis connection."""
        try:
            if self._pool:
                self._pool.disconnect()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """Get global Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def close_redis_client() -> None:
    """Close global Redis client."""
    global _redis_client
    if _redis_client:
        _redis_client.close()
        _redis_client = None