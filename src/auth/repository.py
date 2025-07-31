"""
Repository classes for authentication-related database operations.
"""
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models.database import User as UserModel, APIKey as APIKeyModel
from src.auth.models import User, UserCreate, APIKey, APIKeyCreate, UserRole
from src.auth.security import get_password_hash, verify_password, hash_api_key, verify_api_key


class UserRepository:
    """Repository for user database operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_user(self, user_data: UserCreate) -> Optional[User]:
        """Create a new user."""
        try:
            # Hash the password
            password_hash = get_password_hash(user_data.password)
            
            # Create database model
            db_user = UserModel(
                username=user_data.username,
                email=user_data.email,
                password_hash=password_hash,
                role=user_data.role.value,
                is_active=True
            )
            
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            
            # Convert to Pydantic model
            return User(
                id=db_user.id,
                username=db_user.username,
                email=db_user.email,
                role=UserRole(db_user.role),
                is_active=db_user.is_active,
                created_at=db_user.created_at,
                updated_at=db_user.updated_at
            )
        except IntegrityError:
            self.db.rollback()
            return None
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        db_user = self.db.query(UserModel).filter(
            UserModel.username == username,
            UserModel.is_active == True
        ).first()
        
        if not db_user:
            return None
        
        return User(
            id=db_user.id,
            username=db_user.username,
            email=db_user.email,
            role=UserRole(db_user.role),
            is_active=db_user.is_active,
            created_at=db_user.created_at,
            updated_at=db_user.updated_at
        )
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        db_user = self.db.query(UserModel).filter(
            UserModel.id == user_id,
            UserModel.is_active == True
        ).first()
        
        if not db_user:
            return None
        
        return User(
            id=db_user.id,
            username=db_user.username,
            email=db_user.email,
            role=UserRole(db_user.role),
            is_active=db_user.is_active,
            created_at=db_user.created_at,
            updated_at=db_user.updated_at
        )
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password."""
        db_user = self.db.query(UserModel).filter(
            UserModel.username == username,
            UserModel.is_active == True
        ).first()
        
        if not db_user or not verify_password(password, db_user.password_hash):
            return None
        
        # Update last login timestamp
        db_user.last_login_at = datetime.utcnow()
        self.db.commit()
        
        return User(
            id=db_user.id,
            username=db_user.username,
            email=db_user.email,
            role=UserRole(db_user.role),
            is_active=db_user.is_active,
            created_at=db_user.created_at,
            updated_at=db_user.updated_at
        )
    
    def get_all_users(self) -> List[User]:
        """Get all active users."""
        db_users = self.db.query(UserModel).filter(
            UserModel.is_active == True
        ).all()
        
        return [
            User(
                id=db_user.id,
                username=db_user.username,
                email=db_user.email,
                role=UserRole(db_user.role),
                is_active=db_user.is_active,
                created_at=db_user.created_at,
                updated_at=db_user.updated_at
            )
            for db_user in db_users
        ]
    
    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user."""
        db_user = self.db.query(UserModel).filter(UserModel.id == user_id).first()
        if not db_user:
            return False
        
        db_user.is_active = False
        db_user.updated_at = datetime.utcnow()
        self.db.commit()
        return True


class APIKeyRepository:
    """Repository for API key database operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_api_key(self, api_key_data: APIKeyCreate, plain_key: str, user_id: Optional[int] = None) -> APIKey:
        """Create a new API key."""
        # Calculate expiration date
        expires_at = None
        if api_key_data.expires_days:
            expires_at = datetime.utcnow() + timedelta(days=api_key_data.expires_days)
        
        # Hash the API key
        key_hash = hash_api_key(plain_key)
        
        # Create database model
        db_api_key = APIKeyModel(
            user_id=user_id,
            name=api_key_data.name,
            key_hash=key_hash,
            is_active=True,
            expires_at=expires_at
        )
        
        self.db.add(db_api_key)
        self.db.commit()
        self.db.refresh(db_api_key)
        
        # Convert to Pydantic model
        return APIKey(
            id=db_api_key.id,
            name=db_api_key.name,
            key_hash=db_api_key.key_hash,
            is_active=db_api_key.is_active,
            created_at=db_api_key.created_at,
            expires_at=db_api_key.expires_at,
            last_used_at=db_api_key.last_used_at
        )
    
    def get_by_key(self, plain_key: str) -> Optional[APIKey]:
        """Get API key by plain key value."""
        # Get all active, non-expired API keys
        now = datetime.utcnow()
        db_api_keys = self.db.query(APIKeyModel).filter(
            APIKeyModel.is_active == True
        ).filter(
            (APIKeyModel.expires_at.is_(None)) | (APIKeyModel.expires_at > now)
        ).all()
        
        # Check each key hash
        for db_api_key in db_api_keys:
            if verify_api_key(plain_key, db_api_key.key_hash):
                return APIKey(
                    id=db_api_key.id,
                    name=db_api_key.name,
                    key_hash=db_api_key.key_hash,
                    is_active=db_api_key.is_active,
                    created_at=db_api_key.created_at,
                    expires_at=db_api_key.expires_at,
                    last_used_at=db_api_key.last_used_at
                )
        
        return None
    
    def get_by_id(self, api_key_id: int) -> Optional[APIKey]:
        """Get API key by ID."""
        db_api_key = self.db.query(APIKeyModel).filter(
            APIKeyModel.id == api_key_id
        ).first()
        
        if not db_api_key:
            return None
        
        return APIKey(
            id=db_api_key.id,
            name=db_api_key.name,
            key_hash=db_api_key.key_hash,
            is_active=db_api_key.is_active,
            created_at=db_api_key.created_at,
            expires_at=db_api_key.expires_at,
            last_used_at=db_api_key.last_used_at
        )
    
    def get_all_api_keys(self, user_id: Optional[int] = None) -> List[APIKey]:
        """Get all API keys, optionally filtered by user."""
        query = self.db.query(APIKeyModel)
        if user_id:
            query = query.filter(APIKeyModel.user_id == user_id)
        
        db_api_keys = query.all()
        
        return [
            APIKey(
                id=db_api_key.id,
                name=db_api_key.name,
                key_hash=db_api_key.key_hash,
                is_active=db_api_key.is_active,
                created_at=db_api_key.created_at,
                expires_at=db_api_key.expires_at,
                last_used_at=db_api_key.last_used_at
            )
            for db_api_key in db_api_keys
        ]
    
    def update_last_used(self, api_key_id: int) -> bool:
        """Update the last used timestamp for an API key."""
        db_api_key = self.db.query(APIKeyModel).filter(
            APIKeyModel.id == api_key_id
        ).first()
        
        if not db_api_key:
            return False
        
        db_api_key.last_used_at = datetime.utcnow()
        self.db.commit()
        return True
    
    def deactivate_api_key(self, api_key_id: int) -> bool:
        """Deactivate an API key."""
        db_api_key = self.db.query(APIKeyModel).filter(
            APIKeyModel.id == api_key_id
        ).first()
        
        if not db_api_key:
            return False
        
        db_api_key.is_active = False
        self.db.commit()
        return True