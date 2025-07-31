"""
Tests for the main data processing pipeline.
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple

from src.processing.data_pipeline import DataProcessingPipeline, DataProcessingResult
from src.models.schemas import LaunchData, SourceData, LaunchStatus


class TestDataProcessingPipeline:
    """Test cases for DataProcessingPipeline."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.pipeline = DataProcessingPipeline()
        
        self.base_date = datetime(2024, 2, 6, 20, 45, tzinfo=timezone.utc)
        
        # Valid raw data for testing
        self.valid_raw_launch = {
            'slug': 'falcon-heavy-demo',
            'mission_name': 'Falcon Heavy Demo',
            'launch_date': self.base_date.isoformat(),
            'vehicle_type': 'Falcon Heavy',
            'payload_mass': 1420.0,
            'orbit': 'Heliocentric',
            'status': 'success',
            'details': 'First Falcon Heavy test flight'
        }
        
        self.valid_raw_source = {
            'source_name': 'spacex',
            'source_url': 'https://spacex.com/launches',
            'scraped_at': datetime.now(timezone.utc).isoformat(),
            'data_quality_score': 0.95
        }
        
        # Conflicting data from different source
        self.conflicting_raw_launch = {
            'slug': 'falcon-heavy-demo',
            'mission_name': 'Falcon Heavy Demonstration',  # Different name
            'launch_date': (self.base_date + timedelta(hours=2)).isoformat(),  # Different time
            'vehicle_type': 'Falcon Heavy',
            'payload_mass': 1400.0,  # Different payload
            'orbit': 'Heliocentric',
            'status': 'success',
            'details': 'Inaugural Falcon Heavy flight'
        }
        
        self.conflicting_raw_source = {
            'source_name': 'nasa',
            'source_url': 'https://nasa.gov/launches',
            'scraped_at': datetime.now(timezone.utc).isoformat(),
            'data_quality_score': 0.90
        }
        
        # Invalid raw data for testing validation
        self.invalid_raw_launch = {
            'mission_name': 'Invalid Mission',
            # Missing required fields like slug and status
            'payload_mass': -100.0  # Invalid negative mass
        }
        
        self.invalid_raw_source = {
            'source_name': 'invalid',
            'source_url': 'not-a-url',  # Invalid URL
            'scraped_at': datetime.now(timezone.utc).isoformat(),
            'data_quality_score': 1.5  # Invalid score > 1.0
        }
    
    def test_process_single_valid_record(self):
        """Test processing a single valid record."""
        raw_data_with_sources = [
            (self.valid_raw_launch, self.valid_raw_source)
        ]
        
        result = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        assert isinstance(result, DataProcessingResult)
        assert len(result.processed_launches) == 1
        assert len(result.validation_errors) == 0
        assert len(result.conflicts) == 0
        assert result.processing_time is not None
        assert result.processing_time > 0
        
        # Check the processed launch
        launch = result.processed_launches[0]
        assert launch.slug == 'falcon-heavy-demo'
        assert launch.mission_name == 'Falcon Heavy Demo'
        assert launch.status == LaunchStatus.SUCCESS
    
    def test_process_multiple_sources_same_launch(self):
        """Test processing multiple sources for the same launch."""
        raw_data_with_sources = [
            (self.valid_raw_launch, self.valid_raw_source),
            (self.conflicting_raw_launch, self.conflicting_raw_source)
        ]
        
        result = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        assert len(result.processed_launches) == 1  # Should be reconciled into one
        assert len(result.conflicts) > 0  # Should detect conflicts
        assert len(result.conflict_analyses) > 0  # Should analyze conflicts
        
        # Check that SpaceX data is prioritized
        launch = result.processed_launches[0]
        assert launch.mission_name == 'Falcon Heavy Demo'  # SpaceX version
        assert launch.payload_mass == 1420.0  # SpaceX version
    
    def test_process_invalid_data(self):
        """Test processing invalid data."""
        raw_data_with_sources = [
            (self.invalid_raw_launch, self.invalid_raw_source)
        ]
        
        result = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        assert len(result.processed_launches) == 0  # No valid launches
        assert len(result.validation_errors) > 0  # Should have validation errors
        
        # Check processing stats
        stats = result.processing_stats
        assert stats['input_records'] == 1
        assert stats['validated_records'] == 0
        assert stats['validation_success_rate'] == 0.0
    
    def test_process_mixed_valid_invalid_data(self):
        """Test processing mix of valid and invalid data."""
        raw_data_with_sources = [
            (self.valid_raw_launch, self.valid_raw_source),
            (self.invalid_raw_launch, self.invalid_raw_source),
            (self.conflicting_raw_launch, self.conflicting_raw_source)
        ]
        
        result = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        # Should process valid records and skip invalid ones
        assert len(result.processed_launches) == 1  # One reconciled launch
        assert len(result.validation_errors) > 0  # Errors from invalid data
        
        stats = result.processing_stats
        assert stats['input_records'] == 3
        assert stats['validated_records'] == 2  # Two valid records
        assert 0 < stats['validation_success_rate'] < 1.0
    
    def test_deduplication_functionality(self):
        """Test deduplication functionality."""
        # Create duplicate launches with same slug and similar dates
        duplicate_launch = self.valid_raw_launch.copy()
        duplicate_launch['launch_date'] = (self.base_date + timedelta(hours=12)).isoformat()
        duplicate_launch['details'] = 'Duplicate with different details'
        
        duplicate_source = self.valid_raw_source.copy()
        duplicate_source['source_name'] = 'duplicate_source'
        
        raw_data_with_sources = [
            (self.valid_raw_launch, self.valid_raw_source),
            (duplicate_launch, duplicate_source)
        ]
        
        result = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        # Should deduplicate to single launch
        assert len(result.processed_launches) == 1
        
        # Check deduplication stats
        stats = result.processing_stats
        assert 'deduplication_stats' in stats
    
    def test_disable_deduplication(self):
        """Test pipeline with deduplication disabled."""
        self.pipeline.configure_pipeline(enable_deduplication=False)
        
        # Create duplicate launches
        duplicate_launch = self.valid_raw_launch.copy()
        duplicate_launch['launch_date'] = (self.base_date + timedelta(hours=12)).isoformat()
        
        duplicate_source = self.valid_raw_source.copy()
        duplicate_source['source_name'] = 'duplicate_source'
        
        raw_data_with_sources = [
            (self.valid_raw_launch, self.valid_raw_source),
            (duplicate_launch, duplicate_source)
        ]
        
        result = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        # Should not deduplicate
        assert len(result.processed_launches) == 2
        
        # Should not have deduplication stats
        stats = result.processing_stats
        assert 'deduplication_stats' not in stats
    
    def test_disable_conflict_detection(self):
        """Test pipeline with conflict detection disabled."""
        self.pipeline.configure_pipeline(enable_conflict_detection=False)
        
        raw_data_with_sources = [
            (self.valid_raw_launch, self.valid_raw_source),
            (self.conflicting_raw_launch, self.conflicting_raw_source)
        ]
        
        result = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        # Should not detect conflicts
        assert len(result.conflicts) == 0
        assert len(result.conflict_analyses) == 0
        
        # Should not have conflict detection stats
        stats = result.processing_stats
        assert 'conflict_detection_stats' not in stats
    
    def test_date_tolerance_configuration(self):
        """Test configuring date tolerance for deduplication."""
        # Configure strict date tolerance
        self.pipeline.configure_pipeline(date_tolerance_hours=1)
        
        # Create launches 12 hours apart
        distant_launch = self.valid_raw_launch.copy()
        distant_launch['launch_date'] = (self.base_date + timedelta(hours=12)).isoformat()
        distant_launch['slug'] = 'falcon-heavy-demo'  # Same slug
        
        distant_source = self.valid_raw_source.copy()
        distant_source['source_name'] = 'distant_source'
        
        raw_data_with_sources = [
            (self.valid_raw_launch, self.valid_raw_source),
            (distant_launch, distant_source)
        ]
        
        result = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        # With 1 hour tolerance, 12 hours apart should not be deduplicated
        assert len(result.processed_launches) == 2
    
    def test_process_single_launch(self):
        """Test processing a single launch record."""
        launch_data = self.pipeline.process_single_launch(
            self.valid_raw_launch, 
            self.valid_raw_source
        )
        
        assert launch_data is not None
        assert isinstance(launch_data, LaunchData)
        assert launch_data.slug == 'falcon-heavy-demo'
        assert launch_data.mission_name == 'Falcon Heavy Demo'
    
    def test_process_single_launch_invalid(self):
        """Test processing a single invalid launch record."""
        launch_data = self.pipeline.process_single_launch(
            self.invalid_raw_launch, 
            self.invalid_raw_source
        )
        
        assert launch_data is None
    
    def test_processing_statistics(self):
        """Test comprehensive processing statistics."""
        raw_data_with_sources = [
            (self.valid_raw_launch, self.valid_raw_source),
            (self.conflicting_raw_launch, self.conflicting_raw_source),
            (self.invalid_raw_launch, self.invalid_raw_source)
        ]
        
        result = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        stats = result.processing_stats
        
        # Check all required statistics are present
        required_stats = [
            'input_records', 'validated_records', 'reconciled_records', 
            'final_records', 'validation_success_rate', 'conflicts_detected',
            'validation_errors', 'processing_timestamp'
        ]
        
        for stat in required_stats:
            assert stat in stats
        
        # Check component statistics
        assert 'validator_stats' in stats
        assert 'reconciliation_stats' in stats
        
        # Check values make sense
        assert stats['input_records'] == 3
        assert stats['validated_records'] <= stats['input_records']
        assert stats['final_records'] <= stats['validated_records']
        assert 0 <= stats['validation_success_rate'] <= 1.0
    
    def test_processing_history(self):
        """Test processing history tracking."""
        raw_data_with_sources = [
            (self.valid_raw_launch, self.valid_raw_source)
        ]
        
        # Process data multiple times
        self.pipeline.process_scraped_data(raw_data_with_sources)
        self.pipeline.process_scraped_data(raw_data_with_sources)
        
        history = self.pipeline.get_processing_history()
        
        assert len(history) == 2
        
        for entry in history:
            assert 'timestamp' in entry
            assert 'input_count' in entry
            assert 'output_count' in entry
            assert 'conflicts_detected' in entry
            assert 'processing_time' in entry
    
    def test_clear_processing_history(self):
        """Test clearing processing history."""
        raw_data_with_sources = [
            (self.valid_raw_launch, self.valid_raw_source)
        ]
        
        self.pipeline.process_scraped_data(raw_data_with_sources)
        
        assert len(self.pipeline.get_processing_history()) == 1
        
        self.pipeline.clear_processing_history()
        
        assert len(self.pipeline.get_processing_history()) == 0
    
    def test_reset_components(self):
        """Test resetting pipeline components."""
        raw_data_with_sources = [
            (self.valid_raw_launch, self.valid_raw_source),
            (self.conflicting_raw_launch, self.conflicting_raw_source)
        ]
        
        # Process data to generate some state
        result1 = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        # Reset components
        self.pipeline.reset_components()
        
        # Process again - should work the same
        result2 = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        assert len(result1.processed_launches) == len(result2.processed_launches)
        assert len(result1.conflicts) == len(result2.conflicts)
    
    def test_empty_input(self):
        """Test processing empty input."""
        result = self.pipeline.process_scraped_data([])
        
        assert len(result.processed_launches) == 0
        assert len(result.validation_errors) == 0
        assert len(result.conflicts) == 0
        assert result.processing_time is not None
        
        stats = result.processing_stats
        assert stats['input_records'] == 0
        assert stats['validated_records'] == 0
        assert stats['final_records'] == 0
    
    def test_pipeline_error_handling(self):
        """Test pipeline error handling with malformed data."""
        # Create data that will cause processing errors
        malformed_data = [
            ({'invalid': 'structure'}, {'also': 'invalid'})
        ]
        
        result = self.pipeline.process_scraped_data(malformed_data)
        
        # Should handle errors gracefully
        assert isinstance(result, DataProcessingResult)
        assert len(result.processed_launches) == 0
        assert len(result.validation_errors) > 0
        assert result.processing_time is not None
    
    def test_multiple_different_launches(self):
        """Test processing multiple different launches."""
        # Create data for different launches
        starship_launch = {
            'slug': 'starship-test-1',
            'mission_name': 'Starship Test Flight 1',
            'launch_date': (self.base_date + timedelta(days=30)).isoformat(),
            'vehicle_type': 'Starship',
            'status': 'success'
        }
        
        starship_source = {
            'source_name': 'spacex',
            'source_url': 'https://spacex.com/starship',
            'scraped_at': datetime.now(timezone.utc).isoformat(),
            'data_quality_score': 0.90
        }
        
        raw_data_with_sources = [
            (self.valid_raw_launch, self.valid_raw_source),
            (starship_launch, starship_source)
        ]
        
        result = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        # Should process both launches
        assert len(result.processed_launches) == 2
        assert len(result.conflicts) == 0  # No conflicts between different launches
        
        # Check both launches are present
        slugs = [launch.slug for launch in result.processed_launches]
        assert 'falcon-heavy-demo' in slugs
        assert 'starship-test-1' in slugs
    
    def test_data_quality_score_influence(self):
        """Test that data quality scores influence processing."""
        # Create sources with different quality scores
        high_quality_source = self.valid_raw_source.copy()
        high_quality_source['data_quality_score'] = 0.95
        high_quality_source['source_name'] = 'high_quality'
        
        low_quality_source = self.conflicting_raw_source.copy()
        low_quality_source['data_quality_score'] = 0.60
        low_quality_source['source_name'] = 'low_quality'
        
        raw_data_with_sources = [
            (self.valid_raw_launch, high_quality_source),
            (self.conflicting_raw_launch, low_quality_source)
        ]
        
        result = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        # Should prioritize higher quality data
        assert len(result.processed_launches) == 1
        launch = result.processed_launches[0]
        
        # Should use data from higher quality source
        assert launch.mission_name == 'Falcon Heavy Demo'  # From high quality source
    
    def test_comprehensive_integration(self):
        """Test comprehensive integration of all pipeline components."""
        # Create complex scenario with multiple launches, sources, conflicts, and duplicates
        raw_data_with_sources = [
            # Falcon Heavy from multiple sources with conflicts
            (self.valid_raw_launch, self.valid_raw_source),
            (self.conflicting_raw_launch, self.conflicting_raw_source),
            
            # Duplicate Falcon Heavy with slight differences
            ({**self.valid_raw_launch, 
              'launch_date': (self.base_date + timedelta(hours=6)).isoformat(),
              'details': 'Duplicate entry'}, 
             {**self.valid_raw_source, 'source_name': 'duplicate'}),
            
            # Different launch
            ({'slug': 'starship-test', 'mission_name': 'Starship Test', 
              'status': 'success'}, 
             {**self.valid_raw_source, 'source_name': 'spacex_starship'}),
            
            # Invalid data
            (self.invalid_raw_launch, self.invalid_raw_source)
        ]
        
        result = self.pipeline.process_scraped_data(raw_data_with_sources)
        
        # Should handle all scenarios appropriately
        assert len(result.processed_launches) == 2  # Falcon Heavy + Starship (deduplicated)
        assert len(result.conflicts) > 0  # Conflicts detected
        assert len(result.validation_errors) > 0  # Invalid data errors
        
        # Check processing stats are comprehensive
        stats = result.processing_stats
        assert stats['input_records'] == 5
        assert stats['validated_records'] < stats['input_records']  # Some invalid
        assert stats['final_records'] == 2
        assert stats['conflicts_detected'] > 0
        assert stats['validation_errors'] > 0
        
        # Check all component stats are present
        assert 'validator_stats' in stats
        assert 'deduplication_stats' in stats
        assert 'reconciliation_stats' in stats
        assert 'conflict_detection_stats' in stats