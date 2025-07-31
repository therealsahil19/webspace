"""
Comprehensive health check system for SpaceX Launch Tracker.
Monitors all system components and provides detailed health status.
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

import structlog
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..database import get_db_session
from ..cache.redis_client import get_redis_client
from ..repositories.launch_repository import LaunchRepository
from .metrics import get_metrics_collector

logger = structlog.get_logger(__name__)


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    duration_ms: float
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'duration_ms': self.duration_ms,
            'timestamp': self.timestamp.isoformat(),
        }


class HealthChecker:
    """Comprehensive health checker for all system components."""
    
    def __init__(self):
        self.checks: Dict[str, Callable[[], Awaitable[HealthCheckResult]]] = {}
        self.register_default_checks()
        logger.info("Health checker initialized")
    
    def register_default_checks(self):
        """Register all default health checks."""
        self.register_check('database', self.check_database_health)
        self.register_check('redis', self.check_redis_health)
        self.register_check('scraping_freshness', self.check_scraping_freshness)
        self.register_check('celery_workers', self.check_celery_workers)
        self.register_check('data_quality', self.check_data_quality)
        self.register_check('disk_space', self.check_disk_space)
        self.register_check('memory_usage', self.check_memory_usage)
    
    def register_check(self, name: str, check_func: Callable[[], Awaitable[HealthCheckResult]]):
        """Register a health check function."""
        self.checks[name] = check_func
        logger.debug(f"Registered health check: {name}")
    
    async def run_check(self, name: str) -> HealthCheckResult:
        """Run a specific health check."""
        if name not in self.checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Unknown health check: {name}",
                details={},
                duration_ms=0,
                timestamp=datetime.now(timezone.utc)
            )
        
        start_time = time.time()
        try:
            result = await self.checks[name]()
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Health check {name} failed", error=str(e), exc_info=True)
            
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                details={'error': str(e), 'error_type': type(e).__name__},
                duration_ms=duration_ms,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks."""
        logger.info("Running all health checks")
        
        # Run all checks concurrently
        tasks = {name: self.run_check(name) for name in self.checks.keys()}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # Combine results
        check_results = {}
        for name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                check_results[name] = HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check exception: {str(result)}",
                    details={'error': str(result)},
                    duration_ms=0,
                    timestamp=datetime.now(timezone.utc)
                )
            else:
                check_results[name] = result
        
        # Update metrics
        self._update_health_metrics(check_results)
        
        logger.info(f"Completed {len(check_results)} health checks")
        return check_results
    
    async def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        check_results = await self.run_all_checks()
        
        # Determine overall status
        statuses = [result.status for result in check_results.values()]
        
        if all(status == HealthStatus.HEALTHY for status in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            overall_status = HealthStatus.UNHEALTHY
        else:
            overall_status = HealthStatus.DEGRADED
        
        # Count statuses
        status_counts = {
            'healthy': sum(1 for s in statuses if s == HealthStatus.HEALTHY),
            'degraded': sum(1 for s in statuses if s == HealthStatus.DEGRADED),
            'unhealthy': sum(1 for s in statuses if s == HealthStatus.UNHEALTHY),
        }
        
        return {
            'status': overall_status.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'checks': {name: result.to_dict() for name, result in check_results.items()},
            'summary': {
                'total_checks': len(check_results),
                'status_counts': status_counts,
            }
        }
    
    def _update_health_metrics(self, results: Dict[str, HealthCheckResult]):
        """Update Prometheus metrics with health check results."""
        metrics = get_metrics_collector()
        
        # Update component health metrics
        for name, result in results.items():
            metrics.update_component_health(name, result.status.value)
        
        # Update overall system health
        statuses = [result.status for result in results.values()]
        if all(status == HealthStatus.HEALTHY for status in statuses):
            overall_status = 'healthy'
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            overall_status = 'unhealthy'
        else:
            overall_status = 'degraded'
        
        metrics.update_system_health(overall_status)
    
    # Individual health check methods
    async def check_database_health(self) -> HealthCheckResult:
        """Check database connectivity and performance."""
        start_time = time.time()
        
        try:
            with get_db_session() as session:
                # Test basic connectivity
                result = session.execute(text("SELECT 1")).scalar()
                
                # Test launch repository
                launch_repo = LaunchRepository(session)
                stats = launch_repo.get_launch_statistics()
                
                # Check connection pool
                pool = session.get_bind().pool
                pool_status = {
                    'size': pool.size(),
                    'checked_in': pool.checkedin(),
                    'checked_out': pool.checkedout(),
                    'overflow': pool.overflow(),
                }
                
                duration_ms = (time.time() - start_time) * 1000
                
                # Determine status based on performance
                if duration_ms > 1000:  # > 1 second
                    status = HealthStatus.DEGRADED
                    message = "Database responding slowly"
                else:
                    status = HealthStatus.HEALTHY
                    message = "Database is healthy"
                
                return HealthCheckResult(
                    name='database',
                    status=status,
                    message=message,
                    details={
                        'connection_test': result == 1,
                        'total_launches': stats.get('total_launches', 0),
                        'latest_launch': stats.get('latest_launch_date'),
                        'pool_status': pool_status,
                        'query_duration_ms': duration_ms,
                    },
                    duration_ms=duration_ms,
                    timestamp=datetime.now(timezone.utc)
                )
                
        except SQLAlchemyError as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name='database',
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {str(e)}",
                details={'error': str(e), 'error_type': 'SQLAlchemyError'},
                duration_ms=duration_ms,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def check_redis_health(self) -> HealthCheckResult:
        """Check Redis connectivity and performance."""
        start_time = time.time()
        
        try:
            redis_client = get_redis_client()
            
            # Test basic connectivity
            await redis_client.ping()
            
            # Test read/write operations
            test_key = "health_check_test"
            test_value = str(int(time.time()))
            
            await redis_client.set(test_key, test_value, ex=60)  # Expire in 60 seconds
            retrieved_value = await redis_client.get(test_key)
            await redis_client.delete(test_key)
            
            # Get Redis info
            info = await redis_client.info()
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Determine status
            if duration_ms > 500:  # > 500ms
                status = HealthStatus.DEGRADED
                message = "Redis responding slowly"
            elif retrieved_value.decode() != test_value:
                status = HealthStatus.DEGRADED
                message = "Redis read/write test failed"
            else:
                status = HealthStatus.HEALTHY
                message = "Redis is healthy"
            
            return HealthCheckResult(
                name='redis',
                status=status,
                message=message,
                details={
                    'ping_successful': True,
                    'read_write_test': retrieved_value.decode() == test_value,
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory_human': info.get('used_memory_human', 'unknown'),
                    'response_time_ms': duration_ms,
                },
                duration_ms=duration_ms,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name='redis',
                status=HealthStatus.UNHEALTHY,
                message=f"Redis error: {str(e)}",
                details={'error': str(e), 'error_type': type(e).__name__},
                duration_ms=duration_ms,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def check_scraping_freshness(self) -> HealthCheckResult:
        """Check if scraped data is fresh."""
        start_time = time.time()
        
        try:
            with get_db_session() as session:
                launch_repo = LaunchRepository(session)
                stats = launch_repo.get_launch_statistics()
                
                latest_update = stats.get('latest_update_date')
                if not latest_update:
                    return HealthCheckResult(
                        name='scraping_freshness',
                        status=HealthStatus.UNHEALTHY,
                        message="No data found in database",
                        details={'latest_update': None},
                        duration_ms=(time.time() - start_time) * 1000,
                        timestamp=datetime.now(timezone.utc)
                    )
                
                # Check data age
                now = datetime.now(timezone.utc)
                if latest_update.tzinfo is None:
                    latest_update = latest_update.replace(tzinfo=timezone.utc)
                
                age = now - latest_update
                age_hours = age.total_seconds() / 3600
                
                # Determine status based on data age
                if age_hours > 24:  # > 24 hours
                    status = HealthStatus.UNHEALTHY
                    message = f"Data is {age_hours:.1f} hours old"
                elif age_hours > 12:  # > 12 hours
                    status = HealthStatus.DEGRADED
                    message = f"Data is {age_hours:.1f} hours old"
                else:
                    status = HealthStatus.HEALTHY
                    message = f"Data is {age_hours:.1f} hours old"
                
                return HealthCheckResult(
                    name='scraping_freshness',
                    status=status,
                    message=message,
                    details={
                        'latest_update': latest_update.isoformat(),
                        'age_hours': age_hours,
                        'total_launches': stats.get('total_launches', 0),
                    },
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now(timezone.utc)
                )
                
        except Exception as e:
            return HealthCheckResult(
                name='scraping_freshness',
                status=HealthStatus.UNHEALTHY,
                message=f"Error checking data freshness: {str(e)}",
                details={'error': str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def check_celery_workers(self) -> HealthCheckResult:
        """Check Celery worker status."""
        start_time = time.time()
        
        try:
            from ..celery_app import celery_app
            
            # Check active workers
            inspect = celery_app.control.inspect()
            active_workers = inspect.active()
            stats = inspect.stats()
            
            if not active_workers:
                return HealthCheckResult(
                    name='celery_workers',
                    status=HealthStatus.UNHEALTHY,
                    message="No active Celery workers found",
                    details={'active_workers': 0, 'worker_stats': {}},
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now(timezone.utc)
                )
            
            worker_count = len(active_workers)
            worker_details = {}
            
            for worker_name, tasks in active_workers.items():
                worker_details[worker_name] = {
                    'active_tasks': len(tasks),
                    'stats': stats.get(worker_name, {}) if stats else {}
                }
            
            # Determine status
            if worker_count == 0:
                status = HealthStatus.UNHEALTHY
                message = "No active workers"
            elif worker_count < 2:  # Assuming we want at least 2 workers
                status = HealthStatus.DEGRADED
                message = f"Only {worker_count} worker(s) active"
            else:
                status = HealthStatus.HEALTHY
                message = f"{worker_count} workers active"
            
            return HealthCheckResult(
                name='celery_workers',
                status=status,
                message=message,
                details={
                    'active_workers': worker_count,
                    'worker_details': worker_details,
                },
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            return HealthCheckResult(
                name='celery_workers',
                status=HealthStatus.UNHEALTHY,
                message=f"Error checking Celery workers: {str(e)}",
                details={'error': str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def check_data_quality(self) -> HealthCheckResult:
        """Check data quality metrics."""
        start_time = time.time()
        
        try:
            with get_db_session() as session:
                launch_repo = LaunchRepository(session)
                
                # Get data quality metrics
                total_launches = session.execute(
                    text("SELECT COUNT(*) FROM launches")
                ).scalar()
                
                launches_with_dates = session.execute(
                    text("SELECT COUNT(*) FROM launches WHERE launch_date IS NOT NULL")
                ).scalar()
                
                launches_with_details = session.execute(
                    text("SELECT COUNT(*) FROM launches WHERE details IS NOT NULL AND details != ''")
                ).scalar()
                
                # Calculate quality percentages
                date_completeness = (launches_with_dates / total_launches * 100) if total_launches > 0 else 0
                detail_completeness = (launches_with_details / total_launches * 100) if total_launches > 0 else 0
                
                # Determine status based on data quality
                if date_completeness < 50 or detail_completeness < 30:
                    status = HealthStatus.UNHEALTHY
                    message = "Poor data quality detected"
                elif date_completeness < 80 or detail_completeness < 50:
                    status = HealthStatus.DEGRADED
                    message = "Data quality could be improved"
                else:
                    status = HealthStatus.HEALTHY
                    message = "Data quality is good"
                
                return HealthCheckResult(
                    name='data_quality',
                    status=status,
                    message=message,
                    details={
                        'total_launches': total_launches,
                        'date_completeness_percent': round(date_completeness, 1),
                        'detail_completeness_percent': round(detail_completeness, 1),
                        'launches_with_dates': launches_with_dates,
                        'launches_with_details': launches_with_details,
                    },
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now(timezone.utc)
                )
                
        except Exception as e:
            return HealthCheckResult(
                name='data_quality',
                status=HealthStatus.UNHEALTHY,
                message=f"Error checking data quality: {str(e)}",
                details={'error': str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def check_disk_space(self) -> HealthCheckResult:
        """Check available disk space."""
        start_time = time.time()
        
        try:
            import shutil
            
            # Check disk space for current directory
            total, used, free = shutil.disk_usage('.')
            
            # Convert to GB
            total_gb = total / (1024**3)
            used_gb = used / (1024**3)
            free_gb = free / (1024**3)
            used_percent = (used / total) * 100
            
            # Determine status based on free space
            if free_gb < 1:  # Less than 1GB free
                status = HealthStatus.UNHEALTHY
                message = f"Critical: Only {free_gb:.1f}GB free"
            elif used_percent > 90:  # More than 90% used
                status = HealthStatus.DEGRADED
                message = f"Warning: {used_percent:.1f}% disk usage"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage: {used_percent:.1f}%"
            
            return HealthCheckResult(
                name='disk_space',
                status=status,
                message=message,
                details={
                    'total_gb': round(total_gb, 2),
                    'used_gb': round(used_gb, 2),
                    'free_gb': round(free_gb, 2),
                    'used_percent': round(used_percent, 1),
                },
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            return HealthCheckResult(
                name='disk_space',
                status=HealthStatus.UNHEALTHY,
                message=f"Error checking disk space: {str(e)}",
                details={'error': str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def check_memory_usage(self) -> HealthCheckResult:
        """Check memory usage."""
        start_time = time.time()
        
        try:
            import psutil
            
            # Get memory information
            memory = psutil.virtual_memory()
            
            # Convert to MB
            total_mb = memory.total / (1024**2)
            available_mb = memory.available / (1024**2)
            used_mb = memory.used / (1024**2)
            used_percent = memory.percent
            
            # Determine status based on memory usage
            if used_percent > 95:  # More than 95% used
                status = HealthStatus.UNHEALTHY
                message = f"Critical: {used_percent:.1f}% memory usage"
            elif used_percent > 85:  # More than 85% used
                status = HealthStatus.DEGRADED
                message = f"Warning: {used_percent:.1f}% memory usage"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage: {used_percent:.1f}%"
            
            return HealthCheckResult(
                name='memory_usage',
                status=status,
                message=message,
                details={
                    'total_mb': round(total_mb, 2),
                    'used_mb': round(used_mb, 2),
                    'available_mb': round(available_mb, 2),
                    'used_percent': round(used_percent, 1),
                },
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc)
            )
            
        except ImportError:
            # psutil not available
            return HealthCheckResult(
                name='memory_usage',
                status=HealthStatus.DEGRADED,
                message="Memory monitoring not available (psutil not installed)",
                details={'error': 'psutil not available'},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc)
            )
        except Exception as e:
            return HealthCheckResult(
                name='memory_usage',
                status=HealthStatus.UNHEALTHY,
                message=f"Error checking memory usage: {str(e)}",
                details={'error': str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(timezone.utc)
            )


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get the global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker