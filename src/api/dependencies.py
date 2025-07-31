"""
FastAPI dependencies for database sessions and common functionality.
"""
from typing import Generator
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db_session
from src.repositories import get_repository_manager, RepositoryManager


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    session = get_db_session()
    try:
        yield session
    finally:
        session.close()


def get_repo_manager(db: Session = Depends(get_db)) -> RepositoryManager:
    """Dependency to get repository manager."""
    return get_repository_manager(db)


def validate_pagination(skip: int = 0, limit: int = 50) -> tuple[int, int]:
    """Validate and normalize pagination parameters."""
    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skip parameter must be non-negative"
        )
    
    if limit <= 0 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit parameter must be between 1 and 100"
        )
    
    return skip, limit