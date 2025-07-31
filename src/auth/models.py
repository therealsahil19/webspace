"""
Authentication data models and schemas.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class UserRole(str, Enum):
    """User roles for role-based access control."""
    ADMIN = "admin"
    VIEWER = "viewer"


class TokenType(str, Enum):
    """Token types."""
    ACCESS = "access"
    REFRESH = "refresh"


class User(BaseModel):
    """User model."""
    id: int
    username: str
    email: Optional[str] = None
    role: UserRole
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    """User creation schema."""
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.VIEWER


class UserLogin(BaseModel):
    """User login schema."""
    username: str
    password: str


class Token(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Token payload data."""
    sub: str  # subject (username)
    user_id: int
    role: UserRole
    token_type: TokenType
    exp: int  # expiration timestamp
    iat: int  # issued at timestamp


class APIKey(BaseModel):
    """API Key model."""
    id: int
    name: str
    key_hash: str
    is_active: bool = True
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


class APIKeyCreate(BaseModel):
    """API Key creation schema."""
    name: str = Field(..., min_length=1, max_length=100)
    expires_days: Optional[int] = Field(None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """API Key response (includes plain key only on creation)."""
    id: int
    name: str
    key: Optional[str] = None  # Only returned on creation
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None