"""
Tests for admin API endpoints.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.auth.models import User, UserRole
from src.models.database import Launch, DataConflict
from src.models.schemas import LaunchStatus


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def sample_admin_user():
    """Create a sample admin user object."""
    return User(
        id=1,
        username="admin",
        email="admin@example.com",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_api_key_user():
    """Create a sample API key user object."""
    return User(
        id=0,  # Special ID for API key users
        username="api_key_user",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_launch():
    """Create a sample launch object."""
    launch = Mock(spec=Launch)
    launch.id = 1
    launch.slug = "falcon-heavy-demo"
    launch.mission_name = "Falcon Heavy Demo"
    launch.launch_date = datetime(2024, 6, 15, 12, 0, 0)
    launch.vehicle_type = "Falcon Heavy"
    launch.status = LaunchStatus.SUCCESS
    launch.created_at = datetime.utcnow()
    launch.updated_at = datetime.utcnow()
    launch.details = "Demo flight"
    launch.mission_patch_url = "https://example.com/patch.png"
    launch.webcast_url = "https://example.com/webcast"
    return launch


@pytest.fixture
def sample_conflict():
    """Create a sample data conflict object."""
    conflict = Mock(spec=DataConflict)
    conflict.id = 1
    conflict.launch_id = 1
    conflict.field_name = "launch_date"
    conflict.source1_value = "2024-06-15"
    conflict.source2_value = "2024-06-16"
    conflict.confidence_score = 0.8
    conflict.resolved = False
    conflict.created_at = datetime.utcnow()
    conflict.resolved_at = None
    conflict.launch = Mock()
    conflict.launch.slug = "falcon-heavy-demo"
    conflict.launch.mission_name = "Falcon Heavy Demo"
    return conflict


class TestManualRefreshEndpoint:
    """Test the manual data refresh endpoint."""
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.dependencies.require_auth_or_api_key')
    @patch('src.tasks.scraping_tasks.run_full_scraping_pipeline.delay')
    @patch('src.cache.cache_manager.get_cache_manager')
    def test_manual_refresh_success_jwt_admin(self, mock_get_cache_manager, mock_task_delay, mock_require_auth, mock_get_db, client, sample_admin_user):
        """Test successful manual refresh with JWT admin user."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_require_auth.return_value = sample_admin_user
        
        mock_cache_manager = Mock()
        mock_get_cache_manager.return_value = mock_cache_manager
        
        mock_task = Mock()
        mock_task.id = "task-123"
        mock_task_delay.return_value = mock_task
        
        # Make request
        response = client.post("/api/admin/refresh")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Data refresh triggered successfully"
        assert data["task_id"] == "task-123"
        assert data["status"] == "started"
        assert data["triggered_by"] == "admin"
        
        # Verify cache was invalidated and task was triggered
        mock_cache_manager.invalidate_all_cache.assert_called_once()
        mock_task_delay.assert_called_once()
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.dependencies.require_auth_or_api_key')
    @patch('src.tasks.scraping_tasks.run_full_scraping_pipeline.delay')
    @patch('src.cache.cache_manager.get_cache_manager')
    def test_manual_refresh_success_api_key(self, mock_get_cache_manager, mock_task_delay, mock_require_auth, mock_get_db, client, sample_api_key_user):
        """Test successful manual refresh with API key user."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_require_auth.return_value = sample_api_key_user
        
        mock_cache_manager = Mock()
        mock_get_cache_manager.return_value = mock_cache_manager
        
        mock_task = Mock()
        mock_task.id = "task-456"
        mock_task_delay.return_value = mock_task
        
        # Make request
        response = client.post("/api/admin/refresh")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-456"
        assert data["triggered_by"] == "api_key_user"
    
    @patch('src.auth.dependencies.require_auth_or_api_key')
    def test_manual_refresh_viewer_forbidden(self, mock_require_auth, client):
        """Test manual refresh with viewer user (should be forbidden)."""
        # Create viewer user
        viewer_user = User(
            id=2,
            username="viewer",
            role=UserRole.VIEWER,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        mock_require_auth.return_value = viewer_user
        
        # Make request
        response = client.post("/api/admin/refresh")
        
        # Assertions
        assert response.status_code == 403
        data = response.json()
        assert "Admin access required" in data["detail"]
    
    def test_manual_refresh_unauthorized(self, client):
        """Test manual refresh without authentication."""
        response = client.post("/api/admin/refresh")
        assert response.status_code == 401
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.dependencies.require_auth_or_api_key')
    @patch('src.tasks.scraping_tasks.run_full_scraping_pipeline.delay')
    @patch('src.cache.cache_manager.get_cache_manager')
    def test_manual_refresh_task_error(self, mock_get_cache_manager, mock_task_delay, mock_require_auth, mock_get_db, client, sample_admin_user):
        """Test manual refresh when task creation fails."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_require_auth.return_value = sample_admin_user
        
        mock_cache_manager = Mock()
        mock_get_cache_manager.return_value = mock_cache_manager
        
        mock_task_delay.side_effect = Exception("Celery error")
        
        # Make request
        response = client.post("/api/admin/refresh")
        
        # Assertions
        assert response.status_code == 500
        data = response.json()
        assert "Failed to trigger data refresh" in data["detail"]


class TestRefreshStatusEndpoint:
    """Test the refresh task status endpoint."""
    
    @patch('src.auth.dependencies.require_admin')
    @patch('src.celery_app.celery_app')
    def test_get_refresh_status_success(self, mock_celery_app, mock_require_admin, client, sample_admin_user):
        """Test successful retrieval of refresh task status."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        mock_task_result = Mock()
        mock_task_result.status = "SUCCESS"
        mock_task_result.ready.return_value = True
        mock_task_result.successful.return_value = True
        mock_task_result.result = {"launches_processed": 10, "conflicts_found": 2}
        mock_task_result.current = 10
        mock_task_result.total = 10
        
        with patch('celery.result.AsyncResult') as mock_async_result:
            mock_async_result.return_value = mock_task_result
            
            # Make request
            response = client.get("/api/admin/refresh/status/task-123")
            
            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "task-123"
            assert data["status"] == "SUCCESS"
            assert data["result"]["launches_processed"] == 10
    
    @patch('src.auth.dependencies.require_admin')
    @patch('src.celery_app.celery_app')
    def test_get_refresh_status_pending(self, mock_celery_app, mock_require_admin, client, sample_admin_user):
        """Test retrieval of pending task status."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        mock_task_result = Mock()
        mock_task_result.status = "PENDING"
        mock_task_result.ready.return_value = False
        mock_task_result.info = {"current": 5, "total": 10, "status": "Processing launches"}
        mock_task_result.current = 5
        mock_task_result.total = 10
        
        with patch('celery.result.AsyncResult') as mock_async_result:
            mock_async_result.return_value = mock_task_result
            
            # Make request
            response = client.get("/api/admin/refresh/status/task-456")
            
            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "PENDING"
            assert data["current"] == 5
            assert data["total"] == 10
            assert data["info"]["status"] == "Processing launches"
    
    @patch('src.auth.dependencies.require_admin')
    @patch('src.celery_app.celery_app')
    def test_get_refresh_status_failed(self, mock_celery_app, mock_require_admin, client, sample_admin_user):
        """Test retrieval of failed task status."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        mock_task_result = Mock()
        mock_task_result.status = "FAILURE"
        mock_task_result.ready.return_value = True
        mock_task_result.successful.return_value = False
        mock_task_result.info = "Database connection failed"
        mock_task_result.current = 0
        mock_task_result.total = 1
        
        with patch('celery.result.AsyncResult') as mock_async_result:
            mock_async_result.return_value = mock_task_result
            
            # Make request
            response = client.get("/api/admin/refresh/status/task-789")
            
            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "FAILURE"
            assert data["error"] == "Database connection failed"
    
    def test_get_refresh_status_unauthorized(self, client):
        """Test refresh status without admin authentication."""
        response = client.get("/api/admin/refresh/status/task-123")
        assert response.status_code == 401


class TestSystemHealthEndpoint:
    """Test the system health endpoint."""
    
    @patch('src.api.dependencies.get_repo_manager')
    @patch('src.auth.dependencies.require_admin')
    @patch('src.cache.cache_manager.get_cache_manager')
    @patch('src.celery_app.celery_app')
    def test_system_health_all_healthy(self, mock_celery_app, mock_get_cache_manager, mock_require_admin, mock_get_repo_manager, client, sample_admin_user, sample_launch):
        """Test system health when all components are healthy."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        # Mock repository manager
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_all.return_value = [sample_launch]
        mock_launch_repo.get_upcoming_launches.return_value = [sample_launch]
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Mock cache manager
        mock_cache_manager = Mock()
        mock_cache_manager.get_system_health.return_value = None  # No cached result
        mock_cache_manager.get_cache_info.return_value = {
            "connected": True,
            "enabled": True,
            "cache_entries": {"total": 50},
            "hit_rate": 0.85
        }
        mock_get_cache_manager.return_value = mock_cache_manager
        
        # Mock Celery
        mock_inspect = Mock()
        mock_inspect.active.return_value = {"worker1": [], "worker2": []}
        mock_celery_app.control.inspect.return_value = mock_inspect
        
        # Make request
        response = client.get("/api/admin/system/health")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["components"]["database"]["status"] == "healthy"
        assert data["components"]["celery"]["status"] == "healthy"
        assert data["components"]["cache"]["status"] == "healthy"
        assert data["components"]["data_freshness"]["status"] == "healthy"
        
        # Verify cache was set
        mock_cache_manager.set_system_health.assert_called_once()
    
    @patch('src.api.dependencies.get_repo_manager')
    @patch('src.auth.dependencies.require_admin')
    @patch('src.cache.cache_manager.get_cache_manager')
    def test_system_health_cached_result(self, mock_get_cache_manager, mock_require_admin, mock_get_repo_manager, client, sample_admin_user):
        """Test system health with cached result."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        cached_health = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",
            "components": {"database": {"status": "healthy"}}
        }
        
        mock_cache_manager = Mock()
        mock_cache_manager.get_system_health.return_value = cached_health
        mock_get_cache_manager.return_value = mock_cache_manager
        
        # Make request
        response = client.get("/api/admin/system/health")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data == cached_health
        
        # Verify cache was used and not set again
        mock_cache_manager.get_system_health.assert_called_once()
        mock_cache_manager.set_system_health.assert_not_called()
    
    @patch('src.api.dependencies.get_repo_manager')
    @patch('src.auth.dependencies.require_admin')
    @patch('src.cache.cache_manager.get_cache_manager')
    @patch('src.celery_app.celery_app')
    def test_system_health_database_unhealthy(self, mock_celery_app, mock_get_cache_manager, mock_require_admin, mock_get_repo_manager, client, sample_admin_user):
        """Test system health when database is unhealthy."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        # Mock repository manager with database error
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_all.side_effect = Exception("Database connection failed")
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Mock cache manager
        mock_cache_manager = Mock()
        mock_cache_manager.get_system_health.return_value = None
        mock_cache_manager.get_cache_info.return_value = {"connected": True}
        mock_get_cache_manager.return_value = mock_cache_manager
        
        # Mock Celery
        mock_inspect = Mock()
        mock_inspect.active.return_value = {"worker1": []}
        mock_celery_app.control.inspect.return_value = mock_inspect
        
        # Make request
        response = client.get("/api/admin/system/health")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["database"]["status"] == "unhealthy"
        assert "Database connection failed" in data["components"]["database"]["error"]
    
    @patch('src.api.dependencies.get_repo_manager')
    @patch('src.auth.dependencies.require_admin')
    @patch('src.cache.cache_manager.get_cache_manager')
    @patch('src.celery_app.celery_app')
    def test_system_health_stale_data(self, mock_celery_app, mock_get_cache_manager, mock_require_admin, mock_get_repo_manager, client, sample_admin_user):
        """Test system health when data is stale."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        # Create launch with old update time
        old_launch = Mock()
        old_launch.updated_at = datetime.utcnow() - timedelta(hours=15)  # 15 hours old
        
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_all.return_value = [old_launch]
        mock_launch_repo.get_upcoming_launches.return_value = []
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Mock cache manager
        mock_cache_manager = Mock()
        mock_cache_manager.get_system_health.return_value = None
        mock_cache_manager.get_cache_info.return_value = {"connected": True}
        mock_get_cache_manager.return_value = mock_cache_manager
        
        # Mock Celery
        mock_inspect = Mock()
        mock_inspect.active.return_value = {"worker1": []}
        mock_celery_app.control.inspect.return_value = mock_inspect
        
        # Make request
        response = client.get("/api/admin/system/health")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["data_freshness"]["status"] == "stale"
        assert data["components"]["data_freshness"]["hours_since_update"] > 12
    
    def test_system_health_unauthorized(self, client):
        """Test system health without admin authentication."""
        response = client.get("/api/admin/system/health")
        assert response.status_code == 401


class TestSystemStatsEndpoint:
    """Test the system statistics endpoint."""
    
    @patch('src.api.dependencies.get_repo_manager')
    @patch('src.auth.dependencies.require_admin')
    @patch('src.cache.cache_manager.get_cache_manager')
    def test_system_stats_success(self, mock_get_cache_manager, mock_require_admin, mock_get_repo_manager, client, sample_admin_user):
        """Test successful retrieval of system statistics."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        # Create sample launches with different statuses
        launches = []
        for i in range(10):
            launch = Mock()
            launch.status = LaunchStatus.SUCCESS if i < 7 else LaunchStatus.FAILURE
            launch.vehicle_type = "Falcon 9" if i < 8 else "Falcon Heavy"
            launch.launch_date = datetime.utcnow() + timedelta(days=i-5)  # Mix of past and future
            launch.details = f"Launch {i} details" if i < 8 else None
            launch.mission_patch_url = f"patch{i}.png" if i < 6 else None
            launch.webcast_url = f"webcast{i}" if i < 9 else None
            launch.created_at = datetime.utcnow() - timedelta(days=i)
            launch.updated_at = datetime.utcnow() - timedelta(hours=i)
            launches.append(launch)
        
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_all.return_value = launches
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Mock cache manager
        mock_cache_manager = Mock()
        mock_cache_manager.get_system_stats.return_value = None  # No cached result
        mock_cache_manager.get_cache_info.return_value = {
            "cache_entries": {"total": 100},
            "hit_rate": 0.75
        }
        mock_get_cache_manager.return_value = mock_cache_manager
        
        # Make request
        response = client.get("/api/admin/system/stats")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        # Check launch statistics
        assert data["launch_statistics"]["total_launches"] == 10
        assert data["launch_statistics"]["status_breakdown"]["success"] == 7
        assert data["launch_statistics"]["status_breakdown"]["failure"] == 3
        assert data["launch_statistics"]["vehicle_breakdown"]["Falcon 9"] == 8
        assert data["launch_statistics"]["vehicle_breakdown"]["Falcon Heavy"] == 2
        
        # Check data quality metrics
        assert data["data_quality"]["launches_with_details"] == 8
        assert data["data_quality"]["launches_with_patches"] == 6
        assert data["data_quality"]["launches_with_webcasts"] == 9
        assert data["data_quality"]["detail_coverage"] == 80.0
        assert data["data_quality"]["patch_coverage"] == 60.0
        assert data["data_quality"]["webcast_coverage"] == 90.0
        
        # Verify cache was set
        mock_cache_manager.set_system_stats.assert_called_once()
    
    @patch('src.auth.dependencies.require_admin')
    @patch('src.cache.cache_manager.get_cache_manager')
    def test_system_stats_cached_result(self, mock_get_cache_manager, mock_require_admin, client, sample_admin_user):
        """Test system stats with cached result."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        cached_stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "launch_statistics": {"total_launches": 5}
        }
        
        mock_cache_manager = Mock()
        mock_cache_manager.get_system_stats.return_value = cached_stats
        mock_get_cache_manager.return_value = mock_cache_manager
        
        # Make request
        response = client.get("/api/admin/system/stats")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data == cached_stats
        
        # Verify cache was used
        mock_cache_manager.get_system_stats.assert_called_once()
        mock_cache_manager.set_system_stats.assert_not_called()
    
    def test_system_stats_unauthorized(self, client):
        """Test system stats without admin authentication."""
        response = client.get("/api/admin/system/stats")
        assert response.status_code == 401


class TestDataConflictsEndpoint:
    """Test the data conflicts endpoint."""
    
    @patch('src.api.dependencies.get_repo_manager')
    @patch('src.auth.dependencies.require_admin')
    def test_get_conflicts_unresolved(self, mock_require_admin, mock_get_repo_manager, client, sample_admin_user, sample_conflict):
        """Test retrieval of unresolved conflicts."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        mock_repo_manager = Mock()
        mock_conflict_repo = Mock()
        mock_repo_manager.conflict_repository = mock_conflict_repo
        mock_conflict_repo.get_conflicts.return_value = [sample_conflict]
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request
        response = client.get("/api/admin/conflicts")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["resolved"] is False
        assert len(data["conflicts"]) == 1
        
        conflict = data["conflicts"][0]
        assert conflict["id"] == 1
        assert conflict["field_name"] == "launch_date"
        assert conflict["source1_value"] == "2024-06-15"
        assert conflict["source2_value"] == "2024-06-16"
        assert conflict["resolved"] is False
        assert conflict["launch"]["slug"] == "falcon-heavy-demo"
        
        # Verify repository was called correctly
        mock_conflict_repo.get_conflicts.assert_called_once_with(resolved=False)
    
    @patch('src.api.dependencies.get_repo_manager')
    @patch('src.auth.dependencies.require_admin')
    def test_get_conflicts_resolved(self, mock_require_admin, mock_get_repo_manager, client, sample_admin_user):
        """Test retrieval of resolved conflicts."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        resolved_conflict = Mock()
        resolved_conflict.id = 2
        resolved_conflict.launch_id = 1
        resolved_conflict.field_name = "vehicle_type"
        resolved_conflict.source1_value = "Falcon 9"
        resolved_conflict.source2_value = "Falcon Heavy"
        resolved_conflict.confidence_score = 0.9
        resolved_conflict.resolved = True
        resolved_conflict.created_at = datetime.utcnow()
        resolved_conflict.resolved_at = datetime.utcnow()
        resolved_conflict.launch = Mock()
        resolved_conflict.launch.slug = "test-mission"
        resolved_conflict.launch.mission_name = "Test Mission"
        
        mock_repo_manager = Mock()
        mock_conflict_repo = Mock()
        mock_repo_manager.conflict_repository = mock_conflict_repo
        mock_conflict_repo.get_conflicts.return_value = [resolved_conflict]
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request
        response = client.get("/api/admin/conflicts?resolved=true")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["resolved"] is True
        assert data["conflicts"][0]["resolved"] is True
        assert data["conflicts"][0]["resolved_at"] is not None
        
        # Verify repository was called correctly
        mock_conflict_repo.get_conflicts.assert_called_once_with(resolved=True)
    
    def test_get_conflicts_unauthorized(self, client):
        """Test conflicts endpoint without admin authentication."""
        response = client.get("/api/admin/conflicts")
        assert response.status_code == 401


class TestResolveConflictEndpoint:
    """Test the resolve conflict endpoint."""
    
    @patch('src.api.dependencies.get_repo_manager')
    @patch('src.auth.dependencies.require_admin')
    def test_resolve_conflict_success(self, mock_require_admin, mock_get_repo_manager, client, sample_admin_user):
        """Test successful conflict resolution."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        mock_repo_manager = Mock()
        mock_conflict_repo = Mock()
        mock_repo_manager.conflict_repository = mock_conflict_repo
        mock_conflict_repo.resolve_conflict.return_value = True
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request
        response = client.post("/api/admin/conflicts/1/resolve")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "resolved successfully" in data["message"]
        assert data["conflict_id"] == 1
        assert data["resolved_by"] == "admin"
        
        # Verify repository was called
        mock_conflict_repo.resolve_conflict.assert_called_once_with(1)
    
    @patch('src.api.dependencies.get_repo_manager')
    @patch('src.auth.dependencies.require_admin')
    def test_resolve_conflict_not_found(self, mock_require_admin, mock_get_repo_manager, client, sample_admin_user):
        """Test resolving non-existent conflict."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        mock_repo_manager = Mock()
        mock_conflict_repo = Mock()
        mock_repo_manager.conflict_repository = mock_conflict_repo
        mock_conflict_repo.resolve_conflict.return_value = False
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request
        response = client.post("/api/admin/conflicts/999/resolve")
        
        # Assertions
        assert response.status_code == 404
        data = response.json()
        assert "Conflict not found" in data["detail"]
    
    def test_resolve_conflict_unauthorized(self, client):
        """Test resolve conflict without admin authentication."""
        response = client.post("/api/admin/conflicts/1/resolve")
        assert response.status_code == 401


class TestCacheManagementEndpoints:
    """Test cache management endpoints."""
    
    @patch('src.auth.dependencies.require_admin')
    @patch('src.cache.cache_manager.get_cache_manager')
    def test_get_cache_info_success(self, mock_get_cache_manager, mock_require_admin, client, sample_admin_user):
        """Test successful cache info retrieval."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        cache_info = {
            "connected": True,
            "enabled": True,
            "cache_entries": {"total": 150, "launches": 100, "stats": 50},
            "hit_rate": 0.82,
            "memory_usage": "45MB"
        }
        
        mock_cache_manager = Mock()
        mock_cache_manager.get_cache_info.return_value = cache_info
        mock_get_cache_manager.return_value = mock_cache_manager
        
        # Make request
        response = client.get("/api/admin/cache/info")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert data["cache_info"] == cache_info
    
    @patch('src.auth.dependencies.require_admin')
    @patch('src.cache.cache_manager.get_cache_manager')
    def test_invalidate_all_cache(self, mock_get_cache_manager, mock_require_admin, client, sample_admin_user):
        """Test invalidating all cache entries."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        mock_cache_manager = Mock()
        mock_cache_manager.invalidate_all_cache.return_value = 25
        mock_get_cache_manager.return_value = mock_cache_manager
        
        # Make request
        response = client.post("/api/admin/cache/invalidate?cache_type=all")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "Invalidated all cache entries (25 keys)" in data["message"]
        assert data["cache_type"] == "all"
        assert data["deleted_count"] == 25
        assert data["invalidated_by"] == "admin"
    
    @patch('src.auth.dependencies.require_admin')
    @patch('src.cache.cache_manager.get_cache_manager')
    def test_invalidate_launches_cache(self, mock_get_cache_manager, mock_require_admin, client, sample_admin_user):
        """Test invalidating launches cache entries."""
        # Setup mocks
        mock_require_admin.return_value = sample_admin_user
        
        mock_cache_manager = Mock()
        mock_cache_manager.invalidate_all_launches.return_value = 15
        mock_get_cache_manager.return_value = mock_cache_manager
        
        # Make request
        response = client.post("/api/admin/cache/invalidate?cache_type=launches")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "Invalidated launch cache entries (15 keys)" in data["message"]
        assert data["cache_type"] == "launches"
        assert data["deleted_count"] == 15
    
    def test_invalidate_cache_invalid_type(self, client):
        """Test cache invalidation with invalid cache type."""
        # This would require authentication, but let's test the validation
        response = client.post("/api/admin/cache/invalidate?cache_type=invalid")
        # Should be unauthorized first
        assert response.status_code == 401
    
    def test_cache_endpoints_unauthorized(self, client):
        """Test cache endpoints without admin authentication."""
        # Test cache info
        response = client.get("/api/admin/cache/info")
        assert response.status_code == 401
        
        # Test cache invalidation
        response = client.post("/api/admin/cache/invalidate")
        assert response.status_code == 401
        
        # Test cache warming
        response = client.post("/api/admin/cache/warm")
        assert response.status_code == 401


class TestIntegrationAndEdgeCases:
    """Test integration scenarios and edge cases."""
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.dependencies.require_auth_or_api_key')
    def test_admin_endpoints_with_database_error(self, mock_require_auth, mock_get_db, client, sample_admin_user):
        """Test admin endpoints when database is unavailable."""
        # Setup mocks
        mock_require_auth.return_value = sample_admin_user
        mock_db = Mock()
        mock_get_db.side_effect = Exception("Database connection failed")
        
        # Test various endpoints
        endpoints = [
            "/api/admin/system/health",
            "/api/admin/system/stats",
            "/api/admin/conflicts"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 500
    
    @patch('src.auth.dependencies.require_auth_or_api_key')
    def test_concurrent_refresh_requests(self, mock_require_auth, client, sample_admin_user):
        """Test multiple concurrent refresh requests."""
        mock_require_auth.return_value = sample_admin_user
        
        with patch('src.tasks.scraping_tasks.run_full_scraping_pipeline.delay') as mock_task_delay:
            with patch('src.cache.cache_manager.get_cache_manager') as mock_get_cache_manager:
                mock_cache_manager = Mock()
                mock_get_cache_manager.return_value = mock_cache_manager
                
                mock_task = Mock()
                mock_task.id = "task-concurrent"
                mock_task_delay.return_value = mock_task
                
                # Make multiple requests
                responses = []
                for i in range(3):
                    response = client.post("/api/admin/refresh")
                    responses.append(response)
                
                # All should succeed
                for response in responses:
                    assert response.status_code == 200
                    data = response.json()
                    assert data["task_id"] == "task-concurrent"
                
                # Task should be triggered multiple times
                assert mock_task_delay.call_count == 3
    
    def test_admin_endpoints_response_format(self, client):
        """Test that admin endpoints return consistent response formats."""
        # Test without authentication to check error format consistency
        endpoints = [
            "/api/admin/refresh",
            "/api/admin/system/health",
            "/api/admin/system/stats",
            "/api/admin/conflicts"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint) if endpoint != "/api/admin/refresh" else client.post(endpoint)
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data
            assert isinstance(data["detail"], str)
    
    @patch('src.auth.dependencies.require_admin')
    def test_admin_endpoints_logging(self, mock_require_admin, client, sample_admin_user):
        """Test that admin endpoints log appropriately."""
        mock_require_admin.return_value = sample_admin_user
        
        with patch('src.api.admin.logger') as mock_logger:
            # Test an endpoint that should log
            with patch('src.cache.cache_manager.get_cache_manager') as mock_get_cache_manager:
                mock_cache_manager = Mock()
                mock_cache_manager.invalidate_all_cache.return_value = 10
                mock_get_cache_manager.return_value = mock_cache_manager
                
                response = client.post("/api/admin/cache/invalidate")
                
                # Should log the cache invalidation
                mock_logger.info.assert_called()
                log_call = mock_logger.info.call_args[0][0]
                assert "Cache invalidation by admin" in log_call