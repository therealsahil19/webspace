"""
Tests for the data validator module.
"""
import pytest
from datetime import datetime, timezone
from typing import Dict, Any

from src.processing.data_validator import LaunchDataValidator, DataValidationError
from src.models.schemas import LaunchData, SourceData, ConflictData, LaunchStatus


class TestLaunchDataValidator:
    """Test cases for LaunchDataValidator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = LaunchDataValidator()
        
        self.valid_launch_data = {
            'slug': 'falcon-heavy-demo',
            'mission_name': 'Falcon Heavy Demo',
            'launch_date': datetime(2018, 2, 6, 20, 45, tzinfo=timezone.utc),
            'vehicle_type': 'Falcon Heavy',
            'payload_mass': 1420.0,
            'orbit': 'Heliocentric',
            'status': 'success',
            'details': 'First Falcon Heavy test flight',
            'mission_patch_url': 'https://example.com/patch.png',
            'webcast_url': 'https://example.com/webcast'
        }
        
        self.valid_source_data = {
            'source_name': 'spacex',
            'source_url': 'https://spacex.com/launches',
            'scraped_at': datetime.now(timezone.utc),
            'data_quality_score': 0.95
        }
    
    def test_validate_valid_launch_data(self):
        """Test validation of valid launch data."""
        result = self.validator.validate_launch_data(self.valid_launch_data)
        
        assert result is not None
        assert isinstance(result, LaunchData)
        assert result.slug == 'falcon-heavy-demo'
        assert result.mission_name == 'Falcon Heavy Demo'
        assert result.status == LaunchStatus.SUCCESS
    
    def test_validate_minimal_launch_data(self):
        """Test validation with minimal required fields."""
        minimal_data = {
            'slug': 'test-mission',
            'mission_name': 'Test Mission',
            'status': 'upcoming'
        }
        
        result = self.validator.validate_launch_data(minimal_data)
        
        assert result is not None
        assert result.slug == 'test-mission'
        assert result.mission_name == 'Test Mission'
        assert result.status == LaunchStatus.UPCOMING
        assert result.launch_date is None
        assert result.payload_mass is None
    
    def test_validate_missing_required_fields(self):
        """Test validation fails with missing required fields."""
        invalid_data = {
            'mission_name': 'Test Mission'
            # Missing slug and status
        }
        
        result = self.validator.validate_launch_data(invalid_data)
        assert result is None
        assert len(self.validator.validation_errors) > 0
    
    def test_validate_invalid_slug_format(self):
        """Test validation fails with invalid slug format."""
        invalid_data = self.valid_launch_data.copy()
        invalid_data['slug'] = 'invalid slug with spaces!'
        
        result = self.validator.validate_launch_data(invalid_data)
        assert result is None
    
    def test_validate_invalid_payload_mass(self):
        """Test validation fails with negative payload mass."""
        invalid_data = self.valid_launch_data.copy()
        invalid_data['payload_mass'] = -100.0
        
        result = self.validator.validate_launch_data(invalid_data)
        assert result is None
    
    def test_validate_invalid_url_format(self):
        """Test validation fails with invalid URL format."""
        invalid_data = self.valid_launch_data.copy()
        invalid_data['mission_patch_url'] = 'not-a-valid-url'
        
        result = self.validator.validate_launch_data(invalid_data)
        assert result is None
    
    def test_validate_old_launch_date(self):
        """Test validation fails with launch date before year 2000."""
        invalid_data = self.valid_launch_data.copy()
        invalid_data['launch_date'] = datetime(1999, 1, 1)
        
        result = self.validator.validate_launch_data(invalid_data)
        assert result is None
    
    def test_clean_raw_data_status_normalization(self):
        """Test status normalization during data cleaning."""
        test_cases = [
            ('successful', 'success'),
            ('FAILURE', 'failure'),
            ('scheduled', 'upcoming'),
            ('cancelled', 'aborted'),
            ('in-flight', 'in_flight')
        ]
        
        for input_status, expected_status in test_cases:
            data = self.valid_launch_data.copy()
            data['status'] = input_status
            
            result = self.validator.validate_launch_data(data)
            assert result is not None
            assert result.status.value == expected_status
    
    def test_clean_raw_data_string_trimming(self):
        """Test string field trimming during data cleaning."""
        data = self.valid_launch_data.copy()
        data['mission_name'] = '  Falcon Heavy Demo  '
        data['vehicle_type'] = '\tFalcon Heavy\n'
        
        result = self.validator.validate_launch_data(data)
        assert result is not None
        assert result.mission_name == 'Falcon Heavy Demo'
        assert result.vehicle_type == 'Falcon Heavy'
    
    def test_clean_raw_data_numeric_conversion(self):
        """Test numeric field conversion during data cleaning."""
        data = self.valid_launch_data.copy()
        data['payload_mass'] = '1420.5'  # String number
        
        result = self.validator.validate_launch_data(data)
        assert result is not None
        assert result.payload_mass == 1420.5
    
    def test_clean_raw_data_invalid_numeric(self):
        """Test handling of invalid numeric values."""
        data = self.valid_launch_data.copy()
        data['payload_mass'] = 'not-a-number'
        
        result = self.validator.validate_launch_data(data)
        assert result is not None
        assert result.payload_mass is None  # Should be cleaned to None
    
    def test_generate_slug_from_mission_name(self):
        """Test slug generation from mission name."""
        data = self.valid_launch_data.copy()
        del data['slug']  # Remove slug to trigger generation
        data['mission_name'] = 'Falcon Heavy Demo Mission!'
        
        result = self.validator.validate_launch_data(data)
        assert result is not None
        assert result.slug == 'falcon-heavy-demo-mission'
    
    def test_validate_source_data_valid(self):
        """Test validation of valid source data."""
        result = self.validator.validate_source_data(self.valid_source_data)
        
        assert result is not None
        assert isinstance(result, SourceData)
        assert result.source_name == 'spacex'
        assert result.data_quality_score == 0.95
    
    def test_validate_source_data_invalid_url(self):
        """Test source data validation fails with invalid URL."""
        invalid_data = self.valid_source_data.copy()
        invalid_data['source_url'] = 'not-a-url'
        
        result = self.validator.validate_source_data(invalid_data)
        assert result is None
    
    def test_validate_source_data_future_scraped_date(self):
        """Test source data validation fails with future scraped date."""
        invalid_data = self.valid_source_data.copy()
        invalid_data['scraped_at'] = datetime(2030, 1, 1, tzinfo=timezone.utc)
        
        result = self.validator.validate_source_data(invalid_data)
        assert result is None
    
    def test_validate_conflict_data_valid(self):
        """Test validation of valid conflict data."""
        conflict_data = {
            'field_name': 'mission_name',
            'source1_value': 'Falcon Heavy Demo',
            'source2_value': 'FH Demo',
            'confidence_score': 0.8
        }
        
        result = self.validator.validate_conflict_data(conflict_data)
        
        assert result is not None
        assert isinstance(result, ConflictData)
        assert result.field_name == 'mission_name'
        assert result.confidence_score == 0.8
    
    def test_validate_conflict_data_same_values(self):
        """Test conflict data validation fails with identical values."""
        conflict_data = {
            'field_name': 'mission_name',
            'source1_value': 'Falcon Heavy Demo',
            'source2_value': 'Falcon Heavy Demo',  # Same as source1
            'confidence_score': 0.8
        }
        
        result = self.validator.validate_conflict_data(conflict_data)
        assert result is None
    
    def test_validate_batch_mixed_data(self):
        """Test batch validation with mix of valid and invalid data."""
        batch_data = [
            self.valid_launch_data,
            {'mission_name': 'Invalid Mission'},  # Missing required fields
            {
                'slug': 'valid-mission-2',
                'mission_name': 'Valid Mission 2',
                'status': 'upcoming'
            }
        ]
        
        results = self.validator.validate_batch(batch_data)
        
        assert len(results) == 2  # Only valid records
        assert results[0].slug == 'falcon-heavy-demo'
        assert results[1].slug == 'valid-mission-2'
    
    def test_business_rules_validation_future_date_warning(self):
        """Test business rules generate warning for far future dates."""
        data = self.valid_launch_data.copy()
        data['launch_date'] = datetime(2040, 1, 1, tzinfo=timezone.utc)
        
        result = self.validator.validate_launch_data(data)
        
        assert result is not None
        summary = self.validator.get_validation_summary()
        assert summary['warning_count'] > 0
        assert any('too far in future' in warning for warning in summary['warnings'])
    
    def test_business_rules_validation_status_date_mismatch(self):
        """Test business rules generate warning for status/date mismatch."""
        data = self.valid_launch_data.copy()
        data['status'] = 'upcoming'
        data['launch_date'] = datetime(2020, 1, 1, tzinfo=timezone.utc)  # Past date
        
        result = self.validator.validate_launch_data(data)
        
        assert result is not None
        summary = self.validator.get_validation_summary()
        assert summary['warning_count'] > 0
        assert any('upcoming but date is in past' in warning for warning in summary['warnings'])
    
    def test_business_rules_validation_high_payload_mass(self):
        """Test business rules generate warning for unusually high payload mass."""
        data = self.valid_launch_data.copy()
        data['payload_mass'] = 150000.0  # 150 tons - unusually high
        
        result = self.validator.validate_launch_data(data)
        
        assert result is not None
        summary = self.validator.get_validation_summary()
        assert summary['warning_count'] > 0
        assert any('unusually high' in warning for warning in summary['warnings'])
    
    def test_validation_summary(self):
        """Test validation summary generation."""
        # Process some data to generate errors and warnings
        self.validator.validate_launch_data({'invalid': 'data'})
        self.validator.validate_launch_data(self.valid_launch_data)
        
        summary = self.validator.get_validation_summary()
        
        assert 'errors' in summary
        assert 'warnings' in summary
        assert 'error_count' in summary
        assert 'warning_count' in summary
        assert isinstance(summary['errors'], list)
        assert isinstance(summary['warnings'], list)
    
    def test_clear_results(self):
        """Test clearing validation results."""
        # Generate some errors and warnings
        self.validator.validate_launch_data({'invalid': 'data'})
        
        assert len(self.validator.validation_errors) > 0
        
        self.validator.clear_results()
        
        assert len(self.validator.validation_errors) == 0
        assert len(self.validator.warnings) == 0
    
    @pytest.mark.parametrize("date_string,expected_success", [
        ("2024-02-06T20:45:00+00:00", True),
        ("2024-02-06 20:45:00", True),
        ("2024-02-06", True),
        ("invalid-date", False),
        ("", False)
    ])
    def test_date_parsing_formats(self, date_string, expected_success):
        """Test various date string formats are parsed correctly."""
        data = self.valid_launch_data.copy()
        data['launch_date'] = date_string
        
        result = self.validator.validate_launch_data(data)
        
        if expected_success:
            assert result is not None
            assert result.launch_date is not None
        else:
            assert result is not None  # Should still validate
            assert result.launch_date is None  # But date should be None