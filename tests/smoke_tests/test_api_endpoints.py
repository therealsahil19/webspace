"""
Smoke tests for API endpoints after deployment.
These tests verify that the core functionality is working in production.
"""

import os
import requests
import pytest
from datetime import datetime


class TestAPISmoke:
    """Smoke tests for API endpoints."""
    
    @pytest.fixture
    def base_url(self):
        """Get base URL from environment or use default."""
        return os.getenv('API_BASE_URL', 'http://localhost:8000')
    
    def test_health_endpoint(self, base_url):
        """Test that health endpoint is responding."""
        response = requests.get(f"{base_url}/health", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
        assert 'version' in data
    
    def test_database_health(self, base_url):
        """Test database connectivity."""
        response = requests.get(f"{base_url}/health/database", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'connection' in data
    
    def test_redis_health(self, base_url):
        """Test Redis connectivity."""
        response = requests.get(f"{base_url}/health/redis", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data['status'] == 'healthy'
    
    def test_celery_health(self, base_url):
        """Test Celery worker connectivity."""
        response = requests.get(f"{base_url}/health/celery", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data['status'] == 'healthy'
    
    def test_launches_endpoint(self, base_url):
        """Test launches endpoint returns data."""
        response = requests.get(f"{base_url}/api/launches?limit=5", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert 'launches' in data
        assert 'total' in data
        assert 'page' in data
        assert isinstance(data['launches'], list)
    
    def test_upcoming_launches(self, base_url):
        """Test upcoming launches endpoint."""
        response = requests.get(f"{base_url}/api/launches/upcoming", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # Verify upcoming launches have future dates
        for launch in data:
            if launch.get('launch_date'):
                launch_date = datetime.fromisoformat(launch['launch_date'].replace('Z', '+00:00'))
                # Allow some flexibility for timezone differences
                assert launch_date >= datetime.now().replace(tzinfo=launch_date.tzinfo) or \
                       (datetime.now() - launch_date.replace(tzinfo=None)).days < 1
    
    def test_historical_launches(self, base_url):
        """Test historical launches endpoint."""
        response = requests.get(f"{base_url}/api/launches/historical?limit=5", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_api_documentation(self, base_url):
        """Test that API documentation is accessible."""
        response = requests.get(f"{base_url}/docs", timeout=10)
        assert response.status_code == 200
        assert 'text/html' in response.headers.get('content-type', '')
    
    def test_openapi_spec(self, base_url):
        """Test that OpenAPI specification is accessible."""
        response = requests.get(f"{base_url}/openapi.json", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert 'openapi' in data
        assert 'info' in data
        assert 'paths' in data


class TestAuthenticationSmoke:
    """Smoke tests for authentication endpoints."""
    
    @pytest.fixture
    def base_url(self):
        """Get base URL from environment or use default."""
        return os.getenv('API_BASE_URL', 'http://localhost:8000')
    
    @pytest.fixture
    def admin_credentials(self):
        """Get admin credentials from environment."""
        return {
            'username': os.getenv('ADMIN_USERNAME', 'admin'),
            'password': os.getenv('ADMIN_PASSWORD', 'admin_password')
        }
    
    def test_admin_login(self, base_url, admin_credentials):
        """Test admin login functionality."""
        response = requests.post(
            f"{base_url}/api/auth/login",
            json=admin_credentials,
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert 'access_token' in data
        assert 'token_type' in data
        assert data['token_type'] == 'bearer'
    
    def test_admin_endpoints_require_auth(self, base_url):
        """Test that admin endpoints require authentication."""
        # Test without authentication
        response = requests.post(f"{base_url}/api/admin/refresh", timeout=10)
        assert response.status_code == 401
        
        response = requests.get(f"{base_url}/api/admin/health", timeout=10)
        assert response.status_code == 401


class TestDataIntegritySmoke:
    """Smoke tests for data integrity."""
    
    @pytest.fixture
    def base_url(self):
        """Get base URL from environment or use default."""
        return os.getenv('API_BASE_URL', 'http://localhost:8000')
    
    def test_launch_data_structure(self, base_url):
        """Test that launch data has expected structure."""
        response = requests.get(f"{base_url}/api/launches?limit=1", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        if data['launches']:
            launch = data['launches'][0]
            
            # Required fields
            assert 'slug' in launch
            assert 'mission_name' in launch
            assert 'status' in launch
            
            # Optional fields should be properly typed
            if 'launch_date' in launch and launch['launch_date']:
                # Should be valid ISO format
                datetime.fromisoformat(launch['launch_date'].replace('Z', '+00:00'))
            
            if 'payload_mass' in launch and launch['payload_mass']:
                assert isinstance(launch['payload_mass'], (int, float))
    
    def test_no_duplicate_slugs(self, base_url):
        """Test that there are no duplicate launch slugs."""
        response = requests.get(f"{base_url}/api/launches?limit=100", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        slugs = [launch['slug'] for launch in data['launches']]
        
        # Check for duplicates
        assert len(slugs) == len(set(slugs)), "Found duplicate launch slugs"
    
    def test_status_values_valid(self, base_url):
        """Test that all launch status values are valid."""
        response = requests.get(f"{base_url}/api/launches?limit=100", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        valid_statuses = {'upcoming', 'success', 'failure', 'in_flight', 'aborted'}
        
        for launch in data['launches']:
            assert launch['status'] in valid_statuses, \
                f"Invalid status '{launch['status']}' for launch {launch['slug']}"


if __name__ == "__main__":
    # Allow running smoke tests directly
    pytest.main([__file__, "-v"])