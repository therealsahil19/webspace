"""
Common API response models and utilities.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    code: Optional[str] = Field(None, description="Error code")


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number (1-based)")
    per_page: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")


class PaginatedResponse(BaseModel):
    """Generic paginated response model."""
    data: List[Any] = Field(..., description="List of items")
    meta: PaginationMeta = Field(..., description="Pagination metadata")


def create_pagination_meta(
    total: int,
    skip: int,
    limit: int
) -> PaginationMeta:
    """Create pagination metadata from query parameters."""
    page = (skip // limit) + 1
    total_pages = (total + limit - 1) // limit  # Ceiling division
    
    return PaginationMeta(
        total=total,
        page=page,
        per_page=limit,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )