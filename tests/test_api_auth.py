"""
Tests for authentication API endpoints.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.auth.models import User, UserRole, APIKey, Token, UserCreate, APIKeyCreate
from src.auth.security import create_access_token, create_refresh_token, generate_api_key


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def sample_user():
    """Create a sample user object."""
    return User(
        id=1,
        username="testuser",
        email="test@example.com",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_viewer_user():
    """Create a sample viewer user object."""
    return User(
        id=2,
        username="viewer",
        email="viewer@example.com",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_api_key():
    """Create a sample API key object."""
    return APIKey(
        id=1,
        name="Test API Key",
        key_hash="hashed_key",
        is_active=True,
        created_at=datetime.utcnow(),
        expires_at=None,
        last_used_at=None
    )


@pytest.fixture
def valid_access_token(sample_user):
    """Create a valid access token."""
    token_data = {
        "sub": sample_user.username,
        "user_id": sample_user.id,
        "role": sample_user.role.value
    }
    return create_access_token(data=token_data)


@pytest.fixture
def valid_refresh_token(sample_user):
    """Create a valid refresh token."""
    token_data = {
        "sub": sample_user.username,
        "user_id": sample_user.id,
        "role": sample_user.role.value
    }
    return create_refresh_token(data=token_data)


class TestLoginEndpoint:
    """Test the login endpoint."""
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.repository.UserRepository')
    def test_login_success(self, mock_user_repo_class, mock_get_db, client, sample_user):
        """Test successful login."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        mock_user_repo = Mock()
        mock_user_repo_class.return_value = mock_user_repo
        mock_user_repo.authenticate_user.return_value = sample_user
        
        # Make request
        response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass"}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        
        # Verify repository was called correctly
        mock_user_repo.authenticate_user.assert_called_once_with("testuser", "testpass")
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.repository.UserRepository')
    def test_login_invalid_credentials(self, mock_user_repo_class, mock_get_db, client):
        """Test login with invalid credentials."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        mock_user_repo = Mock()
        mock_user_repo_class.return_value = mock_user_repo
        mock_user_repo.authenticate_user.return_value = None
        
        # Make request
        response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "wrongpass"}
        )
        
        # Assertions
        assert response.status_code == 401
        data = response.json()
        assert "Incorrect username or password" in data["detail"]
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.repository.UserRepository')
    def test_login_database_error(self, mock_user_repo_class, mock_get_db, client):
        """Test login with database error."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        mock_user_repo = Mock()
        mock_user_repo_class.return_value = mock_user_repo
        mock_user_repo.authenticate_user.side_effect = Exception("Database error")
        
        # Make request
        response = client.post(
            "/api/auth/login",
            data={"username": "testuser", "password": "testpass"}
        )
        
        # Assertions
        assert response.status_code == 500
        data = response.json()
        assert "Authentication failed" in data["detail"]
    
    def test_login_missing_credentials(self, client):
        """Test login with missing credentials."""
        # Test missing username
        response = client.post(
            "/api/auth/login",
            data={"password": "testpass"}
        )
        assert response.status_code == 422
        
        # Test missing password
        response = client.post(
            "/api/auth/login",
            data={"username": "testuser"}
        )
        assert response.status_code == 422
        
        # Test empty request
        response = client.post("/api/auth/login", data={})
        assert response.status_code == 422


class TestRefreshTokenEndpoint:
    """Test the refresh token endpoint."""
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.repository.UserRepository')
    @patch('src.auth.security.verify_token')
    def test_refresh_token_success(self, mock_verify_token, mock_user_repo_class, mock_get_db, client, sample_user, valid_refresh_token):
        """Test successful token refresh."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        mock_user_repo = Mock()
        mock_user_repo_class.return_value = mock_user_repo
        mock_user_repo.get_by_username.return_value = sample_user
        
        # Mock token verification
        from src.auth.models import TokenData, TokenType
        token_data = TokenData(
            sub=sample_user.username,
            user_id=sample_user.id,
            role=sample_user.role,
            token_type=TokenType.REFRESH,
            exp=int((datetime.utcnow() + timedelta(days=7)).timestamp()),
            iat=int(datetime.utcnow().timestamp())
        )
        mock_verify_token.return_value = token_data
        
        # Make request
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": valid_refresh_token}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        
        # Verify token verification was called
        mock_verify_token.assert_called_once()
        mock_user_repo.get_by_username.assert_called_once_with(sample_user.username)
    
    @patch('src.auth.security.verify_token')
    def test_refresh_token_invalid_token(self, mock_verify_token, client):
        """Test refresh with invalid token."""
        # Setup mock to return None (invalid token)
        mock_verify_token.return_value = None
        
        # Make request
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid_token"}
        )
        
        # Assertions
        assert response.status_code == 401
        data = response.json()
        assert "Invalid refresh token" in data["detail"]
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.repository.UserRepository')
    @patch('src.auth.security.verify_token')
    def test_refresh_token_user_not_found(self, mock_verify_token, mock_user_repo_class, mock_get_db, client, sample_user):
        """Test refresh when user no longer exists."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        mock_user_repo = Mock()
        mock_user_repo_class.return_value = mock_user_repo
        mock_user_repo.get_by_username.return_value = None  # User not found
        
        # Mock token verification
        from src.auth.models import TokenData, TokenType
        token_data = TokenData(
            sub=sample_user.username,
            user_id=sample_user.id,
            role=sample_user.role,
            token_type=TokenType.REFRESH,
            exp=int((datetime.utcnow() + timedelta(days=7)).timestamp()),
            iat=int(datetime.utcnow().timestamp())
        )
        mock_verify_token.return_value = token_data
        
        # Make request
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "valid_token"}
        )
        
        # Assertions
        assert response.status_code == 401
        data = response.json()
        assert "User not found or inactive" in data["detail"]


class TestRegisterEndpoint:
    """Test the register endpoint."""
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.repository.UserRepository')
    @patch('src.auth.dependencies.require_admin')
    def test_register_success(self, mock_require_admin, mock_user_repo_class, mock_get_db, client, sample_user):
        """Test successful user registration."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_require_admin.return_value = sample_user
        
        mock_user_repo = Mock()
        mock_user_repo_class.return_value = mock_user_repo
        
        new_user = User(
            id=2,
            username="newuser",
            email="new@example.com",
            role=UserRole.VIEWER,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        mock_user_repo.create_user.return_value = new_user
        
        # Make request
        user_data = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "newpassword",
            "role": "viewer"
        }
        response = client.post("/api/auth/register", json=user_data)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "new@example.com"
        assert data["role"] == "viewer"
        
        # Verify repository was called
        mock_user_repo.create_user.assert_called_once()
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.repository.UserRepository')
    @patch('src.auth.dependencies.require_admin')
    def test_register_username_exists(self, mock_require_admin, mock_user_repo_class, mock_get_db, client, sample_user):
        """Test registration with existing username."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_require_admin.return_value = sample_user
        
        mock_user_repo = Mock()
        mock_user_repo_class.return_value = mock_user_repo
        mock_user_repo.create_user.return_value = None  # Username exists
        
        # Make request
        user_data = {
            "username": "existinguser",
            "email": "existing@example.com",
            "password": "password",
            "role": "viewer"
        }
        response = client.post("/api/auth/register", json=user_data)
        
        # Assertions
        assert response.status_code == 400
        data = response.json()
        assert "Username already exists" in data["detail"]
    
    def test_register_unauthorized(self, client):
        """Test registration without admin authentication."""
        user_data = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "password",
            "role": "viewer"
        }
        response = client.post("/api/auth/register", json=user_data)
        
        # Should be unauthorized
        assert response.status_code == 401
    
    def test_register_invalid_data(self, client):
        """Test registration with invalid data."""
        # Test missing required fields
        response = client.post("/api/auth/register", json={})
        assert response.status_code == 422
        
        # Test invalid email format
        user_data = {
            "username": "newuser",
            "email": "invalid-email",
            "password": "password",
            "role": "viewer"
        }
        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 422
        
        # Test short password
        user_data = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "short",
            "role": "viewer"
        }
        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 422


class TestGetCurrentUserEndpoint:
    """Test the get current user endpoint."""
    
    @patch('src.auth.dependencies.require_auth')
    def test_get_current_user_success(self, mock_require_auth, client, sample_user):
        """Test successful retrieval of current user."""
        # Setup mock
        mock_require_auth.return_value = sample_user
        
        # Make request
        response = client.get("/api/auth/me")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == sample_user.username
        assert data["email"] == sample_user.email
        assert data["role"] == sample_user.role.value
    
    def test_get_current_user_unauthorized(self, client):
        """Test get current user without authentication."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401


class TestListUsersEndpoint:
    """Test the list users endpoint."""
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.repository.UserRepository')
    @patch('src.auth.dependencies.require_admin')
    def test_list_users_success(self, mock_require_admin, mock_user_repo_class, mock_get_db, client, sample_user):
        """Test successful listing of users."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_require_admin.return_value = sample_user
        
        mock_user_repo = Mock()
        mock_user_repo_class.return_value = mock_user_repo
        
        users = [sample_user, User(
            id=2,
            username="user2",
            email="user2@example.com",
            role=UserRole.VIEWER,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )]
        mock_user_repo.get_all_users.return_value = users
        
        # Make request
        response = client.get("/api/auth/users")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["username"] == "testuser"
        assert data[1]["username"] == "user2"
    
    def test_list_users_unauthorized(self, client):
        """Test list users without admin authentication."""
        response = client.get("/api/auth/users")
        assert response.status_code == 401


class TestAPIKeyEndpoints:
    """Test API key management endpoints."""
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.repository.APIKeyRepository')
    @patch('src.auth.dependencies.require_admin')
    @patch('src.auth.security.generate_api_key')
    def test_create_api_key_success(self, mock_generate_api_key, mock_require_admin, mock_api_key_repo_class, mock_get_db, client, sample_user, sample_api_key):
        """Test successful API key creation."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_require_admin.return_value = sample_user
        mock_generate_api_key.return_value = "generated_api_key"
        
        mock_api_key_repo = Mock()
        mock_api_key_repo_class.return_value = mock_api_key_repo
        mock_api_key_repo.create_api_key.return_value = sample_api_key
        
        # Make request
        api_key_data = {
            "name": "Test API Key",
            "expires_days": 30
        }
        response = client.post("/api/auth/api-keys", json=api_key_data)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test API Key"
        assert data["key"] == "generated_api_key"  # Plain key returned only on creation
        assert data["is_active"] is True
        
        # Verify repository was called
        mock_api_key_repo.create_api_key.assert_called_once()
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.repository.APIKeyRepository')
    @patch('src.auth.dependencies.require_admin')
    def test_list_api_keys_success(self, mock_require_admin, mock_api_key_repo_class, mock_get_db, client, sample_user, sample_api_key):
        """Test successful API key listing."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_require_admin.return_value = sample_user
        
        mock_api_key_repo = Mock()
        mock_api_key_repo_class.return_value = mock_api_key_repo
        mock_api_key_repo.get_all_api_keys.return_value = [sample_api_key]
        
        # Make request
        response = client.get("/api/auth/api-keys")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test API Key"
        assert "key" not in data[0]  # Plain key not returned in list
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.repository.APIKeyRepository')
    @patch('src.auth.dependencies.require_admin')
    def test_deactivate_api_key_success(self, mock_require_admin, mock_api_key_repo_class, mock_get_db, client, sample_user):
        """Test successful API key deactivation."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_require_admin.return_value = sample_user
        
        mock_api_key_repo = Mock()
        mock_api_key_repo_class.return_value = mock_api_key_repo
        mock_api_key_repo.deactivate_api_key.return_value = True
        
        # Make request
        response = client.delete("/api/auth/api-keys/1")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "deactivated successfully" in data["message"]
        
        # Verify repository was called
        mock_api_key_repo.deactivate_api_key.assert_called_once_with(1)
    
    @patch('src.api.dependencies.get_db')
    @patch('src.auth.repository.APIKeyRepository')
    @patch('src.auth.dependencies.require_admin')
    def test_deactivate_api_key_not_found(self, mock_require_admin, mock_api_key_repo_class, mock_get_db, client, sample_user):
        """Test API key deactivation when key not found."""
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_require_admin.return_value = sample_user
        
        mock_api_key_repo = Mock()
        mock_api_key_repo_class.return_value = mock_api_key_repo
        mock_api_key_repo.deactivate_api_key.return_value = False
        
        # Make request
        response = client.delete("/api/auth/api-keys/999")
        
        # Assertions
        assert response.status_code == 404
        data = response.json()
        assert "API key not found" in data["detail"]
    
    def test_api_key_endpoints_unauthorized(self, client):
        """Test API key endpoints without admin authentication."""
        # Test create
        response = client.post("/api/auth/api-keys", json={"name": "Test"})
        assert response.status_code == 401
        
        # Test list
        response = client.get("/api/auth/api-keys")
        assert response.status_code == 401
        
        # Test deactivate
        response = client.delete("/api/auth/api-keys/1")
        assert response.status_code == 401


class TestSecurityAndEdgeCases:
    """Test security scenarios and edge cases."""
    
    def test_malformed_jwt_token(self, client):
        """Test endpoints with malformed JWT tokens."""
        headers = {"Authorization": "Bearer malformed.jwt.token"}
        
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401
    
    def test_expired_jwt_token(self, client):
        """Test endpoints with expired JWT tokens."""
        # Create an expired token
        token_data = {
            "sub": "testuser",
            "user_id": 1,
            "role": "admin",
            "exp": int((datetime.utcnow() - timedelta(hours=1)).timestamp())  # Expired
        }
        from jose import jwt
        from src.auth.security import SECRET_KEY, ALGORITHM
        expired_token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401
    
    def test_role_based_access_control(self, client):
        """Test role-based access control."""
        # Create a viewer token
        token_data = {
            "sub": "viewer",
            "user_id": 2,
            "role": "viewer"
        }
        viewer_token = create_access_token(data=token_data)
        headers = {"Authorization": f"Bearer {viewer_token}"}
        
        # Viewer should not be able to access admin endpoints
        response = client.post("/api/auth/register", headers=headers, json={
            "username": "newuser",
            "password": "password",
            "role": "viewer"
        })
        assert response.status_code == 403
    
    @patch('src.api.dependencies.get_db')
    def test_sql_injection_protection(self, mock_get_db, client):
        """Test SQL injection protection in login."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        # Attempt SQL injection in username
        response = client.post(
            "/api/auth/login",
            data={
                "username": "admin'; DROP TABLE users; --",
                "password": "password"
            }
        )
        
        # Should handle gracefully (either 401 or 500, but not crash)
        assert response.status_code in [401, 500]
    
    def test_password_complexity_validation(self, client):
        """Test password complexity validation."""
        # This would be handled by Pydantic validation
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "123",  # Too short
            "role": "viewer"
        }
        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 422
    
    def test_rate_limiting_simulation(self, client):
        """Test multiple rapid requests (simulating rate limiting)."""
        # Make multiple login attempts
        for _ in range(5):
            response = client.post(
                "/api/auth/login",
                data={"username": "testuser", "password": "wrongpass"}
            )
            # Each should fail with 401
            assert response.status_code == 401
    
    @patch('src.auth.dependencies.get_current_user')
    def test_token_reuse_protection(self, mock_get_current_user, client, sample_user):
        """Test that tokens work correctly for authenticated requests."""
        # Setup mock
        mock_get_current_user.return_value = sample_user
        
        # Make authenticated request
        token = create_access_token(data={
            "sub": sample_user.username,
            "user_id": sample_user.id,
            "role": sample_user.role.value
        })
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 200