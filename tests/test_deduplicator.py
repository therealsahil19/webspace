"""
Tests for the deduplicator module.
"""
import pytest
from datetime import datetime, timezone, timedelta

from src.processing.deduplicator import LaunchDeduplicator
from src.models.schemas import LaunchData, LaunchStatus


class TestLaunchDeduplicator:
    """Test cases for LaunchDeduplicator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.deduplicator = LaunchDeduplicator(date_tolerance_hours=24)
        
        # Base launch data for testing
        self.base_date = datetime(2024, 2, 6, 20, 45, tzinfo=timezone.utc)
        
        self.launch1 = LaunchData(
            slug='falcon-heavy-demo',
            mission_name='Falcon Heavy Demo',
            launch_date=self.base_date,
            vehicle_type='Falcon Heavy',
            payload_mass=1420.0,
            orbit='Heliocentric',
            status=LaunchStatus.SUCCESS,
            details='First Falcon Heavy test flight'
        )
        
        self.launch2 = LaunchData(
            slug='falcon-heavy-demo',
            mission_name='Falcon Heavy Demo',
            launch_date=self.base_date + timedelta(hours=12),  # 12 hours later
            vehicle_type='Falcon Heavy',
            payload_mass=1420.0,
            orbit='Heliocentric',
            status=LaunchStatus.SUCCESS,
            details='First Falcon Heavy test flight with more details'
        )
        
        self.launch3 = LaunchData(
            slug='starship-test',
            mission_name='Starship Test Flight',
            launch_date=self.base_date + timedelta(days=1),
            vehicle_type='Starship',
            status=LaunchStatus.SUCCESS
        )
    
    def test_deduplicate_no_duplicates(self):
        """Test deduplication with no duplicates."""
        launches = [self.launch1, self.launch3]
        
        result = self.deduplicator.deduplicate_launches(launches)
        
        assert len(result) == 2
        assert self.launch1 in result
        assert self.launch3 in result
    
    def test_deduplicate_same_slug_similar_dates(self):
        """Test deduplication removes launches with same slug and similar dates."""
        launches = [self.launch1, self.launch2]  # Same slug, dates within tolerance
        
        result = self.deduplicator.deduplicate_launches(launches)
        
        assert len(result) == 1
        # Should keep the one with more complete data (launch2 has more details)
        assert result[0].details == 'First Falcon Heavy test flight with more details'
    
    def test_deduplicate_same_slug_distant_dates(self):
        """Test deduplication keeps launches with same slug but distant dates."""
        launch2_distant = LaunchData(
            slug='falcon-heavy-demo',
            mission_name='Falcon Heavy Demo 2',
            launch_date=self.base_date + timedelta(days=30),  # 30 days later
            vehicle_type='Falcon Heavy',
            status=LaunchStatus.SUCCESS
        )
        
        launches = [self.launch1, launch2_distant]
        
        result = self.deduplicator.deduplicate_launches(launches)
        
        assert len(result) == 2  # Both should be kept
    
    def test_deduplicate_multiple_groups(self):
        """Test deduplication with multiple groups of duplicates."""
        # Create another duplicate for launch3
        launch3_duplicate = LaunchData(
            slug='starship-test',
            mission_name='Starship Test Flight',
            launch_date=self.launch3.launch_date + timedelta(hours=6),
            vehicle_type='Starship',
            status=LaunchStatus.SUCCESS,
            details='More detailed description'
        )
        
        launches = [self.launch1, self.launch2, self.launch3, launch3_duplicate]
        
        result = self.deduplicator.deduplicate_launches(launches)
        
        assert len(result) == 2  # One from each group
        
        # Check that we got the best from each group
        slugs = [launch.slug for launch in result]
        assert 'falcon-heavy-demo' in slugs
        assert 'starship-test' in slugs
    
    def test_deduplicate_none_dates(self):
        """Test deduplication with None launch dates."""
        launch_no_date1 = LaunchData(
            slug='test-mission',
            mission_name='Test Mission',
            status='upcoming'
        )
        
        launch_no_date2 = LaunchData(
            slug='test-mission',
            mission_name='Test Mission',
            status='upcoming',
            details='With details'
        )
        
        launches = [launch_no_date1, launch_no_date2]
        
        result = self.deduplicator.deduplicate_launches(launches)
        
        assert len(result) == 1
        # Should keep the one with more data
        assert result[0].details == 'With details'
    
    def test_find_potential_duplicates(self):
        """Test finding potential duplicates without removing them."""
        launches = [self.launch1, self.launch2, self.launch3]
        
        duplicate_groups = self.deduplicator.find_potential_duplicates(launches)
        
        assert len(duplicate_groups) == 1  # One group of duplicates
        assert len(duplicate_groups[0]) == 2  # Two launches in the group
        assert self.launch1 in duplicate_groups[0]
        assert self.launch2 in duplicate_groups[0]
    
    def test_find_similar_mission_names(self):
        """Test finding launches with similar mission names."""
        launch_similar_name = LaunchData(
            slug='falcon-heavy-demo-2',
            mission_name='Falcon Heavy Demonstration',  # Similar to 'Falcon Heavy Demo'
            launch_date=self.base_date + timedelta(days=30),
            vehicle_type='Falcon Heavy',
            status=LaunchStatus.SUCCESS
        )
        
        launches = [self.launch1, launch_similar_name, self.launch3]
        
        duplicate_groups = self.deduplicator.find_potential_duplicates(launches)
        
        # Should find the similar mission names
        assert len(duplicate_groups) >= 1
        similar_group = next((group for group in duplicate_groups 
                            if self.launch1 in group and launch_similar_name in group), None)
        assert similar_group is not None
    
    def test_completeness_scoring(self):
        """Test completeness scoring for selecting best launch."""
        # Create launches with different levels of completeness
        minimal_launch = LaunchData(
            slug='test-mission',
            mission_name='Test Mission',
            status=LaunchStatus.UPCOMING
        )
        
        complete_launch = LaunchData(
            slug='test-mission',
            mission_name='Test Mission',
            launch_date=self.base_date,
            vehicle_type='Falcon 9',
            payload_mass=5000.0,
            orbit='LEO',
            status=LaunchStatus.UPCOMING,
            details='Complete mission details',
            mission_patch_url='https://example.com/patch.png',
            webcast_url='https://example.com/webcast'
        )
        
        launches = [minimal_launch, complete_launch]
        
        result = self.deduplicator.deduplicate_launches(launches)
        
        assert len(result) == 1
        # Should select the more complete launch
        assert result[0] == complete_launch
    
    def test_date_tolerance_configuration(self):
        """Test different date tolerance configurations."""
        # Test with 1 hour tolerance
        strict_deduplicator = LaunchDeduplicator(date_tolerance_hours=1)
        
        launches = [self.launch1, self.launch2]  # 12 hours apart
        
        result = strict_deduplicator.deduplicate_launches(launches)
        
        # With 1 hour tolerance, these should not be considered duplicates
        assert len(result) == 2
        
        # Test with 48 hour tolerance
        lenient_deduplicator = LaunchDeduplicator(date_tolerance_hours=48)
        
        result = lenient_deduplicator.deduplicate_launches(launches)
        
        # With 48 hour tolerance, these should be considered duplicates
        assert len(result) == 1
    
    def test_mission_name_normalization(self):
        """Test mission name normalization for similarity detection."""
        launch_with_prefix = LaunchData(
            slug='mission-1',
            mission_name='SpaceX Falcon Heavy Demo Mission',
            status=LaunchStatus.SUCCESS
        )
        
        launch_without_prefix = LaunchData(
            slug='mission-2',
            mission_name='Falcon Heavy Demo',
            status=LaunchStatus.SUCCESS
        )
        
        launches = [launch_with_prefix, launch_without_prefix]
        
        duplicate_groups = self.deduplicator.find_potential_duplicates(launches)
        
        # Should find these as similar despite different prefixes
        assert len(duplicate_groups) >= 1
        similar_group = next((group for group in duplicate_groups 
                            if launch_with_prefix in group and launch_without_prefix in group), None)
        assert similar_group is not None
    
    def test_empty_input(self):
        """Test deduplication with empty input."""
        result = self.deduplicator.deduplicate_launches([])
        assert result == []
    
    def test_single_launch(self):
        """Test deduplication with single launch."""
        result = self.deduplicator.deduplicate_launches([self.launch1])
        assert len(result) == 1
        assert result[0] == self.launch1
    
    def test_deduplication_summary(self):
        """Test deduplication summary generation."""
        launches = [self.launch1, self.launch2, self.launch3]
        
        self.deduplicator.deduplicate_launches(launches)
        summary = self.deduplicator.get_deduplication_summary()
        
        assert 'unique_launches' in summary
        assert 'duplicate_groups_found' in summary
        assert 'total_duplicates_in_groups' in summary
        assert 'date_tolerance_hours' in summary
        
        assert summary['unique_launches'] == 2
        assert summary['date_tolerance_hours'] == 24
    
    def test_word_similarity_calculation(self):
        """Test word-based similarity calculation for mission names."""
        # Test cases with different similarity levels
        test_cases = [
            ('Falcon Heavy Demo', 'Falcon Heavy Demonstration', True),  # High similarity
            ('Falcon Heavy Demo', 'Starship Test Flight', False),       # Low similarity
            ('CRS-25 Mission', 'CRS-25 Dragon Mission', True),          # Partial match
            ('Falcon 9 Launch', 'Falcon Heavy Launch', True),           # Some common words
        ]
        
        for name1, name2, should_be_similar in test_cases:
            launch1 = LaunchData(slug='test-1', mission_name=name1, status=LaunchStatus.SUCCESS)
            launch2 = LaunchData(slug='test-2', mission_name=name2, status=LaunchStatus.SUCCESS)
            
            is_similar = self.deduplicator._are_mission_names_similar(name1, name2)
            
            if should_be_similar:
                assert is_similar, f"'{name1}' and '{name2}' should be considered similar"
            else:
                assert not is_similar, f"'{name1}' and '{name2}' should not be considered similar"
    
    def test_date_proximity_grouping(self):
        """Test grouping launches by date proximity."""
        # Create launches with various date differences
        launches = [
            LaunchData(slug='test', mission_name='Test 1', 
                      launch_date=self.base_date, status=LaunchStatus.SUCCESS),
            LaunchData(slug='test', mission_name='Test 2', 
                      launch_date=self.base_date + timedelta(hours=6), status=LaunchStatus.SUCCESS),
            LaunchData(slug='test', mission_name='Test 3', 
                      launch_date=self.base_date + timedelta(days=2), status=LaunchStatus.SUCCESS),
            LaunchData(slug='test', mission_name='Test 4', 
                      launch_date=self.base_date + timedelta(days=2, hours=3), status=LaunchStatus.SUCCESS),
        ]
        
        date_groups = self.deduplicator._group_by_date_proximity(launches)
        
        # Should have 2 groups: first two launches close together, last two close together
        assert len(date_groups) == 2
        assert len(date_groups[0]) == 2  # First group
        assert len(date_groups[1]) == 2  # Second group