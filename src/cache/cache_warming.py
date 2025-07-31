"""
Cache warming service for preloading frequently accessed data.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio

from src.cache.cache_manager import get_cache_manager
from src.repositories import get_repository_manager
from src.models.schemas import LaunchResponse

logger = logging.getLogger(__name__)


class CacheWarmingService:
    """Service for warming up cache with frequently accessed data."""
    
    def __init__(self):
        """Initialize cache warming service."""
        self.cache_manager = get_cache_manager()
        self.repo_manager = get_repository_manager()
        
    def warm_upcoming_launches(self) -> Dict[str, Any]:
        """Warm cache with upcoming launches data."""
        if not self.cache_manager.is_enabled():
            return {"status": "disabled", "message": "Cache not enabled"}
        
        try:
            launch_repo = self.repo_manager.launch_repository
            
            # Get upcoming launches from database
            upcoming_launches = launch_repo.get_upcoming_launches(limit=100, include_sources=True)
            
            if not upcoming_launches:
                return {"status": "no_data", "message": "No upcoming launches found"}
            
            # Convert to response format
            launch_dicts = []
            for launch in upcoming_launches:
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
                
                launch_dicts.append(launch_dict)
            
            # Warm cache for different limits
            limits = [10, 25, 50]
            warmed_count = 0
            
            for limit in limits:
                limited_data = launch_dicts[:limit]
                if self.cache_manager.set_upcoming_launches(limited_data, limit):
                    warmed_count += 1
                    logger.debug(f"Warmed upcoming launches cache for limit {limit}")
            
            # Also cache individual launch details for the next few launches
            detail_count = 0
            for launch_dict in launch_dicts[:10]:  # Cache first 10 upcoming launches
                if self.cache_manager.set_launch_detail(launch_dict['slug'], launch_dict):
                    detail_count += 1
            
            return {
                "status": "success",
                "upcoming_launches_cached": len(launch_dicts),
                "limits_warmed": warmed_count,
                "details_cached": detail_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error warming upcoming launches cache: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def warm_popular_launches(self) -> Dict[str, Any]:
        """Warm cache with popular/recent launch data."""
        if not self.cache_manager.is_enabled():
            return {"status": "disabled", "message": "Cache not enabled"}
        
        try:
            launch_repo = self.repo_manager.launch_repository
            
            # Get recent launches (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            all_launches = launch_repo.get_all()
            recent_launches = [
                l for l in all_launches 
                if l.launch_date and l.launch_date > thirty_days_ago
            ]
            
            # Sort by launch date (most recent first)
            recent_launches.sort(key=lambda x: x.launch_date or datetime.min, reverse=True)
            
            # Cache individual launch details for recent launches
            cached_count = 0
            for launch in recent_launches[:20]:  # Cache 20 most recent
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
                
                if self.cache_manager.set_launch_detail(launch.slug, launch_dict):
                    cached_count += 1
            
            return {
                "status": "success",
                "recent_launches_found": len(recent_launches),
                "details_cached": cached_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error warming popular launches cache: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def warm_launches_lists(self) -> Dict[str, Any]:
        """Warm cache with common launch list queries."""
        if not self.cache_manager.is_enabled():
            return {"status": "disabled", "message": "Cache not enabled"}
        
        try:
            launch_repo = self.repo_manager.launch_repository
            
            # Common query patterns to warm
            query_patterns = [
                {"skip": 0, "limit": 25, "status": None, "vehicle_type": None},
                {"skip": 0, "limit": 50, "status": None, "vehicle_type": None},
                {"skip": 0, "limit": 25, "status": "success", "vehicle_type": None},
                {"skip": 0, "limit": 25, "status": "upcoming", "vehicle_type": None},
                {"skip": 0, "limit": 25, "status": None, "vehicle_type": "Falcon 9"},
                {"skip": 0, "limit": 25, "status": None, "vehicle_type": "Falcon Heavy"},
            ]
            
            warmed_count = 0
            
            for pattern in query_patterns:
                try:
                    # Get launches with filters
                    all_launches = launch_repo.get_all()
                    filtered_launches = all_launches
                    
                    # Apply filters
                    if pattern["status"]:
                        filtered_launches = [l for l in filtered_launches if l.status == pattern["status"]]
                    if pattern["vehicle_type"]:
                        filtered_launches = [l for l in filtered_launches if l.vehicle_type == pattern["vehicle_type"]]
                    
                    total_launches = len(filtered_launches)
                    
                    # Apply pagination
                    launches = filtered_launches[pattern["skip"]:pattern["skip"] + pattern["limit"]]
                    
                    # Convert to response format
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
                        launch_responses.append(launch_dict)
                    
                    # Create pagination metadata
                    pagination_meta = {
                        "total": total_launches,
                        "skip": pattern["skip"],
                        "limit": pattern["limit"],
                        "has_next": (pattern["skip"] + pattern["limit"]) < total_launches,
                        "has_prev": pattern["skip"] > 0
                    }
                    
                    result = {
                        "data": launch_responses,
                        "meta": pagination_meta
                    }
                    
                    # Cache the result
                    if self.cache_manager.set_launches_list(
                        result,
                        skip=pattern["skip"],
                        limit=pattern["limit"],
                        status=pattern["status"],
                        vehicle_type=pattern["vehicle_type"]
                    ):
                        warmed_count += 1
                        logger.debug(f"Warmed launches list cache for pattern: {pattern}")
                
                except Exception as e:
                    logger.error(f"Error warming cache for pattern {pattern}: {e}")
                    continue
            
            return {
                "status": "success",
                "patterns_attempted": len(query_patterns),
                "patterns_warmed": warmed_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error warming launches lists cache: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def warm_all_caches(self) -> Dict[str, Any]:
        """Warm all cache types."""
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "success",
            "results": {}
        }
        
        # Warm upcoming launches
        upcoming_result = self.warm_upcoming_launches()
        results["results"]["upcoming_launches"] = upcoming_result
        if upcoming_result["status"] != "success":
            results["overall_status"] = "partial"
        
        # Warm popular launches
        popular_result = self.warm_popular_launches()
        results["results"]["popular_launches"] = popular_result
        if popular_result["status"] != "success":
            results["overall_status"] = "partial"
        
        # Warm launch lists
        lists_result = self.warm_launches_lists()
        results["results"]["launch_lists"] = lists_result
        if lists_result["status"] != "success":
            results["overall_status"] = "partial"
        
        # Update cache warming status
        self.cache_manager.set_cache_warming_status(results)
        
        logger.info(f"Cache warming completed with status: {results['overall_status']}")
        
        return results
    
    def get_cache_warming_status(self) -> Dict[str, Any]:
        """Get the status of the last cache warming operation."""
        if not self.cache_manager.is_enabled():
            return {"status": "disabled", "message": "Cache not enabled"}
        
        status = self.cache_manager.get_cache_warming_status()
        if status:
            return status
        
        return {
            "status": "never_run",
            "message": "Cache warming has never been executed"
        }


# Global cache warming service instance
_cache_warming_service: Optional[CacheWarmingService] = None


def get_cache_warming_service() -> CacheWarmingService:
    """Get global cache warming service instance."""
    global _cache_warming_service
    if _cache_warming_service is None:
        _cache_warming_service = CacheWarmingService()
    return _cache_warming_service