"""
Repository manager for coordinating database operations across multiple repositories.
"""
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging

from src.database import DatabaseManager, get_database_manager
from src.repositories.launch_repository import LaunchRepository
from src.repositories.source_repository import SourceRepository
from src.repositories.conflict_repository import ConflictRepository
from src.models.schemas import LaunchData, SourceData, ConflictData

logger = logging.getLogger(__name__)


class RepositoryManager:
    """Manager class that coordinates operations across multiple repositories."""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """Initialize repository manager with database manager."""
        self.db_manager = db_manager or get_database_manager()
        self._session: Optional[Session] = None
        self._launch_repo: Optional[LaunchRepository] = None
        self._source_repo: Optional[SourceRepository] = None
        self._conflict_repo: Optional[ConflictRepository] = None
    
    def _ensure_session(self) -> None:
        """Ensure we have an active database session."""
        if self._session is None:
            self._session = self.db_manager.get_session()
    
    def _ensure_repositories(self) -> None:
        """Ensure all repositories are initialized."""
        self._ensure_session()
        
        if self._launch_repo is None:
            self._launch_repo = LaunchRepository(self._session)
        
        if self._source_repo is None:
            self._source_repo = SourceRepository(self._session)
        
        if self._conflict_repo is None:
            self._conflict_repo = ConflictRepository(self._session)
    
    @property
    def launches(self) -> LaunchRepository:
        """Get the launch repository."""
        self._ensure_repositories()
        return self._launch_repo
    
    @property
    def sources(self) -> SourceRepository:
        """Get the source repository."""
        self._ensure_repositories()
        return self._source_repo
    
    @property
    def conflicts(self) -> ConflictRepository:
        """Get the conflict repository."""
        self._ensure_repositories()
        return self._conflict_repo
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        self._ensure_session()
        try:
            yield self
            self._session.commit()
            logger.debug("Transaction committed successfully")
        except Exception as e:
            self._session.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
            raise
        finally:
            if self._session:
                self._session.close()
                self._session = None
                self._launch_repo = None
                self._source_repo = None
                self._conflict_repo = None
    
    def process_launch_with_sources_and_conflicts(
        self,
        launch_data: LaunchData,
        sources: List[SourceData],
        conflicts: Optional[List[ConflictData]] = None
    ) -> Dict[str, Any]:
        """
        Process a complete launch record with sources and conflicts in a single transaction.
        Returns summary of operations performed.
        """
        try:
            with self.transaction():
                # Upsert the launch
                launch, was_created = self.launches.upsert_launch(launch_data)
                
                # Create source records
                created_sources = []
                if sources:
                    created_sources = self.sources.batch_create_sources(launch.id, sources)
                
                # Create conflict records if any
                created_conflicts = []
                if conflicts:
                    created_conflicts = self.conflicts.batch_create_conflicts(launch.id, conflicts)
                
                result = {
                    'launch': {
                        'id': launch.id,
                        'slug': launch.slug,
                        'was_created': was_created
                    },
                    'sources_created': len(created_sources),
                    'conflicts_created': len(created_conflicts)
                }
                
                logger.info(f"Processed launch {launch.slug}: "
                          f"{'created' if was_created else 'updated'}, "
                          f"{len(created_sources)} sources, "
                          f"{len(created_conflicts)} conflicts")
                
                return result
                
        except SQLAlchemyError as e:
            logger.error(f"Error processing launch {launch_data.slug}: {e}")
            raise
    
    def batch_process_launches(
        self,
        launch_data_list: List[Tuple[LaunchData, List[SourceData], Optional[List[ConflictData]]]]
    ) -> Dict[str, Any]:
        """
        Process multiple launches with their sources and conflicts in a single transaction.
        Each item in launch_data_list should be a tuple of (launch_data, sources, conflicts).
        """
        try:
            with self.transaction():
                results = {
                    'launches_created': 0,
                    'launches_updated': 0,
                    'total_sources_created': 0,
                    'total_conflicts_created': 0,
                    'processed_launches': []
                }
                
                for launch_data, sources, conflicts in launch_data_list:
                    # Upsert the launch
                    launch, was_created = self.launches.upsert_launch(launch_data)
                    
                    if was_created:
                        results['launches_created'] += 1
                    else:
                        results['launches_updated'] += 1
                    
                    # Create source records
                    created_sources = []
                    if sources:
                        created_sources = self.sources.batch_create_sources(launch.id, sources)
                        results['total_sources_created'] += len(created_sources)
                    
                    # Create conflict records if any
                    created_conflicts = []
                    if conflicts:
                        created_conflicts = self.conflicts.batch_create_conflicts(launch.id, conflicts)
                        results['total_conflicts_created'] += len(created_conflicts)
                    
                    results['processed_launches'].append({
                        'id': launch.id,
                        'slug': launch.slug,
                        'was_created': was_created,
                        'sources_created': len(created_sources),
                        'conflicts_created': len(created_conflicts)
                    })
                
                logger.info(f"Batch processed {len(launch_data_list)} launches: "
                          f"{results['launches_created']} created, "
                          f"{results['launches_updated']} updated, "
                          f"{results['total_sources_created']} sources, "
                          f"{results['total_conflicts_created']} conflicts")
                
                return results
                
        except SQLAlchemyError as e:
            logger.error(f"Error in batch processing launches: {e}")
            raise
    
    def get_system_health_stats(self) -> Dict[str, Any]:
        """Get comprehensive system health statistics."""
        try:
            with self.transaction():
                launch_stats = self.launches.get_launch_statistics()
                source_stats = self.sources.get_source_quality_stats()
                conflict_stats = self.conflicts.get_conflict_statistics()
                
                return {
                    'launches': launch_stats,
                    'sources': source_stats,
                    'conflicts': conflict_stats,
                    'database_pool': self.db_manager.get_pool_status()
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting system health stats: {e}")
            raise
    
    def cleanup_old_data(
        self,
        source_retention_days: int = 30,
        conflict_retention_days: int = 90
    ) -> Dict[str, int]:
        """Clean up old data from the database."""
        try:
            with self.transaction():
                deleted_sources = self.sources.delete_old_sources(source_retention_days)
                deleted_conflicts = self.conflicts.delete_old_resolved_conflicts(conflict_retention_days)
                
                result = {
                    'deleted_sources': deleted_sources,
                    'deleted_conflicts': deleted_conflicts
                }
                
                logger.info(f"Cleanup completed: {deleted_sources} sources, {deleted_conflicts} conflicts deleted")
                return result
                
        except SQLAlchemyError as e:
            logger.error(f"Error during cleanup: {e}")
            raise
    
    def resolve_conflicts_by_criteria(
        self,
        field_name: Optional[str] = None,
        min_confidence: Optional[float] = None,
        max_age_days: Optional[int] = None
    ) -> int:
        """Resolve conflicts based on specified criteria."""
        try:
            with self.transaction():
                # Get conflicts matching criteria
                if field_name:
                    conflicts = self.conflicts.get_conflicts_by_field(field_name, resolved=False)
                elif min_confidence:
                    conflicts = self.conflicts.get_high_confidence_conflicts(min_confidence, resolved=False)
                else:
                    conflicts = self.conflicts.get_unresolved_conflicts()
                
                # Filter by age if specified
                if max_age_days and conflicts:
                    from datetime import datetime, timedelta
                    cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
                    conflicts = [c for c in conflicts if c.created_at >= cutoff_date]
                
                # Resolve the conflicts
                if conflicts:
                    conflict_ids = [c.id for c in conflicts]
                    resolved_count = self.conflicts.batch_resolve_conflicts(conflict_ids)
                    logger.info(f"Resolved {resolved_count} conflicts based on criteria")
                    return resolved_count
                
                return 0
                
        except SQLAlchemyError as e:
            logger.error(f"Error resolving conflicts by criteria: {e}")
            raise
    
    def close(self) -> None:
        """Close the repository manager and clean up resources."""
        if self._session:
            self._session.close()
            self._session = None
        
        self._launch_repo = None
        self._source_repo = None
        self._conflict_repo = None


# Global repository manager instance
_repo_manager: Optional[RepositoryManager] = None


def get_repository_manager() -> RepositoryManager:
    """Get the global repository manager instance."""
    global _repo_manager
    if _repo_manager is None:
        _repo_manager = RepositoryManager()
    return _repo_manager


def close_repository_manager() -> None:
    """Close the global repository manager."""
    global _repo_manager
    if _repo_manager:
        _repo_manager.close()
        _repo_manager = None