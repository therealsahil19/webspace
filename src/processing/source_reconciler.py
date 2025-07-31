"""
Source reconciliation system that prioritizes SpaceX official data and handles conflicts.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from enum import Enum

from src.models.schemas import LaunchData, SourceData, ConflictData

logger = logging.getLogger(__name__)


class SourcePriority(Enum):
    """Source priority levels for data reconciliation."""
    SPACEX_OFFICIAL = 1      # SpaceX website - highest priority
    NASA_OFFICIAL = 2        # NASA official pages
    SPACEX_PRESS_KIT = 3     # SpaceX press kits/PDFs
    WIKIPEDIA = 4            # Wikipedia - lowest priority
    UNKNOWN = 5              # Unknown sources


class SourceReconciler:
    """Reconciles launch data from multiple sources with conflict detection."""
    
    def __init__(self):
        """Initialize the source reconciler."""
        self.source_priorities = {
            'spacex': SourcePriority.SPACEX_OFFICIAL,
            'spacex.com': SourcePriority.SPACEX_OFFICIAL,
            'nasa': SourcePriority.NASA_OFFICIAL,
            'nasa.gov': SourcePriority.NASA_OFFICIAL,
            'spacex_press_kit': SourcePriority.SPACEX_PRESS_KIT,
            'wikipedia': SourcePriority.WIKIPEDIA,
            'wikipedia.org': SourcePriority.WIKIPEDIA,
        }
        self.conflicts_detected = []
        self.reconciliation_log = []
    
    def reconcile_launch_data(
        self, 
        launch_data_list: List[Tuple[LaunchData, SourceData]]
    ) -> Tuple[LaunchData, List[ConflictData]]:
        """
        Reconcile launch data from multiple sources.
        
        Args:
            launch_data_list: List of tuples containing (LaunchData, SourceData)
            
        Returns:
            Tuple of (reconciled LaunchData, list of conflicts detected)
        """
        if not launch_data_list:
            raise ValueError("No launch data provided for reconciliation")
        
        if len(launch_data_list) == 1:
            # Single source, no reconciliation needed
            launch_data, source_data = launch_data_list[0]
            logger.debug(f"Single source for {launch_data.mission_name}: {source_data.source_name}")
            return launch_data, []
        
        logger.info(f"Reconciling {len(launch_data_list)} sources for launch data")
        
        # Sort sources by priority
        sorted_sources = self._sort_by_priority(launch_data_list)
        
        # Start with highest priority source as base
        base_launch, base_source = sorted_sources[0]
        conflicts = []
        
        # Compare with other sources and detect conflicts
        for launch_data, source_data in sorted_sources[1:]:
            field_conflicts = self._detect_conflicts(base_launch, launch_data, base_source, source_data)
            conflicts.extend(field_conflicts)
        
        # Apply reconciliation rules to resolve conflicts
        reconciled_launch = self._apply_reconciliation_rules(sorted_sources, conflicts)
        
        # Log reconciliation results
        self._log_reconciliation(reconciled_launch, sorted_sources, conflicts)
        
        self.conflicts_detected.extend(conflicts)
        return reconciled_launch, conflicts
    
    def reconcile_multiple_launches(
        self, 
        launches_by_slug: Dict[str, List[Tuple[LaunchData, SourceData]]]
    ) -> Dict[str, Tuple[LaunchData, List[ConflictData]]]:
        """
        Reconcile multiple launches grouped by slug.
        
        Args:
            launches_by_slug: Dictionary mapping slug to list of (LaunchData, SourceData) tuples
            
        Returns:
            Dictionary mapping slug to (reconciled LaunchData, conflicts)
        """
        reconciled_launches = {}
        
        for slug, launch_data_list in launches_by_slug.items():
            try:
                reconciled_launch, conflicts = self.reconcile_launch_data(launch_data_list)
                reconciled_launches[slug] = (reconciled_launch, conflicts)
            except Exception as e:
                logger.error(f"Failed to reconcile launch {slug}: {e}")
                # Use the highest priority source as fallback
                if launch_data_list:
                    sorted_sources = self._sort_by_priority(launch_data_list)
                    fallback_launch, _ = sorted_sources[0]
                    reconciled_launches[slug] = (fallback_launch, [])
        
        return reconciled_launches
    
    def _sort_by_priority(
        self, 
        launch_data_list: List[Tuple[LaunchData, SourceData]]
    ) -> List[Tuple[LaunchData, SourceData]]:
        """
        Sort launch data by source priority.
        
        Args:
            launch_data_list: List of (LaunchData, SourceData) tuples
            
        Returns:
            Sorted list with highest priority sources first
        """
        def get_priority(item):
            _, source_data = item
            priority = self._get_source_priority(source_data.source_name)
            # Also consider data quality score as secondary sort
            return (priority.value, -source_data.data_quality_score)
        
        return sorted(launch_data_list, key=get_priority)
    
    def _get_source_priority(self, source_name: str) -> SourcePriority:
        """
        Get priority level for a source.
        
        Args:
            source_name: Name of the data source
            
        Returns:
            SourcePriority enum value
        """
        source_lower = source_name.lower()
        
        for key, priority in self.source_priorities.items():
            if key in source_lower:
                return priority
        
        return SourcePriority.UNKNOWN
    
    def _detect_conflicts(
        self, 
        launch1: LaunchData, 
        launch2: LaunchData,
        source1: SourceData,
        source2: SourceData
    ) -> List[ConflictData]:
        """
        Detect conflicts between two launch data objects.
        
        Args:
            launch1: First launch data object
            launch2: Second launch data object
            source1: Source data for first launch
            source2: Source data for second launch
            
        Returns:
            List of detected conflicts
        """
        conflicts = []
        
        # Fields to check for conflicts
        comparable_fields = [
            'mission_name', 'launch_date', 'vehicle_type', 
            'payload_mass', 'orbit', 'status', 'details'
        ]
        
        for field in comparable_fields:
            value1 = getattr(launch1, field)
            value2 = getattr(launch2, field)
            
            if self._values_conflict(value1, value2, field):
                confidence_score = self._calculate_conflict_confidence(
                    value1, value2, field, source1, source2
                )
                
                conflict = ConflictData(
                    field_name=field,
                    source1_value=str(value1) if value1 is not None else "None",
                    source2_value=str(value2) if value2 is not None else "None",
                    confidence_score=confidence_score
                )
                
                conflicts.append(conflict)
                logger.debug(f"Conflict detected in {field}: '{value1}' vs '{value2}'")
        
        return conflicts
    
    def _values_conflict(self, value1: Any, value2: Any, field_name: str) -> bool:
        """
        Check if two values represent a conflict.
        
        Args:
            value1: First value
            value2: Second value
            field_name: Name of the field being compared
            
        Returns:
            True if values conflict
        """
        # If either value is None, no conflict
        if value1 is None or value2 is None:
            return False
        
        # Special handling for different field types
        if field_name == 'launch_date':
            return self._dates_conflict(value1, value2)
        elif field_name == 'payload_mass':
            return self._numeric_values_conflict(value1, value2, tolerance=0.1)
        elif field_name in ['mission_name', 'vehicle_type', 'orbit']:
            return self._string_values_conflict(value1, value2)
        else:
            # Default comparison
            return str(value1).strip() != str(value2).strip()
    
    def _dates_conflict(self, date1: datetime, date2: datetime) -> bool:
        """Check if two dates conflict (allowing small tolerance)."""
        if not isinstance(date1, datetime) or not isinstance(date2, datetime):
            return str(date1) != str(date2)
        
        # Allow 1 hour tolerance for date conflicts
        time_diff = abs((date1 - date2).total_seconds())
        return time_diff > 3600  # 1 hour in seconds
    
    def _numeric_values_conflict(self, val1: float, val2: float, tolerance: float = 0.1) -> bool:
        """Check if two numeric values conflict within tolerance."""
        try:
            num1 = float(val1)
            num2 = float(val2)
            
            # Calculate relative difference
            if num1 == 0 and num2 == 0:
                return False
            
            max_val = max(abs(num1), abs(num2))
            if max_val == 0:
                return False
            
            relative_diff = abs(num1 - num2) / max_val
            return relative_diff > tolerance
        except (ValueError, TypeError):
            return str(val1) != str(val2)
    
    def _string_values_conflict(self, str1: str, str2: str) -> bool:
        """Check if two string values conflict (with normalization)."""
        # Normalize strings for comparison
        norm1 = str(str1).strip().lower()
        norm2 = str(str2).strip().lower()
        
        # Exact match
        if norm1 == norm2:
            return False
        
        # Check if one is contained in the other (might be abbreviation)
        if norm1 in norm2 or norm2 in norm1:
            return False
        
        return True
    
    def _calculate_conflict_confidence(
        self, 
        value1: Any, 
        value2: Any, 
        field_name: str,
        source1: SourceData,
        source2: SourceData
    ) -> float:
        """
        Calculate confidence score for a detected conflict.
        
        Args:
            value1: First conflicting value
            value2: Second conflicting value
            field_name: Name of the conflicting field
            source1: First source data
            source2: Second source data
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        base_confidence = 0.5
        
        # Adjust based on source priorities
        priority1 = self._get_source_priority(source1.source_name)
        priority2 = self._get_source_priority(source2.source_name)
        
        if priority1.value < priority2.value:  # source1 has higher priority
            base_confidence += 0.2
        elif priority2.value < priority1.value:  # source2 has higher priority
            base_confidence += 0.2
        
        # Adjust based on data quality scores
        quality_diff = abs(source1.data_quality_score - source2.data_quality_score)
        base_confidence += quality_diff * 0.2
        
        # Adjust based on field importance
        important_fields = ['mission_name', 'launch_date', 'status']
        if field_name in important_fields:
            base_confidence += 0.1
        
        return min(1.0, base_confidence)
    
    def _apply_reconciliation_rules(
        self, 
        sorted_sources: List[Tuple[LaunchData, SourceData]],
        conflicts: List[ConflictData]
    ) -> LaunchData:
        """
        Apply reconciliation rules to create final launch data.
        
        Args:
            sorted_sources: Sources sorted by priority
            conflicts: List of detected conflicts
            
        Returns:
            Reconciled LaunchData object
        """
        # Start with highest priority source
        base_launch, base_source = sorted_sources[0]
        
        # Create a copy to modify
        reconciled_data = base_launch.dict()
        
        # Apply field-specific reconciliation rules
        for launch_data, source_data in sorted_sources[1:]:
            self._apply_field_reconciliation(reconciled_data, launch_data, source_data, base_source)
        
        # Create new LaunchData object with reconciled data
        return LaunchData(**reconciled_data)
    
    def _apply_field_reconciliation(
        self, 
        reconciled_data: Dict[str, Any], 
        source_launch: LaunchData,
        source_data: SourceData,
        base_source: SourceData
    ) -> None:
        """
        Apply field-specific reconciliation rules.
        
        Args:
            reconciled_data: Dictionary of reconciled data to modify
            source_launch: Launch data from current source
            source_data: Current source metadata
            base_source: Base source metadata
        """
        # Fill in missing fields from lower priority sources
        for field in reconciled_data:
            current_value = reconciled_data[field]
            source_value = getattr(source_launch, field)
            
            # If current value is None/empty and source has value, use source value
            if (current_value is None or current_value == "") and source_value is not None:
                reconciled_data[field] = source_value
                logger.debug(f"Filled missing {field} from {source_data.source_name}")
        
        # Special rules for specific fields
        self._apply_special_reconciliation_rules(reconciled_data, source_launch, source_data)
    
    def _apply_special_reconciliation_rules(
        self, 
        reconciled_data: Dict[str, Any], 
        source_launch: LaunchData,
        source_data: SourceData
    ) -> None:
        """
        Apply special reconciliation rules for specific fields.
        
        Args:
            reconciled_data: Dictionary of reconciled data to modify
            source_launch: Launch data from current source
            source_data: Current source metadata
        """
        # For details field, prefer longer/more detailed descriptions
        if source_launch.details and len(str(source_launch.details)) > len(str(reconciled_data.get('details', ''))):
            reconciled_data['details'] = source_launch.details
        
        # For URLs, prefer non-None values
        url_fields = ['mission_patch_url', 'webcast_url']
        for field in url_fields:
            source_value = getattr(source_launch, field)
            if source_value and not reconciled_data.get(field):
                reconciled_data[field] = source_value
    
    def _log_reconciliation(
        self, 
        reconciled_launch: LaunchData,
        sources: List[Tuple[LaunchData, SourceData]],
        conflicts: List[ConflictData]
    ) -> None:
        """
        Log reconciliation results.
        
        Args:
            reconciled_launch: Final reconciled launch data
            sources: List of source data used
            conflicts: List of conflicts detected
        """
        log_entry = {
            'mission_name': reconciled_launch.mission_name,
            'slug': reconciled_launch.slug,
            'sources_used': [source.source_name for _, source in sources],
            'conflicts_count': len(conflicts),
            'reconciled_at': datetime.now()
        }
        
        self.reconciliation_log.append(log_entry)
        
        logger.info(f"Reconciled {reconciled_launch.mission_name} from {len(sources)} sources "
                   f"with {len(conflicts)} conflicts")
    
    def get_reconciliation_summary(self) -> Dict[str, Any]:
        """
        Get summary of reconciliation results.
        
        Returns:
            Dictionary with reconciliation statistics
        """
        return {
            'total_conflicts_detected': len(self.conflicts_detected),
            'launches_reconciled': len(self.reconciliation_log),
            'conflicts_by_field': self._get_conflicts_by_field(),
            'sources_by_priority': self._get_source_priority_stats()
        }
    
    def _get_conflicts_by_field(self) -> Dict[str, int]:
        """Get count of conflicts by field name."""
        field_counts = {}
        for conflict in self.conflicts_detected:
            field_counts[conflict.field_name] = field_counts.get(conflict.field_name, 0) + 1
        return field_counts
    
    def _get_source_priority_stats(self) -> Dict[str, int]:
        """Get statistics on source priorities used."""
        priority_counts = {}
        for log_entry in self.reconciliation_log:
            for source_name in log_entry['sources_used']:
                priority = self._get_source_priority(source_name)
                priority_name = priority.name
                priority_counts[priority_name] = priority_counts.get(priority_name, 0) + 1
        return priority_counts
    
    def clear_results(self) -> None:
        """Clear reconciliation results for next batch."""
        self.conflicts_detected.clear()
        self.reconciliation_log.clear()