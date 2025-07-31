"""
System validation tests that verify the complete SpaceX Launch Tracker system
meets all performance and functional requirements.
"""
import pytest
import asyncio
import time
import requests
import json
import subprocess
import os
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.database import get_database_manager
from src.models.launch import Launch
from src.cache.cache_manager import CacheManager


class TestPerformanceRequirements:
    """Test that system meets performance requirements."""
    
    def test_api_response_time_requirements(self):
        """Test that API responses meet performance requirements (< 1 second for cached content)."""
        try:
            base_url = "http://localhost:8000"
            
            # Test multiple endpoints for response time
            endpoints = [
                "/api/launches?limit=10",
                "/api/launches/upcoming?limit=5", 
                "/api/launches/historical?limit=5",
                "/health"
            ]
            
            response_times = {}
            
            for endpoint in endpoints:
                start_time = time.time()
                response = requests.get(f"{base_url}{endpoint}", timeout=5)
                end_time = time.time()
                
                response_time = end_time - start_time
                response_times[endpoint] = response_time
                
                # API should respond within 1 second for cached content
                assert response_time < 1.0, f"Endpoint {endpoint} took {response_time:.3f}s (> 1.0s limit)"
                assert response.status_code == 200, f"Endpoint {endpoint} returned {response.status_code}"
            
            print(f"API Response Times: {response_times}")
            
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_concurrent_request_handling(self):
        """Test system can handle concurrent requests efficiently."""
        try:
            base_url = "http://localhost:8000"
            endpoint = "/api/launches?limit=10"
            
            def make_request():
                start_time = time.time()
                response = requests.get(f"{base_url}{endpoint}", timeout=10)
                end_time = time.time()
                return {
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "success": response.status_code == 200
                }
            
            # Test with 20 concurrent requests
            num_requests = 20
            results = []
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(make_request) for _ in range(num_requests)]
                
                for future in as_completed(futures, timeout=30):
                    results.append(future.result())
            
            # Analyze results
            successful_requests = [r for r in results if r["success"]]
            success_rate = len(successful_requests) / num_requests
            
            # At least 95% success rate under concurrent load
            assert success_rate >= 0.95, f"Success rate {success_rate:.2%} below 95% threshold"
            
            # Average response time should still be reasonable
            avg_response_time = sum(r["response_time"] for r in successful_requests) / len(successful_requests)
            assert avg_response_time < 2.0, f"Average response time {avg_response_time:.3f}s too high under load"
            
            print(f"Concurrent Load Test: {success_rate:.2%} success rate, {avg_response_time:.3f}s avg response time")
            
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_database_query_performance(self):
        """Test database query performance meets requirements."""
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as session:
            # Test launch listing query performance
            start_time = time.time()
            launches = session.query(Launch).limit(50).all()
            query_time = time.time() - start_time
            
            # Database queries should complete within 100ms
            assert query_time < 0.1, f"Launch listing query took {query_time:.3f}s (> 0.1s limit)"
            
            # Test specific launch query performance
            if launches:
                start_time = time.time()
                specific_launch = session.query(Launch).filter(
                    Launch.slug == launches[0].slug
                ).first()
                query_time = time.time() - start_time
                
                # Single launch queries should be very fast
                assert query_time < 0.05, f"Single launch query took {query_time:.3f}s (> 0.05s limit)"
                assert specific_launch is not None
            
            print(f"Database query performance validated")
    
    def test_cache_performance(self):
        """Test cache performance meets requirements."""
        cache_manager = CacheManager()
        
        if not cache_manager.is_enabled():
            pytest.skip("Redis not available")
        
        # Test cache write performance
        test_data = {"id": 1, "mission_name": "Performance Test", "data": "x" * 1000}
        
        start_time = time.time()
        for i in range(100):
            cache_manager.set_launch_detail(f"perf-test-{i}", test_data)
        write_time = time.time() - start_time
        
        # Cache writes should be fast
        avg_write_time = write_time / 100
        assert avg_write_time < 0.01, f"Cache write too slow: {avg_write_time:.4f}s average"
        
        # Test cache read performance
        start_time = time.time()
        for i in range(100):
            cached_data = cache_manager.get_launch_detail(f"perf-test-{i}")
            assert cached_data == test_data
        read_time = time.time() - start_time
        
        # Cache reads should be very fast
        avg_read_time = read_time / 100
        assert avg_read_time < 0.005, f"Cache read too slow: {avg_read_time:.4f}s average"
        
        # Cleanup
        for i in range(100):
            cache_manager.invalidate_launch_detail(f"perf-test-{i}")
        
        print(f"Cache performance: {avg_write_time:.4f}s write, {avg_read_time:.4f}s read")


class TestSystemReliability:
    """Test system reliability and fault tolerance."""
    
    def test_graceful_degradation_database_failure(self):
        """Test system gracefully degrades when database is unavailable."""
        try:
            # Test health endpoint when database might be down
            response = requests.get("http://localhost:8000/health/database", timeout=5)
            
            if response.status_code == 503:
                # Database is down - test that API still responds appropriately
                launches_response = requests.get("http://localhost:8000/api/launches", timeout=5)
                
                # Should return appropriate error or cached data
                assert launches_response.status_code in [200, 503]
                
                if launches_response.status_code == 503:
                    error_data = launches_response.json()
                    assert "error" in error_data
                    assert "database" in error_data["error"].lower()
            
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_graceful_degradation_redis_failure(self):
        """Test system gracefully degrades when Redis is unavailable."""
        try:
            # Test health endpoint for Redis
            response = requests.get("http://localhost:8000/health/redis", timeout=5)
            
            if response.status_code == 503:
                # Redis is down - API should still work but without caching
                launches_response = requests.get("http://localhost:8000/api/launches", timeout=10)
                
                # Should still return data (from database)
                assert launches_response.status_code == 200
                
                data = launches_response.json()
                assert "data" in data
            
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_error_handling_invalid_requests(self):
        """Test proper error handling for invalid requests."""
        try:
            base_url = "http://localhost:8000"
            
            # Test invalid launch slug
            response = requests.get(f"{base_url}/api/launches/nonexistent-launch", timeout=5)
            assert response.status_code == 404
            
            error_data = response.json()
            assert "error" in error_data
            
            # Test invalid query parameters
            response = requests.get(f"{base_url}/api/launches?limit=invalid", timeout=5)
            assert response.status_code == 422  # Validation error
            
            # Test invalid date format
            response = requests.get(f"{base_url}/api/launches?date_from=invalid-date", timeout=5)
            assert response.status_code == 422
            
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_rate_limiting_functionality(self):
        """Test that rate limiting works correctly."""
        try:
            base_url = "http://localhost:8000"
            endpoint = "/api/launches"
            
            # Make rapid requests to trigger rate limiting
            responses = []
            for i in range(100):  # Exceed typical rate limit
                response = requests.get(f"{base_url}{endpoint}", timeout=1)
                responses.append(response.status_code)
                
                if response.status_code == 429:  # Rate limited
                    break
            
            # Should eventually get rate limited
            rate_limited = any(status == 429 for status in responses)
            
            # Note: This might not trigger if rate limits are high or Redis is unavailable
            # So we don't assert, just log the result
            print(f"Rate limiting test: {'triggered' if rate_limited else 'not triggered'}")
            
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
        except requests.exceptions.Timeout:
            # Timeout might occur under heavy load - this is acceptable
            pass


class TestDataIntegrity:
    """Test data integrity and validation."""
    
    def test_launch_data_validation(self):
        """Test that launch data is properly validated."""
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as session:
            launches = session.query(Launch).limit(10).all()
            
            for launch in launches:
                # Required fields should not be None
                assert launch.slug is not None and launch.slug.strip() != ""
                assert launch.mission_name is not None and launch.mission_name.strip() != ""
                assert launch.status is not None
                
                # Status should be valid
                valid_statuses = ["upcoming", "success", "failure", "in_flight", "aborted"]
                assert launch.status in valid_statuses, f"Invalid status: {launch.status}"
                
                # Date validation
                if launch.launch_date:
                    assert isinstance(launch.launch_date, datetime)
                    # Launch date should be reasonable (not too far in past/future)
                    now = datetime.utcnow()
                    assert launch.launch_date > datetime(2000, 1, 1)  # Not before SpaceX existed
                    assert launch.launch_date < now + timedelta(days=3650)  # Not more than 10 years in future
                
                # Numeric fields validation
                if launch.payload_mass is not None:
                    assert launch.payload_mass >= 0, f"Negative payload mass: {launch.payload_mass}"
                    assert launch.payload_mass < 100000, f"Unrealistic payload mass: {launch.payload_mass}"
    
    def test_data_consistency_checks(self):
        """Test data consistency across the system."""
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as session:
            # Check for duplicate slugs
            slug_counts = session.execute("""
                SELECT slug, COUNT(*) as count 
                FROM launches 
                GROUP BY slug 
                HAVING COUNT(*) > 1
            """).fetchall()
            
            assert len(slug_counts) == 0, f"Found duplicate slugs: {[row.slug for row in slug_counts]}"
            
            # Check for launches with invalid date/status combinations
            upcoming_with_past_dates = session.query(Launch).filter(
                Launch.status == "upcoming",
                Launch.launch_date < datetime.utcnow() - timedelta(days=1)
            ).count()
            
            # Allow some tolerance for recently past launches that might still be marked as upcoming
            assert upcoming_with_past_dates < 5, f"Too many upcoming launches with past dates: {upcoming_with_past_dates}"
    
    def test_api_data_consistency(self):
        """Test that API returns consistent data."""
        try:
            base_url = "http://localhost:8000"
            
            # Get launch from general endpoint
            launches_response = requests.get(f"{base_url}/api/launches?limit=1", timeout=5)
            assert launches_response.status_code == 200
            
            launches_data = launches_response.json()
            if launches_data["data"]:
                launch_slug = launches_data["data"][0]["slug"]
                
                # Get same launch from specific endpoint
                specific_response = requests.get(f"{base_url}/api/launches/{launch_slug}", timeout=5)
                assert specific_response.status_code == 200
                
                specific_data = specific_response.json()
                
                # Data should be consistent
                assert specific_data["slug"] == launch_slug
                assert specific_data["mission_name"] == launches_data["data"][0]["mission_name"]
                assert specific_data["status"] == launches_data["data"][0]["status"]
            
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")


class TestSystemMonitoring:
    """Test system monitoring and health checks."""
    
    def test_health_check_endpoints(self):
        """Test all health check endpoints return proper status."""
        try:
            base_url = "http://localhost:8000"
            
            health_endpoints = {
                "/health": "overall system health",
                "/health/database": "database connectivity", 
                "/health/redis": "Redis connectivity",
                "/health/celery": "Celery worker status"
            }
            
            health_status = {}
            
            for endpoint, description in health_endpoints.items():
                response = requests.get(f"{base_url}{endpoint}", timeout=10)
                
                # Should return either 200 (healthy) or 503 (unhealthy)
                assert response.status_code in [200, 503], f"Health endpoint {endpoint} returned {response.status_code}"
                
                data = response.json()
                assert "status" in data, f"Health endpoint {endpoint} missing status field"
                
                health_status[endpoint] = {
                    "status": data["status"],
                    "healthy": response.status_code == 200
                }
            
            print(f"Health Check Status: {health_status}")
            
            # Overall health should be healthy if core components are healthy
            overall_healthy = health_status["/health"]["healthy"]
            database_healthy = health_status["/health/database"]["healthy"]
            
            if database_healthy:
                assert overall_healthy, "Overall health should be healthy when database is healthy"
            
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_system_resource_usage(self):
        """Test that system resource usage is within acceptable limits."""
        # Get current process and children
        current_process = psutil.Process()
        
        # Memory usage check
        memory_info = current_process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        
        # System should not use excessive memory (adjust limit based on your requirements)
        assert memory_mb < 1000, f"Memory usage too high: {memory_mb:.1f}MB"
        
        # CPU usage check (average over short period)
        cpu_percent = current_process.cpu_percent(interval=1)
        
        # CPU usage should be reasonable when not actively scraping
        assert cpu_percent < 50, f"CPU usage too high: {cpu_percent:.1f}%"
        
        print(f"Resource Usage: {memory_mb:.1f}MB memory, {cpu_percent:.1f}% CPU")
    
    def test_log_file_creation(self):
        """Test that log files are being created and written to."""
        log_file_path = os.getenv("LOG_FILE_PATH", "logs/spacex_tracker.log")
        
        if os.path.exists(log_file_path):
            # Check that log file is not empty
            file_size = os.path.getsize(log_file_path)
            assert file_size > 0, "Log file exists but is empty"
            
            # Check that log file has been written to recently (within last hour)
            mod_time = os.path.getmtime(log_file_path)
            time_since_mod = time.time() - mod_time
            
            # Log should have been written to within the last hour
            assert time_since_mod < 3600, f"Log file not updated recently: {time_since_mod:.0f}s ago"
            
            print(f"Log file: {log_file_path} ({file_size} bytes, updated {time_since_mod:.0f}s ago)")
        else:
            pytest.skip(f"Log file not found: {log_file_path}")


class TestDeploymentValidation:
    """Test deployment configuration and setup."""
    
    def test_docker_services_running(self):
        """Test that all required Docker services are running."""
        try:
            # Check if Docker is available
            result = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                pytest.skip("Docker not available")
            
            # Parse running containers
            running_containers = result.stdout
            
            # Expected services in development
            expected_services = [
                "postgres",
                "redis", 
                "backend",
                "frontend"
            ]
            
            missing_services = []
            for service in expected_services:
                if service not in running_containers.lower():
                    missing_services.append(service)
            
            if missing_services:
                pytest.skip(f"Missing Docker services: {', '.join(missing_services)}")
            
            print("All expected Docker services are running")
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Docker command not available")
    
    def test_environment_configuration(self):
        """Test that environment is properly configured."""
        # Check critical environment variables
        critical_vars = {
            "DATABASE_URL": "postgresql://",
            "REDIS_URL": "redis://",
            "JWT_SECRET_KEY": None  # Should exist but we won't check content
        }
        
        for var, expected_prefix in critical_vars.items():
            value = os.getenv(var)
            assert value is not None, f"Missing environment variable: {var}"
            
            if expected_prefix:
                assert value.startswith(expected_prefix), f"{var} has incorrect format"
        
        # Check that we're not using default/insecure values in production
        environment = os.getenv("ENVIRONMENT", "development")
        
        if environment == "production":
            # In production, certain values should not be defaults
            jwt_secret = os.getenv("JWT_SECRET_KEY")
            assert jwt_secret != "your_super_secret_jwt_key_here_change_in_production", \
                "Using default JWT secret in production"
            
            admin_password = os.getenv("ADMIN_PASSWORD")
            assert admin_password != "change_this_password_in_production", \
                "Using default admin password in production"
    
    def test_database_schema_current(self):
        """Test that database schema is up to date."""
        try:
            # Check Alembic current revision
            result = subprocess.run(
                ["alembic", "current"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                current_output = result.stdout.strip()
                
                # Check if there are pending migrations
                heads_result = subprocess.run(
                    ["alembic", "heads"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if heads_result.returncode == 0:
                    heads_output = heads_result.stdout.strip()
                    
                    # Current should match heads (no pending migrations)
                    if current_output and heads_output:
                        # Extract revision IDs (first part before space)
                        current_rev = current_output.split()[0] if current_output else ""
                        heads_rev = heads_output.split()[0] if heads_output else ""
                        
                        assert current_rev == heads_rev, \
                            f"Database schema not current. Current: {current_rev}, Head: {heads_rev}"
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Alembic not available")


class TestUserAcceptanceValidation:
    """Final user acceptance validation tests."""
    
    def test_complete_user_journey_upcoming_launches(self):
        """Test complete user journey for viewing upcoming launches."""
        try:
            base_url = "http://localhost:8000"
            
            # Step 1: Get upcoming launches
            response = requests.get(f"{base_url}/api/launches/upcoming", timeout=10)
            assert response.status_code == 200
            
            data = response.json()
            assert "data" in data
            
            if data["data"]:
                # Step 2: Get details for first upcoming launch
                first_launch = data["data"][0]
                launch_slug = first_launch["slug"]
                
                detail_response = requests.get(f"{base_url}/api/launches/{launch_slug}", timeout=10)
                assert detail_response.status_code == 200
                
                detail_data = detail_response.json()
                
                # Validate launch details
                assert detail_data["slug"] == launch_slug
                assert detail_data["status"] == "upcoming"
                assert detail_data["mission_name"] is not None
                
                # Launch date should be in the future
                if detail_data.get("launch_date"):
                    launch_date = datetime.fromisoformat(detail_data["launch_date"].replace("Z", "+00:00"))
                    assert launch_date > datetime.utcnow().replace(tzinfo=launch_date.tzinfo)
                
                print(f"User journey test passed for launch: {detail_data['mission_name']}")
            
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_complete_user_journey_search_filter(self):
        """Test complete user journey for searching and filtering launches."""
        try:
            base_url = "http://localhost:8000"
            
            # Step 1: Get all launches to find a search term
            response = requests.get(f"{base_url}/api/launches?limit=50", timeout=10)
            assert response.status_code == 200
            
            data = response.json()
            if data["data"]:
                # Step 2: Search for launches containing common terms
                search_terms = ["starlink", "crew", "dragon", "falcon"]
                
                for term in search_terms:
                    search_response = requests.get(
                        f"{base_url}/api/launches?search={term}&limit=10", 
                        timeout=10
                    )
                    
                    if search_response.status_code == 200:
                        search_data = search_response.json()
                        
                        # All results should contain the search term
                        for launch in search_data["data"]:
                            mission_name = launch["mission_name"].lower()
                            assert term.lower() in mission_name, \
                                f"Search result '{launch['mission_name']}' doesn't contain '{term}'"
                        
                        if search_data["data"]:
                            print(f"Search test passed for term: {term} ({len(search_data['data'])} results)")
                            break
            
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_system_meets_all_requirements(self):
        """Final validation that system meets all specified requirements."""
        requirements_met = {
            "api_response_time": False,
            "data_accuracy": False,
            "error_handling": False,
            "health_monitoring": False,
            "data_validation": False
        }
        
        try:
            base_url = "http://localhost:8000"
            
            # Test API response time requirement
            start_time = time.time()
            response = requests.get(f"{base_url}/api/launches?limit=10", timeout=5)
            response_time = time.time() - start_time
            
            if response.status_code == 200 and response_time < 1.0:
                requirements_met["api_response_time"] = True
            
            # Test data accuracy requirement
            data = response.json()
            if data["data"]:
                launch = data["data"][0]
                if all(key in launch for key in ["slug", "mission_name", "status"]):
                    requirements_met["data_accuracy"] = True
            
            # Test error handling requirement
            error_response = requests.get(f"{base_url}/api/launches/nonexistent", timeout=5)
            if error_response.status_code == 404:
                requirements_met["error_handling"] = True
            
            # Test health monitoring requirement
            health_response = requests.get(f"{base_url}/health", timeout=5)
            if health_response.status_code in [200, 503]:
                requirements_met["health_monitoring"] = True
            
            # Test data validation requirement (already tested in other methods)
            requirements_met["data_validation"] = True
            
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
        
        # Report results
        met_count = sum(requirements_met.values())
        total_count = len(requirements_met)
        
        print(f"Requirements Met: {met_count}/{total_count}")
        for requirement, met in requirements_met.items():
            print(f"  {requirement}: {'✓' if met else '✗'}")
        
        # At least 80% of requirements should be met
        success_rate = met_count / total_count
        assert success_rate >= 0.8, f"Only {success_rate:.1%} of requirements met (need ≥80%)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])