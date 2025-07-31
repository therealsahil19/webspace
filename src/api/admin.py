"""
Admin endpoints for system monitoring and management.
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session
from celery.result import AsyncResult

from src.api.dependencies import get_db, get_repo_manager
from src.auth.dependencies import require_admin, require_auth_or_api_key
from src.auth.models import User
from src.repositories import RepositoryManager
from src.celery_app import celery_app
from src.tasks.scraping_tasks import run_full_scraping_pipeline
from src.cache.cache_manager import get_cache_manager

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post(
    "/refresh",
    summary="Manual data refresh",
    description="Trigger manual data refresh from all sources."
)
async def trigger_manual_refresh(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_auth_or_api_key),
    db: Session = Depends(get_db)
):
    """Trigger manual data refresh from all sources."""
    try:
        # Check if user has admin permissions (JWT users need admin role, API key users are automatically admin)
        if hasattr(current_user, 'role') and current_user.role.value != 'admin' and current_user.id != 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        # Invalidate all caches before triggering refresh
        cache_manager = get_cache_manager()
        cache_manager.invalidate_all_cache()
        
        # Trigger the scraping task
        task = run_full_scraping_pipeline.delay()
        
        logger.info(f"Manual refresh triggered by user {current_user.username}, task ID: {task.id}")
        
        return {
            "message": "Data refresh triggered successfully",
            "task_id": task.id,
            "status": "started",
            "triggered_by": current_user.username,
            "triggered_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manual refresh trigger error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger data refresh"
        )


@router.get(
    "/refresh/status/{task_id}",
    summary="Get refresh task status",
    description="Get the status of a data refresh task."
)
async def get_refresh_status(
    task_id: str,
    current_user: User = Depends(require_admin)
):
    """Get the status of a data refresh task."""
    try:
        # Get task result from Celery
        task_result = AsyncResult(task_id, app=celery_app)
        
        response = {
            "task_id": task_id,
            "status": task_result.status,
            "current": getattr(task_result, 'current', 0),
            "total": getattr(task_result, 'total', 1),
        }
        
        if task_result.ready():
            if task_result.successful():
                response["result"] = task_result.result
            else:
                response["error"] = str(task_result.info)
        else:
            response["info"] = task_result.info
        
        return response
        
    except Exception as e:
        logger.error(f"Get refresh status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get task status"
        )


@router.get(
    "/system/health",
    summary="System health check",
    description="Get comprehensive system health information."
)
async def get_system_health(
    current_user: User = Depends(require_admin),
    repo_manager: RepositoryManager = Depends(get_repo_manager)
):
    """Get system health information."""
    try:
        cache_manager = get_cache_manager()
        
        # Try to get from cache first
        cached_health = cache_manager.get_system_health()
        if cached_health:
            logger.debug("Cache hit for system health")
            return cached_health
        
        health_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",
            "components": {}
        }
        
        # Database health
        try:
            launch_repo = repo_manager.launch_repository
            total_launches = len(launch_repo.get_all())
            recent_launches = len(launch_repo.get_upcoming_launches(limit=10))
            
            health_info["components"]["database"] = {
                "status": "healthy",
                "total_launches": total_launches,
                "upcoming_launches": recent_launches
            }
        except Exception as e:
            health_info["components"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_info["status"] = "degraded"
        
        # Celery health
        try:
            # Check if Celery is responsive
            celery_inspect = celery_app.control.inspect()
            active_tasks = celery_inspect.active()
            
            if active_tasks is not None:
                health_info["components"]["celery"] = {
                    "status": "healthy",
                    "active_tasks": sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0,
                    "workers": list(active_tasks.keys()) if active_tasks else []
                }
            else:
                health_info["components"]["celery"] = {
                    "status": "unhealthy",
                    "error": "No workers available"
                }
                health_info["status"] = "degraded"
        except Exception as e:
            health_info["components"]["celery"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_info["status"] = "degraded"
        
        # Data freshness check
        try:
            # Check when data was last updated
            launches = launch_repo.get_all()
            if launches:
                latest_update = max(launch.updated_at for launch in launches)
                hours_since_update = (datetime.utcnow() - latest_update).total_seconds() / 3600
                
                health_info["components"]["data_freshness"] = {
                    "status": "healthy" if hours_since_update < 12 else "stale",
                    "last_update": latest_update.isoformat(),
                    "hours_since_update": round(hours_since_update, 2)
                }
                
                if hours_since_update >= 12:
                    health_info["status"] = "degraded"
            else:
                health_info["components"]["data_freshness"] = {
                    "status": "no_data",
                    "message": "No launch data available"
                }
                health_info["status"] = "degraded"
        except Exception as e:
            health_info["components"]["data_freshness"] = {
                "status": "unknown",
                "error": str(e)
            }
        
        # Add cache information
        try:
            cache_info = cache_manager.get_cache_info()
            health_info["components"]["cache"] = {
                "status": "healthy" if cache_info.get("connected", False) else "unhealthy",
                "enabled": cache_info.get("enabled", False),
                "entries": cache_info.get("cache_entries", {}).get("total", 0),
                "hit_rate": cache_info.get("hit_rate", 0)
            }
        except Exception as e:
            health_info["components"]["cache"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Cache the result
        cache_manager.set_system_health(health_info)
        
        return health_info
        
    except Exception as e:
        logger.error(f"System health check error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system health"
        )


@router.get(
    "/system/stats",
    summary="System statistics",
    description="Get detailed system statistics and metrics."
)
async def get_system_stats(
    current_user: User = Depends(require_admin),
    repo_manager: RepositoryManager = Depends(get_repo_manager)
):
    """Get system statistics and metrics."""
    try:
        cache_manager = get_cache_manager()
        
        # Try to get from cache first
        cached_stats = cache_manager.get_system_stats()
        if cached_stats:
            logger.debug("Cache hit for system stats")
            return cached_stats
        
        launch_repo = repo_manager.launch_repository
        
        # Get all launches for analysis
        all_launches = launch_repo.get_all()
        
        # Basic statistics
        total_launches = len(all_launches)
        upcoming_launches = len([l for l in all_launches if l.launch_date and l.launch_date > datetime.utcnow()])
        historical_launches = total_launches - upcoming_launches
        
        # Status breakdown
        status_counts = {}
        for launch in all_launches:
            status = launch.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Vehicle type breakdown
        vehicle_counts = {}
        for launch in all_launches:
            if launch.vehicle_type:
                vehicle = launch.vehicle_type
                vehicle_counts[vehicle] = vehicle_counts.get(vehicle, 0) + 1
        
        # Recent activity (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_launches = [
            l for l in all_launches 
            if l.created_at and l.created_at > thirty_days_ago
        ]
        
        # Data quality metrics
        launches_with_details = len([l for l in all_launches if l.details])
        launches_with_patches = len([l for l in all_launches if l.mission_patch_url])
        launches_with_webcasts = len([l for l in all_launches if l.webcast_url])
        
        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "launch_statistics": {
                "total_launches": total_launches,
                "upcoming_launches": upcoming_launches,
                "historical_launches": historical_launches,
                "status_breakdown": status_counts,
                "vehicle_breakdown": vehicle_counts
            },
            "data_quality": {
                "launches_with_details": launches_with_details,
                "launches_with_patches": launches_with_patches,
                "launches_with_webcasts": launches_with_webcasts,
                "detail_coverage": round(launches_with_details / total_launches * 100, 2) if total_launches > 0 else 0,
                "patch_coverage": round(launches_with_patches / total_launches * 100, 2) if total_launches > 0 else 0,
                "webcast_coverage": round(launches_with_webcasts / total_launches * 100, 2) if total_launches > 0 else 0
            },
            "recent_activity": {
                "new_launches_last_30_days": len(recent_launches),
                "last_data_update": max(l.updated_at for l in all_launches).isoformat() if all_launches else None
            },
            "cache_statistics": cache_manager.get_cache_info()
        }
        
        # Cache the result
        cache_manager.set_system_stats(stats)
        
        return stats
        
    except Exception as e:
        logger.error(f"System stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system statistics"
        )


@router.get(
    "/conflicts",
    summary="Get data conflicts",
    description="Get list of unresolved data conflicts between sources."
)
async def get_data_conflicts(
    resolved: bool = False,
    current_user: User = Depends(require_admin),
    repo_manager: RepositoryManager = Depends(get_repo_manager)
):
    """Get data conflicts for admin review."""
    try:
        conflict_repo = repo_manager.conflict_repository
        conflicts = conflict_repo.get_conflicts(resolved=resolved)
        
        # Convert to response format
        conflict_list = []
        for conflict in conflicts:
            conflict_data = {
                "id": conflict.id,
                "launch_id": conflict.launch_id,
                "field_name": conflict.field_name,
                "source1_value": conflict.source1_value,
                "source2_value": conflict.source2_value,
                "confidence_score": float(conflict.confidence_score) if conflict.confidence_score else 0.0,
                "resolved": conflict.resolved,
                "created_at": conflict.created_at.isoformat(),
                "resolved_at": conflict.resolved_at.isoformat() if conflict.resolved_at else None
            }
            
            # Add launch information if available
            if hasattr(conflict, 'launch') and conflict.launch:
                conflict_data["launch"] = {
                    "slug": conflict.launch.slug,
                    "mission_name": conflict.launch.mission_name
                }
            
            conflict_list.append(conflict_data)
        
        return {
            "conflicts": conflict_list,
            "total": len(conflict_list),
            "resolved": resolved
        }
        
    except Exception as e:
        logger.error(f"Get conflicts error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get data conflicts"
        )


@router.post(
    "/conflicts/{conflict_id}/resolve",
    summary="Resolve data conflict",
    description="Mark a data conflict as resolved."
)
async def resolve_conflict(
    conflict_id: int,
    current_user: User = Depends(require_admin),
    repo_manager: RepositoryManager = Depends(get_repo_manager)
):
    """Resolve a data conflict."""
    try:
        conflict_repo = repo_manager.conflict_repository
        success = conflict_repo.resolve_conflict(conflict_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conflict not found"
            )
        
        return {
            "message": "Conflict resolved successfully",
            "conflict_id": conflict_id,
            "resolved_by": current_user.username,
            "resolved_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resolve conflict error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve conflict"
        )

@router.get(
    "/cache/info",
    summary="Get cache information",
    description="Get detailed cache statistics and information."
)
async def get_cache_info(
    current_user: User = Depends(require_admin)
):
    """Get cache information and statistics."""
    try:
        cache_manager = get_cache_manager()
        cache_info = cache_manager.get_cache_info()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cache_info": cache_info
        }
        
    except Exception as e:
        logger.error(f"Cache info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cache information"
        )


@router.post(
    "/cache/invalidate",
    summary="Invalidate cache",
    description="Invalidate all or specific cache entries."
)
async def invalidate_cache(
    cache_type: str = Query("all", description="Type of cache to invalidate: all, launches, stats"),
    current_user: User = Depends(require_admin)
):
    """Invalidate cache entries."""
    try:
        cache_manager = get_cache_manager()
        
        if cache_type == "all":
            deleted_count = cache_manager.invalidate_all_cache()
            message = f"Invalidated all cache entries ({deleted_count} keys)"
        elif cache_type == "launches":
            deleted_count = cache_manager.invalidate_all_launches()
            message = f"Invalidated launch cache entries ({deleted_count} keys)"
        elif cache_type == "stats":
            deleted_count = cache_manager.invalidate_stats_cache()
            message = f"Invalidated stats cache entries ({deleted_count} keys)"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cache type. Use: all, launches, or stats"
            )
        
        logger.info(f"Cache invalidation by {current_user.username}: {message}")
        
        return {
            "message": message,
            "cache_type": cache_type,
            "deleted_count": deleted_count,
            "invalidated_by": current_user.username,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache invalidation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate cache"
        )


@router.post(
    "/cache/warm",
    summary="Warm cache",
    description="Warm cache with frequently accessed data."
)
async def warm_cache(
    current_user: User = Depends(require_admin)
):
    """Warm cache with frequently accessed data."""
    try:
        from src.cache.cache_warming import get_cache_warming_service
        
        cache_warming_service = get_cache_warming_service()
        result = cache_warming_service.warm_all_caches()
        
        logger.info(f"Cache warming triggered by {current_user.username}")
        
        return {
            "message": "Cache warming completed",
            "result": result,
            "triggered_by": current_user.username,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cache warming error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to warm cache"
        )


@router.get(
    "/cache/warming/status",
    summary="Get cache warming status",
    description="Get the status of the last cache warming operation."
)
async def get_cache_warming_status(
    current_user: User = Depends(require_admin)
):
    """Get cache warming status."""
    try:
        from src.cache.cache_warming import get_cache_warming_service
        
        cache_warming_service = get_cache_warming_service()
        status = cache_warming_service.get_cache_warming_status()
        
        return status
        
    except Exception as e:
        logger.error(f"Cache warming status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cache warming status"
        )


@router.get(
    "/performance/database",
    summary="Get database performance analysis",
    description="Get database performance analysis and optimization recommendations."
)
async def get_database_performance(
    current_user: User = Depends(require_admin)
):
    """Get database performance analysis."""
    try:
        from src.database_optimization import get_database_optimizer
        
        db_optimizer = get_database_optimizer()
        analysis = db_optimizer.analyze_query_performance()
        
        return {
            "message": "Database performance analysis completed",
            "analysis": analysis,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Database performance analysis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze database performance"
        )


@router.post(
    "/performance/optimize",
    summary="Optimize database performance",
    description="Create performance indexes and run database optimization."
)
async def optimize_database_performance(
    current_user: User = Depends(require_admin)
):
    """Optimize database performance."""
    try:
        from src.database_optimization import get_database_optimizer
        
        db_optimizer = get_database_optimizer()
        
        # Create performance indexes
        index_results = db_optimizer.create_performance_indexes()
        
        # Run VACUUM ANALYZE
        vacuum_results = db_optimizer.vacuum_analyze_tables()
        
        logger.info(f"Database optimization triggered by {current_user.username}")
        
        return {
            "message": "Database optimization completed",
            "index_creation": index_results,
            "vacuum_analyze": vacuum_results,
            "optimized_by": current_user.username,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Database optimization error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to optimize database"
        )