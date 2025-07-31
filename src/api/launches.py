"""
Launch endpoints for the FastAPI application.
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.api.dependencies import get_repo_manager, validate_pagination
from src.api.responses import PaginatedResponse, create_pagination_meta, ErrorResponse
from src.models.schemas import LaunchResponse, LaunchStatus
from src.repositories import RepositoryManager
from src.cache.cache_manager import get_cache_manager

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/launches", tags=["launches"])


@router.get(
    "",
    response_model=PaginatedResponse,
    summary="Get all launches with pagination and filtering",
    description="Retrieve a paginated list of launches with optional filtering by status, vehicle type, and search term."
)
async def get_launches(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    status: Optional[LaunchStatus] = Query(None, description="Filter by launch status"),
    vehicle_type: Optional[str] = Query(None, description="Filter by vehicle type"),
    search: Optional[str] = Query(None, description="Search in mission name and details"),
    repo_manager: RepositoryManager = Depends(get_repo_manager)
):
    """Get launches with pagination and filtering."""
    try:
        skip, limit = validate_pagination(skip, limit)
        cache_manager = get_cache_manager()
        
        # Try to get from cache first
        status_str = status.value if status else None
        cached_result = cache_manager.get_launches_list(
            skip=skip, 
            limit=limit, 
            status=status_str, 
            vehicle_type=vehicle_type, 
            search=search
        )
        
        if cached_result:
            logger.debug(f"Cache hit for launches list: skip={skip}, limit={limit}")
            return PaginatedResponse(**cached_result)
        
        launch_repo = repo_manager.launch_repository
        
        # Get total count for pagination
        if search:
            launches = launch_repo.search_launches(
                search_term=search,
                skip=skip,
                limit=limit,
                status_filter=status
            )
            # For search, we need to count separately
            total_launches = len(launch_repo.search_launches(
                search_term=search,
                skip=0,
                limit=1000,  # Large limit to get all for counting
                status_filter=status
            ))
        else:
            # Get all launches with filters
            all_launches = launch_repo.get_all()
            
            # Apply filters
            filtered_launches = all_launches
            if status:
                filtered_launches = [l for l in filtered_launches if l.status == status]
            if vehicle_type:
                filtered_launches = [l for l in filtered_launches if l.vehicle_type == vehicle_type]
            
            total_launches = len(filtered_launches)
            
            # Apply pagination
            launches = filtered_launches[skip:skip + limit]
        
        # Convert to response models
        launch_responses = []
        for launch in launches:
            launch_dict = {
                'id': launch.id,
                'slug': launch.slug,
                'mission_name': launch.mission_name,
                'launch_date': launch.launch_date,
                'vehicle_type': launch.vehicle_type,
                'payload_mass': launch.payload_mass,
                'orbit': launch.orbit,
                'status': launch.status,
                'details': launch.details,
                'mission_patch_url': launch.mission_patch_url,
                'webcast_url': launch.webcast_url,
                'created_at': launch.created_at,
                'updated_at': launch.updated_at,
                'sources': []
            }
            
            # Add sources if available
            if hasattr(launch, 'sources') and launch.sources:
                for source in launch.sources:
                    launch_dict['sources'].append({
                        'source_name': source.source_name,
                        'source_url': source.source_url,
                        'scraped_at': source.scraped_at,
                        'data_quality_score': source.data_quality_score
                    })
            
            launch_responses.append(LaunchResponse(**launch_dict))
        
        # Create pagination metadata
        pagination_meta = create_pagination_meta(total_launches, skip, limit)
        
        result = PaginatedResponse(
            data=launch_responses,
            meta=pagination_meta
        )
        
        # Cache the result
        cache_manager.set_launches_list(
            result.model_dump(),
            skip=skip,
            limit=limit,
            status=status_str,
            vehicle_type=vehicle_type,
            search=search
        )
        
        return result
        
    except SQLAlchemyError as e:
        logger.error(f"Database error getting launches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting launches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.get(
    "/{slug}",
    response_model=LaunchResponse,
    summary="Get launch by slug",
    description="Retrieve detailed information about a specific launch by its slug identifier.",
    responses={
        404: {"model": ErrorResponse, "description": "Launch not found"}
    }
)
async def get_launch_by_slug(
    slug: str,
    repo_manager: RepositoryManager = Depends(get_repo_manager)
):
    """Get a specific launch by slug."""
    try:
        cache_manager = get_cache_manager()
        
        # Try to get from cache first
        cached_launch = cache_manager.get_launch_detail(slug)
        if cached_launch:
            logger.debug(f"Cache hit for launch detail: {slug}")
            return LaunchResponse(**cached_launch)
        
        launch_repo = repo_manager.launch_repository
        launch = launch_repo.get_by_slug(slug)
        
        if not launch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Launch with slug '{slug}' not found"
            )
        
        # Convert to response model
        launch_dict = {
            'id': launch.id,
            'slug': launch.slug,
            'mission_name': launch.mission_name,
            'launch_date': launch.launch_date,
            'vehicle_type': launch.vehicle_type,
            'payload_mass': launch.payload_mass,
            'orbit': launch.orbit,
            'status': launch.status,
            'details': launch.details,
            'mission_patch_url': launch.mission_patch_url,
            'webcast_url': launch.webcast_url,
            'created_at': launch.created_at,
            'updated_at': launch.updated_at,
            'sources': []
        }
        
        # Add sources if available
        if hasattr(launch, 'sources') and launch.sources:
            for source in launch.sources:
                launch_dict['sources'].append({
                    'source_name': source.source_name,
                    'source_url': source.source_url,
                    'scraped_at': source.scraped_at,
                    'data_quality_score': source.data_quality_score
                })
        
        result = LaunchResponse(**launch_dict)
        
        # Cache the result
        cache_manager.set_launch_detail(slug, launch_dict)
        
        return result
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error getting launch {slug}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting launch {slug}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.get(
    "/upcoming",
    response_model=List[LaunchResponse],
    summary="Get upcoming launches",
    description="Retrieve all upcoming launches ordered by launch date."
)
async def get_upcoming_launches(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of launches to return"),
    repo_manager: RepositoryManager = Depends(get_repo_manager)
):
    """Get upcoming launches."""
    try:
        cache_manager = get_cache_manager()
        
        # Try to get from cache first
        cached_launches = cache_manager.get_upcoming_launches(limit)
        if cached_launches:
            logger.debug(f"Cache hit for upcoming launches: limit={limit}")
            return [LaunchResponse(**launch) for launch in cached_launches]
        
        launch_repo = repo_manager.launch_repository
        launches = launch_repo.get_upcoming_launches(limit=limit, include_sources=True)
        
        # Convert to response models
        launch_responses = []
        launch_dicts = []
        for launch in launches:
            launch_dict = {
                'id': launch.id,
                'slug': launch.slug,
                'mission_name': launch.mission_name,
                'launch_date': launch.launch_date,
                'vehicle_type': launch.vehicle_type,
                'payload_mass': launch.payload_mass,
                'orbit': launch.orbit,
                'status': launch.status,
                'details': launch.details,
                'mission_patch_url': launch.mission_patch_url,
                'webcast_url': launch.webcast_url,
                'created_at': launch.created_at,
                'updated_at': launch.updated_at,
                'sources': []
            }
            
            # Add sources if available
            if hasattr(launch, 'sources') and launch.sources:
                for source in launch.sources:
                    launch_dict['sources'].append({
                        'source_name': source.source_name,
                        'source_url': source.source_url,
                        'scraped_at': source.scraped_at,
                        'data_quality_score': source.data_quality_score
                    })
            
            launch_responses.append(LaunchResponse(**launch_dict))
            launch_dicts.append(launch_dict)
        
        # Cache the result
        cache_manager.set_upcoming_launches(launch_dicts, limit)
        
        return launch_responses
        
    except SQLAlchemyError as e:
        logger.error(f"Database error getting upcoming launches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting upcoming launches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.get(
    "/historical",
    response_model=PaginatedResponse,
    summary="Get historical launches",
    description="Retrieve historical (past) launches with pagination and filtering options."
)
async def get_historical_launches(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    status: Optional[LaunchStatus] = Query(None, description="Filter by launch status"),
    vehicle_type: Optional[str] = Query(None, description="Filter by vehicle type"),
    repo_manager: RepositoryManager = Depends(get_repo_manager)
):
    """Get historical launches with pagination and filtering."""
    try:
        skip, limit = validate_pagination(skip, limit)
        launch_repo = repo_manager.launch_repository
        
        # Get historical launches
        launches = launch_repo.get_historical_launches(
            skip=skip,
            limit=limit,
            status_filter=status,
            vehicle_filter=vehicle_type,
            include_sources=True
        )
        
        # Get total count for pagination (approximate for performance)
        # In a real implementation, you might want to cache this or use a more efficient count query
        all_historical = launch_repo.get_historical_launches(
            skip=0,
            limit=1000,  # Large limit to get count
            status_filter=status,
            vehicle_filter=vehicle_type,
            include_sources=False
        )
        total_launches = len(all_historical)
        
        # Convert to response models
        launch_responses = []
        for launch in launches:
            launch_dict = {
                'id': launch.id,
                'slug': launch.slug,
                'mission_name': launch.mission_name,
                'launch_date': launch.launch_date,
                'vehicle_type': launch.vehicle_type,
                'payload_mass': launch.payload_mass,
                'orbit': launch.orbit,
                'status': launch.status,
                'details': launch.details,
                'mission_patch_url': launch.mission_patch_url,
                'webcast_url': launch.webcast_url,
                'created_at': launch.created_at,
                'updated_at': launch.updated_at,
                'sources': []
            }
            
            # Add sources if available
            if hasattr(launch, 'sources') and launch.sources:
                for source in launch.sources:
                    launch_dict['sources'].append({
                        'source_name': source.source_name,
                        'source_url': source.source_url,
                        'scraped_at': source.scraped_at,
                        'data_quality_score': source.data_quality_score
                    })
            
            launch_responses.append(LaunchResponse(**launch_dict))
        
        # Create pagination metadata
        pagination_meta = create_pagination_meta(total_launches, skip, limit)
        
        return PaginatedResponse(
            data=launch_responses,
            meta=pagination_meta
        )
        
    except SQLAlchemyError as e:
        logger.error(f"Database error getting historical launches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting historical launches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )