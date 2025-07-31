"""
Task locking mechanism to prevent overlapping scraping operations.
"""
import time
import logging
from typing import Optional, Any
from contextlib import contextmanager
from datetime import datetime, timezone

import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class TaskLockError(Exception):
    """Exception raised when task locking fails."""
    pass


class TaskLock:
    """Redis-based distributed task locking mechanism."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        Initialize task lock with Redis connection.
        
        Args:
            redis_url: Redis connection URL
        """
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info("TaskLock initialized with Redis connection")
        except RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise TaskLockError(f"Redis connection failed: {e}")
    
    @contextmanager
    def acquire_lock(self, 
                    lock_key: str, 
                    timeout: int = 3600, 
                    blocking_timeout: int = 10):
        """
        Context manager for acquiring and releasing distributed locks.
        
        Args:
            lock_key: Unique key for the lock
            timeout: Lock expiration timeout in seconds
            blocking_timeout: How long to wait for lock acquisition
            
        Yields:
            Lock identifier if successful
            
        Raises:
            TaskLockError: If lock cannot be acquired
        """
        lock_id = f"{lock_key}:{int(time.time())}"
        lock_acquired = False
        
        try:
            # Try to acquire lock with blocking timeout
            start_time = time.time()
            while time.time() - start_time < blocking_timeout:
                if self._acquire_lock(lock_key, lock_id, timeout):
                    lock_acquired = True
                    logger.info(f"Lock acquired: {lock_key} ({lock_id})")
                    break
                
                # Wait before retrying
                time.sleep(0.1)
            
            if not lock_acquired:
                existing_lock = self._get_lock_info(lock_key)
                raise TaskLockError(
                    f"Could not acquire lock '{lock_key}' within {blocking_timeout}s. "
                    f"Existing lock: {existing_lock}"
                )
            
            yield lock_id
            
        finally:
            if lock_acquired:
                self._release_lock(lock_key, lock_id)
                logger.info(f"Lock released: {lock_key} ({lock_id})")
    
    def _acquire_lock(self, lock_key: str, lock_id: str, timeout: int) -> bool:
        """
        Attempt to acquire a lock.
        
        Args:
            lock_key: Lock key
            lock_id: Unique lock identifier
            timeout: Lock expiration timeout
            
        Returns:
            True if lock was acquired, False otherwise
        """
        try:
            # Use SET with NX (only if not exists) and EX (expiration)
            result = self.redis_client.set(
                lock_key, 
                lock_id, 
                nx=True, 
                ex=timeout
            )
            return result is True
            
        except RedisError as e:
            logger.error(f"Error acquiring lock {lock_key}: {e}")
            return False
    
    def _release_lock(self, lock_key: str, lock_id: str) -> bool:
        """
        Release a lock only if we own it.
        
        Args:
            lock_key: Lock key
            lock_id: Lock identifier to verify ownership
            
        Returns:
            True if lock was released, False otherwise
        """
        try:
            # Lua script to atomically check and delete lock
            lua_script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("DEL", KEYS[1])
            else
                return 0
            end
            """
            
            result = self.redis_client.eval(lua_script, 1, lock_key, lock_id)
            return result == 1
            
        except RedisError as e:
            logger.error(f"Error releasing lock {lock_key}: {e}")
            return False
    
    def _get_lock_info(self, lock_key: str) -> Optional[dict]:
        """
        Get information about an existing lock.
        
        Args:
            lock_key: Lock key to check
            
        Returns:
            Dictionary with lock information or None if no lock exists
        """
        try:
            lock_value = self.redis_client.get(lock_key)
            if lock_value:
                ttl = self.redis_client.ttl(lock_key)
                return {
                    'lock_id': lock_value,
                    'ttl_seconds': ttl,
                    'expires_at': datetime.now(timezone.utc).timestamp() + ttl if ttl > 0 else None
                }
            return None
            
        except RedisError as e:
            logger.error(f"Error getting lock info for {lock_key}: {e}")
            return None
    
    def is_locked(self, lock_key: str) -> bool:
        """
        Check if a lock exists.
        
        Args:
            lock_key: Lock key to check
            
        Returns:
            True if lock exists, False otherwise
        """
        try:
            return self.redis_client.exists(lock_key) == 1
        except RedisError as e:
            logger.error(f"Error checking lock existence for {lock_key}: {e}")
            return False
    
    def force_release_lock(self, lock_key: str) -> bool:
        """
        Force release a lock (use with caution).
        
        Args:
            lock_key: Lock key to release
            
        Returns:
            True if lock was released, False otherwise
        """
        try:
            result = self.redis_client.delete(lock_key)
            if result:
                logger.warning(f"Force released lock: {lock_key}")
            return result == 1
            
        except RedisError as e:
            logger.error(f"Error force releasing lock {lock_key}: {e}")
            return False
    
    def get_all_locks(self, pattern: str = "*_lock") -> dict:
        """
        Get information about all locks matching a pattern.
        
        Args:
            pattern: Redis key pattern to match
            
        Returns:
            Dictionary mapping lock keys to lock information
        """
        try:
            lock_keys = self.redis_client.keys(pattern)
            locks_info = {}
            
            for lock_key in lock_keys:
                lock_info = self._get_lock_info(lock_key)
                if lock_info:
                    locks_info[lock_key] = lock_info
            
            return locks_info
            
        except RedisError as e:
            logger.error(f"Error getting all locks: {e}")
            return {}
    
    def cleanup_expired_locks(self) -> int:
        """
        Clean up any expired locks (Redis should handle this automatically).
        This is mainly for monitoring purposes.
        
        Returns:
            Number of locks that were found to be expired
        """
        try:
            all_locks = self.get_all_locks()
            expired_count = 0
            
            for lock_key, lock_info in all_locks.items():
                if lock_info.get('ttl_seconds', 0) <= 0:
                    expired_count += 1
                    logger.info(f"Found expired lock: {lock_key}")
            
            return expired_count
            
        except Exception as e:
            logger.error(f"Error during lock cleanup: {e}")
            return 0
    
    def extend_lock(self, lock_key: str, lock_id: str, additional_time: int) -> bool:
        """
        Extend the expiration time of an existing lock.
        
        Args:
            lock_key: Lock key
            lock_id: Lock identifier to verify ownership
            additional_time: Additional seconds to extend the lock
            
        Returns:
            True if lock was extended, False otherwise
        """
        try:
            # Lua script to atomically check ownership and extend expiration
            lua_script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                local current_ttl = redis.call("TTL", KEYS[1])
                if current_ttl > 0 then
                    return redis.call("EXPIRE", KEYS[1], current_ttl + tonumber(ARGV[2]))
                end
            end
            return 0
            """
            
            result = self.redis_client.eval(lua_script, 1, lock_key, lock_id, additional_time)
            if result == 1:
                logger.info(f"Extended lock {lock_key} by {additional_time} seconds")
                return True
            return False
            
        except RedisError as e:
            logger.error(f"Error extending lock {lock_key}: {e}")
            return False


# Utility functions for common lock operations
def with_task_lock(lock_key: str, timeout: int = 3600, blocking_timeout: int = 10):
    """
    Decorator for functions that need task locking.
    
    Args:
        lock_key: Lock key to use
        timeout: Lock expiration timeout
        blocking_timeout: Time to wait for lock acquisition
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            task_lock = TaskLock()
            try:
                with task_lock.acquire_lock(lock_key, timeout, blocking_timeout):
                    return func(*args, **kwargs)
            except TaskLockError as e:
                logger.warning(f"Function {func.__name__} skipped due to lock: {e}")
                raise
        return wrapper
    return decorator


# Example usage and testing
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Test basic locking functionality
    task_lock = TaskLock()
    
    try:
        with task_lock.acquire_lock("test_lock", timeout=60, blocking_timeout=5):
            print("Lock acquired successfully")
            time.sleep(2)
            print("Work completed")
    except TaskLockError as e:
        print(f"Lock acquisition failed: {e}")
    
    # Test lock information
    lock_info = task_lock._get_lock_info("test_lock")
    print(f"Lock info: {lock_info}")
    
    # Test getting all locks
    all_locks = task_lock.get_all_locks()
    print(f"All locks: {all_locks}")