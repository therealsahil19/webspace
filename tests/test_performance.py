"""
Performance tests for caching and optimization features.
"""
import pytest
import time
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from src.cache.redis_client import RedisClient
from src.cache.cache_manager import CacheManager
from src.cache.rate_limiter import RateLimiter
from src.cache.cache_warming import CacheWarmingService
from src.database_optimization import DatabaseOptimizer


class TestRedisClient:
    """Test Redis client functionality."""
    
    def test_redis_connection(self):
        """Test Redis connection and basic operations."""
        redis_client = RedisClient()
        
        # Test connection
        if redis_client.is_connected():
            # Test basic operations
            assert redis_client.set("test_key", "test_value", ttl=60)
            assert redis_client.get("test_key") == "test_value"
            assert redis_client.exists("test_key")
            assert redis_client.delete("test_key") == 1
            assert not redis_client.exists("test_key")
    
    def test_json_serialization(self):
        """Test JSON serialization and deserialization."""
        redis_client = RedisClient()
        
        if redis_client.is_connected():
            test_data = {
                "id": 1,
                "name": "Test Launch",
                "date": "2024-01-01T00:00:00Z",
                "success": True,
                "payload_mass": 1000.5
            }
            
            assert redis_client.set("test_json", test_data, ttl=60)
            retrieved_data = redis_client.get("test_json")
            
            assert retrieved_data == test_data
            assert isinstance(retrieved_data, dict)
            
            # Cleanup
            redis_client.delete("test_json")
    
    def test_ttl_functionality(self):
        """Test TTL (time to live) functionality."""
        redis_client = RedisClient()
        
        if redis_client.is_connected():
            # Set key with 2 second TTL
            assert redis_client.set("ttl_test", "value", ttl=2)
            
            # Check TTL
            ttl = redis_client.ttl("ttl_test")
            assert 0 < ttl <= 2
            
            # Wait for expiration
            time.sleep(3)
            
            # Key should be expired
            assert not redis_client.exists("ttl_test")


class TestCacheManager:
    """Test cache manager functionality."""
    
    @pytest.fixture
    def cache_manager(self):
        """Create cache manager for testing."""
        return CacheManager()
    
    def test_launch_detail_caching(self, cache_manager):
        """Test launch detail caching."""
        if not cache_manager.is_enabled():
            pytest.skip("Redis not available")
        
        test_launch = {
            "id": 1,
            "slug": "test-launch",
            "mission_name": "Test Mission",
            "launch_date": "2024-01-01T00:00:00Z",
            "status": "upcoming"
        }
        
        # Cache launch detail
        assert cache_manager.set_launch_detail("test-launch", test_launch)
        
        # Retrieve from cache
        cached_launch = cache_manager.get_launch_detail("test-launch")
        assert cached_launch == test_launch
        
        # Invalidate cache
        assert cache_manager.invalidate_launch_detail("test-launch")
        assert cache_manager.get_launch_detail("test-launch") is None
    
    def test_launches_list_caching(self, cache_manager):
        """Test launches list caching."""
        if not cache_manager.is_enabled():
            pytest.skip("Redis not available")
        
        test_launches = {
            "data": [
                {"id": 1, "slug": "launch-1", "mission_name": "Mission 1"},
                {"id": 2, "slug": "launch-2", "mission_name": "Mission 2"}
            ],
            "meta": {"total": 2, "skip": 0, "limit": 50}
        }
        
        # Cache launches list
        assert cache_manager.set_launches_list(test_launches, skip=0, limit=50)
        
        # Retrieve from cache
        cached_launches = cache_manager.get_launches_list(skip=0, limit=50)
        assert cached_launches == test_launches
        
        # Test with different parameters
        assert cache_manager.get_launches_list(skip=10, limit=25) is None
    
    def test_cache_invalidation(self, cache_manager):
        """Test cache invalidation functionality."""
        if not cache_manager.is_enabled():
            pytest.skip("Redis not available")
        
        # Set up test data
        cache_manager.set_launch_detail("test-1", {"id": 1})
        cache_manager.set_launch_detail("test-2", {"id": 2})
        cache_manager.set_upcoming_launches([{"id": 1}], 10)
        
        # Invalidate all launches
        deleted_count = cache_manager.invalidate_all_launches()
        assert deleted_count >= 3
        
        # Verify invalidation
        assert cache_manager.get_launch_detail("test-1") is None
        assert cache_manager.get_launch_detail("test-2") is None
        assert cache_manager.get_upcoming_launches(10) is None


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter for testing."""
        return RateLimiter()
    
    def test_rate_limit_basic(self, rate_limiter):
        """Test basic rate limiting."""
        if not rate_limiter.is_enabled():
            pytest.skip("Redis not available")
        
        identifier = "test_user"
        endpoint = "/api/test"
        limit = 5
        window = 60
        
        # Reset any existing rate limit
        rate_limiter.reset_rate_limit(identifier, endpoint)
        
        # Make requests within limit
        for i in range(limit):
            allowed, info = rate_limiter.check_rate_limit(identifier, endpoint, limit, window)
            assert allowed
            assert info["remaining"] == limit - i - 1
        
        # Next request should be blocked
        allowed, info = rate_limiter.check_rate_limit(identifier, endpoint, limit, window)
        assert not allowed
        assert info["remaining"] == 0
        assert info["retry_after"] > 0
    
    def test_rate_limit_sliding_window(self, rate_limiter):
        """Test sliding window behavior."""
        if not rate_limiter.is_enabled():
            pytest.skip("Redis not available")
        
        identifier = "test_sliding"
        endpoint = "/api/sliding"
        limit = 3
        window = 2  # 2 seconds
        
        # Reset rate limit
        rate_limiter.reset_rate_limit(identifier, endpoint)
        
        # Use up the limit
        for _ in range(limit):
            allowed, _ = rate_limiter.check_rate_limit(identifier, endpoint, limit, window)
            assert allowed
        
        # Should be blocked now
        allowed, info = rate_limiter.check_rate_limit(identifier, endpoint, limit, window)
        assert not allowed
        
        # Wait for window to slide
        time.sleep(window + 0.1)
        
        # Should be allowed again
        allowed, info = rate_limiter.check_rate_limit(identifier, endpoint, limit, window)
        assert allowed
    
    def test_rate_limit_different_identifiers(self, rate_limiter):
        """Test rate limiting with different identifiers."""
        if not rate_limiter.is_enabled():
            pytest.skip("Redis not available")
        
        endpoint = "/api/test"
        limit = 2
        window = 60
        
        # Reset rate limits
        rate_limiter.reset_rate_limit("user1", endpoint)
        rate_limiter.reset_rate_limit("user2", endpoint)
        
        # User1 uses up their limit
        for _ in range(limit):
            allowed, _ = rate_limiter.check_rate_limit("user1", endpoint, limit, window)
            assert allowed
        
        # User1 should be blocked
        allowed, _ = rate_limiter.check_rate_limit("user1", endpoint, limit, window)
        assert not allowed
        
        # User2 should still be allowed
        allowed, _ = rate_limiter.check_rate_limit("user2", endpoint, limit, window)
        assert allowed


class TestCacheWarming:
    """Test cache warming functionality."""
    
    @pytest.fixture
    def cache_warming_service(self):
        """Create cache warming service for testing."""
        return CacheWarmingService()
    
    @patch('src.cache.cache_warming.get_repository_manager')
    def test_warm_upcoming_launches(self, mock_repo_manager, cache_warming_service):
        """Test warming upcoming launches cache."""
        if not cache_warming_service.cache_manager.is_enabled():
            pytest.skip("Redis not available")
        
        # Mock repository data
        mock_launch = Mock()
        mock_launch.id = 1
        mock_launch.slug = "test-upcoming"
        mock_launch.mission_name = "Test Upcoming Mission"
        mock_launch.launch_date = datetime.utcnow() + timedelta(days=1)
        mock_launch.vehicle_type = "Falcon 9"
        mock_launch.status = "upcoming"
        mock_launch.sources = []
        
        # Set up other required attributes
        for attr in ['payload_mass', 'orbit', 'details', 'mission_patch_url', 
                    'webcast_url', 'created_at', 'updated_at']:
            setattr(mock_launch, attr, None)
        
        mock_repo_manager.return_value.launch_repository.get_upcoming_launches.return_value = [mock_launch]
        
        # Warm cache
        result = cache_warming_service.warm_upcoming_launches()
        
        assert result["status"] == "success"
        assert result["upcoming_launches_cached"] == 1
        assert result["limits_warmed"] > 0
    
    @patch('src.cache.cache_warming.get_repository_manager')
    def test_warm_all_caches(self, mock_repo_manager, cache_warming_service):
        """Test warming all caches."""
        if not cache_warming_service.cache_manager.is_enabled():
            pytest.skip("Redis not available")
        
        # Mock repository data
        mock_launch = Mock()
        mock_launch.id = 1
        mock_launch.slug = "test-all"
        mock_launch.mission_name = "Test All Mission"
        mock_launch.launch_date = datetime.utcnow() + timedelta(days=1)
        mock_launch.status = "upcoming"
        mock_launch.sources = []
        
        # Set up other required attributes
        for attr in ['vehicle_type', 'payload_mass', 'orbit', 'details', 
                    'mission_patch_url', 'webcast_url', 'created_at', 'updated_at']:
            setattr(mock_launch, attr, None)
        
        mock_repo_manager.return_value.launch_repository.get_upcoming_launches.return_value = [mock_launch]
        mock_repo_manager.return_value.launch_repository.get_all.return_value = [mock_launch]
        
        # Warm all caches
        result = cache_warming_service.warm_all_caches()
        
        assert result["overall_status"] in ["success", "partial"]
        assert "upcoming_launches" in result["results"]
        assert "popular_launches" in result["results"]
        assert "launch_lists" in result["results"]


class TestDatabaseOptimization:
    """Test database optimization functionality."""
    
    @pytest.fixture
    def db_optimizer(self):
        """Create database optimizer for testing."""
        return DatabaseOptimizer()
    
    @patch('src.database_optimization.get_database_manager')
    def test_analyze_query_performance(self, mock_db_manager, db_optimizer):
        """Test query performance analysis."""
        # Mock database session
        mock_session = Mock()
        mock_db_manager.return_value.session_scope.return_value.__enter__.return_value = mock_session
        
        # Mock query results
        mock_session.execute.return_value.fetchall.return_value = []
        
        analysis = db_optimizer.analyze_query_performance()
        
        assert "table_stats" in analysis
        assert "index_usage" in analysis
        assert "recommendations" in analysis
        assert "table_sizes" in analysis
    
    @patch('src.database_optimization.get_database_manager')
    def test_optimize_database_settings(self, mock_db_manager, db_optimizer):
        """Test database settings optimization."""
        # Mock database session
        mock_session = Mock()
        mock_db_manager.return_value.session_scope.return_value.__enter__.return_value = mock_session
        
        # Mock settings query results
        mock_setting = Mock()
        mock_setting.name = "shared_buffers"
        mock_setting.setting = "128MB"
        mock_setting.unit = "8kB"
        mock_setting.short_desc = "Sets the number of shared memory buffers used by the server."
        
        mock_session.execute.return_value.fetchall.return_value = [mock_setting]
        
        recommendations = db_optimizer.optimize_database_settings()
        
        assert "current_settings" in recommendations
        assert "recommendations" in recommendations
        assert len(recommendations["recommendations"]) > 0


class TestPerformanceBenchmarks:
    """Performance benchmark tests."""
    
    def test_cache_vs_database_performance(self):
        """Benchmark cache vs database performance."""
        cache_manager = CacheManager()
        
        if not cache_manager.is_enabled():
            pytest.skip("Redis not available")
        
        # Test data
        test_data = {
            "id": 1,
            "slug": "performance-test",
            "mission_name": "Performance Test Mission",
            "data": "x" * 1000  # 1KB of data
        }
        
        # Cache the data
        cache_manager.set_launch_detail("performance-test", test_data)
        
        # Benchmark cache retrieval
        cache_times = []
        for _ in range(100):
            start_time = time.time()
            cached_data = cache_manager.get_launch_detail("performance-test")
            end_time = time.time()
            cache_times.append(end_time - start_time)
            assert cached_data == test_data
        
        avg_cache_time = sum(cache_times) / len(cache_times)
        
        # Cache should be very fast (< 10ms on average)
        assert avg_cache_time < 0.01, f"Cache too slow: {avg_cache_time:.4f}s average"
        
        # Cleanup
        cache_manager.invalidate_launch_detail("performance-test")
    
    def test_rate_limiter_performance(self):
        """Test rate limiter performance under load."""
        rate_limiter = RateLimiter()
        
        if not rate_limiter.is_enabled():
            pytest.skip("Redis not available")
        
        identifier = "perf_test"
        endpoint = "/api/perf"
        limit = 1000
        window = 3600
        
        # Reset rate limit
        rate_limiter.reset_rate_limit(identifier, endpoint)
        
        # Benchmark rate limit checks
        start_time = time.time()
        
        for i in range(100):
            allowed, info = rate_limiter.check_rate_limit(identifier, endpoint, limit, window)
            assert allowed
            assert info["remaining"] == limit - i - 1
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / 100
        
        # Rate limiting should be fast (< 5ms per check on average)
        assert avg_time < 0.005, f"Rate limiter too slow: {avg_time:.4f}s average"
        
        # Cleanup
        rate_limiter.reset_rate_limit(identifier, endpoint)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])