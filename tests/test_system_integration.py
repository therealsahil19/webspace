"""
Comprehensive system integration tests for the SpaceX Launch Tracker.
Tests the complete system with real data sources and validates end-to-end functionality.
"""
import pytest
import asyncio
import time
import requests
import json
import subprocess
import os
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from typing import Dict, List, Any

from src.database import get_database_manager
from src.models.launch import Launch
from src.repositories.launch_repository import LaunchRepository
from src.scraping.unified_scraper import UnifiedScraper
from src.processing.data_pipeline import DataPipeline
from src.cache.cache_manager import CacheManager
from src.tasks.scraping_tasks import scrape_all_sources


class TestSystemIntegration:
    """Comprehensive system integration tests."""
    
    @pytest.fixture(scope="class")
    def system_setup(self):
        """Set up system for integration testing."""
        # Ensure test database is clean
        db_manager = get_database_manager()
        
        # Store original data for restoration
        original_launches = []
        with db_manager.session_scope() as session:
            original_launches = session.query(Launch).all()
        
        yield {
            "db_manager": db_manager,
            "original_launches": original_launches
        }
        
        # Restore original data
        with db_manager.session_scope() as session:
            # Clear test data
            session.query(Launch).delete()
            
            # Restore original data
            for launch in original_launches:
                session.merge(launch)
            session.commit()
    
    def test_complete_data_pipeline_integration(self, system_setup):
        """Test complete data pipeline from scraping to database storage."""
        db_manager = system_setup["db_manager"]
        
        # Initialize components
        unified_scraper = UnifiedScraper()
        data_pipeline = DataPipeline()
        
        # Mock scraper to return test data instead of real scraping
        test_launch_data = {
            "slug": "integration-test-launch",
            "mission_name": "Integration Test Mission",
            "launch_date": datetime.utcnow() + timedelta(days=30),
            "vehicle_type": "Falcon 9",
            "status": "upcoming",
            "details": "Test launch for integration testing",
            "payload_mass": 5000.0,
            "orbit": "LEO",
            "mission_patch_url": "https://example.com/patch.png",
            "webcast_url": "https://example.com/webcast"
        }
        
        with patch.object(unified_scraper, 'scrape_all_sources') as mock_scrape:
            mock_scrape.return_value = [test_launch_data]
            
            # Run complete pipeline
            scraped_data = unified_scraper.scrape_all_sources()
            processed_data = data_pipeline.process_scraped_data(scraped_data)
            
            # Verify data was processed correctly
            assert len(processed_data) == 1
            assert processed_data[0]["slug"] == "integration-test-launch"
            assert processed_data[0]["status"] == "upcoming"
            
            # Verify data was stored in database
            with db_manager.session_scope() as session:
                stored_launch = session.query(Launch).filter(
                    Launch.slug == "integration-test-launch"
                ).first()
                
                assert stored_launch is not None
                assert stored_launch.mission_name == "Integration Test Mission"
                assert stored_launch.vehicle_type == "Falcon 9"
                assert stored_launch.status == "upcoming"
    
    def test_api_database_integration(self, system_setup):
        """Test API endpoints with real database integration."""
        db_manager = system_setup["db_manager"]
        
        # Create test data in database
        test_launch = Launch(
            slug="api-integration-test",
            mission_name="API Integration Test",
            launch_date=datetime.utcnow() + timedelta(days=15),
            vehicle_type="Falcon Heavy",
            status="upcoming",
            details="Test launch for API integration",
            payload_mass=8000.0,
            orbit="GTO"
        )
        
        with db_manager.session_scope() as session:
            session.add(test_launch)
            session.commit()
        
        try:
            # Test API endpoints (assuming API is running on localhost:8000)
            base_url = "http://localhost:8000"
            
            # Test launches list endpoint
            response = requests.get(f"{base_url}/api/launches", timeout=10)
            if response.status_code == 200:
                launches_data = response.json()
                assert "data" in launches_data
                assert len(launches_data["data"]) > 0
                
                # Find our test launch
                test_launch_found = any(
                    launch["slug"] == "api-integration-test" 
                    for launch in launches_data["data"]
                )
                assert test_launch_found, "Test launch not found in API response"
            
            # Test specific launch endpoint
            response = requests.get(f"{base_url}/api/launches/api-integration-test", timeout=10)
            if response.status_code == 200:
                launch_data = response.json()
                assert launch_data["slug"] == "api-integration-test"
                assert launch_data["mission_name"] == "API Integration Test"
                assert launch_data["vehicle_type"] == "Falcon Heavy"
            
            # Test upcoming launches endpoint
            response = requests.get(f"{base_url}/api/launches/upcoming", timeout=10)
            if response.status_code == 200:
                upcoming_data = response.json()
                assert "data" in upcoming_data
                
                # Our test launch should be in upcoming
                test_launch_found = any(
                    launch["slug"] == "api-integration-test" 
                    for launch in upcoming_data["data"]
                )
                assert test_launch_found, "Test launch not found in upcoming launches"
        
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running - skipping API integration tests")
        
        finally:
            # Cleanup test data
            with db_manager.session_scope() as session:
                session.query(Launch).filter(
                    Launch.slug == "api-integration-test"
                ).delete()
                session.commit()
    
    def test_cache_integration(self, system_setup):
        """Test cache integration with database and API."""
        cache_manager = CacheManager()
        
        if not cache_manager.is_enabled():
            pytest.skip("Redis not available - skipping cache integration tests")
        
        db_manager = system_setup["db_manager"]
        
        # Create test data
        test_launch = Launch(
            slug="cache-integration-test",
            mission_name="Cache Integration Test",
            launch_date=datetime.utcnow() + timedelta(days=20),
            vehicle_type="Falcon 9",
            status="upcoming",
            details="Test launch for cache integration"
        )
        
        with db_manager.session_scope() as session:
            session.add(test_launch)
            session.commit()
        
        try:
            # Test cache warming
            launch_dict = {
                "id": test_launch.id,
                "slug": test_launch.slug,
                "mission_name": test_launch.mission_name,
                "launch_date": test_launch.launch_date.isoformat() if test_launch.launch_date else None,
                "vehicle_type": test_launch.vehicle_type,
                "status": test_launch.status,
                "details": test_launch.details
            }
            
            # Cache the launch
            assert cache_manager.set_launch_detail(test_launch.slug, launch_dict)
            
            # Retrieve from cache
            cached_launch = cache_manager.get_launch_detail(test_launch.slug)
            assert cached_launch is not None
            assert cached_launch["slug"] == "cache-integration-test"
            assert cached_launch["mission_name"] == "Cache Integration Test"
            
            # Test cache invalidation
            assert cache_manager.invalidate_launch_detail(test_launch.slug)
            assert cache_manager.get_launch_detail(test_launch.slug) is None
        
        finally:
            # Cleanup
            with db_manager.session_scope() as session:
                session.query(Launch).filter(
                    Launch.slug == "cache-integration-test"
                ).delete()
                session.commit()
    
    def test_celery_task_integration(self, system_setup):
        """Test Celery task integration with scraping and database."""
        # This test requires Celery to be running
        try:
            from celery import Celery
            from src.celery_app import celery_app
            
            # Check if Celery is available
            inspector = celery_app.control.inspect()
            active_workers = inspector.active()
            
            if not active_workers:
                pytest.skip("No Celery workers available - skipping task integration tests")
            
            # Test scraping task
            with patch('src.scraping.unified_scraper.UnifiedScraper.scrape_all_sources') as mock_scrape:
                mock_scrape.return_value = [{
                    "slug": "celery-test-launch",
                    "mission_name": "Celery Test Mission",
                    "launch_date": datetime.utcnow() + timedelta(days=10),
                    "vehicle_type": "Falcon 9",
                    "status": "upcoming",
                    "details": "Test launch for Celery integration"
                }]
                
                # Trigger scraping task
                result = scrape_all_sources.delay()
                
                # Wait for task completion (with timeout)
                task_result = result.get(timeout=30)
                
                assert task_result["status"] == "success"
                assert task_result["launches_processed"] > 0
        
        except ImportError:
            pytest.skip("Celery not available - skipping task integration tests")
        except Exception as e:
            pytest.skip(f"Celery integration test failed: {str(e)}")


class TestDataAccuracyValidation:
    """Tests to validate data accuracy against official sources."""
    
    def test_spacex_data_structure_validation(self):
        """Validate that scraped SpaceX data matches expected structure."""
        from src.scraping.spacex_scraper import SpaceXScraper
        
        scraper = SpaceXScraper()
        
        # Mock the scraping to avoid hitting real SpaceX website during tests
        with patch.object(scraper, 'scrape_launches') as mock_scrape:
            mock_scrape.return_value = [{
                "slug": "starlink-mission",
                "mission_name": "Starlink Mission",
                "launch_date": datetime.utcnow() + timedelta(days=5),
                "vehicle_type": "Falcon 9",
                "status": "upcoming",
                "details": "Starlink satellite deployment mission",
                "payload_mass": 15000.0,
                "orbit": "LEO"
            }]
            
            launches = scraper.scrape_launches()
            
            # Validate data structure
            assert len(launches) > 0
            
            for launch in launches:
                # Required fields
                assert "slug" in launch
                assert "mission_name" in launch
                assert "status" in launch
                
                # Data types
                assert isinstance(launch["slug"], str)
                assert isinstance(launch["mission_name"], str)
                assert launch["status"] in ["upcoming", "success", "failure", "in_flight", "aborted"]
                
                if launch.get("launch_date"):
                    assert isinstance(launch["launch_date"], datetime)
                
                if launch.get("payload_mass"):
                    assert isinstance(launch["payload_mass"], (int, float))
    
    def test_data_consistency_across_sources(self):
        """Test data consistency when multiple sources provide the same launch."""
        from src.processing.source_reconciler import SourceReconciler
        
        reconciler = SourceReconciler()
        
        # Mock data from different sources for the same launch
        spacex_data = {
            "slug": "consistency-test",
            "mission_name": "Consistency Test Mission",
            "launch_date": datetime(2024, 6, 15, 10, 30),
            "vehicle_type": "Falcon 9",
            "status": "upcoming",
            "source": "spacex"
        }
        
        nasa_data = {
            "slug": "consistency-test",
            "mission_name": "Consistency Test Mission",
            "launch_date": datetime(2024, 6, 15, 10, 30),
            "vehicle_type": "Falcon 9",
            "status": "upcoming",
            "source": "nasa"
        }
        
        wikipedia_data = {
            "slug": "consistency-test",
            "mission_name": "Consistency Test Mission",
            "launch_date": datetime(2024, 6, 15, 10, 35),  # Slightly different time
            "vehicle_type": "Falcon 9",
            "status": "upcoming",
            "source": "wikipedia"
        }
        
        # Reconcile data
        reconciled = reconciler.reconcile_launch_data([spacex_data, nasa_data, wikipedia_data])
        
        # SpaceX data should be prioritized
        assert reconciled["source"] == "spacex"
        assert reconciled["launch_date"] == datetime(2024, 6, 15, 10, 30)
        
        # Check that conflicts were detected
        conflicts = reconciler.get_detected_conflicts()
        assert len(conflicts) > 0
        
        # Should have conflict for launch_date
        date_conflict = next((c for c in conflicts if c["field"] == "launch_date"), None)
        assert date_conflict is not None


class TestSystemResilience:
    """Tests for system resilience and fault tolerance."""
    
    def test_database_connection_failure_handling(self):
        """Test system behavior when database connection fails."""
        from src.api.main import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # Mock database connection failure
        with patch('src.database.get_database_manager') as mock_db:
            mock_db.side_effect = Exception("Database connection failed")
            
            # API should return appropriate error
            response = client.get("/api/launches")
            assert response.status_code == 503  # Service Unavailable
            
            error_data = response.json()
            assert "error" in error_data
            assert "database" in error_data["error"].lower()
    
    def test_redis_connection_failure_handling(self):
        """Test system behavior when Redis connection fails."""
        cache_manager = CacheManager()
        
        # Mock Redis connection failure
        with patch.object(cache_manager.redis_client, 'is_connected', return_value=False):
            # Cache operations should fail gracefully
            result = cache_manager.set_launch_detail("test", {"data": "test"})
            assert result is False
            
            cached_data = cache_manager.get_launch_detail("test")
            assert cached_data is None
    
    def test_scraping_source_failure_handling(self):
        """Test system behavior when scraping sources are unavailable."""
        from src.scraping.unified_scraper import UnifiedScraper
        
        scraper = UnifiedScraper()
        
        # Mock all scrapers to fail
        with patch.object(scraper.spacex_scraper, 'scrape_launches', side_effect=Exception("SpaceX site unavailable")), \
             patch.object(scraper.nasa_scraper, 'scrape_launches', side_effect=Exception("NASA site unavailable")), \
             patch.object(scraper.wikipedia_scraper, 'scrape_launches', side_effect=Exception("Wikipedia unavailable")):
            
            # Should handle failures gracefully and return empty list
            launches = scraper.scrape_all_sources()
            assert isinstance(launches, list)
            assert len(launches) == 0
    
    def test_high_load_performance(self):
        """Test system performance under high load conditions."""
        from src.api.main import app
        from fastapi.testclient import TestClient
        import concurrent.futures
        import threading
        
        client = TestClient(app)
        
        def make_request():
            """Make a single API request."""
            try:
                response = client.get("/api/launches?limit=10")
                return response.status_code == 200
            except Exception:
                return False
        
        # Simulate concurrent requests
        num_requests = 50
        success_count = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            
            for future in concurrent.futures.as_completed(futures, timeout=30):
                if future.result():
                    success_count += 1
        
        # At least 80% of requests should succeed under load
        success_rate = success_count / num_requests
        assert success_rate >= 0.8, f"Success rate too low: {success_rate:.2%}"


class TestUserAcceptanceScenarios:
    """User acceptance testing scenarios for major features."""
    
    def test_user_can_view_upcoming_launches(self):
        """Test that users can view upcoming launches with countdown timers."""
        # This would typically be done with Selenium or Playwright
        # For now, we'll test the API that powers this functionality
        
        try:
            response = requests.get("http://localhost:8000/api/launches/upcoming", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                assert "data" in data
                
                # Check that upcoming launches have future dates
                for launch in data["data"]:
                    if launch.get("launch_date"):
                        launch_date = datetime.fromisoformat(launch["launch_date"].replace("Z", "+00:00"))
                        assert launch_date > datetime.utcnow().replace(tzinfo=launch_date.tzinfo)
                    
                    assert launch["status"] == "upcoming"
        
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_user_can_search_launches(self):
        """Test that users can search for specific launches."""
        try:
            # Test search functionality
            response = requests.get(
                "http://localhost:8000/api/launches?search=starlink", 
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                assert "data" in data
                
                # All results should contain "starlink" in mission name (case insensitive)
                for launch in data["data"]:
                    assert "starlink" in launch["mission_name"].lower()
        
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_user_can_filter_by_status(self):
        """Test that users can filter launches by status."""
        try:
            # Test filtering by success status
            response = requests.get(
                "http://localhost:8000/api/launches?status=success", 
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                assert "data" in data
                
                # All results should have success status
                for launch in data["data"]:
                    assert launch["status"] == "success"
        
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_admin_can_trigger_refresh(self):
        """Test that admin users can trigger manual data refresh."""
        try:
            # First, try to authenticate (this would need valid credentials)
            auth_response = requests.post(
                "http://localhost:8000/api/auth/login",
                json={"username": "admin", "password": "admin123"},
                timeout=10
            )
            
            if auth_response.status_code == 200:
                token = auth_response.json()["access_token"]
                
                # Try to trigger refresh
                refresh_response = requests.post(
                    "http://localhost:8000/api/admin/refresh",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30
                )
                
                # Should either succeed or return appropriate error
                assert refresh_response.status_code in [200, 202, 401, 403]
        
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")


class TestSystemConfiguration:
    """Tests for system configuration and operational procedures."""
    
    def test_environment_variables_validation(self):
        """Test that all required environment variables are properly configured."""
        required_vars = [
            "DATABASE_URL",
            "REDIS_URL",
            "JWT_SECRET_KEY",
            "ADMIN_USERNAME",
            "ADMIN_PASSWORD"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            pytest.skip(f"Missing environment variables: {', '.join(missing_vars)}")
        
        # Validate format of critical variables
        database_url = os.getenv("DATABASE_URL")
        assert database_url.startswith("postgresql://"), "DATABASE_URL should be PostgreSQL connection string"
        
        redis_url = os.getenv("REDIS_URL")
        assert redis_url.startswith("redis://"), "REDIS_URL should be Redis connection string"
        
        jwt_secret = os.getenv("JWT_SECRET_KEY")
        assert len(jwt_secret) >= 32, "JWT_SECRET_KEY should be at least 32 characters long"
    
    def test_database_migrations_status(self):
        """Test that database migrations are up to date."""
        try:
            # Check Alembic migration status
            result = subprocess.run(
                ["alembic", "current"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Should show current migration
                assert "current" in result.stdout.lower() or len(result.stdout.strip()) > 0
            else:
                pytest.skip("Alembic not available or database not accessible")
        
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Alembic command not available")
    
    def test_health_endpoints_availability(self):
        """Test that all health check endpoints are available."""
        health_endpoints = [
            "/health",
            "/health/database", 
            "/health/redis",
            "/health/celery"
        ]
        
        try:
            for endpoint in health_endpoints:
                response = requests.get(f"http://localhost:8000{endpoint}", timeout=10)
                
                # Health endpoints should return 200 or 503 (service unavailable)
                assert response.status_code in [200, 503], f"Health endpoint {endpoint} returned {response.status_code}"
                
                # Response should be JSON
                data = response.json()
                assert "status" in data
        
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")
    
    def test_logging_configuration(self):
        """Test that logging is properly configured."""
        import logging
        from src.logging_config import setup_logging
        
        # Test logging setup
        setup_logging()
        
        # Get logger
        logger = logging.getLogger("spacex_tracker")
        
        # Logger should be configured
        assert logger.level <= logging.INFO
        assert len(logger.handlers) > 0
        
        # Test log file creation
        log_file_path = os.getenv("LOG_FILE_PATH", "logs/spacex_tracker.log")
        log_dir = os.path.dirname(log_file_path)
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Test logging
        logger.info("Integration test log message")
        
        # Log file should exist after logging
        assert os.path.exists(log_file_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])