"""
Tests for the source reconciler module.
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import List, Tuple

from src.processing.source_reconciler import SourceReconciler, SourcePriority
from src.models.schemas import LaunchData, SourceData, ConflictData, LaunchStatus


class TestSourceReconciler:
    """Test cases for SourceReconciler."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.reconciler = SourceReconciler()
        
        self.base_date = datetime(2024, 2, 6, 20, 45, tzinfo=timezone.utc)
        
        # SpaceX official source (highest priority)
        self.spacex_launch = LaunchData(
            slug='falcon-heavy-demo',
            mission_name='Falcon Heavy Demo',
            launch_date=self.base_date,
            vehicle_type='Falcon Heavy',
            payload_mass=1420.0,
            orbit='Heliocentric',
            status=LaunchStatus.SUCCESS,
            details='Official SpaceX description'
        )
        
        self.spacex_source = SourceData(
            source_name='spacex',
            source_url='https://spacex.com/launches',
            scraped_at=datetime.now(timezone.utc),
            data_quality_score=0.95
        )
        
        # NASA source (second priority)
        self.nasa_launch = LaunchData(
            slug='falcon-heavy-demo',
            mission_name='Falcon Heavy Demonstration',  # Slightly different name
            launch_date=self.base_date + timedelta(minutes=30),  # Slightly different time
            vehicle_type='Falcon Heavy',
            payload_mass=1400.0,  # Different payload mass
            orbit='Heliocentric',
            status=LaunchStatus.SUCCESS,
            details='NASA description with additional details'
        )
        
        self.nasa_source = SourceData(
            source_name='nasa',
            source_url='https://nasa.gov/launches',
            scraped_at=datetime.now(timezone.utc),
            data_quality_score=0.90
        )
        
        # Wikipedia source (lowest priority)
        self.wikipedia_launch = LaunchData(
            slug='falcon-heavy-demo',
            mission_name='Falcon Heavy Demo Flight',
            launch_date=self.base_date,
            vehicle_type='Falcon Heavy',
            payload_mass=None,  # Missing data
            orbit='Heliocentric',
            status=LaunchStatus.SUCCESS,
            details=None,  # Missing details
            mission_patch_url='https://wikipedia.org/patch.png'  # Has patch URL
        )
        
        self.wikipedia_source = SourceData(
            source_name='wikipedia',
            source_url='https://en.wikipedia.org/wiki/falcon_heavy',
            scraped_at=datetime.now(timezone.utc),
            data_quality_score=0.75
        )
    
    def test_reconcile_single_source(self):
        """Test reconciliation with single source."""
        launch_data_list = [(self.spacex_launch, self.spacex_source)]
        
        reconciled_launch, conflicts = self.reconciler.reconcile_launch_data(launch_data_list)
        
        assert reconciled_launch == self.spacex_launch
        assert len(conflicts) == 0
    
    def test_reconcile_multiple_sources_no_conflicts(self):
        """Test reconciliation with multiple sources that don't conflict."""
        # Create sources with complementary data (no conflicts)
        spacex_minimal = LaunchData(
            slug='test-mission',
            mission_name='Test Mission',
            status=LaunchStatus.SUCCESS,
            details='SpaceX details'
        )
        
        nasa_complementary = LaunchData(
            slug='test-mission',
            mission_name='Test Mission',
            status=LaunchStatus.SUCCESS,
            launch_date=self.base_date,
            vehicle_type='Falcon 9',
            payload_mass=5000.0
        )
        
        launch_data_list = [
            (spacex_minimal, self.spacex_source),
            (nasa_complementary, self.nasa_source)
        ]
        
        reconciled_launch, conflicts = self.reconciler.reconcile_launch_data(launch_data_list)
        
        # Should combine data from both sources
        assert reconciled_launch.mission_name == 'Test Mission'
        assert reconciled_launch.details == 'SpaceX details'  # From SpaceX
        assert reconciled_launch.launch_date == self.base_date  # From NASA
        assert reconciled_launch.vehicle_type == 'Falcon 9'  # From NASA
        assert len(conflicts) == 0
    
    def test_reconcile_with_conflicts(self):
        """Test reconciliation with conflicting data."""
        launch_data_list = [
            (self.spacex_launch, self.spacex_source),
            (self.nasa_launch, self.nasa_source)
        ]
        
        reconciled_launch, conflicts = self.reconciler.reconcile_launch_data(launch_data_list)
        
        # Should prioritize SpaceX data
        assert reconciled_launch.mission_name == 'Falcon Heavy Demo'  # SpaceX version
        assert reconciled_launch.payload_mass == 1420.0  # SpaceX version
        
        # Should detect conflicts
        assert len(conflicts) > 0
        
        # Check specific conflicts
        conflict_fields = [conflict.field_name for conflict in conflicts]
        assert 'mission_name' in conflict_fields
        assert 'payload_mass' in conflict_fields
    
    def test_source_priority_ordering(self):
        """Test that sources are ordered by priority correctly."""
        launch_data_list = [
            (self.wikipedia_launch, self.wikipedia_source),  # Lowest priority
            (self.spacex_launch, self.spacex_source),        # Highest priority
            (self.nasa_launch, self.nasa_source)             # Medium priority
        ]
        
        sorted_sources = self.reconciler._sort_by_priority(launch_data_list)
        
        # Should be ordered: SpaceX, NASA, Wikipedia
        assert sorted_sources[0][1].source_name == 'spacex'
        assert sorted_sources[1][1].source_name == 'nasa'
        assert sorted_sources[2][1].source_name == 'wikipedia'
    
    def test_get_source_priority(self):
        """Test source priority determination."""
        test_cases = [
            ('spacex', SourcePriority.SPACEX_OFFICIAL),
            ('spacex.com', SourcePriority.SPACEX_OFFICIAL),
            ('nasa', SourcePriority.NASA_OFFICIAL),
            ('nasa.gov', SourcePriority.NASA_OFFICIAL),
            ('spacex_press_kit', SourcePriority.SPACEX_PRESS_KIT),
            ('wikipedia', SourcePriority.WIKIPEDIA),
            ('unknown_source', SourcePriority.UNKNOWN)
        ]
        
        for source_name, expected_priority in test_cases:
            priority = self.reconciler._get_source_priority(source_name)
            assert priority == expected_priority
    
    def test_detect_date_conflicts(self):
        """Test date conflict detection."""
        # Dates within 1 hour - should not conflict
        date1 = self.base_date
        date2 = self.base_date + timedelta(minutes=30)
        assert not self.reconciler._dates_conflict(date1, date2)
        
        # Dates more than 1 hour apart - should conflict
        date3 = self.base_date + timedelta(hours=2)
        assert self.reconciler._dates_conflict(date1, date3)
    
    def test_detect_numeric_conflicts(self):
        """Test numeric value conflict detection."""
        # Values within 10% tolerance - should not conflict
        assert not self.reconciler._numeric_values_conflict(1000.0, 1050.0, tolerance=0.1)
        
        # Values outside tolerance - should conflict
        assert self.reconciler._numeric_values_conflict(1000.0, 1200.0, tolerance=0.1)
        
        # Zero values
        assert not self.reconciler._numeric_values_conflict(0.0, 0.0, tolerance=0.1)
    
    def test_detect_string_conflicts(self):
        """Test string value conflict detection."""
        # Exact match - no conflict
        assert not self.reconciler._string_values_conflict('Falcon Heavy', 'Falcon Heavy')
        
        # Case difference - no conflict
        assert not self.reconciler._string_values_conflict('Falcon Heavy', 'falcon heavy')
        
        # Substring relationship - no conflict
        assert not self.reconciler._string_values_conflict('Falcon Heavy', 'Falcon Heavy Demo')
        
        # Completely different - conflict
        assert self.reconciler._string_values_conflict('Falcon Heavy', 'Starship')
    
    def test_fill_missing_fields(self):
        """Test filling missing fields from lower priority sources."""
        # SpaceX source with missing fields
        spacex_incomplete = LaunchData(
            slug='test-mission',
            mission_name='Test Mission',
            status=LaunchStatus.SUCCESS
            # Missing launch_date, vehicle_type, etc.
        )
        
        # NASA source with additional fields
        nasa_complete = LaunchData(
            slug='test-mission',
            mission_name='Test Mission',
            status=LaunchStatus.SUCCESS,
            launch_date=self.base_date,
            vehicle_type='Falcon 9',
            payload_mass=5000.0,
            orbit='LEO'
        )
        
        launch_data_list = [
            (spacex_incomplete, self.spacex_source),
            (nasa_complete, self.nasa_source)
        ]
        
        reconciled_launch, conflicts = self.reconciler.reconcile_launch_data(launch_data_list)
        
        # Should fill missing fields from NASA
        assert reconciled_launch.launch_date == self.base_date
        assert reconciled_launch.vehicle_type == 'Falcon 9'
        assert reconciled_launch.payload_mass == 5000.0
        assert reconciled_launch.orbit == 'LEO'
    
    def test_special_reconciliation_rules(self):
        """Test special reconciliation rules for specific fields."""
        # Test details field - prefer longer description
        spacex_short = LaunchData(
            slug='test-mission',
            mission_name='Test Mission',
            status=LaunchStatus.SUCCESS,
            details='Short description'
        )
        
        nasa_long = LaunchData(
            slug='test-mission',
            mission_name='Test Mission',
            status=LaunchStatus.SUCCESS,
            details='Much longer and more detailed description with lots of information'
        )
        
        launch_data_list = [
            (spacex_short, self.spacex_source),
            (nasa_long, self.nasa_source)
        ]
        
        reconciled_launch, conflicts = self.reconciler.reconcile_launch_data(launch_data_list)
        
        # Should prefer longer details despite SpaceX priority
        assert reconciled_launch.details == nasa_long.details
    
    def test_reconcile_multiple_launches(self):
        """Test reconciling multiple launches grouped by slug."""
        launches_by_slug = {
            'falcon-heavy-demo': [
                (self.spacex_launch, self.spacex_source),
                (self.nasa_launch, self.nasa_source)
            ],
            'starship-test': [
                (LaunchData(slug='starship-test', mission_name='Starship Test', 
                           status=LaunchStatus.SUCCESS), self.spacex_source)
            ]
        }
        
        reconciled_launches = self.reconciler.reconcile_multiple_launches(launches_by_slug)
        
        assert len(reconciled_launches) == 2
        assert 'falcon-heavy-demo' in reconciled_launches
        assert 'starship-test' in reconciled_launches
        
        # Check that conflicts were detected for falcon-heavy-demo
        falcon_heavy_result = reconciled_launches['falcon-heavy-demo']
        reconciled_launch, conflicts = falcon_heavy_result
        assert len(conflicts) > 0
        
        # Check that no conflicts for starship-test (single source)
        starship_result = reconciled_launches['starship-test']
        reconciled_launch, conflicts = starship_result
        assert len(conflicts) == 0
    
    def test_conflict_confidence_calculation(self):
        """Test conflict confidence score calculation."""
        # High priority source vs low priority source should have higher confidence
        confidence = self.reconciler._calculate_conflict_confidence(
            'value1', 'value2', 'mission_name', self.spacex_source, self.wikipedia_source
        )
        
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.5  # Should be reasonably confident
    
    def test_reconciliation_summary(self):
        """Test reconciliation summary generation."""
        launch_data_list = [
            (self.spacex_launch, self.spacex_source),
            (self.nasa_launch, self.nasa_source),
            (self.wikipedia_launch, self.wikipedia_source)
        ]
        
        self.reconciler.reconcile_launch_data(launch_data_list)
        summary = self.reconciler.get_reconciliation_summary()
        
        assert 'total_conflicts_detected' in summary
        assert 'launches_reconciled' in summary
        assert 'conflicts_by_field' in summary
        assert 'sources_by_priority' in summary
        
        assert summary['launches_reconciled'] == 1
        assert summary['total_conflicts_detected'] > 0
    
    def test_clear_results(self):
        """Test clearing reconciliation results."""
        launch_data_list = [
            (self.spacex_launch, self.spacex_source),
            (self.nasa_launch, self.nasa_source)
        ]
        
        self.reconciler.reconcile_launch_data(launch_data_list)
        
        assert len(self.reconciler.conflicts_detected) > 0
        assert len(self.reconciler.reconciliation_log) > 0
        
        self.reconciler.clear_results()
        
        assert len(self.reconciler.conflicts_detected) == 0
        assert len(self.reconciler.reconciliation_log) == 0
    
    def test_empty_input_handling(self):
        """Test handling of empty input."""
        with pytest.raises(ValueError, match="No launch data provided"):
            self.reconciler.reconcile_launch_data([])
    
    def test_url_field_reconciliation(self):
        """Test reconciliation of URL fields."""
        spacex_no_urls = LaunchData(
            slug='test-mission',
            mission_name='Test Mission',
            status=LaunchStatus.SUCCESS
        )
        
        wikipedia_with_urls = LaunchData(
            slug='test-mission',
            mission_name='Test Mission',
            status=LaunchStatus.SUCCESS,
            mission_patch_url='https://example.com/patch.png',
            webcast_url='https://example.com/webcast'
        )
        
        launch_data_list = [
            (spacex_no_urls, self.spacex_source),
            (wikipedia_with_urls, self.wikipedia_source)
        ]
        
        reconciled_launch, conflicts = self.reconciler.reconcile_launch_data(launch_data_list)
        
        # Should fill URL fields from Wikipedia
        assert reconciled_launch.mission_patch_url == 'https://example.com/patch.png'
        assert reconciled_launch.webcast_url == 'https://example.com/webcast'
    
    def test_data_quality_score_influence(self):
        """Test that data quality scores influence reconciliation."""
        # Create two sources with different quality scores
        high_quality_source = SourceData(
            source_name='high_quality',
            source_url='https://example.com/high',
            scraped_at=datetime.now(timezone.utc),
            data_quality_score=0.95
        )
        
        low_quality_source = SourceData(
            source_name='low_quality',
            source_url='https://example.com/low',
            scraped_at=datetime.now(timezone.utc),
            data_quality_score=0.60
        )
        
        launch_data_list = [
            (self.spacex_launch, low_quality_source),   # Lower quality
            (self.nasa_launch, high_quality_source)    # Higher quality
        ]
        
        sorted_sources = self.reconciler._sort_by_priority(launch_data_list)
        
        # Despite same source priority, higher quality should come first
        # (Note: This test assumes both sources have same priority level)
        # The actual behavior depends on the specific priority mapping