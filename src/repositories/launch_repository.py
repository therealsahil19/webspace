"""
Repository for launch data operations with CRUD and batch functionality.
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import and_, or_, desc, asc, func

import logging

from src.models.database import Launch, LaunchSource, DataConflict
from src.models.schemas import LaunchData, SourceData, ConflictData, LaunchStatus
from src.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class LaunchRepository(BaseRepository[Launch, LaunchData, LaunchData]):
    """Repository for launch data operations."""
    
    def __init__(self, session: Session):
        """Initialize launch repository."""
        super().__init__(Launch, session)
    
    def get_by_slug(self, slug: str) -> Optional[Launch]:
        """Get launch by slug with sources and conflicts."""
        try:
            return (
                self.session.query(Launch)
                .options(
                    joinedload(Launch.sources),
                    joinedload(Launch.conflicts)
                )
                .filter(Launch.slug == slug)
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"Error getting launch by slug {slug}: {e}")
            raise
    
    def get_upcoming_launches(
        self, 
        limit: int = 50,
        include_sources: bool = False
    ) -> List[Launch]:
        """Get upcoming launches ordered by launch date."""
        try:
            query = self.session.query(Launch).filter(
                and_(
                    Launch.status == LaunchStatus.UPCOMING,
                    Launch.launch_date >= datetime.now(timezone.utc)
                )
            ).order_by(asc(Launch.launch_date))
            
            if include_sources:
                query = query.options(joinedload(Launch.sources))
            
            return query.limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting upcoming launches: {e}")
            raise
    
    def get_historical_launches(
        self,
        skip: int = 0,
        limit: int = 50,
        status_filter: Optional[LaunchStatus] = None,
        vehicle_filter: Optional[str] = None,
        include_sources: bool = False
    ) -> List[Launch]:
        """Get historical launches with optional filtering."""
        try:
            query = self.session.query(Launch).filter(
                Launch.launch_date < datetime.now(timezone.utc)
            )
            
            if status_filter:
                query = query.filter(Launch.status == status_filter)
            
            if vehicle_filter:
                query = query.filter(Launch.vehicle_type == vehicle_filter)
            
            if include_sources:
                query = query.options(joinedload(Launch.sources))
            
            return (
                query.order_by(desc(Launch.launch_date))
                .offset(skip)
                .limit(limit)
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Error getting historical launches: {e}")
            raise
    
    def search_launches(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 50,
        status_filter: Optional[LaunchStatus] = None
    ) -> List[Launch]:
        """Search launches by mission name or details."""
        try:
            search_pattern = f"%{search_term}%"
            query = self.session.query(Launch).filter(
                or_(
                    Launch.mission_name.ilike(search_pattern),
                    Launch.details.ilike(search_pattern)
                )
            )
            
            if status_filter:
                query = query.filter(Launch.status == status_filter)
            
            return (
                query.order_by(desc(Launch.launch_date))
                .offset(skip)
                .limit(limit)
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Error searching launches with term '{search_term}': {e}")
            raise
    
    def upsert_launch(self, launch_data: LaunchData) -> Tuple[Launch, bool]:
        """
        Insert or update launch data with conflict resolution.
        Returns tuple of (launch_object, was_created).
        """
        try:
            # Check if launch already exists
            existing_launch = self.get_by_slug(launch_data.slug)
            
            if existing_launch:
                # Update existing launch
                launch_dict = launch_data.model_dump() if hasattr(launch_data, 'model_dump') else launch_data.dict()
                for key, value in launch_dict.items():
                    if key not in ['slug']:  # Don't update slug
                        setattr(existing_launch, key, value)
                
                self.session.flush()
                self.session.refresh(existing_launch)
                return existing_launch, False
            else:
                # Create new launch
                new_launch = self.create(launch_data)
                return new_launch, True
            
        except IntegrityError as e:
            logger.error(f"Integrity error upserting launch {launch_data.slug}: {e}")
            self.session.rollback()
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error upserting launch {launch_data.slug}: {e}")
            self.session.rollback()
            raise
    
    def batch_upsert_launches(self, launches: List[LaunchData]) -> Dict[str, int]:
        """
        Batch upsert multiple launches.
        Returns dict with counts of created and updated records.
        """
        try:
            created_count = 0
            updated_count = 0
            
            for launch_data in launches:
                _, was_created = self.upsert_launch(launch_data)
                if was_created:
                    created_count += 1
                else:
                    updated_count += 1
            
            logger.info(f"Batch upsert completed: {created_count} created, {updated_count} updated")
            
            return {
                'created': created_count,
                'updated': updated_count,
                'total': len(launches)
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Error in batch upsert launches: {e}")
            self.session.rollback()
            raise
    
    def get_launches_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        include_sources: bool = False
    ) -> List[Launch]:
        """Get launches within a specific date range."""
        try:
            query = self.session.query(Launch).filter(
                and_(
                    Launch.launch_date >= start_date,
                    Launch.launch_date <= end_date
                )
            )
            
            if include_sources:
                query = query.options(joinedload(Launch.sources))
            
            return query.order_by(asc(Launch.launch_date)).all()
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting launches by date range: {e}")
            raise
    
    def get_launches_with_conflicts(self) -> List[Launch]:
        """Get launches that have unresolved data conflicts."""
        try:
            return (
                self.session.query(Launch)
                .join(DataConflict)
                .filter(DataConflict.resolved == False)
                .options(
                    joinedload(Launch.conflicts),
                    joinedload(Launch.sources)
                )
                .distinct()
                .all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Error getting launches with conflicts: {e}")
            raise
    
    def get_launch_statistics(self) -> Dict[str, Any]:
        """Get various statistics about launches in the database."""
        try:
            total_launches = self.session.query(Launch).count()
            
            upcoming_count = self.session.query(Launch).filter(
                Launch.status == LaunchStatus.UPCOMING
            ).count()
            
            successful_count = self.session.query(Launch).filter(
                Launch.status == LaunchStatus.SUCCESS
            ).count()
            
            failed_count = self.session.query(Launch).filter(
                Launch.status == LaunchStatus.FAILURE
            ).count()
            
            # Get vehicle type distribution
            vehicle_stats = (
                self.session.query(
                    Launch.vehicle_type,
                    func.count(Launch.id).label('count')
                )
                .group_by(Launch.vehicle_type)
                .all()
            )
            
            # Get latest launch date
            latest_launch = (
                self.session.query(func.max(Launch.launch_date))
                .scalar()
            )
            
            return {
                'total_launches': total_launches,
                'upcoming_launches': upcoming_count,
                'successful_launches': successful_count,
                'failed_launches': failed_count,
                'vehicle_distribution': {stat.vehicle_type: stat.count for stat in vehicle_stats},
                'latest_launch_date': latest_launch,
                'success_rate': (successful_count / max(total_launches - upcoming_count, 1)) * 100
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting launch statistics: {e}")
            raise