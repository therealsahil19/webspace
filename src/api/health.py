"""
Health check endpoints for SpaceX Launch Tracker API.
Provides comprehensive health monitoring and metrics endpoints.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Response
from fastapi.responses import PlainTextResponse
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

import structlog
from ..monitoring.health_checks import get_health_checker, HealthStatus
from ..monitoring.metrics import get_metrics_collector
from ..auth.dependencies import require_admin_user
from ..models.schemas import User

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", summary="Basic health check", description="Quick health status check")
async def basic_health_check():
    """Basic health check endpoint for load balancers."""
    try:
        health_checker = get_health_checker()
        
        # Run only critical checks for basic health
        critical_checks = ['database', 'redis']
        results = {}
        
        for check_name in critical_checks:
            result = await health_checker.run_check(check_name)
            results[check_name] = result
            
            # If any critical check fails, return unhealthy
            if result.status == HealthStatus.UNHEALTHY:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Critical component {check_name} is unhealthy: {result.message}"
                )
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "spacex-launch-tracker",
            "version": "1.0.0",
            "checks": {name: result.to_dict() for name, result in results.items()}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Basic health check failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/detailed", summary="Detailed health check", description="Comprehensive health status")
async def detailed_health_check():
    """Detailed health check with all components."""
    try:
        health_checker = get_health_checker()
        health_status = await health_checker.get_overall_health()
        
        # Set appropriate HTTP status code
        if health_status['status'] == 'unhealthy':
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif health_status['status'] == 'degraded':
            status_code = status.HTTP_200_OK  # Still operational
        else:
            status_code = status.HTTP_200_OK
        
        # Add additional system information
        health_status.update({
            "service": "spacex-launch-tracker",
            "version": "1.0.0",
            "environment": "production",  # Could be from env var
        })
        
        return Response(
            content=health_status,
            status_code=status_code,
            media_type="application/json"
        )
        
    except Exception as e:
        logger.error("Detailed health check failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/live", summary="Liveness probe", description="Kubernetes liveness probe endpoint")
async def liveness_probe():
    """
    Liveness probe for Kubernetes.
    Returns 200 if the application is running, regardless of dependencies.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "spacex-launch-tracker"
    }


@router.get("/ready", summary="Readiness probe", description="Kubernetes readiness probe endpoint")
async def readiness_probe():
    """
    Readiness probe for Kubernetes.
    Returns 200 only if the application is ready to serve traffic.
    """
    try:
        health_checker = get_health_checker()
        
        # Check critical dependencies for readiness
        critical_checks = ['database', 'redis']
        for check_name in critical_checks:
            result = await health_checker.run_check(check_name)
            
            if result.status == HealthStatus.UNHEALTHY:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Not ready: {check_name} is unhealthy"
                )
        
        return {
            "status": "ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "spacex-launch-tracker"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness probe failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Not ready: {str(e)}"
        )


@router.get("/metrics", summary="Prometheus metrics", description="Prometheus metrics endpoint")
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    try:
        metrics_collector = get_metrics_collector()
        metrics_data = metrics_collector.get_metrics()
        
        return PlainTextResponse(
            content=metrics_data,
            media_type=metrics_collector.get_content_type()
        )
        
    except Exception as e:
        logger.error("Metrics endpoint failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Metrics collection failed: {str(e)}"
        )


@router.get("/check/{check_name}", summary="Individual health check", description="Run a specific health check")
async def individual_health_check(check_name: str):
    """Run a specific health check by name."""
    try:
        health_checker = get_health_checker()
        result = await health_checker.run_check(check_name)
        
        # Set status code based on result
        if result.status == HealthStatus.UNHEALTHY:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif result.status == HealthStatus.DEGRADED:
            status_code = status.HTTP_200_OK
        else:
            status_code = status.HTTP_200_OK
        
        return Response(
            content=result.to_dict(),
            status_code=status_code,
            media_type="application/json"
        )
        
    except Exception as e:
        logger.error(f"Health check {check_name} failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/admin/status", summary="Admin health status", description="Detailed health status for administrators")
async def admin_health_status(current_user: User = Depends(require_admin_user)):
    """
    Administrative health status endpoint with sensitive information.
    Requires admin authentication.
    """
    try:
        health_checker = get_health_checker()
        health_status = await health_checker.get_overall_health()
        
        # Add administrative details
        admin_details = {
            "system_info": {
                "python_version": "3.11+",  # Could get actual version
                "service_uptime": "unknown",  # Could track actual uptime
                "last_restart": "unknown",
            },
            "performance_metrics": {
                "avg_response_time": "unknown",  # Could calculate from metrics
                "request_rate": "unknown",
                "error_rate": "unknown",
            }
        }
        
        health_status["admin_details"] = admin_details
        
        return health_status
        
    except Exception as e:
        logger.error("Admin health status failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Admin health check failed: {str(e)}"
        )


@router.get("/admin/metrics/summary", summary="Metrics summary", description="Summary of key metrics")
async def metrics_summary(current_user: User = Depends(require_admin_user)):
    """
    Get a summary of key metrics for administrators.
    """
    try:
        # This would typically query the metrics collector for aggregated data
        # For now, return a placeholder structure
        
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scraping_metrics": {
                "total_requests_24h": 0,  # Would calculate from metrics
                "success_rate_24h": 0.0,
                "avg_duration_seconds": 0.0,
                "last_successful_scrape": None,
            },
            "api_metrics": {
                "total_requests_24h": 0,
                "avg_response_time_ms": 0.0,
                "error_rate_24h": 0.0,
                "active_requests": 0,
            },
            "database_metrics": {
                "total_launches": 0,
                "avg_query_time_ms": 0.0,
                "active_connections": 0,
            },
            "cache_metrics": {
                "hit_rate": 0.0,
                "total_operations_24h": 0,
            }
        }
        
        return summary
        
    except Exception as e:
        logger.error("Metrics summary failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Metrics summary failed: {str(e)}"
        )


@router.post("/admin/checks/run", summary="Run health checks", description="Manually trigger health checks")
async def run_health_checks(
    checks: Optional[List[str]] = None,
    current_user: User = Depends(require_admin_user)
):
    """
    Manually trigger health checks.
    
    Args:
        checks: Optional list of specific checks to run. If None, runs all checks.
    """
    try:
        health_checker = get_health_checker()
        
        if checks:
            # Run specific checks
            results = {}
            for check_name in checks:
                result = await health_checker.run_check(check_name)
                results[check_name] = result.to_dict()
        else:
            # Run all checks
            all_results = await health_checker.run_all_checks()
            results = {name: result.to_dict() for name, result in all_results.items()}
        
        return {
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks_run": list(results.keys()),
            "results": results
        }
        
    except Exception as e:
        logger.error("Manual health check run failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check run failed: {str(e)}"
        )


@router.get("/admin/logs/recent", summary="Recent log entries", description="Get recent log entries")
async def recent_logs(
    lines: int = 100,
    level: str = "INFO",
    current_user: User = Depends(require_admin_user)
):
    """
    Get recent log entries for debugging.
    
    Args:
        lines: Number of log lines to return
        level: Minimum log level to include
    """
    try:
        # This would typically read from log files
        # For now, return a placeholder
        
        logs = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "lines_requested": lines,
            "level_filter": level,
            "entries": [
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "INFO",
                    "logger": "src.api.health",
                    "message": "Recent logs endpoint accessed",
                    "component": "health_api"
                }
            ]
        }
        
        return logs
        
    except Exception as e:
        logger.error("Recent logs retrieval failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Log retrieval failed: {str(e)}"
        )