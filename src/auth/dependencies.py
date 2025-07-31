"""
Authentication dependencies for FastAPI.
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from src.auth.models import User, UserRole, TokenData
from src.auth.security import verify_token, verify_api_key, check_role_permission
from src.auth.repository import UserRepository, APIKeyRepository
from src.api.dependencies import get_db


# Security scheme for JWT tokens
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current authenticated user from JWT token."""
    if not credentials:
        return None
    
    token_data = verify_token(credentials.credentials)
    if not token_data:
        return None
    
    user_repo = UserRepository(db)
    user = user_repo.get_by_username(token_data.sub)
    
    if not user or not user.is_active:
        return None
    
    return user


async def require_auth(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """Require authentication - raise exception if not authenticated."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def require_admin(
    current_user: User = Depends(require_auth)
) -> User:
    """Require admin role - raise exception if not admin."""
    if not check_role_permission(current_user.role, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def get_api_key_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get user from API key authentication."""
    if not credentials:
        return None
    
    # Check if it's an API key (different format than JWT)
    api_key = credentials.credentials
    if not api_key or len(api_key) < 20:  # API keys should be longer
        return None
    
    api_key_repo = APIKeyRepository(db)
    api_key_record = api_key_repo.get_by_key(api_key)
    
    if not api_key_record or not api_key_record.is_active:
        return None
    
    # Update last used timestamp
    api_key_repo.update_last_used(api_key_record.id)
    
    # For API keys, we'll create a virtual admin user
    # In a real implementation, you might want to link API keys to actual users
    from src.auth.models import User
    from datetime import datetime
    
    return User(
        id=0,  # Special ID for API key users
        username="api_key_user",
        role=UserRole.ADMIN,  # API keys have admin access
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


async def get_current_user_or_api_key(
    jwt_user: Optional[User] = Depends(get_current_user),
    api_key_user: Optional[User] = Depends(get_api_key_user)
) -> Optional[User]:
    """Get current user from either JWT token or API key."""
    return jwt_user or api_key_user


async def require_auth_or_api_key(
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
) -> User:
    """Require authentication via JWT or API key."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (JWT token or API key)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user