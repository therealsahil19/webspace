"""
Authentication endpoints for the FastAPI application.
"""
from typing import List
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.auth.models import (
    User, UserCreate, UserLogin, Token, APIKeyCreate, APIKeyResponse, UserRole
)
from src.auth.repository import UserRepository, APIKeyRepository
from src.auth.security import (
    create_access_token, create_refresh_token, verify_token, generate_api_key,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, TokenType
)
from src.auth.dependencies import require_admin, require_auth

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post(
    "/login",
    response_model=Token,
    summary="User login",
    description="Authenticate user and return JWT tokens."
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Authenticate user and return JWT tokens."""
    try:
        user_repo = UserRepository(db)
        user = user_repo.authenticate_user(form_data.username, form_data.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create tokens
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        token_data = {
            "sub": user.username,
            "user_id": user.id,
            "role": user.role.value
        }
        
        access_token = create_access_token(
            data=token_data,
            expires_delta=access_token_expires
        )
        
        refresh_token = create_refresh_token(
            data=token_data,
            expires_delta=refresh_token_expires
        )
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh token",
    description="Refresh access token using refresh token."
)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token."""
    try:
        # Verify refresh token
        token_data = verify_token(refresh_token, TokenType.REFRESH)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify user still exists and is active
        user_repo = UserRepository(db)
        user = user_repo.get_by_username(token_data.sub)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create new access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        new_token_data = {
            "sub": user.username,
            "user_id": user.id,
            "role": user.role.value
        }
        
        access_token = create_access_token(
            data=new_token_data,
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post(
    "/register",
    response_model=User,
    summary="Register new user",
    description="Register a new user account (admin only)."
)
async def register_user(
    user_data: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Register a new user (admin only)."""
    try:
        user_repo = UserRepository(db)
        user = user_repo.create_user(user_data)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User registration failed"
        )


@router.get(
    "/me",
    response_model=User,
    summary="Get current user",
    description="Get current authenticated user information."
)
async def get_current_user_info(
    current_user: User = Depends(require_auth)
):
    """Get current user information."""
    return current_user


@router.get(
    "/users",
    response_model=List[User],
    summary="List all users",
    description="Get list of all users (admin only)."
)
async def list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all users (admin only)."""
    try:
        user_repo = UserRepository(db)
        users = user_repo.get_all_users()
        return users
        
    except Exception as e:
        logger.error(f"List users error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )


@router.post(
    "/api-keys",
    response_model=APIKeyResponse,
    summary="Create API key",
    description="Create a new API key (admin only)."
)
async def create_api_key(
    api_key_data: APIKeyCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new API key (admin only)."""
    try:
        # Generate API key
        plain_key = generate_api_key()
        
        # Store in database
        api_key_repo = APIKeyRepository(db)
        api_key = api_key_repo.create_api_key(
            api_key_data=api_key_data,
            plain_key=plain_key,
            user_id=current_user.id
        )
        
        # Return response with plain key (only time it's shown)
        return APIKeyResponse(
            id=api_key.id,
            name=api_key.name,
            key=plain_key,  # Only returned on creation
            is_active=api_key.is_active,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at
        )
        
    except Exception as e:
        logger.error(f"API key creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key creation failed"
        )


@router.get(
    "/api-keys",
    response_model=List[APIKeyResponse],
    summary="List API keys",
    description="Get list of all API keys (admin only)."
)
async def list_api_keys(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all API keys (admin only)."""
    try:
        api_key_repo = APIKeyRepository(db)
        api_keys = api_key_repo.get_all_api_keys()
        
        # Convert to response models (without plain key)
        return [
            APIKeyResponse(
                id=api_key.id,
                name=api_key.name,
                is_active=api_key.is_active,
                created_at=api_key.created_at,
                expires_at=api_key.expires_at,
                last_used_at=api_key.last_used_at
            )
            for api_key in api_keys
        ]
        
    except Exception as e:
        logger.error(f"List API keys error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API keys"
        )


@router.delete(
    "/api-keys/{api_key_id}",
    summary="Deactivate API key",
    description="Deactivate an API key (admin only)."
)
async def deactivate_api_key(
    api_key_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Deactivate an API key (admin only)."""
    try:
        api_key_repo = APIKeyRepository(db)
        success = api_key_repo.deactivate_api_key(api_key_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        return {"message": "API key deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API key deactivation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key deactivation failed"
        )