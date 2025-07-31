"""
Base repository class providing common database operations.
"""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

# Generic type for model classes
ModelType = TypeVar('ModelType')
CreateSchemaType = TypeVar('CreateSchemaType')
UpdateSchemaType = TypeVar('UpdateSchemaType')


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType], ABC):
    """Base repository class with common CRUD operations."""
    
    def __init__(self, model: type[ModelType], session: Session):
        """Initialize repository with model class and database session."""
        self.model = model
        self.session = session
    
    def get(self, id: int) -> Optional[ModelType]:
        """Get a single record by ID."""
        try:
            return self.session.query(self.model).filter(self.model.id == id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model.__name__} with id {id}: {e}")
            raise
    
    def get_by_field(self, field_name: str, value: Any) -> Optional[ModelType]:
        """Get a single record by a specific field."""
        try:
            field = getattr(self.model, field_name)
            return self.session.query(self.model).filter(field == value).first()
        except (AttributeError, SQLAlchemyError) as e:
            logger.error(f"Error getting {self.model.__name__} by {field_name}={value}: {e}")
            raise
    
    def get_multi(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None
    ) -> List[ModelType]:
        """Get multiple records with optional filtering and pagination."""
        try:
            query = self.session.query(self.model)
            
            # Apply filters
            if filters:
                for field_name, value in filters.items():
                    if hasattr(self.model, field_name):
                        field = getattr(self.model, field_name)
                        query = query.filter(field == value)
            
            # Apply ordering
            if order_by and hasattr(self.model, order_by):
                order_field = getattr(self.model, order_by)
                query = query.order_by(order_field)
            
            return query.offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting multiple {self.model.__name__} records: {e}")
            raise
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filtering."""
        try:
            query = self.session.query(self.model)
            
            # Apply filters
            if filters:
                for field_name, value in filters.items():
                    if hasattr(self.model, field_name):
                        field = getattr(self.model, field_name)
                        query = query.filter(field == value)
            
            return query.count()
        except SQLAlchemyError as e:
            logger.error(f"Error counting {self.model.__name__} records: {e}")
            raise
    
    def create(self, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record."""
        try:
            if hasattr(obj_in, 'model_dump'):
                obj_data = obj_in.model_dump()
            elif hasattr(obj_in, 'dict'):
                obj_data = obj_in.dict()
            else:
                obj_data = obj_in
            
            db_obj = self.model(**obj_data)
            self.session.add(db_obj)
            self.session.flush()  # Flush to get the ID without committing
            self.session.refresh(db_obj)
            return db_obj
        except IntegrityError as e:
            logger.error(f"Integrity error creating {self.model.__name__}: {e}")
            self.session.rollback()
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            self.session.rollback()
            raise
    
    def update(self, db_obj: ModelType, obj_in: UpdateSchemaType) -> ModelType:
        """Update an existing record."""
        try:
            if hasattr(obj_in, 'model_dump'):
                update_data = obj_in.model_dump(exclude_unset=True)
            elif hasattr(obj_in, 'dict'):
                update_data = obj_in.dict(exclude_unset=True)
            else:
                update_data = obj_in
            
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)
            
            self.session.flush()
            self.session.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            logger.error(f"Error updating {self.model.__name__}: {e}")
            self.session.rollback()
            raise
    
    def delete(self, id: int) -> bool:
        """Delete a record by ID."""
        try:
            db_obj = self.get(id)
            if db_obj:
                self.session.delete(db_obj)
                self.session.flush()
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error deleting {self.model.__name__} with id {id}: {e}")
            self.session.rollback()
            raise
    
    def bulk_create(self, objects: List[CreateSchemaType]) -> List[ModelType]:
        """Create multiple records in a single transaction."""
        try:
            db_objects = []
            for obj_in in objects:
                if hasattr(obj_in, 'model_dump'):
                    obj_data = obj_in.model_dump()
                elif hasattr(obj_in, 'dict'):
                    obj_data = obj_in.dict()
                else:
                    obj_data = obj_in
                
                db_obj = self.model(**obj_data)
                db_objects.append(db_obj)
            
            self.session.add_all(db_objects)
            self.session.flush()
            
            # Refresh all objects to get their IDs
            for db_obj in db_objects:
                self.session.refresh(db_obj)
            
            return db_objects
        except IntegrityError as e:
            logger.error(f"Integrity error in bulk create for {self.model.__name__}: {e}")
            self.session.rollback()
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error in bulk create for {self.model.__name__}: {e}")
            self.session.rollback()
            raise