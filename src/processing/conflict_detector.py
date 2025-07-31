"""
Conflict detection and flagging for discrepant data between sources.
"""
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from dataclasses import dataclass

from src.models.schemas import LaunchData, SourceData, ConflictData

logger = logging.getLogger(__name__)


@dataclass
class ConflictAnalysis:
    """Analysis results for a detected conflict."""
    conflict: ConflictData
    severity: str  # 'low', 'medium', 'high', 'critical'
    recommendation: str
    auto_resolvable: bool


class ConflictDetector:
    """Detects and analyzes conflicts between launch data from different sources."""
    
    def __init__(self):
        """Initialize the conflict detector."""
        self.detected_conflicts = []
        self.conflict_analyses = []
        self.field_weights = {
            'mission_name': 1.0,
            'launch_date': 0.9,
            'status': 0.8,
            'vehicle_type': 0.7,
            'payload_mass': 0.6,
            'orbit': 0.5,
            'details': 0.3,
            'mission_patch_url': 0.2,
            'webcast_url': 0.2
        }
    
    def detect_conflicts(
        self, 
        launch_data_groups: Dict[str, List[Tuple[LaunchData, SourceData]]]
    ) -> List[ConflictAnalysis]:
        """
        Detect conflicts across all launch data groups.
        
        Args:
            launch_data_groups: Dictionary mapping slug to list of (LaunchData, SourceData)
            
        Returns:
            List of conflict analyses
        """
        all_conflicts = []
        
        for slug, launch_data_list in launch_data_groups.items():
            if len(launch_data_list) < 2:
                continue  # No conflicts possible with single source
            
            conflicts = self._detect_conflicts_in_group(slug, launch_data_list)
            all_conflicts.extend(conflicts)
        
        # Analyze conflicts for severity and recommendations
        conflict_analyses = []
        for conflict in all_conflicts:
            analysis = self._analyze_conflict(conflict)
            conflict_analyses.append(analysis)
        
        self.detected_conflicts = all_conflicts
        self.conflict_analyses = conflict_analyses
        
        logger.info(f"Detected {len(all_conflicts)} conflicts across {len(launch_data_groups)} launch groups")
        
        return conflict_analyses
    
    def _detect_conflicts_in_group(
        self, 
        slug: str, 
        launch_data_list: List[Tuple[LaunchData, SourceData]]
    ) -> List[ConflictData]:
        """
        Detect conflicts within a single launch group.
        
        Args:
            slug: Launch slug
            launch_data_list: List of (LaunchData, SourceData) tuples
            
        Returns:
            List of detected conflicts
        """
        conflicts = []
        
        # Compare each pair of sources
        for i in range(len(launch_data_list)):
            for j in range(i + 1, len(launch_data_list)):
                launch1, source1 = launch_data_list[i]
                launch2, source2 = launch_data_list[j]
                
                pair_conflicts = self._compare_launch_data(launch1, launch2, source1, source2)
                conflicts.extend(pair_conflicts)
        
        logger.debug(f"Found {len(conflicts)} conflicts for launch {slug}")
        return conflicts
    
    def _compare_launch_data(
        self, 
        launch1: LaunchData, 
        launch2: LaunchData,
        source1: SourceData,
        source2: SourceData
    ) -> List[ConflictData]:
        """
        Compare two launch data objects and detect conflicts.
        
        Args:
            launch1: First launch data
            launch2: Second launch data
            source1: First source data
            source2: Second source data
            
        Returns:
            List of conflicts between the two launches
        """
        conflicts = []
        
        # Check each field for conflicts
        for field_name in self.field_weights.keys():
            value1 = getattr(launch1, field_name)
            value2 = getattr(launch2, field_name)
            
            if self._is_conflict(value1, value2, field_name):
                confidence = self._calculate_conflict_confidence(
                    value1, value2, field_name, source1, source2
                )
                
                conflict = ConflictData(
                    field_name=field_name,
                    source1_value=self._format_value_for_conflict(value1),
                    source2_value=self._format_value_for_conflict(value2),
                    confidence_score=confidence
                )
                
                conflicts.append(conflict)
        
        return conflicts
    
    def _is_conflict(self, value1: Any, value2: Any, field_name: str) -> bool:
        """
        Determine if two values represent a conflict.
        
        Args:
            value1: First value
            value2: Second value
            field_name: Name of the field
            
        Returns:
            True if values conflict
        """
        # Skip if either value is None/empty
        if self._is_empty_value(value1) or self._is_empty_value(value2):
            return False
        
        # Field-specific conflict detection
        if field_name == 'launch_date':
            return self._is_date_conflict(value1, value2)
        elif field_name == 'payload_mass':
            return self._is_numeric_conflict(value1, value2, tolerance_percent=10)
        elif field_name in ['mission_name', 'vehicle_type', 'orbit']:
            return self._is_string_conflict(value1, value2)
        elif field_name == 'status':
            return self._is_status_conflict(value1, value2)
        else:
            # Default string comparison
            return str(value1).strip() != str(value2).strip()
    
    def _is_empty_value(self, value: Any) -> bool:
        """Check if a value is considered empty."""
        return value is None or (isinstance(value, str) and not value.strip())
    
    def _is_date_conflict(self, date1: datetime, date2: datetime) -> bool:
        """Check if two dates conflict (allowing reasonable tolerance)."""
        if not isinstance(date1, datetime) or not isinstance(date2, datetime):
            return str(date1) != str(date2)
        
        # Allow 2 hours tolerance for launch dates
        time_diff = abs((date1 - date2).total_seconds())
        return time_diff > 7200  # 2 hours in seconds
    
    def _is_numeric_conflict(self, val1: float, val2: float, tolerance_percent: float = 5) -> bool:
        """Check if two numeric values conflict within percentage tolerance."""
        try:
            num1 = float(val1)
            num2 = float(val2)
            
            if num1 == 0 and num2 == 0:
                return False
            
            # Calculate percentage difference
            avg_val = (abs(num1) + abs(num2)) / 2
            if avg_val == 0:
                return False
            
            percent_diff = abs(num1 - num2) / avg_val * 100
            return percent_diff > tolerance_percent
            
        except (ValueError, TypeError):
            return str(val1) != str(val2)
    
    def _is_string_conflict(self, str1: str, str2: str) -> bool:
        """Check if two strings conflict with normalization and fuzzy matching."""
        # Normalize strings
        norm1 = self._normalize_string(str1)
        norm2 = self._normalize_string(str2)
        
        # Exact match
        if norm1 == norm2:
            return False
        
        # Check for substring relationships
        if norm1 in norm2 or norm2 in norm1:
            return False
        
        # Check for similar words (simple fuzzy matching)
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if words1 and words2:
            common_words = words1.intersection(words2)
            similarity = len(common_words) / max(len(words1), len(words2))
            # If 70% or more words are common, not a conflict
            return similarity < 0.7
        
        return True
    
    def _is_status_conflict(self, status1: str, status2: str) -> bool:
        """Check if two status values conflict with status equivalence."""
        # Normalize status values
        status_equivalents = {
            'success': ['successful', 'completed'],
            'failure': ['failed', 'unsuccessful'],
            'upcoming': ['scheduled', 'planned'],
            'aborted': ['cancelled', 'canceled', 'scrubbed'],
            'in_flight': ['in-flight', 'active', 'flying']
        }
        
        norm1 = str(status1).lower().strip()
        norm2 = str(status2).lower().strip()
        
        # Direct match
        if norm1 == norm2:
            return False
        
        # Check equivalents
        for canonical, equivalents in status_equivalents.items():
            group = [canonical] + equivalents
            if norm1 in group and norm2 in group:
                return False
        
        return True
    
    def _normalize_string(self, text: str) -> str:
        """Normalize string for comparison."""
        import re
        
        if not text:
            return ""
        
        # Convert to lowercase
        normalized = text.lower()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove common punctuation
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        return normalized.strip()
    
    def _calculate_conflict_confidence(
        self, 
        value1: Any, 
        value2: Any, 
        field_name: str,
        source1: SourceData,
        source2: SourceData
    ) -> float:
        """
        Calculate confidence score for a conflict.
        
        Args:
            value1: First conflicting value
            value2: Second conflicting value
            field_name: Field name
            source1: First source
            source2: Second source
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        base_confidence = 0.6
        
        # Adjust based on field importance
        field_weight = self.field_weights.get(field_name, 0.5)
        base_confidence += (field_weight - 0.5) * 0.2
        
        # Adjust based on source quality difference
        quality_diff = abs(source1.data_quality_score - source2.data_quality_score)
        base_confidence += quality_diff * 0.1
        
        # Adjust based on value similarity (less similar = higher confidence)
        similarity = self._calculate_value_similarity(value1, value2, field_name)
        base_confidence += (1.0 - similarity) * 0.2
        
        return min(1.0, max(0.0, base_confidence))
    
    def _calculate_value_similarity(self, value1: Any, value2: Any, field_name: str) -> float:
        """Calculate similarity between two values (0.0 = completely different, 1.0 = identical)."""
        if field_name in ['mission_name', 'vehicle_type', 'orbit']:
            return self._string_similarity(str(value1), str(value2))
        elif field_name == 'payload_mass':
            return self._numeric_similarity(value1, value2)
        else:
            # Default: exact match or not
            return 1.0 if str(value1) == str(value2) else 0.0
    
    def _string_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using simple word overlap."""
        words1 = set(self._normalize_string(str1).split())
        words2 = set(self._normalize_string(str2).split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _numeric_similarity(self, val1: Any, val2: Any) -> float:
        """Calculate numeric similarity."""
        try:
            num1 = float(val1)
            num2 = float(val2)
            
            if num1 == num2:
                return 1.0
            
            # Calculate relative difference
            max_val = max(abs(num1), abs(num2))
            if max_val == 0:
                return 1.0
            
            relative_diff = abs(num1 - num2) / max_val
            return max(0.0, 1.0 - relative_diff)
            
        except (ValueError, TypeError):
            return 1.0 if str(val1) == str(val2) else 0.0
    
    def _format_value_for_conflict(self, value: Any) -> str:
        """Format a value for display in conflict data."""
        if value is None:
            return "None"
        elif isinstance(value, datetime):
            return value.isoformat()
        else:
            return str(value)
    
    def _analyze_conflict(self, conflict: ConflictData) -> ConflictAnalysis:
        """
        Analyze a conflict to determine severity and recommendations.
        
        Args:
            conflict: ConflictData object to analyze
            
        Returns:
            ConflictAnalysis with severity and recommendations
        """
        field_name = conflict.field_name
        confidence = conflict.confidence_score
        
        # Determine severity based on field importance and confidence
        field_weight = self.field_weights.get(field_name, 0.5)
        severity_score = field_weight * confidence
        
        if severity_score >= 0.8:
            severity = 'critical'
        elif severity_score >= 0.6:
            severity = 'high'
        elif severity_score >= 0.4:
            severity = 'medium'
        else:
            severity = 'low'
        
        # Generate recommendation
        recommendation = self._generate_recommendation(conflict, severity)
        
        # Determine if auto-resolvable
        auto_resolvable = self._is_auto_resolvable(conflict, severity)
        
        return ConflictAnalysis(
            conflict=conflict,
            severity=severity,
            recommendation=recommendation,
            auto_resolvable=auto_resolvable
        )
    
    def _generate_recommendation(self, conflict: ConflictData, severity: str) -> str:
        """Generate recommendation for resolving a conflict."""
        field_name = conflict.field_name
        
        if severity == 'critical':
            return f"Manual review required for {field_name} conflict. Values significantly different."
        elif severity == 'high':
            return f"Prioritize higher-quality source for {field_name}. Consider manual verification."
        elif severity == 'medium':
            return f"Use source priority rules for {field_name}. Monitor for pattern."
        else:
            return f"Auto-resolve using highest priority source for {field_name}."
    
    def _is_auto_resolvable(self, conflict: ConflictData, severity: str) -> bool:
        """Determine if a conflict can be automatically resolved."""
        # Critical conflicts should not be auto-resolved
        if severity == 'critical':
            return False
        
        # High severity conflicts in important fields should be reviewed
        important_fields = ['mission_name', 'launch_date', 'status']
        if severity == 'high' and conflict.field_name in important_fields:
            return False
        
        # Other conflicts can be auto-resolved using priority rules
        return True
    
    def get_conflict_summary(self) -> Dict[str, Any]:
        """
        Get summary of conflict detection results.
        
        Returns:
            Dictionary with conflict statistics
        """
        if not self.conflict_analyses:
            return {
                'total_conflicts': 0,
                'by_severity': {},
                'by_field': {},
                'auto_resolvable': 0,
                'manual_review_required': 0
            }
        
        severity_counts = {}
        field_counts = {}
        auto_resolvable = 0
        
        for analysis in self.conflict_analyses:
            # Count by severity
            severity = analysis.severity
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Count by field
            field = analysis.conflict.field_name
            field_counts[field] = field_counts.get(field, 0) + 1
            
            # Count auto-resolvable
            if analysis.auto_resolvable:
                auto_resolvable += 1
        
        return {
            'total_conflicts': len(self.conflict_analyses),
            'by_severity': severity_counts,
            'by_field': field_counts,
            'auto_resolvable': auto_resolvable,
            'manual_review_required': len(self.conflict_analyses) - auto_resolvable
        }
    
    def get_critical_conflicts(self) -> List[ConflictAnalysis]:
        """Get list of critical conflicts that require immediate attention."""
        return [analysis for analysis in self.conflict_analyses if analysis.severity == 'critical']
    
    def clear_results(self) -> None:
        """Clear conflict detection results for next batch."""
        self.detected_conflicts.clear()
        self.conflict_analyses.clear()