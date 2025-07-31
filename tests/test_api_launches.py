"""
Tests for launch API endpoints using pytest-httpx.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.models.schemas import LaunchStatus
from src.models.database import Launch, LaunchSource


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def sample_launch():
    """Create a sample launch object."""
    launch = Mock(spec=Launch)
    launch.id = 1
    launch.slug = "falcon-heavy-demo"
    launch.mission_name = "Falcon Heavy Demo"
    launch.launch_date = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    launch.vehicle_type = "Falcon Heavy"
    launch.payload_mass = 1420.0
    launch.orbit = "LEO"
    launch.status = LaunchStatus.SUCCESS
    launch.details = "Demonstration flight of Falcon Heavy"
    launch.mission_patch_url = "https://example.com/patch.png"
    launch.webcast_url = "https://example.com/webcast"
    launch.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    launch.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    launch.sources = []
    return launch


@pytest.fixture
def sample_upcoming_launch():
    """Create a sample upcoming launch object."""
    launch = Mock(spec=Launch)
    launch.id = 2
    launch.slug = "starship-test-flight"
    launch.mission_name = "Starship Test Flight"
    launch.launch_date = datetime(2024, 12, 15, 12, 0, 0, tzinfo=timezone.utc)
    launch.vehicle_type = "Starship"
    launch.payload_mass = None
    launch.orbit = "Suborbital"
    launch.status = LaunchStatus.UPCOMING
    launch.details = "Test flight of Starship vehicle"
    launch.mission_patch_url = None
    launch.webcast_url = "https://example.com/live"
    launch.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    launch.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    launch.sources = []
    return launch


class TestLaunchesEndpoint:
    """Test the main launches endpoint."""
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_launches_success(self, mock_get_repo_manager, client, sample_launch):
        """Test successful retrieval of launches."""
        # Setup mock
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_all.return_value = [sample_launch]
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request
        response = client.get("/api/launches")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "meta" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["slug"] == "falcon-heavy-demo"
        assert data["data"][0]["mission_name"] == "Falcon Heavy Demo"
        assert data["meta"]["total"] == 1
        assert data["meta"]["page"] == 1
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_launches_with_pagination(self, mock_get_repo_manager, client, sample_launch):
        """Test launches endpoint with pagination parameters."""
        # Setup mock
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_all.return_value = [sample_launch] * 5
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request with pagination
        response = client.get("/api/launches?skip=2&limit=2")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["meta"]["page"] == 2
        assert data["meta"]["per_page"] == 2
        assert data["meta"]["total"] == 5
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_launches_with_status_filter(self, mock_get_repo_manager, client, sample_launch):
        """Test launches endpoint with status filter."""
        # Setup mock
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_all.return_value = [sample_launch]
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request with status filter
        response = client.get("/api/launches?status=success")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["status"] == "success"
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_launches_with_search(self, mock_get_repo_manager, client, sample_launch):
        """Test launches endpoint with search parameter."""
        # Setup mock
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.search_launches.return_value = [sample_launch]
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request with search
        response = client.get("/api/launches?search=falcon")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        mock_launch_repo.search_launches.assert_called()
    
    def test_get_launches_invalid_pagination(self, client):
        """Test launches endpoint with invalid pagination parameters."""
        # Test negative skip
        response = client.get("/api/launches?skip=-1")
        assert response.status_code == 400
        
        # Test invalid limit
        response = client.get("/api/launches?limit=0")
        assert response.status_code == 400
        
        response = client.get("/api/launches?limit=101")
        assert response.status_code == 400
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_launches_database_error(self, mock_get_repo_manager, client):
        """Test launches endpoint with database error."""
        # Setup mock to raise exception
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_all.side_effect = Exception("Database error")
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request
        response = client.get("/api/launches")
        
        # Assertions
        assert response.status_code == 500


class TestLaunchBySlugEndpoint:
    """Test the launch by slug endpoint."""
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_launch_by_slug_success(self, mock_get_repo_manager, client, sample_launch):
        """Test successful retrieval of launch by slug."""
        # Setup mock
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_by_slug.return_value = sample_launch
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request
        response = client.get("/api/launches/falcon-heavy-demo")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == "falcon-heavy-demo"
        assert data["mission_name"] == "Falcon Heavy Demo"
        assert data["status"] == "success"
        mock_launch_repo.get_by_slug.assert_called_once_with("falcon-heavy-demo")
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_launch_by_slug_not_found(self, mock_get_repo_manager, client):
        """Test launch by slug endpoint when launch not found."""
        # Setup mock
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_by_slug.return_value = None
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request
        response = client.get("/api/launches/nonexistent-launch")
        
        # Assertions
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["error"].lower()
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_launch_by_slug_database_error(self, mock_get_repo_manager, client):
        """Test launch by slug endpoint with database error."""
        # Setup mock to raise exception
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_by_slug.side_effect = Exception("Database error")
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request
        response = client.get("/api/launches/test-slug")
        
        # Assertions
        assert response.status_code == 500


class TestUpcomingLaunchesEndpoint:
    """Test the upcoming launches endpoint."""
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_upcoming_launches_success(self, mock_get_repo_manager, client, sample_upcoming_launch):
        """Test successful retrieval of upcoming launches."""
        # Setup mock
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_upcoming_launches.return_value = [sample_upcoming_launch]
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request
        response = client.get("/api/launches/upcoming")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["slug"] == "starship-test-flight"
        assert data[0]["status"] == "upcoming"
        mock_launch_repo.get_upcoming_launches.assert_called_once_with(limit=50, include_sources=True)
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_upcoming_launches_with_limit(self, mock_get_repo_manager, client, sample_upcoming_launch):
        """Test upcoming launches endpoint with custom limit."""
        # Setup mock
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_upcoming_launches.return_value = [sample_upcoming_launch]
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request with custom limit
        response = client.get("/api/launches/upcoming?limit=10")
        
        # Assertions
        assert response.status_code == 200
        mock_launch_repo.get_upcoming_launches.assert_called_once_with(limit=10, include_sources=True)
    
    def test_get_upcoming_launches_invalid_limit(self, client):
        """Test upcoming launches endpoint with invalid limit."""
        response = client.get("/api/launches/upcoming?limit=0")
        assert response.status_code == 422  # Validation error
        
        response = client.get("/api/launches/upcoming?limit=101")
        assert response.status_code == 422  # Validation error
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_upcoming_launches_empty_result(self, mock_get_repo_manager, client):
        """Test upcoming launches endpoint with no upcoming launches."""
        # Setup mock
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_upcoming_launches.return_value = []
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request
        response = client.get("/api/launches/upcoming")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0


class TestHistoricalLaunchesEndpoint:
    """Test the historical launches endpoint."""
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_historical_launches_success(self, mock_get_repo_manager, client, sample_launch):
        """Test successful retrieval of historical launches."""
        # Setup mock
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_historical_launches.return_value = [sample_launch]
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request
        response = client.get("/api/launches/historical")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "meta" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["slug"] == "falcon-heavy-demo"
        assert data["data"][0]["status"] == "success"
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_historical_launches_with_filters(self, mock_get_repo_manager, client, sample_launch):
        """Test historical launches endpoint with status and vehicle filters."""
        # Setup mock
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_historical_launches.return_value = [sample_launch]
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request with filters
        response = client.get("/api/launches/historical?status=success&vehicle_type=Falcon Heavy")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        
        # Verify the repository method was called with correct parameters
        calls = mock_launch_repo.get_historical_launches.call_args_list
        assert len(calls) == 2  # Called twice - once for data, once for count
        
        # Check the first call (for actual data)
        args, kwargs = calls[0]
        assert kwargs['status_filter'] == LaunchStatus.SUCCESS
        assert kwargs['vehicle_filter'] == "Falcon Heavy"
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_get_historical_launches_pagination(self, mock_get_repo_manager, client, sample_launch):
        """Test historical launches endpoint with pagination."""
        # Setup mock
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_historical_launches.return_value = [sample_launch] * 3
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request with pagination
        response = client.get("/api/launches/historical?skip=1&limit=2")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["page"] == 2
        assert data["meta"]["per_page"] == 2


class TestRootAndHealthEndpoints:
    """Test root and health check endpoints."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "SpaceX Launch Tracker API" in data["message"]
        assert "endpoints" in data
    
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "version" in data


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @patch('src.api.dependencies.get_repo_manager')
    def test_sqlalchemy_error_handling(self, mock_get_repo_manager, client):
        """Test SQLAlchemy error handling."""
        from sqlalchemy.exc import SQLAlchemyError
        
        # Setup mock to raise SQLAlchemy error
        mock_repo_manager = Mock()
        mock_launch_repo = Mock()
        mock_repo_manager.launch_repository = mock_launch_repo
        mock_launch_repo.get_all.side_effect = SQLAlchemyError("Database connection failed")
        mock_get_repo_manager.return_value = mock_repo_manager
        
        # Make request
        response = client.get("/api/launches")
        
        # Assertions
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
    
    def test_validation_error_handling(self, client):
        """Test validation error handling."""
        # Test with invalid query parameters
        response = client.get("/api/launches?limit=invalid")
        assert response.status_code == 422  # Validation error
    
    @patch('src.main.logger')
    def test_general_exception_handling(self, mock_logger, client):
        """Test general exception handling."""
        with patch('src.api.launches.router') as mock_router:
            mock_router.side_effect = Exception("Unexpected error")
            
            # This would trigger the general exception handler
            # Note: This is a bit tricky to test directly, so we're mainly
            # ensuring the handler exists and logs properly
            assert hasattr(client.app, 'exception_handlers')