"""
Main data processing pipeline that orchestrates validation, deduplication, and reconciliation.
"""
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from collections import defaultdict

from src.models.schemas import LaunchData, SourceData, ConflictData
from src.processing.data_validator import LaunchDataValidator, DataValidationError
from src.processing.deduplicator import LaunchDeduplicator
from src.processing.source_reconciler import SourceReconciler
from src.processing.conflict_detector import ConflictDetector, ConflictAnalysis

logger = logging.getLogger(__name__)


class DataProcessingResult:
    """Container for data processing results."""
    
    def __init__(self):
        self.processed_launches: List[LaunchData] = []
        self.conflicts: List[ConflictData] = []
        self.conflict_analyses: List[ConflictAnalysis] = []
        self.validation_errors: List[str] = []
        self.processing_stats: Dict[str, Any] = {}
        self.processing_time: Optional[float] = None


class DataProcessingPipeline:
    """Main data processing pipeline for launch data."""
    
    def __init__(self, 
                 date_tolerance_hours: int = 24,
                 enable_conflict_detection: bool = True,
                 enable_deduplication: bool = True):
        """
        Initialize the data processing pipeline.
        
        Args:
            date_tolerance_hours: Hours of tolerance for date-based deduplication
            enable_conflict_detection: Whether to enable conflict detection
            enable_deduplication: Whether to enable deduplication
        """
        self.validator = LaunchDataValidator()
        self.deduplicator = LaunchDeduplicator(date_tolerance_hours)
        self.reconciler = SourceReconciler()
        self.conflict_detector = ConflictDetector()
        
        self.enable_conflict_detection = enable_conflict_detection
        self.enable_deduplication = enable_deduplication
        
        self.processing_history = []
    
    def process_scraped_data(self, 
                           raw_data_with_sources: List[Tuple[Dict[str, Any], Dict[str, Any]]]) -> DataProcessingResult:
        """
        Process scraped data through the complete pipeline.
        
        Args:
            raw_data_with_sources: List of tuples containing (raw_launch_data, raw_source_data)
            
        Returns:
            DataProcessingResult with processed launches and metadata
        """
        start_time = datetime.now()
        result = DataProcessingResult()
        
        logger.info(f"Starting data processing pipeline with {len(raw_data_with_sources)} raw records")
        
        try:
            # Step 1: Validate raw data
            validated_data = self._validate_raw_data(raw_data_with_sources, result)
            
            if not validated_data:
                logger.warning("No valid data after validation step")
                result.processing_time = (datetime.now() - start_time).total_seconds()
                return result
            
            # Step 2: Group by launch slug for processing
            grouped_data = self._group_by_slug(validated_data)
            
            # Step 3: Detect conflicts (if enabled)
            if self.enable_conflict_detection:
                conflict_analyses = self.conflict_detector.detect_conflicts(grouped_data)
                result.conflict_analyses = conflict_analyses
                result.conflicts = [analysis.conflict for analysis in conflict_analyses]
            
            # Step 4: Reconcile data from multiple sources
            reconciled_data = self._reconcile_grouped_data(grouped_data, result)
            
            # Step 5: Deduplicate launches (if enabled)
            if self.enable_deduplication:
                final_launches = self.deduplicator.deduplicate_launches(reconciled_data)
            else:
                final_launches = reconciled_data
            
            result.processed_launches = final_launches
            
            # Step 6: Generate processing statistics
            result.processing_stats = self._generate_processing_stats(
                len(raw_data_with_sources), 
                len(validated_data),
                len(reconciled_data),
                len(final_launches),
                result
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            result.processing_time = processing_time
            
            # Log processing summary
            self._log_processing_summary(result)
            
            # Store in processing history
            self.processing_history.append({
                'timestamp': start_time,
                'input_count': len(raw_data_with_sources),
                'output_count': len(final_launches),
                'conflicts_detected': len(result.conflicts),
                'processing_time': processing_time
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Data processing pipeline failed: {e}")
            result.validation_errors.append(f"Pipeline error: {str(e)}")
            result.processing_time = (datetime.now() - start_time).total_seconds()
            return result
    
    def _validate_raw_data(self, 
                          raw_data_with_sources: List[Tuple[Dict[str, Any], Dict[str, Any]]],
                          result: DataProcessingResult) -> List[Tuple[LaunchData, SourceData]]:
        """
        Validate raw data using Pydantic schemas.
        
        Args:
            raw_data_with_sources: Raw data tuples
            result: Result object to update with validation errors
            
        Returns:
            List of validated (LaunchData, SourceData) tuples
        """
        validated_data = []
        
        for raw_launch_data, raw_source_data in raw_data_with_sources:
            try:
                # Validate launch data
                launch_data = self.validator.validate_launch_data(raw_launch_data)
                if not launch_data:
                    continue
                
                # Validate source data
                source_data = self.validator.validate_source_data(raw_source_data)
                if not source_data:
                    continue
                
                validated_data.append((launch_data, source_data))
                
            except Exception as e:
                error_msg = f"Validation failed for {raw_launch_data.get('mission_name', 'unknown')}: {e}"
                logger.error(error_msg)
                result.validation_errors.append(error_msg)
        
        # Collect validation summary
        validation_summary = self.validator.get_validation_summary()
        result.validation_errors.extend(validation_summary['errors'])
        
        logger.info(f"Validated {len(validated_data)} out of {len(raw_data_with_sources)} records")
        
        return validated_data
    
    def _group_by_slug(self, 
                      validated_data: List[Tuple[LaunchData, SourceData]]) -> Dict[str, List[Tuple[LaunchData, SourceData]]]:
        """
        Group validated data by launch slug.
        
        Args:
            validated_data: List of validated (LaunchData, SourceData) tuples
            
        Returns:
            Dictionary mapping slug to list of data tuples
        """
        grouped_data = defaultdict(list)
        
        for launch_data, source_data in validated_data:
            grouped_data[launch_data.slug].append((launch_data, source_data))
        
        logger.debug(f"Grouped data into {len(grouped_data)} unique launch slugs")
        
        return dict(grouped_data)
    
    def _reconcile_grouped_data(self, 
                               grouped_data: Dict[str, List[Tuple[LaunchData, SourceData]]],
                               result: DataProcessingResult) -> List[LaunchData]:
        """
        Reconcile data from multiple sources for each launch.
        
        Args:
            grouped_data: Dictionary of grouped launch data
            result: Result object to update with conflicts
            
        Returns:
            List of reconciled LaunchData objects
        """
        reconciled_launches = []
        
        reconciled_results = self.reconciler.reconcile_multiple_launches(grouped_data)
        
        for slug, (reconciled_launch, conflicts) in reconciled_results.items():
            reconciled_launches.append(reconciled_launch)
            result.conflicts.extend(conflicts)
        
        logger.info(f"Reconciled {len(reconciled_launches)} launches with {len(result.conflicts)} conflicts")
        
        return reconciled_launches
    
    def _generate_processing_stats(self, 
                                  input_count: int,
                                  validated_count: int,
                                  reconciled_count: int,
                                  final_count: int,
                                  result: DataProcessingResult) -> Dict[str, Any]:
        """
        Generate comprehensive processing statistics.
        
        Args:
            input_count: Number of input records
            validated_count: Number of validated records
            reconciled_count: Number of reconciled records
            final_count: Number of final processed records
            result: Processing result object
            
        Returns:
            Dictionary with processing statistics
        """
        stats = {
            'input_records': input_count,
            'validated_records': validated_count,
            'reconciled_records': reconciled_count,
            'final_records': final_count,
            'validation_success_rate': validated_count / input_count if input_count > 0 else 0,
            'conflicts_detected': len(result.conflicts),
            'validation_errors': len(result.validation_errors),
            'processing_timestamp': datetime.now().isoformat()
        }
        
        # Add validator statistics
        validator_summary = self.validator.get_validation_summary()
        stats['validator_stats'] = validator_summary
        
        # Add deduplicator statistics (if enabled)
        if self.enable_deduplication:
            dedup_summary = self.deduplicator.get_deduplication_summary()
            stats['deduplication_stats'] = dedup_summary
        
        # Add reconciler statistics
        reconciler_summary = self.reconciler.get_reconciliation_summary()
        stats['reconciliation_stats'] = reconciler_summary
        
        # Add conflict detector statistics (if enabled)
        if self.enable_conflict_detection:
            conflict_summary = self.conflict_detector.get_conflict_summary()
            stats['conflict_detection_stats'] = conflict_summary
        
        return stats
    
    def _log_processing_summary(self, result: DataProcessingResult) -> None:
        """
        Log a summary of processing results.
        
        Args:
            result: Processing result object
        """
        stats = result.processing_stats
        
        logger.info("=== Data Processing Pipeline Summary ===")
        logger.info(f"Input records: {stats['input_records']}")
        logger.info(f"Validated records: {stats['validated_records']}")
        logger.info(f"Final processed records: {stats['final_records']}")
        logger.info(f"Validation success rate: {stats['validation_success_rate']:.2%}")
        logger.info(f"Conflicts detected: {stats['conflicts_detected']}")
        logger.info(f"Validation errors: {stats['validation_errors']}")
        logger.info(f"Processing time: {result.processing_time:.2f} seconds")
        
        if result.conflict_analyses:
            critical_conflicts = [a for a in result.conflict_analyses if a.severity == 'critical']
            if critical_conflicts:
                logger.warning(f"Critical conflicts requiring attention: {len(critical_conflicts)}")
        
        logger.info("=== End Processing Summary ===")
    
    def process_single_launch(self, 
                             raw_launch_data: Dict[str, Any], 
                             raw_source_data: Dict[str, Any]) -> Optional[LaunchData]:
        """
        Process a single launch record through validation only.
        
        Args:
            raw_launch_data: Raw launch data dictionary
            raw_source_data: Raw source data dictionary
            
        Returns:
            Validated LaunchData object or None if validation fails
        """
        try:
            # Validate launch data
            launch_data = self.validator.validate_launch_data(raw_launch_data)
            if not launch_data:
                return None
            
            # Validate source data (for completeness, though not used in single processing)
            source_data = self.validator.validate_source_data(raw_source_data)
            if not source_data:
                return None
            
            return launch_data
            
        except Exception as e:
            logger.error(f"Single launch processing failed: {e}")
            return None
    
    def get_processing_history(self) -> List[Dict[str, Any]]:
        """
        Get history of processing runs.
        
        Returns:
            List of processing history entries
        """
        return self.processing_history.copy()
    
    def clear_processing_history(self) -> None:
        """Clear processing history."""
        self.processing_history.clear()
    
    def reset_components(self) -> None:
        """Reset all pipeline components to clear cached results."""
        self.validator.clear_results()
        self.deduplicator = LaunchDeduplicator(self.deduplicator.date_tolerance.total_seconds() / 3600)
        self.reconciler.clear_results()
        self.conflict_detector.clear_results()
    
    def configure_pipeline(self, 
                          date_tolerance_hours: Optional[int] = None,
                          enable_conflict_detection: Optional[bool] = None,
                          enable_deduplication: Optional[bool] = None) -> None:
        """
        Reconfigure pipeline settings.
        
        Args:
            date_tolerance_hours: New date tolerance for deduplication
            enable_conflict_detection: Whether to enable conflict detection
            enable_deduplication: Whether to enable deduplication
        """
        if date_tolerance_hours is not None:
            self.deduplicator = LaunchDeduplicator(date_tolerance_hours)
        
        if enable_conflict_detection is not None:
            self.enable_conflict_detection = enable_conflict_detection
        
        if enable_deduplication is not None:
            self.enable_deduplication = enable_deduplication
        
        logger.info(f"Pipeline reconfigured: conflict_detection={self.enable_conflict_detection}, "
                   f"deduplication={self.enable_deduplication}")