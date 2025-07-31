"""
Deduplication logic for launch data based on mission slug and launch date.
"""
import logging
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from src.models.schemas import LaunchData

logger = logging.getLogger(__name__)


class LaunchDeduplicator:
    """Handles deduplication of launch data based on mission slug and launch date."""
    
    def __init__(self, date_tolerance_hours: int = 24):
        """
        Initialize the deduplicator.
        
        Args:
            date_tolerance_hours: Hours of tolerance for considering launch dates as duplicates
        """
        self.date_tolerance = timedelta(hours=date_tolerance_hours)
        self.duplicate_groups = []
        self.unique_launches = []
    
    def deduplicate_launches(self, launches: List[LaunchData]) -> List[LaunchData]:
        """
        Remove duplicate launches based on slug and launch date proximity.
        
        Args:
            launches: List of LaunchData objects to deduplicate
            
        Returns:
            List of unique LaunchData objects
        """
        if not launches:
            return []
        
        logger.info(f"Starting deduplication of {len(launches)} launches")
        
        # Group launches by slug first
        slug_groups = self._group_by_slug(launches)
        
        # Within each slug group, check for date-based duplicates
        unique_launches = []
        duplicate_count = 0
        
        for slug, slug_launches in slug_groups.items():
            if len(slug_launches) == 1:
                unique_launches.extend(slug_launches)
            else:
                # Handle multiple launches with same slug
                deduplicated_group, duplicates_found = self._deduplicate_slug_group(slug_launches)
                unique_launches.extend(deduplicated_group)
                duplicate_count += duplicates_found
        
        logger.info(f"Deduplication complete: {len(unique_launches)} unique launches, "
                   f"{duplicate_count} duplicates removed")
        
        self.unique_launches = unique_launches
        return unique_launches
    
    def find_potential_duplicates(self, launches: List[LaunchData]) -> List[List[LaunchData]]:
        """
        Find potential duplicate groups without removing them.
        
        Args:
            launches: List of LaunchData objects to analyze
            
        Returns:
            List of groups where each group contains potential duplicates
        """
        duplicate_groups = []
        
        # Group by slug
        slug_groups = self._group_by_slug(launches)
        
        for slug, slug_launches in slug_groups.items():
            if len(slug_launches) > 1:
                # Check for date-based duplicates within slug group
                date_groups = self._group_by_date_proximity(slug_launches)
                for date_group in date_groups:
                    if len(date_group) > 1:
                        duplicate_groups.append(date_group)
        
        # Also check for similar mission names across different slugs
        name_duplicates = self._find_similar_mission_names(launches)
        duplicate_groups.extend(name_duplicates)
        
        self.duplicate_groups = duplicate_groups
        return duplicate_groups
    
    def _group_by_slug(self, launches: List[LaunchData]) -> Dict[str, List[LaunchData]]:
        """
        Group launches by their slug.
        
        Args:
            launches: List of LaunchData objects
            
        Returns:
            Dictionary mapping slug to list of launches
        """
        slug_groups = defaultdict(list)
        
        for launch in launches:
            slug_groups[launch.slug].append(launch)
        
        return dict(slug_groups)
    
    def _deduplicate_slug_group(self, launches: List[LaunchData]) -> Tuple[List[LaunchData], int]:
        """
        Deduplicate launches within a single slug group.
        
        Args:
            launches: List of launches with the same slug
            
        Returns:
            Tuple of (unique launches, number of duplicates removed)
        """
        if len(launches) <= 1:
            return launches, 0
        
        # Group by date proximity
        date_groups = self._group_by_date_proximity(launches)
        
        unique_launches = []
        duplicates_removed = 0
        
        for date_group in date_groups:
            if len(date_group) == 1:
                unique_launches.extend(date_group)
            else:
                # Multiple launches with same slug and similar dates - keep the best one
                best_launch = self._select_best_launch(date_group)
                unique_launches.append(best_launch)
                duplicates_removed += len(date_group) - 1
                
                logger.debug(f"Removed {len(date_group) - 1} duplicates for slug: {best_launch.slug}")
        
        return unique_launches, duplicates_removed
    
    def _group_by_date_proximity(self, launches: List[LaunchData]) -> List[List[LaunchData]]:
        """
        Group launches by date proximity within tolerance.
        
        Args:
            launches: List of launches to group
            
        Returns:
            List of groups where each group has launches with similar dates
        """
        # Sort by launch date (None dates go to end)
        sorted_launches = sorted(launches, key=lambda x: x.launch_date or datetime.max)
        
        groups = []
        current_group = []
        
        for launch in sorted_launches:
            if not current_group:
                current_group = [launch]
            else:
                # Check if this launch is close enough to the current group
                if self._is_date_similar(launch, current_group[0]):
                    current_group.append(launch)
                else:
                    # Start new group
                    groups.append(current_group)
                    current_group = [launch]
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _is_date_similar(self, launch1: LaunchData, launch2: LaunchData) -> bool:
        """
        Check if two launches have similar dates within tolerance.
        
        Args:
            launch1: First launch to compare
            launch2: Second launch to compare
            
        Returns:
            True if dates are similar or both are None
        """
        date1 = launch1.launch_date
        date2 = launch2.launch_date
        
        # If both dates are None, consider them similar
        if date1 is None and date2 is None:
            return True
        
        # If only one date is None, they're not similar
        if date1 is None or date2 is None:
            return False
        
        # Check if dates are within tolerance
        time_diff = abs(date1 - date2)
        return time_diff <= self.date_tolerance
    
    def _select_best_launch(self, launches: List[LaunchData]) -> LaunchData:
        """
        Select the best launch from a group of duplicates.
        
        Prioritizes launches with:
        1. More complete data (non-null fields)
        2. More recent data (assuming it's more accurate)
        3. Specific launch date over None
        
        Args:
            launches: List of duplicate launches
            
        Returns:
            The best launch from the group
        """
        if len(launches) == 1:
            return launches[0]
        
        # Score each launch based on data completeness
        scored_launches = []
        
        for launch in launches:
            score = self._calculate_completeness_score(launch)
            scored_launches.append((score, launch))
        
        # Sort by score (descending) and return the best one
        scored_launches.sort(key=lambda x: x[0], reverse=True)
        best_launch = scored_launches[0][1]
        
        logger.debug(f"Selected best launch: {best_launch.mission_name} "
                    f"(score: {scored_launches[0][0]})")
        
        return best_launch
    
    def _calculate_completeness_score(self, launch: LaunchData) -> float:
        """
        Calculate a completeness score for a launch based on available data.
        
        Args:
            launch: LaunchData object to score
            
        Returns:
            Completeness score (higher is better)
        """
        score = 0.0
        
        # Required fields (higher weight)
        if launch.slug:
            score += 2.0
        if launch.mission_name:
            score += 2.0
        if launch.status:
            score += 2.0
        
        # Optional but important fields
        if launch.launch_date:
            score += 1.5
        if launch.vehicle_type:
            score += 1.0
        if launch.payload_mass:
            score += 1.0
        if launch.orbit:
            score += 1.0
        if launch.details:
            score += 0.5
        if launch.mission_patch_url:
            score += 0.5
        if launch.webcast_url:
            score += 0.5
        
        return score
    
    def _find_similar_mission_names(self, launches: List[LaunchData]) -> List[List[LaunchData]]:
        """
        Find launches with similar mission names that might be duplicates.
        
        Args:
            launches: List of all launches
            
        Returns:
            List of groups with similar mission names
        """
        similar_groups = []
        processed_indices = set()
        
        for i, launch1 in enumerate(launches):
            if i in processed_indices:
                continue
            
            similar_group = [launch1]
            processed_indices.add(i)
            
            for j, launch2 in enumerate(launches[i+1:], i+1):
                if j in processed_indices:
                    continue
                
                if self._are_mission_names_similar(launch1.mission_name, launch2.mission_name):
                    similar_group.append(launch2)
                    processed_indices.add(j)
            
            if len(similar_group) > 1:
                similar_groups.append(similar_group)
        
        return similar_groups
    
    def _are_mission_names_similar(self, name1: str, name2: str) -> bool:
        """
        Check if two mission names are similar enough to be potential duplicates.
        
        Args:
            name1: First mission name
            name2: Second mission name
            
        Returns:
            True if names are similar
        """
        if not name1 or not name2:
            return False
        
        # Normalize names for comparison
        norm1 = self._normalize_mission_name(name1)
        norm2 = self._normalize_mission_name(name2)
        
        # Exact match after normalization
        if norm1 == norm2:
            return True
        
        # Check for substring matches (one name contains the other)
        if norm1 in norm2 or norm2 in norm1:
            return True
        
        # Check for similar words (simple approach)
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if words1 and words2:
            # If most words are the same, consider similar
            common_words = words1.intersection(words2)
            similarity_ratio = len(common_words) / max(len(words1), len(words2))
            return similarity_ratio >= 0.7
        
        return False
    
    def _normalize_mission_name(self, name: str) -> str:
        """
        Normalize mission name for comparison.
        
        Args:
            name: Mission name to normalize
            
        Returns:
            Normalized mission name
        """
        import re
        
        # Convert to lowercase
        normalized = name.lower()
        
        # Remove common prefixes/suffixes
        normalized = re.sub(r'^(spacex\s+|mission\s+)', '', normalized)
        normalized = re.sub(r'\s+(mission|launch)$', '', normalized)
        
        # Remove special characters and extra spaces
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = normalized.strip()
        
        return normalized
    
    def get_deduplication_summary(self) -> Dict[str, any]:
        """
        Get summary of deduplication results.
        
        Returns:
            Dictionary with deduplication statistics
        """
        return {
            'unique_launches': len(self.unique_launches),
            'duplicate_groups_found': len(self.duplicate_groups),
            'total_duplicates_in_groups': sum(len(group) for group in self.duplicate_groups),
            'date_tolerance_hours': self.date_tolerance.total_seconds() / 3600
        }