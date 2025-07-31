"""
Pydantic models for data validation and serialization.
"""
from pydantic import BaseModel, Field, validator
from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum


class LaunchStatus(str, Enum):
    """Enumeration of possible launch statuses."""
    UPCOMING = "upcoming"
    SUCCESS = "success"
    FAILURE = "failure"
    IN_FLIGHT = "in_flight"
    ABORTED = "aborted"


class LaunchData(BaseModel):
    """Pydantic model for launch data validation."""
    slug: str = Field(..., description="Unique identifier for the launch", min_length=1, max_length=255)
    mission_name: str = Field(..., description="Name of the mission", min_length=1, max_length=255)
    launch_date: Optional[datetime] = Field(None, description="Scheduled launch date")
    vehicle_type: Optional[str] = Field(None, description="Rocket vehicle type", max_length=100)
    payload_mass: Optional[float] = Field(None, description="Payload mass in kg", ge=0)
    orbit: Optional[str] = Field(None, description="Target orbit", max_length=100)
    status: LaunchStatus = Field(..., description="Launch status")
    details: Optional[str] = Field(None, description="Mission details")
    mission_patch_url: Optional[str] = Field(None, description="Mission patch image URL", max_length=500)
    webcast_url: Optional[str] = Field(None, description="Live webcast URL", max_length=500)
    
    @validator('slug')
    def validate_slug(cls, v):
        """Validate slug format - should be URL-friendly."""
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Slug must contain only alphanumeric characters, hyphens, and underscores')
        return v.lower()
    
    @validator('launch_date')
    def validate_launch_date(cls, v):
        """Validate launch date is not too far in the past."""
        if v and v.year < 2000:
            raise ValueError('Launch date cannot be before year 2000')
        return v
    
    @validator('mission_patch_url', 'webcast_url')
    def validate_urls(cls, v):
        """Basic URL validation."""
        if v and not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True


class SourceData(BaseModel):
    """Pydantic model for tracking data sources."""
    source_name: str = Field(..., description="Name of the data source", min_length=1, max_length=100)
    source_url: str = Field(..., description="URL of the data source", max_length=500)
    scraped_at: datetime = Field(..., description="When the data was scraped")
    data_quality_score: float = Field(..., description="Quality score of the data", ge=0.0, le=1.0)
    
    @validator('source_url')
    def validate_source_url(cls, v):
        """Validate source URL format."""
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('Source URL must start with http:// or https://')
        return v
    
    @validator('scraped_at')
    def validate_scraped_at(cls, v):
        """Validate scraped_at is not in the future."""
        # Use timezone-aware datetime for comparison
        now = datetime.now(timezone.utc) if v.tzinfo else datetime.now()
        if v > now:
            raise ValueError('Scraped date cannot be in the future')
        return v

    class Config:
        """Pydantic configuration."""
        validate_assignment = True


class ConflictData(BaseModel):
    """Pydantic model for tracking data conflicts between sources."""
    field_name: str = Field(..., description="Name of the conflicting field", min_length=1, max_length=100)
    source1_value: str = Field(..., description="Value from first source")
    source2_value: str = Field(..., description="Value from second source")
    confidence_score: float = Field(..., description="Confidence in conflict detection", ge=0.0, le=1.0)
    resolved: bool = Field(False, description="Whether the conflict has been resolved")
    
    @validator('source1_value', 'source2_value')
    def validate_values_different(cls, v, values):
        """Ensure the conflicting values are actually different."""
        if 'source1_value' in values and v == values['source1_value']:
            raise ValueError('Conflicting values must be different')
        return v

    class Config:
        """Pydantic configuration."""
        validate_assignment = True


# Response models for API
class LaunchResponse(LaunchData):
    """Response model for launch data with additional metadata."""
    id: int = Field(..., description="Database ID")
    created_at: datetime = Field(..., description="When the record was created")
    updated_at: datetime = Field(..., description="When the record was last updated")
    sources: List[SourceData] = Field(default_factory=list, description="Data sources for this launch")
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True


class LaunchListResponse(BaseModel):
    """Response model for paginated launch lists."""
    launches: List[LaunchResponse] = Field(..., description="List of launches")
    total: int = Field(..., description="Total number of launches")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Number of items per page")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")