"""
Repository for launch source tracking operations.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import and_, desc, func
import logging

from src.models.database import LaunchSource, Launch
from src.models.schemas import SourceData
from src.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class SourceRepository(BaseRepository[LaunchSource, SourceData, SourceData]):
    """Repository for launch source tracking operations."""
    
    def __init__(self, session: Session):
        """Initialize source repository."""
        super().__init__(LaunchSource, session)
    
    def create_source_for_launch(
        self, 
        launch_id: int, 
        source_data: SourceData
    ) -> LaunchSource:
        """Create a new source record for a specific launch."""
        try:
            source_dict = source_data.model_dump() if hasattr(source_data, 'model_dump') else source_data.dict()
            source_dict['launch_id'] = launch_id
            
            db_source = LaunchSource(**source_dict)
            self.session.add(db_source)
            self.session.flush()
            self.session.refresh(db_source)
            
            logger.info(f"Created source record for launch {launch_id} from {source_data.source_name}")
            return db_source
            
        except IntegrityError as e:
            logger.error(f"Integrity error creating source for launch {launch_id}: {e}")
            self.session.rollback()
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error creating source for launch {launch_id}: {e}")
            self.session.rollback()
            raise
    
    def get_sources_for_launch(self, launch_id: int) -> List[LaunchSource]:
        """Get all sources for a specific launch."""
        try:
            return (
                self.session.query(LaunchSource)
                .filter(LaunchSource.launch_id == launch_id)
                .order_by(desc(LaunchSource.data_quality_score), desc(LaunchSource.scraped_at))
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Error getting sources for launch {launch_id}: {e}")
            raise
    
    def get_sources_by_name(
        self, 
        source_name: str,
        limit: int = 100
    ) -> List[LaunchSource]:
        """Get sources by source name."""
        try:
            return (
                self.session.query(LaunchSource)
                .filter(LaunchSource.source_name == source_name)
                .order_by(desc(LaunchSource.scraped_at))
                .limit(limit)
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Error getting sources by name {source_name}: {e}")
            raise
    
    def get_recent_sources(
        self, 
        hours: int = 24,
        include_launch: bool = False
    ) -> List[LaunchSource]:
        """Get sources scraped within the last N hours."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            query = self.session.query(LaunchSource).filter(
                LaunchSource.scraped_at >= cutoff_time
            )
            
            if include_launch:
                query = query.options(joinedload(LaunchSource.launch))
            
            return query.order_by(desc(LaunchSource.scraped_at)).all()
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting recent sources: {e}")
            raise
    
    def get_source_quality_stats(self) -> Dict[str, Any]:
        """Get statistics about source data quality."""
        try:
            # Overall quality statistics
            quality_stats = (
                self.session.query(
                    func.avg(LaunchSource.data_quality_score).label('avg_quality'),
                    func.min(LaunchSource.data_quality_score).label('min_quality'),
                    func.max(LaunchSource.data_quality_score).label('max_quality'),
                    func.count(LaunchSource.id).label('total_sources')
                )
                .first()
            )
            
            # Quality by source name
            source_quality = (
                self.session.query(
                    LaunchSource.source_name,
                    func.avg(LaunchSource.data_quality_score).label('avg_quality'),
                    func.count(LaunchSource.id).label('count')
                )
                .group_by(LaunchSource.source_name)
                .all()
            )
            
            # Recent scraping activity (last 7 days)
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            recent_activity = (
                self.session.query(
                    LaunchSource.source_name,
                    func.count(LaunchSource.id).label('recent_scrapes')
                )
                .filter(LaunchSource.scraped_at >= week_ago)
                .group_by(LaunchSource.source_name)
                .all()
            )
            
            return {
                'overall': {
                    'average_quality': float(quality_stats.avg_quality or 0),
                    'min_quality': float(quality_stats.min_quality or 0),
                    'max_quality': float(quality_stats.max_quality or 0),
                    'total_sources': quality_stats.total_sources
                },
                'by_source': {
                    stat.source_name: {
                        'average_quality': float(stat.avg_quality),
                        'count': stat.count
                    }
                    for stat in source_quality
                },
                'recent_activity': {
                    stat.source_name: stat.recent_scrapes
                    for stat in recent_activity
                }
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting source quality stats: {e}")
            raise
    
    def update_source_quality(
        self, 
        source_id: int, 
        quality_score: float
    ) -> Optional[LaunchSource]:
        """Update the quality score for a source."""
        try:
            source = self.get(source_id)
            if source:
                source.data_quality_score = quality_score
                self.session.flush()
                self.session.refresh(source)
                logger.info(f"Updated quality score for source {source_id} to {quality_score}")
            return source
            
        except SQLAlchemyError as e:
            logger.error(f"Error updating source quality for {source_id}: {e}")
            self.session.rollback()
            raise
    
    def batch_create_sources(
        self, 
        launch_id: int, 
        sources: List[SourceData]
    ) -> List[LaunchSource]:
        """Create multiple source records for a launch in batch."""
        try:
            db_sources = []
            for source_data in sources:
                source_dict = source_data.model_dump() if hasattr(source_data, 'model_dump') else source_data.dict()
                source_dict['launch_id'] = launch_id
                
                db_source = LaunchSource(**source_dict)
                db_sources.append(db_source)
            
            self.session.add_all(db_sources)
            self.session.flush()
            
            # Refresh all objects to get their IDs
            for db_source in db_sources:
                self.session.refresh(db_source)
            
            logger.info(f"Created {len(db_sources)} source records for launch {launch_id}")
            return db_sources
            
        except IntegrityError as e:
            logger.error(f"Integrity error in batch create sources for launch {launch_id}: {e}")
            self.session.rollback()
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error in batch create sources for launch {launch_id}: {e}")
            self.session.rollback()
            raise
    
    def get_stale_sources(self, hours: int = 48) -> List[LaunchSource]:
        """Get sources that haven't been updated in N hours."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            return (
                self.session.query(LaunchSource)
                .filter(LaunchSource.scraped_at < cutoff_time)
                .options(joinedload(LaunchSource.launch))
                .order_by(asc(LaunchSource.scraped_at))
                .all()
            )
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting stale sources: {e}")
            raise
    
    def delete_old_sources(self, days: int = 30) -> int:
        """Delete source records older than N days. Returns count of deleted records."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            
            deleted_count = (
                self.session.query(LaunchSource)
                .filter(LaunchSource.scraped_at < cutoff_time)
                .delete()
            )
            
            self.session.flush()
            logger.info(f"Deleted {deleted_count} old source records")
            return deleted_count
            
        except SQLAlchemyError as e:
            logger.error(f"Error deleting old sources: {e}")
            self.session.rollback()
            raise