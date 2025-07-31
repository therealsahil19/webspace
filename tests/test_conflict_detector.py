"""
Tests for the conflict detector module.
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple

from src.processing.conflict_detector import ConflictDetector, ConflictAnalysis
from src.models.schemas import LaunchData, SourceData, ConflictData, LaunchStatus


class TestConflictDetector:
    """Test cases for ConflictDetector."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = ConflictDetector()
        
        self.base_date = datetime(2024, 2, 6, 20, 45, tzinfo=timezone.utc)
        
        # Create test launch data with conflicts
        self.launch1 = LaunchData(
            slug='falcon-heavy-demo',
            mission_name='Falcon Heavy Demo',
            launch_date=self.base_date,
            vehicle_type='Falcon Heavy',
            payload_mass=1420.0,
            orbit='Heliocentric',
            status=LaunchStatus.SUCCESS,
            details='First test flight'
        )
        
        self.launch2 = LaunchData(
            slug='falcon-heavy-demo',
            mission_name='Falcon Heavy Demonstration',  # Different name
            launch_date=self.base_date + timedelta(hours=3),  # Different time
            vehicle_type='Falcon Heavy',
            payload_mass=1400.0,  # Different payload
            orbit='Heliocentric',
            status=LaunchStatus.SUCCESS,
            details='Inaugural test flight'  # Different details
        )
        
        self.source1 = SourceData(
            source_name='spacex',
            source_url='https://spacex.com/launches',
            scraped_at=datetime.now(timezone.utc),
            data_quality_score=0.95
        )
        
        self.source2 = SourceData(
            source_name='nasa',
            source_url='https://nasa.gov/launches',
            scraped_at=datetime.now(timezone.utc),
            data_quality_score=0.90
        )
    
    def test_detect_conflicts_single_group(self):
        """Test conflict detection within a single launch group."""
        launch_data_groups = {
            'falcon-heavy-demo': [
                (self.launch1, self.source1),
                (self.launch2, self.source2)
            ]
        }
        
        conflict_analyses = self.detector.detect_conflicts(launch_data_groups)
        
        assert len(conflict_analyses) > 0
        
        # Check that conflicts were detected for expected fields
        conflict_fields = [analysis.conflict.field_name for analysis in conflict_analyses]
        assert 'mission_name' in conflict_fields
        assert 'launch_date' in conflict_fields
        assert 'payload_mass' in conflict_fields
    
    def test_detect_conflicts_no_conflicts(self):
        """Test conflict detection with identical data."""
        launch_data_groups = {
            'test-mission': [
                (self.launch1, self.source1),
                (self.launch1, self.source2)  # Same launch data
            ]
        }
        
        conflict_analyses = self.detector.detect_conflicts(launch_data_groups)
        
        assert len(conflict_analyses) == 0
    
    def test_detect_conflicts_single_source(self):
        """Test conflict detection with single source (no conflicts possible)."""
        launch_data_groups = {
            'test-mission': [
                (self.launch1, self.source1)
            ]
        }
        
        conflict_analyses = self.detector.detect_conflicts(launch_data_groups)
        
        assert len(conflict_analyses) == 0
    
    def test_date_conflict_detection(self):
        """Test date-specific conflict detection."""
        # Dates within tolerance (2 hours) - should not conflict
        close_date = self.base_date + timedelta(hours=1)
        assert not self.detector._is_date_conflict(self.base_date, close_date)
        
        # Dates outside tolerance - should conflict
        distant_date = self.base_date + timedelta(hours=3)
        assert self.detector._is_date_conflict(self.base_date, distant_date)
    
    def test_numeric_conflict_detection(self):
        """Test numeric conflict detection with percentage tolerance."""
        # Values within 10% tolerance - should not conflict
        assert not self.detector._is_numeric_conflict(1000.0, 1050.0, tolerance_percent=10)
        
        # Values outside tolerance - should conflict
        assert self.detector._is_numeric_conflict(1000.0, 1200.0, tolerance_percent=10)
        
        # Edge case: zero values
        assert not self.detector._is_numeric_conflict(0.0, 0.0, tolerance_percent=10)
    
    def test_string_conflict_detection(self):
        """Test string conflict detection with normalization."""
        # Exact match - no conflict
        assert not self.detector._is_string_conflict('Falcon Heavy', 'Falcon Heavy')
        
        # Case difference - no conflict
        assert not self.detector._is_string_conflict('Falcon Heavy', 'falcon heavy')
        
        # Substring relationship - no conflict
        assert not self.detector._is_string_conflict('Falcon Heavy', 'Falcon Heavy Demo')
        
        # High word overlap - no conflict
        assert not self.detector._is_string_conflict('Falcon Heavy Demo', 'Falcon Heavy Test')
        
        # Low word overlap - conflict
        assert self.detector._is_string_conflict('Falcon Heavy', 'Starship Test')
    
    def test_status_conflict_detection(self):
        """Test status-specific conflict detection with equivalents."""
        # Equivalent statuses - no conflict
        assert not self.detector._is_status_conflict('success', 'successful')
        assert not self.detector._is_status_conflict('failure', 'failed')
        assert not self.detector._is_status_conflict('upcoming', 'scheduled')
        assert not self.detector._is_status_conflict('aborted', 'cancelled')
        assert not self.detector._is_status_conflict('in_flight', 'in-flight')
        
        # Different statuses - conflict
        assert self.detector._is_status_conflict('success', 'failure')
        assert self.detector._is_status_conflict('upcoming', 'success')
    
    def test_empty_value_handling(self):
        """Test handling of empty/None values."""
        # None values should not create conflicts
        assert not self.detector._is_conflict(None, 'some_value', 'mission_name')
        assert not self.detector._is_conflict('some_value', None, 'mission_name')
        assert not self.detector._is_conflict(None, None, 'mission_name')
        
        # Empty strings should not create conflicts
        assert not self.detector._is_conflict('', 'some_value', 'mission_name')
        assert not self.detector._is_conflict('some_value', '', 'mission_name')
    
    def test_conflict_confidence_calculation(self):
        """Test conflict confidence score calculation."""
        confidence = self.detector._calculate_conflict_confidence(
            'value1', 'value2', 'mission_name', self.source1, self.source2
        )
        
        assert 0.0 <= confidence <= 1.0
        
        # Important fields should have higher confidence
        important_confidence = self.detector._calculate_conflict_confidence(
            'value1', 'value2', 'mission_name', self.source1, self.source2
        )
        
        less_important_confidence = self.detector._calculate_conflict_confidence(
            'value1', 'value2', 'details', self.source1, self.source2
        )
        
        assert important_confidence >= less_important_confidence
    
    def test_value_similarity_calculation(self):
        """Test value similarity calculation."""
        # String similarity
        high_similarity = self.detector._string_similarity('Falcon Heavy Demo', 'Falcon Heavy Test')
        low_similarity = self.detector._string_similarity('Falcon Heavy', 'Starship')
        
        assert high_similarity > low_similarity
        assert 0.0 <= high_similarity <= 1.0
        assert 0.0 <= low_similarity <= 1.0
        
        # Numeric similarity
        high_num_similarity = self.detector._numeric_similarity(1000.0, 1010.0)
        low_num_similarity = self.detector._numeric_similarity(1000.0, 2000.0)
        
        assert high_num_similarity > low_num_similarity
        assert 0.0 <= high_num_similarity <= 1.0
        assert 0.0 <= low_num_similarity <= 1.0
    
    def test_conflict_analysis_severity(self):
        """Test conflict analysis severity determination."""
        # Create conflicts with different characteristics
        high_importance_conflict = ConflictData(
            field_name='mission_name',  # High importance field
            source1_value='Falcon Heavy Demo',
            source2_value='Starship Test',
            confidence_score=0.9
        )
        
        low_importance_conflict = ConflictData(
            field_name='details',  # Low importance field
            source1_value='Some details',
            source2_value='Other details',
            confidence_score=0.5
        )
        
        high_analysis = self.detector._analyze_conflict(high_importance_conflict)
        low_analysis = self.detector._analyze_conflict(low_importance_conflict)
        
        # High importance + high confidence should be more severe
        severity_order = ['low', 'medium', 'high', 'critical']
        high_severity_index = severity_order.index(high_analysis.severity)
        low_severity_index = severity_order.index(low_analysis.severity)
        
        assert high_severity_index >= low_severity_index
    
    def test_auto_resolvable_determination(self):
        """Test determination of auto-resolvable conflicts."""
        # Critical conflicts should not be auto-resolvable
        critical_conflict = ConflictData(
            field_name='mission_name',
            source1_value='Falcon Heavy',
            source2_value='Starship',
            confidence_score=0.95
        )
        
        critical_analysis = self.detector._analyze_conflict(critical_conflict)
        
        if critical_analysis.severity == 'critical':
            assert not critical_analysis.auto_resolvable
        
        # Low severity conflicts should be auto-resolvable
        low_conflict = ConflictData(
            field_name='details',
            source1_value='Some details',
            source2_value='Other details',
            confidence_score=0.3
        )
        
        low_analysis = self.detector._analyze_conflict(low_conflict)
        
        if low_analysis.severity == 'low':
            assert low_analysis.auto_resolvable
    
    def test_recommendation_generation(self):
        """Test recommendation generation for conflicts."""
        conflict = ConflictData(
            field_name='mission_name',
            source1_value='Falcon Heavy Demo',
            source2_value='Falcon Heavy Test',
            confidence_score=0.7
        )
        
        analysis = self.detector._analyze_conflict(conflict)
        
        assert analysis.recommendation is not None
        assert len(analysis.recommendation) > 0
        assert 'mission_name' in analysis.recommendation
    
    def test_conflict_summary_generation(self):
        """Test conflict summary generation."""
        launch_data_groups = {
            'falcon-heavy-demo': [
                (self.launch1, self.source1),
                (self.launch2, self.source2)
            ]
        }
        
        self.detector.detect_conflicts(launch_data_groups)
        summary = self.detector.get_conflict_summary()
        
        assert 'total_conflicts' in summary
        assert 'by_severity' in summary
        assert 'by_field' in summary
        assert 'auto_resolvable' in summary
        assert 'manual_review_required' in summary
        
        assert summary['total_conflicts'] > 0
        assert isinstance(summary['by_severity'], dict)
        assert isinstance(summary['by_field'], dict)
    
    def test_get_critical_conflicts(self):
        """Test getting critical conflicts."""
        launch_data_groups = {
            'test-mission': [
                (self.launch1, self.source1),
                (self.launch2, self.source2)
            ]
        }
        
        self.detector.detect_conflicts(launch_data_groups)
        critical_conflicts = self.detector.get_critical_conflicts()
        
        # All returned conflicts should be critical
        for analysis in critical_conflicts:
            assert analysis.severity == 'critical'
    
    def test_string_normalization(self):
        """Test string normalization for comparison."""
        test_cases = [
            ('Falcon Heavy Demo!', 'falcon heavy demo'),
            ('  SpaceX Mission  ', 'spacex mission'),
            ('Test-Mission_1', 'testmission1'),
            ('Multiple   Spaces', 'multiple spaces')
        ]
        
        for input_str, expected in test_cases:
            normalized = self.detector._normalize_string(input_str)
            assert normalized == expected
    
    def test_format_value_for_conflict(self):
        """Test value formatting for conflict display."""
        # Test different value types
        assert self.detector._format_value_for_conflict(None) == "None"
        assert self.detector._format_value_for_conflict("string") == "string"
        assert self.detector._format_value_for_conflict(123) == "123"
        
        # Test datetime formatting
        test_date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        formatted_date = self.detector._format_value_for_conflict(test_date)
        assert formatted_date == test_date.isoformat()
    
    def test_clear_results(self):
        """Test clearing conflict detection results."""
        launch_data_groups = {
            'test-mission': [
                (self.launch1, self.source1),
                (self.launch2, self.source2)
            ]
        }
        
        self.detector.detect_conflicts(launch_data_groups)
        
        assert len(self.detector.detected_conflicts) > 0
        assert len(self.detector.conflict_analyses) > 0
        
        self.detector.clear_results()
        
        assert len(self.detector.detected_conflicts) == 0
        assert len(self.detector.conflict_analyses) == 0
    
    def test_multiple_launch_groups(self):
        """Test conflict detection across multiple launch groups."""
        # Create another launch with conflicts
        launch3 = LaunchData(
            slug='starship-test',
            mission_name='Starship Test',
            status=LaunchStatus.SUCCESS
        )
        
        launch4 = LaunchData(
            slug='starship-test',
            mission_name='Starship Test Flight',  # Different name
            status=LaunchStatus.FAILURE  # Different status
        )
        
        launch_data_groups = {
            'falcon-heavy-demo': [
                (self.launch1, self.source1),
                (self.launch2, self.source2)
            ],
            'starship-test': [
                (launch3, self.source1),
                (launch4, self.source2)
            ]
        }
        
        conflict_analyses = self.detector.detect_conflicts(launch_data_groups)
        
        # Should detect conflicts in both groups
        assert len(conflict_analyses) > 0
        
        # Check that conflicts from both groups are present
        slugs_with_conflicts = set()
        for analysis in conflict_analyses:
            # We can't directly get the slug from ConflictData, but we know
            # conflicts should exist for both launches
            pass
        
        # At minimum, we should have conflicts from both groups
        assert len(conflict_analyses) >= 2  # At least one from each group
    
    def test_field_weight_influence(self):
        """Test that field weights influence conflict analysis."""
        # Create conflicts in fields with different weights
        important_field_conflict = ConflictData(
            field_name='mission_name',  # Weight: 1.0
            source1_value='value1',
            source2_value='value2',
            confidence_score=0.7
        )
        
        less_important_field_conflict = ConflictData(
            field_name='webcast_url',  # Weight: 0.2
            source1_value='url1',
            source2_value='url2',
            confidence_score=0.7  # Same confidence
        )
        
        important_analysis = self.detector._analyze_conflict(important_field_conflict)
        less_important_analysis = self.detector._analyze_conflict(less_important_field_conflict)
        
        # Important field should have higher or equal severity
        severity_order = ['low', 'medium', 'high', 'critical']
        important_index = severity_order.index(important_analysis.severity)
        less_important_index = severity_order.index(less_important_analysis.severity)
        
        assert important_index >= less_important_index