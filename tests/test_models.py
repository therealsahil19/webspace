"""
Unit tests for data models and validation logic.
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from pydantic import ValidationError

from src.models.schemas import (
    LaunchStatus,
    LaunchData,
    SourceData,
    ConflictData,
    LaunchResponse,
    LaunchListResponse
)


class TestLaunchStatus:
    """Test cases for LaunchStatus enum."""
    
    def test_enum_values(self):
        """Test that all expected enum values are present."""
        assert LaunchStatus.UPCOMING == "upcoming"
        assert LaunchStatus.SUCCESS == "success"
        assert LaunchStatus.FAILURE == "failure"
        assert LaunchStatus.IN_FLIGHT == "in_flight"
        assert LaunchStatus.ABORTED == "aborted"


class TestLaunchData:
    """Test cases for LaunchData Pydantic model."""
    
    def test_valid_launch_data(self):
        """Test creation of valid launch data."""
        launch_date = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        data = {
            "slug": "falcon-heavy-demo",
            "mission_name": "Falcon Heavy Demo",
            "launch_date": launch_date,
            "vehicle_type": "Falcon Heavy",
            "payload_mass": 1420.5,
            "orbit": "LEO",
            "status": LaunchStatus.SUCCESS,
            "details": "Successful demonstration flight",
            "mission_patch_url": "https://example.com/patch.png",
            "webcast_url": "https://example.com/webcast"
        }
        
        launch = LaunchData(**data)
        
        assert launch.slug == "falcon-heavy-demo"
        assert launch.mission_name == "Falcon Heavy Demo"
        assert launch.launch_date == launch_date
        assert launch.vehicle_type == "Falcon Heavy"
        assert launch.payload_mass == 1420.5
        assert launch.orbit == "LEO"
        assert launch.status == LaunchStatus.SUCCESS
        assert launch.details == "Successful demonstration flight"
        assert launch.mission_patch_url == "https://example.com/patch.png"
        assert launch.webcast_url == "https://example.com/webcast"
    
    def test_minimal_valid_launch_data(self):
        """Test creation with only required fields."""
        data = {
            "slug": "test-mission",
            "mission_name": "Test Mission",
            "status": LaunchStatus.UPCOMING
        }
        
        launch = LaunchData(**data)
        
        assert launch.slug == "test-mission"
        assert launch.mission_name == "Test Mission"
        assert launch.status == LaunchStatus.UPCOMING
        assert launch.launch_date is None
        assert launch.vehicle_type is None
        assert launch.payload_mass is None
        assert launch.orbit is None
        assert launch.details is None
        assert launch.mission_patch_url is None
        assert launch.webcast_url is None
    
    def test_slug_validation_lowercase(self):
        """Test that slug is converted to lowercase."""
        data = {
            "slug": "FALCON-HEAVY-DEMO",
            "mission_name": "Test Mission",
            "status": LaunchStatus.UPCOMING
        }
        
        launch = LaunchData(**data)
        assert launch.slug == "falcon-heavy-demo"
    
    def test_slug_validation_invalid_characters(self):
        """Test slug validation with invalid characters."""
        data = {
            "slug": "falcon@heavy#demo",
            "mission_name": "Test Mission",
            "status": LaunchStatus.UPCOMING
        }
        
        with pytest.raises(ValidationError) as exc_info:
            LaunchData(**data)
        
        assert "Slug must contain only alphanumeric characters" in str(exc_info.value)
    
    def test_slug_validation_empty(self):
        """Test slug validation with empty string."""
        data = {
            "slug": "",
            "mission_name": "Test Mission",
            "status": LaunchStatus.UPCOMING
        }
        
        with pytest.raises(ValidationError) as exc_info:
            LaunchData(**data)
        
        assert "String should have at least 1 character" in str(exc_info.value)
    
    def test_slug_validation_too_long(self):
        """Test slug validation with string too long."""
        data = {
            "slug": "a" * 256,  # Exceeds 255 character limit
            "mission_name": "Test Mission",
            "status": LaunchStatus.UPCOMING
        }
        
        with pytest.raises(ValidationError) as exc_info:
            LaunchData(**data)
        
        assert "String should have at most 255 characters" in str(exc_info.value)
    
    def test_mission_name_validation_empty(self):
        """Test mission name validation with empty string."""
        data = {
            "slug": "test-mission",
            "mission_name": "",
            "status": LaunchStatus.UPCOMING
        }
        
        with pytest.raises(ValidationError) as exc_info:
            LaunchData(**data)
        
        assert "String should have at least 1 character" in str(exc_info.value)
    
    def test_launch_date_validation_too_old(self):
        """Test launch date validation with date before year 2000."""
        data = {
            "slug": "test-mission",
            "mission_name": "Test Mission",
            "launch_date": datetime(1999, 12, 31, tzinfo=timezone.utc),
            "status": LaunchStatus.UPCOMING
        }
        
        with pytest.raises(ValidationError) as exc_info:
            LaunchData(**data)
        
        assert "Launch date cannot be before year 2000" in str(exc_info.value)
    
    def test_payload_mass_validation_negative(self):
        """Test payload mass validation with negative value."""
        data = {
            "slug": "test-mission",
            "mission_name": "Test Mission",
            "payload_mass": -100.0,
            "status": LaunchStatus.UPCOMING
        }
        
        with pytest.raises(ValidationError) as exc_info:
            LaunchData(**data)
        
        assert "Input should be greater than or equal to 0" in str(exc_info.value)
    
    def test_url_validation_invalid_scheme(self):
        """Test URL validation with invalid scheme."""
        data = {
            "slug": "test-mission",
            "mission_name": "Test Mission",
            "mission_patch_url": "ftp://example.com/patch.png",
            "status": LaunchStatus.UPCOMING
        }
        
        with pytest.raises(ValidationError) as exc_info:
            LaunchData(**data)
        
        assert "URL must start with http:// or https://" in str(exc_info.value)
    
    def test_url_validation_valid_schemes(self):
        """Test URL validation with valid schemes."""
        data = {
            "slug": "test-mission",
            "mission_name": "Test Mission",
            "mission_patch_url": "https://example.com/patch.png",
            "webcast_url": "http://example.com/webcast",
            "status": LaunchStatus.UPCOMING
        }
        
        launch = LaunchData(**data)
        assert launch.mission_patch_url == "https://example.com/patch.png"
        assert launch.webcast_url == "http://example.com/webcast"


class TestSourceData:
    """Test cases for SourceData Pydantic model."""
    
    def test_valid_source_data(self):
        """Test creation of valid source data."""
        scraped_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        data = {
            "source_name": "SpaceX Website",
            "source_url": "https://www.spacex.com/launches",
            "scraped_at": scraped_at,
            "data_quality_score": 0.95
        }
        
        source = SourceData(**data)
        
        assert source.source_name == "SpaceX Website"
        assert source.source_url == "https://www.spacex.com/launches"
        assert source.scraped_at == scraped_at
        assert source.data_quality_score == 0.95
    
    def test_source_name_validation_empty(self):
        """Test source name validation with empty string."""
        data = {
            "source_name": "",
            "source_url": "https://example.com",
            "scraped_at": datetime.now(),
            "data_quality_score": 0.5
        }
        
        with pytest.raises(ValidationError) as exc_info:
            SourceData(**data)
        
        assert "String should have at least 1 character" in str(exc_info.value)
    
    def test_source_url_validation_invalid_scheme(self):
        """Test source URL validation with invalid scheme."""
        data = {
            "source_name": "Test Source",
            "source_url": "ftp://example.com",
            "scraped_at": datetime.now(),
            "data_quality_score": 0.5
        }
        
        with pytest.raises(ValidationError) as exc_info:
            SourceData(**data)
        
        assert "Source URL must start with http:// or https://" in str(exc_info.value)
    
    def test_scraped_at_validation_future_date(self):
        """Test scraped_at validation with future date."""
        future_date = datetime(2030, 1, 1, tzinfo=timezone.utc)
        data = {
            "source_name": "Test Source",
            "source_url": "https://example.com",
            "scraped_at": future_date,
            "data_quality_score": 0.5
        }
        
        with pytest.raises(ValidationError) as exc_info:
            SourceData(**data)
        
        assert "Scraped date cannot be in the future" in str(exc_info.value)
    
    def test_data_quality_score_validation_range(self):
        """Test data quality score validation with out-of-range values."""
        # Test negative value
        data = {
            "source_name": "Test Source",
            "source_url": "https://example.com",
            "scraped_at": datetime.now(),
            "data_quality_score": -0.1
        }
        
        with pytest.raises(ValidationError) as exc_info:
            SourceData(**data)
        
        assert "Input should be greater than or equal to 0" in str(exc_info.value)
        
        # Test value greater than 1
        data["data_quality_score"] = 1.1
        
        with pytest.raises(ValidationError) as exc_info:
            SourceData(**data)
        
        assert "Input should be less than or equal to 1" in str(exc_info.value)


class TestConflictData:
    """Test cases for ConflictData Pydantic model."""
    
    def test_valid_conflict_data(self):
        """Test creation of valid conflict data."""
        data = {
            "field_name": "launch_date",
            "source1_value": "2024-06-15T10:30:00Z",
            "source2_value": "2024-06-15T10:45:00Z",
            "confidence_score": 0.8,
            "resolved": False
        }
        
        conflict = ConflictData(**data)
        
        assert conflict.field_name == "launch_date"
        assert conflict.source1_value == "2024-06-15T10:30:00Z"
        assert conflict.source2_value == "2024-06-15T10:45:00Z"
        assert conflict.confidence_score == 0.8
        assert conflict.resolved is False
    
    def test_field_name_validation_empty(self):
        """Test field name validation with empty string."""
        data = {
            "field_name": "",
            "source1_value": "value1",
            "source2_value": "value2",
            "confidence_score": 0.5
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ConflictData(**data)
        
        assert "String should have at least 1 character" in str(exc_info.value)
    
    def test_confidence_score_validation_range(self):
        """Test confidence score validation with out-of-range values."""
        # Test negative value
        data = {
            "field_name": "test_field",
            "source1_value": "value1",
            "source2_value": "value2",
            "confidence_score": -0.1
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ConflictData(**data)
        
        assert "Input should be greater than or equal to 0" in str(exc_info.value)
        
        # Test value greater than 1
        data["confidence_score"] = 1.1
        
        with pytest.raises(ValidationError) as exc_info:
            ConflictData(**data)
        
        assert "Input should be less than or equal to 1" in str(exc_info.value)
    
    def test_default_resolved_value(self):
        """Test that resolved defaults to False."""
        data = {
            "field_name": "test_field",
            "source1_value": "value1",
            "source2_value": "value2",
            "confidence_score": 0.5
        }
        
        conflict = ConflictData(**data)
        assert conflict.resolved is False


class TestLaunchResponse:
    """Test cases for LaunchResponse model."""
    
    def test_valid_launch_response(self):
        """Test creation of valid launch response."""
        launch_date = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        updated_at = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        
        data = {
            "id": 1,
            "slug": "test-mission",
            "mission_name": "Test Mission",
            "launch_date": launch_date,
            "status": LaunchStatus.UPCOMING,
            "created_at": created_at,
            "updated_at": updated_at,
            "sources": []
        }
        
        response = LaunchResponse(**data)
        
        assert response.id == 1
        assert response.slug == "test-mission"
        assert response.mission_name == "Test Mission"
        assert response.launch_date == launch_date
        assert response.status == LaunchStatus.UPCOMING
        assert response.created_at == created_at
        assert response.updated_at == updated_at
        assert response.sources == []


class TestLaunchListResponse:
    """Test cases for LaunchListResponse model."""
    
    def test_valid_launch_list_response(self):
        """Test creation of valid launch list response."""
        launch_data = {
            "id": 1,
            "slug": "test-mission",
            "mission_name": "Test Mission",
            "status": LaunchStatus.UPCOMING,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "sources": []
        }
        
        data = {
            "launches": [LaunchResponse(**launch_data)],
            "total": 1,
            "page": 1,
            "per_page": 10,
            "has_next": False,
            "has_prev": False
        }
        
        response = LaunchListResponse(**data)
        
        assert len(response.launches) == 1
        assert response.total == 1
        assert response.page == 1
        assert response.per_page == 10
        assert response.has_next is False
        assert response.has_prev is False
    
    def test_empty_launch_list_response(self):
        """Test creation of empty launch list response."""
        data = {
            "launches": [],
            "total": 0,
            "page": 1,
            "per_page": 10,
            "has_next": False,
            "has_prev": False
        }
        
        response = LaunchListResponse(**data)
        
        assert response.launches == []
        assert response.total == 0