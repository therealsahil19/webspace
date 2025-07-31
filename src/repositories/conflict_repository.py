"""
Repository for data conflict tracking and resolution operations.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import and_, desc, func
import logging

from src.models.database import DataConflict, Launch
from src.models.schemas import ConflictData
from src.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ConflictRepository(BaseRepository[DataConflict, ConflictData, ConflictData]):
    """Repository for data conflict tracking and resolution operations."""
    
    def __init__(self, session: Session):
        """Initialize conflict repository."""
        super().__init__(DataConflict, session)
    
    def create_conflict_for_launch(
        self, 
        launch_id: int, 
        conflict_data: ConflictData
    ) -> DataConflict:
        """Create a new conflict record for a specific launch."""
        try:
            conflict_dict = conflict_data.model_dump() if hasattr(conflict_data, 'model_dump') else conflict_data.dict()
            conflict_dict['launch_id'] = launch_id
            
            db_conflict = DataConflict(**conflict_dict)
            self.session.add(db_conflict)
            self.session.flush()
            self.session.refresh(db_conflict)
            
            logger.info(f"Created conflict record for launch {launch_id}, field: {conflict_data.field_name}")
            return db_conflict
            
        except IntegrityError as e:
            logger.error(f"Integrity error creating conflict for launch {launch_id}: {e}")
            self.session.rollback()
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error creating conflict for launch {launch_id}: {e}")
            self.session.rollback()
            raise
    
    def get_conflicts_for_launch(
        self, 
        launch_id: int,
        resolved: Optional[bool] = None
    ) -> List[DataConflict]:
        """Get all conflicts for a specific launch."""
        try:
            query = self.session.query(DataConflict).filter(
                DataConflict.launch_id == launch_id
            )
            
            if resolved is not None:
                query = query.filter(DataConflict.resolved == resolved)
            
            return query.order_by(desc(DataConflict.created_at)).all()
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting conflicts for launch {launch_id}: {e}")
            raise
    
    def get_unresolved_conflicts(
        self,
        limit: int = 100,
        include_launch: bool = False
    ) -> List[DataConflict]:
        """Get all unresolved conflicts."""
        try:
            query = self.session.query(DataConflict).filter(
                DataConflict.resolved == False
            )
            
            if include_launch:
                query = query.options(joinedload(DataConflict.launch))
            
            return (
                query.order_by(desc(DataConflict.created_at))
                .limit(limit)
                .all()
            )
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting unresolved conflicts: {e}")
            raise
    
    def get_conflicts_by_field(
        self, 
        field_name: str,
        resolved: Optional[bool] = None
    ) -> List[DataConflict]:
        """Get conflicts for a specific field."""
        try:
            query = self.session.query(DataConflict).filter(
                DataConflict.field_name == field_name
            )
            
            if resolved is not None:
                query = query.filter(DataConflict.resolved == resolved)
            
            return (
                query.options(joinedload(DataConflict.launch))
                .order_by(desc(DataConflict.created_at))
                .all()
            )
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting conflicts by field {field_name}: {e}")
            raise
    
    def resolve_conflict(
        self, 
        conflict_id: int,
        resolution_note: Optional[str] = None
    ) -> Optional[DataConflict]:
        """Mark a conflict as resolved."""
        try:
            conflict = self.get(conflict_id)
            if conflict:
                conflict.resolved = True
                conflict.resolved_at = datetime.utcnow()
                
                self.session.flush()
                self.session.refresh(conflict)
                
                logger.info(f"Resolved conflict {conflict_id}")
            return conflict
            
        except SQLAlchemyError as e:
            logger.error(f"Error resolving conflict {conflict_id}: {e}")
            self.session.rollback()
            raise
    
    def batch_resolve_conflicts(
        self, 
        conflict_ids: List[int]
    ) -> int:
        """Resolve multiple conflicts in batch. Returns count of resolved conflicts."""
        try:
            resolved_count = (
                self.session.query(DataConflict)
                .filter(DataConflict.id.in_(conflict_ids))
                .update({
                    'resolved': True,
                    'resolved_at': datetime.utcnow()
                }, synchronize_session=False)
            )
            
            self.session.flush()
            logger.info(f"Resolved {resolved_count} conflicts in batch")
            return resolved_count
            
        except SQLAlchemyError as e:
            logger.error(f"Error in batch resolve conflicts: {e}")
            self.session.rollback()
            raise
    
    def get_conflict_statistics(self) -> Dict[str, Any]:
        """Get statistics about data conflicts."""
        try:
            # Overall conflict statistics
            total_conflicts = self.session.query(DataConflict).count()
            unresolved_conflicts = self.session.query(DataConflict).filter(
                DataConflict.resolved == False
            ).count()
            resolved_conflicts = total_conflicts - unresolved_conflicts
            
            # Conflicts by field
            field_stats = (
                self.session.query(
                    DataConflict.field_name,
                    func.count(DataConflict.id).label('total'),
                    func.sum(func.case((DataConflict.resolved == True, 1), else_=0)).label('resolved')
                )
                .group_by(DataConflict.field_name)
                .all()
            )
            
            # Recent conflicts (last 7 days)
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_conflicts = (
                self.session.query(DataConflict)
                .filter(DataConflict.created_at >= week_ago)
                .count()
            )
            
            # Average confidence score
            avg_confidence = (
                self.session.query(func.avg(DataConflict.confidence_score))
                .scalar() or 0
            )
            
            return {
                'total_conflicts': total_conflicts,
                'unresolved_conflicts': unresolved_conflicts,
                'resolved_conflicts': resolved_conflicts,
                'resolution_rate': (resolved_conflicts / max(total_conflicts, 1)) * 100,
                'recent_conflicts': recent_conflicts,
                'average_confidence': float(avg_confidence),
                'by_field': {
                    stat.field_name: {
                        'total': stat.total,
                        'resolved': stat.resolved or 0,
                        'unresolved': stat.total - (stat.resolved or 0)
                    }
                    for stat in field_stats
                }
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting conflict statistics: {e}")
            raise
    
    def get_high_confidence_conflicts(
        self, 
        min_confidence: float = 0.8,
        resolved: Optional[bool] = None
    ) -> List[DataConflict]:
        """Get conflicts with high confidence scores."""
        try:
            query = self.session.query(DataConflict).filter(
                DataConflict.confidence_score >= min_confidence
            )
            
            if resolved is not None:
                query = query.filter(DataConflict.resolved == resolved)
            
            return (
                query.options(joinedload(DataConflict.launch))
                .order_by(desc(DataConflict.confidence_score))
                .all()
            )
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting high confidence conflicts: {e}")
            raise
    
    def batch_create_conflicts(
        self, 
        launch_id: int, 
        conflicts: List[ConflictData]
    ) -> List[DataConflict]:
        """Create multiple conflict records for a launch in batch."""
        try:
            db_conflicts = []
            for conflict_data in conflicts:
                conflict_dict = conflict_data.model_dump() if hasattr(conflict_data, 'model_dump') else conflict_data.dict()
                conflict_dict['launch_id'] = launch_id
                
                db_conflict = DataConflict(**conflict_dict)
                db_conflicts.append(db_conflict)
            
            self.session.add_all(db_conflicts)
            self.session.flush()
            
            # Refresh all objects to get their IDs
            for db_conflict in db_conflicts:
                self.session.refresh(db_conflict)
            
            logger.info(f"Created {len(db_conflicts)} conflict records for launch {launch_id}")
            return db_conflicts
            
        except IntegrityError as e:
            logger.error(f"Integrity error in batch create conflicts for launch {launch_id}: {e}")
            self.session.rollback()
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error in batch create conflicts for launch {launch_id}: {e}")
            self.session.rollback()
            raise
    
    def delete_old_resolved_conflicts(self, days: int = 90) -> int:
        """Delete resolved conflicts older than N days. Returns count of deleted records."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            
            deleted_count = (
                self.session.query(DataConflict)
                .filter(
                    and_(
                        DataConflict.resolved == True,
                        DataConflict.resolved_at < cutoff_time
                    )
                )
                .delete()
            )
            
            self.session.flush()
            logger.info(f"Deleted {deleted_count} old resolved conflict records")
            return deleted_count
            
        except SQLAlchemyError as e:
            logger.error(f"Error deleting old resolved conflicts: {e}")
            self.session.rollback()
            raise
    
    def find_duplicate_conflicts(self) -> List[Dict[str, Any]]:
        """Find potential duplicate conflicts for the same launch and field."""
        try:
            duplicates = (
                self.session.query(
                    DataConflict.launch_id,
                    DataConflict.field_name,
                    func.count(DataConflict.id).label('count')
                )
                .group_by(DataConflict.launch_id, DataConflict.field_name)
                .having(func.count(DataConflict.id) > 1)
                .all()
            )
            
            return [
                {
                    'launch_id': dup.launch_id,
                    'field_name': dup.field_name,
                    'count': dup.count
                }
                for dup in duplicates
            ]
            
        except SQLAlchemyError as e:
            logger.error(f"Error finding duplicate conflicts: {e}")
            raise