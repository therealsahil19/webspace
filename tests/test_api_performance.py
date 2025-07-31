"""
Performance tests for API endpoints under load.
Tests API response times, throughput, and behavior under concurrent requests.
"""
import pytest
import asyncio
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import httpx
from unittest.mock import patch, Mock

from src.main import app
from src.database import get_database_manager
from src.models.launch import Launch
from src.cache.cache_manager import CacheManager


class TestAPIPerformance:
    """Performance tests for API endpoints."""
    
    @pytest.fixture(scope="class")
    def test_client(self):
        """Create test client for API testing."""
        from fastapi.testclient import TestClient
        return TestClient(app)
    
    @pytest.fixture
    async def performance_test_data(self):
        """Set up performance test data."""
        db_manager = get_database_manager()
        
        # Create 100 test launches for performance testing
        test_launches = []
        for i in range(100):
            launch = Launch(
                slug=f"perf-test-launch-{i:03d}",
                mission_name=f"Performance Test Mission {i:03d}",
                launch_date=datetime.utcnow() + timedelta(days=i-50),  # Mix of past and future
                vehicle_type="Falcon 9" if i % 2 == 0 else "Falcon Heavy",
                status="upcoming" if i < 30 else ("success" if i % 3 == 0 else "failure"),
                details=f"Performance test launch {i:03d} for load testing",
                payload_mass=float(1000 + i * 100),
                orbit="LEO" if i % 2 == 0 else "GTO"
            )
            test_launches.append(launch)
        
        with db_manager.session_scope() as session:
            # Clean up existing test data
            session.query(Launch).filter(
                Launch.slug.like("perf-test-launch-%")
            ).delete(synchronize_session=False)
            
            # Add test data
            for launch in test_launches:
                session.add(launch)
            session.commit()
        
        yield test_launches
        
        # Cleanup
        with db_manager.session_scope() as session:
            session.query(Launch).filter(
                Launch.slug.like("perf-test-launch-%")
            ).delete(synchronize_session=False)
            session.commit()
    
    def test_launches_endpoint_response_time(self, test_client, performance_test_data):
        """Test launches endpoint response time under normal load."""
        response_times = []
        
        # Make 50 requests to measure response time
        for _ in range(50):
            start_time = time.time()
            response = test_client.get("/api/launches")
            end_time = time.time()
            
            assert response.status_code == 200
            response_times.append(end_time - start_time)
        
        # Calculate statistics
        avg_response_time = statistics.mean(response_times)
        median_response_time = statistics.median(response_times)
        p95_response_time = sorted(response_times)[int(0.95 * len(response_times))]
        
        # Performance assertions
        assert avg_response_time < 0.5, f"Average response time too high: {avg_response_time:.3f}s"
        assert median_response_time < 0.3, f"Median response time too high: {median_response_time:.3f}s"
        assert p95_response_time < 1.0, f"95th percentile response time too high: {p95_response_time:.3f}s"
        
        print(f"Launches endpoint performance:")
        print(f"  Average: {avg_response_time:.3f}s")
        print(f"  Median: {median_response_time:.3f}s")
        print(f"  95th percentile: {p95_response_time:.3f}s")
    
    def test_launch_detail_endpoint_response_time(self, test_client, performance_test_data):
        """Test launch detail endpoint response time."""
        response_times = []
        
        # Test with different launch slugs
        test_slugs = [f"perf-test-launch-{i:03d}" for i in range(0, 20, 2)]
        
        for slug in test_slugs:
            start_time = time.time()
            response = test_client.get(f"/api/launches/{slug}")
            end_time = time.time()
            
            assert response.status_code == 200
            response_times.append(end_time - start_time)
        
        # Calculate statistics
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        
        # Performance assertions
        assert avg_response_time < 0.2, f"Average detail response time too high: {avg_response_time:.3f}s"
        assert max_response_time < 0.5, f"Max detail response time too high: {max_response_time:.3f}s"
        
        print(f"Launch detail endpoint performance:")
        print(f"  Average: {avg_response_time:.3f}s")
        print(f"  Maximum: {max_response_time:.3f}s")
    
    def test_concurrent_requests_performance(self, test_client, performance_test_data):
        """Test API performance under concurrent requests."""
        def make_request(endpoint):
            start_time = time.time()
            response = test_client.get(endpoint)
            end_time = time.time()
            return {
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "endpoint": endpoint
            }
        
        # Prepare endpoints to test
        endpoints = [
            "/api/launches",
            "/api/launches/upcoming",
            "/api/launches/historical",
            "/api/health"
        ]
        
        # Add some specific launch detail endpoints
        for i in range(0, 10):
            endpoints.append(f"/api/launches/perf-test-launch-{i:03d}")
        
        # Make concurrent requests
        results = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            # Submit 100 requests across different endpoints
            futures = []
            for i in range(100):
                endpoint = endpoints[i % len(endpoints)]
                future = executor.submit(make_request, endpoint)
                futures.append(future)
            
            # Collect results
            for future in as_completed(futures):
                results.append(future.result())
        
        # Analyze results
        successful_requests = [r for r in results if r["status_code"] == 200]
        failed_requests = [r for r in results if r["status_code"] != 200]
        
        success_rate = len(successful_requests) / len(results)
        avg_response_time = statistics.mean([r["response_time"] for r in successful_requests])
        
        # Performance assertions
        assert success_rate >= 0.95, f"Success rate too low: {success_rate:.2%}"
        assert avg_response_time < 1.0, f"Average response time under load too high: {avg_response_time:.3f}s"
        
        print(f"Concurrent requests performance:")
        print(f"  Success rate: {success_rate:.2%}")
        print(f"  Average response time: {avg_response_time:.3f}s")
        print(f"  Failed requests: {len(failed_requests)}")
    
    def test_pagination_performance(self, test_client, performance_test_data):
        """Test pagination performance with large datasets."""
        response_times = []
        
        # Test different page sizes and offsets
        test_cases = [
            {"skip": 0, "limit": 10},
            {"skip": 0, "limit": 50},
            {"skip": 0, "limit": 100},
            {"skip": 50, "limit": 10},
            {"skip": 90, "limit": 10}
        ]
        
        for params in test_cases:
            start_time = time.time()
            response = test_client.get("/api/launches", params=params)
            end_time = time.time()
            
            assert response.status_code == 200
            response_times.append({
                "params": params,
                "response_time": end_time - start_time
            })
        
        # All pagination requests should be fast
        for result in response_times:
            assert result["response_time"] < 0.5, \
                f"Pagination too slow for {result['params']}: {result['response_time']:.3f}s"
        
        print("Pagination performance:")
        for result in response_times:
            print(f"  {result['params']}: {result['response_time']:.3f}s")
    
    def test_search_and_filter_performance(self, test_client, performance_test_data):
        """Test search and filtering performance."""
        response_times = []
        
        # Test different search and filter combinations
        test_cases = [
            {"search": "Performance"},
            {"search": "Mission"},
            {"status": "upcoming"},
            {"status": "success"},
            {"vehicle_type": "Falcon 9"},
            {"search": "Test", "status": "upcoming"},
            {"search": "Performance", "vehicle_type": "Falcon Heavy"}
        ]
        
        for params in test_cases:
            start_time = time.time()
            response = test_client.get("/api/launches", params=params)
            end_time = time.time()
            
            assert response.status_code == 200
            response_times.append({
                "params": params,
                "response_time": end_time - start_time
            })
        
        # Search and filter should be reasonably fast
        avg_response_time = statistics.mean([r["response_time"] for r in response_times])
        max_response_time = max([r["response_time"] for r in response_times])
        
        assert avg_response_time < 0.3, f"Average search response time too high: {avg_response_time:.3f}s"
        assert max_response_time < 0.8, f"Max search response time too high: {max_response_time:.3f}s"
        
        print("Search and filter performance:")
        for result in response_times:
            print(f"  {result['params']}: {result['response_time']:.3f}s")
    
    def test_cache_performance_impact(self, test_client, performance_test_data):
        """Test performance impact of caching."""
        cache_manager = CacheManager()
        
        if not cache_manager.is_enabled():
            pytest.skip("Redis cache not available")
        
        # Clear cache first
        cache_manager.invalidate_all_launches()
        
        # Measure cold cache performance
        cold_cache_times = []
        for _ in range(10):
            start_time = time.time()
            response = test_client.get("/api/launches")
            end_time = time.time()
            assert response.status_code == 200
            cold_cache_times.append(end_time - start_time)
        
        # Measure warm cache performance
        warm_cache_times = []
        for _ in range(10):
            start_time = time.time()
            response = test_client.get("/api/launches")
            end_time = time.time()
            assert response.status_code == 200
            warm_cache_times.append(end_time - start_time)
        
        cold_avg = statistics.mean(cold_cache_times)
        warm_avg = statistics.mean(warm_cache_times)
        
        # Warm cache should be significantly faster
        improvement = (cold_avg - warm_avg) / cold_avg
        assert improvement > 0.2, f"Cache improvement too low: {improvement:.2%}"
        
        print(f"Cache performance impact:")
        print(f"  Cold cache average: {cold_avg:.3f}s")
        print(f"  Warm cache average: {warm_avg:.3f}s")
        print(f"  Performance improvement: {improvement:.2%}")
    
    def test_memory_usage_under_load(self, test_client, performance_test_data):
        """Test memory usage under sustained load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Make sustained requests
        for i in range(200):
            response = test_client.get("/api/launches")
            assert response.status_code == 200
            
            # Check memory every 50 requests
            if i % 50 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = current_memory - initial_memory
                
                # Memory shouldn't grow excessively
                assert memory_increase < 100, f"Memory usage increased by {memory_increase:.1f}MB"
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_increase = final_memory - initial_memory
        
        print(f"Memory usage under load:")
        print(f"  Initial: {initial_memory:.1f}MB")
        print(f"  Final: {final_memory:.1f}MB")
        print(f"  Increase: {total_increase:.1f}MB")
    
    @pytest.mark.asyncio
    async def test_async_endpoint_performance(self):
        """Test async endpoint performance using httpx."""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            # Test concurrent async requests
            tasks = []
            for _ in range(50):
                task = client.get("/api/launches")
                tasks.append(task)
            
            start_time = time.time()
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            total_time = end_time - start_time
            successful_responses = [r for r in responses if isinstance(r, httpx.Response) and r.status_code == 200]
            
            # All requests should complete within reasonable time
            assert total_time < 5.0, f"Async requests took too long: {total_time:.3f}s"
            assert len(successful_responses) >= 45, f"Too many failed async requests: {len(successful_responses)}/50"
            
            print(f"Async endpoint performance:")
            print(f"  50 concurrent requests completed in: {total_time:.3f}s")
            print(f"  Successful responses: {len(successful_responses)}/50")
            print(f"  Average time per request: {total_time/50:.3f}s")


class TestDatabasePerformance:
    """Performance tests for database operations."""
    
    def test_database_query_performance(self, performance_test_data):
        """Test database query performance."""
        from src.repositories.launch_repository import LaunchRepository
        
        db_manager = get_database_manager()
        launch_repo = LaunchRepository(db_manager)
        
        # Test different query patterns
        query_times = {}
        
        # Test get_all performance
        start_time = time.time()
        all_launches = launch_repo.get_all(limit=100)
        query_times["get_all"] = time.time() - start_time
        assert len(all_launches) > 0
        
        # Test get_upcoming performance
        start_time = time.time()
        upcoming_launches = launch_repo.get_upcoming_launches(limit=50)
        query_times["get_upcoming"] = time.time() - start_time
        
        # Test get_by_slug performance
        start_time = time.time()
        launch = launch_repo.get_by_slug("perf-test-launch-001")
        query_times["get_by_slug"] = time.time() - start_time
        assert launch is not None
        
        # Test search performance
        start_time = time.time()
        search_results = launch_repo.search_launches("Performance", limit=50)
        query_times["search"] = time.time() - start_time
        
        # All queries should be fast
        for query_type, query_time in query_times.items():
            assert query_time < 0.1, f"{query_type} query too slow: {query_time:.3f}s"
        
        print("Database query performance:")
        for query_type, query_time in query_times.items():
            print(f"  {query_type}: {query_time:.3f}s")
    
    def test_bulk_operations_performance(self, performance_test_data):
        """Test bulk database operations performance."""
        from src.repositories.launch_repository import LaunchRepository
        
        db_manager = get_database_manager()
        launch_repo = LaunchRepository(db_manager)
        
        # Test bulk insert performance
        bulk_launches = []
        for i in range(50):
            launch = Launch(
                slug=f"bulk-test-launch-{i:03d}",
                mission_name=f"Bulk Test Mission {i:03d}",
                launch_date=datetime.utcnow() + timedelta(days=i),
                vehicle_type="Falcon 9",
                status="upcoming",
                details=f"Bulk test launch {i:03d}",
                payload_mass=float(1000 + i * 10),
                orbit="LEO"
            )
            bulk_launches.append(launch)
        
        start_time = time.time()
        launch_repo.bulk_create(bulk_launches)
        bulk_insert_time = time.time() - start_time
        
        # Bulk insert should be efficient
        assert bulk_insert_time < 1.0, f"Bulk insert too slow: {bulk_insert_time:.3f}s"
        
        # Cleanup
        with db_manager.session_scope() as session:
            session.query(Launch).filter(
                Launch.slug.like("bulk-test-launch-%")
            ).delete(synchronize_session=False)
            session.commit()
        
        print(f"Bulk operations performance:")
        print(f"  Bulk insert (50 records): {bulk_insert_time:.3f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])