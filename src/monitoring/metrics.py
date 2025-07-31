"""
Metrics collection system for SpaceX Launch Tracker using Prometheus.
Tracks scraping success rates, API performance, and system health.
"""

import time
import functools
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timezone
from contextlib import contextmanager

from prometheus_client import (
    Counter, Histogram, Gauge, Info, Enum,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)
import structlog

logger = structlog.get_logger(__name__)


class MetricsCollector:
    """Central metrics collector for the SpaceX Launch Tracker application."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collector.
        
        Args:
            registry: Prometheus registry, uses default if None
        """
        self.registry = registry or CollectorRegistry()
        self._setup_metrics()
        logger.info("Metrics collector initialized")
    
    def _setup_metrics(self):
        """Set up all Prometheus metrics."""
        
        # Application info
        self.app_info = Info(
            'spacex_tracker_info',
            'Application information',
            registry=self.registry
        )
        self.app_info.info({
            'version': '1.0.0',
            'service': 'spacex-launch-tracker',
            'component': 'metrics'
        })
        
        # Scraping metrics
        self.scraping_requests_total = Counter(
            'scraping_requests_total',
            'Total number of scraping requests',
            ['source', 'status'],
            registry=self.registry
        )
        
        self.scraping_duration_seconds = Histogram(
            'scraping_duration_seconds',
            'Time spent scraping data from sources',
            ['source'],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
            registry=self.registry
        )
        
        self.scraped_launches_total = Counter(
            'scraped_launches_total',
            'Total number of launches scraped',
            ['source'],
            registry=self.registry
        )
        
        self.scraping_errors_total = Counter(
            'scraping_errors_total',
            'Total number of scraping errors',
            ['source', 'error_type'],
            registry=self.registry
        )
        
        self.last_successful_scrape = Gauge(
            'last_successful_scrape_timestamp',
            'Timestamp of last successful scrape',
            ['source'],
            registry=self.registry
        )
        
        # Data processing metrics
        self.data_validation_total = Counter(
            'data_validation_total',
            'Total number of data validation attempts',
            ['status'],
            registry=self.registry
        )
        
        self.data_conflicts_detected = Counter(
            'data_conflicts_detected_total',
            'Total number of data conflicts detected',
            ['field_name'],
            registry=self.registry
        )
        
        self.data_deduplication_total = Counter(
            'data_deduplication_total',
            'Total number of duplicate records removed',
            registry=self.registry
        )
        
        self.processing_duration_seconds = Histogram(
            'processing_duration_seconds',
            'Time spent processing scraped data',
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
            registry=self.registry
        )
        
        # Database metrics
        self.database_operations_total = Counter(
            'database_operations_total',
            'Total number of database operations',
            ['operation', 'table', 'status'],
            registry=self.registry
        )
        
        self.database_query_duration_seconds = Histogram(
            'database_query_duration_seconds',
            'Time spent on database queries',
            ['operation', 'table'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry
        )
        
        self.database_connections_active = Gauge(
            'database_connections_active',
            'Number of active database connections',
            registry=self.registry
        )
        
        # API metrics
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total number of HTTP requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        self.http_request_duration_seconds = Histogram(
            'http_request_duration_seconds',
            'Time spent processing HTTP requests',
            ['method', 'endpoint'],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=self.registry
        )
        
        self.active_requests = Gauge(
            'active_requests',
            'Number of active HTTP requests',
            registry=self.registry
        )
        
        # Cache metrics
        self.cache_operations_total = Counter(
            'cache_operations_total',
            'Total number of cache operations',
            ['operation', 'status'],
            registry=self.registry
        )
        
        self.cache_hit_ratio = Gauge(
            'cache_hit_ratio',
            'Cache hit ratio (0-1)',
            registry=self.registry
        )
        
        # Celery task metrics
        self.celery_tasks_total = Counter(
            'celery_tasks_total',
            'Total number of Celery tasks',
            ['task_name', 'status'],
            registry=self.registry
        )
        
        self.celery_task_duration_seconds = Histogram(
            'celery_task_duration_seconds',
            'Time spent executing Celery tasks',
            ['task_name'],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0],
            registry=self.registry
        )
        
        self.celery_queue_size = Gauge(
            'celery_queue_size',
            'Number of tasks in Celery queues',
            ['queue_name'],
            registry=self.registry
        )
        
        # System health metrics
        self.system_health_status = Enum(
            'system_health_status',
            'Overall system health status',
            states=['healthy', 'degraded', 'unhealthy'],
            registry=self.registry
        )
        
        self.component_health_status = Enum(
            'component_health_status',
            'Health status of individual components',
            ['component'],
            states=['healthy', 'degraded', 'unhealthy'],
            registry=self.registry
        )
        
        # Launch data metrics
        self.launches_in_database = Gauge(
            'launches_in_database_total',
            'Total number of launches in database',
            registry=self.registry
        )
        
        self.upcoming_launches = Gauge(
            'upcoming_launches_total',
            'Number of upcoming launches',
            registry=self.registry
        )
        
        self.data_freshness_seconds = Gauge(
            'data_freshness_seconds',
            'Age of the most recent data update',
            registry=self.registry
        )
    
    # Scraping metrics methods
    def record_scraping_request(self, source: str, status: str):
        """Record a scraping request."""
        self.scraping_requests_total.labels(source=source, status=status).inc()
    
    def record_scraping_duration(self, source: str, duration: float):
        """Record scraping duration."""
        self.scraping_duration_seconds.labels(source=source).observe(duration)
    
    def record_scraped_launches(self, source: str, count: int):
        """Record number of launches scraped."""
        self.scraped_launches_total.labels(source=source).inc(count)
    
    def record_scraping_error(self, source: str, error_type: str):
        """Record a scraping error."""
        self.scraping_errors_total.labels(source=source, error_type=error_type).inc()
    
    def update_last_successful_scrape(self, source: str, timestamp: Optional[datetime] = None):
        """Update timestamp of last successful scrape."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        self.last_successful_scrape.labels(source=source).set(timestamp.timestamp())
    
    # Data processing metrics methods
    def record_data_validation(self, status: str):
        """Record data validation result."""
        self.data_validation_total.labels(status=status).inc()
    
    def record_data_conflict(self, field_name: str):
        """Record a data conflict."""
        self.data_conflicts_detected.labels(field_name=field_name).inc()
    
    def record_deduplication(self, count: int = 1):
        """Record data deduplication."""
        self.data_deduplication_total.inc(count)
    
    def record_processing_duration(self, duration: float):
        """Record data processing duration."""
        self.processing_duration_seconds.observe(duration)
    
    # Database metrics methods
    def record_database_operation(self, operation: str, table: str, status: str):
        """Record a database operation."""
        self.database_operations_total.labels(
            operation=operation, table=table, status=status
        ).inc()
    
    def record_database_query_duration(self, operation: str, table: str, duration: float):
        """Record database query duration."""
        self.database_query_duration_seconds.labels(
            operation=operation, table=table
        ).observe(duration)
    
    def update_active_connections(self, count: int):
        """Update active database connections count."""
        self.database_connections_active.set(count)
    
    # API metrics methods
    def record_http_request(self, method: str, endpoint: str, status_code: int):
        """Record an HTTP request."""
        self.http_requests_total.labels(
            method=method, endpoint=endpoint, status_code=status_code
        ).inc()
    
    def record_http_duration(self, method: str, endpoint: str, duration: float):
        """Record HTTP request duration."""
        self.http_request_duration_seconds.labels(
            method=method, endpoint=endpoint
        ).observe(duration)
    
    def increment_active_requests(self):
        """Increment active requests counter."""
        self.active_requests.inc()
    
    def decrement_active_requests(self):
        """Decrement active requests counter."""
        self.active_requests.dec()
    
    # Cache metrics methods
    def record_cache_operation(self, operation: str, status: str):
        """Record a cache operation."""
        self.cache_operations_total.labels(operation=operation, status=status).inc()
    
    def update_cache_hit_ratio(self, ratio: float):
        """Update cache hit ratio."""
        self.cache_hit_ratio.set(ratio)
    
    # Celery metrics methods
    def record_celery_task(self, task_name: str, status: str):
        """Record a Celery task execution."""
        self.celery_tasks_total.labels(task_name=task_name, status=status).inc()
    
    def record_celery_task_duration(self, task_name: str, duration: float):
        """Record Celery task duration."""
        self.celery_task_duration_seconds.labels(task_name=task_name).observe(duration)
    
    def update_queue_size(self, queue_name: str, size: int):
        """Update Celery queue size."""
        self.celery_queue_size.labels(queue_name=queue_name).set(size)
    
    # Health metrics methods
    def update_system_health(self, status: str):
        """Update overall system health status."""
        self.system_health_status.state(status)
    
    def update_component_health(self, component: str, status: str):
        """Update component health status."""
        self.component_health_status.labels(component=component).state(status)
    
    # Launch data metrics methods
    def update_launches_count(self, count: int):
        """Update total launches in database."""
        self.launches_in_database.set(count)
    
    def update_upcoming_launches_count(self, count: int):
        """Update upcoming launches count."""
        self.upcoming_launches.set(count)
    
    def update_data_freshness(self, last_update: datetime):
        """Update data freshness metric."""
        age_seconds = (datetime.now(timezone.utc) - last_update).total_seconds()
        self.data_freshness_seconds.set(age_seconds)
    
    def get_metrics(self) -> str:
        """Get all metrics in Prometheus format."""
        return generate_latest(self.registry).decode('utf-8')
    
    def get_content_type(self) -> str:
        """Get content type for metrics endpoint."""
        return CONTENT_TYPE_LATEST


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


# Decorators for automatic metrics collection
def track_scraping_metrics(source: str):
    """Decorator to automatically track scraping metrics."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            metrics = get_metrics_collector()
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                metrics.record_scraping_request(source, 'success')
                metrics.record_scraping_duration(source, duration)
                metrics.update_last_successful_scrape(source)
                
                # Count launches if result is a list
                if isinstance(result, list):
                    metrics.record_scraped_launches(source, len(result))
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                error_type = type(e).__name__
                
                metrics.record_scraping_request(source, 'error')
                metrics.record_scraping_duration(source, duration)
                metrics.record_scraping_error(source, error_type)
                
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            metrics = get_metrics_collector()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                metrics.record_scraping_request(source, 'success')
                metrics.record_scraping_duration(source, duration)
                metrics.update_last_successful_scrape(source)
                
                if isinstance(result, list):
                    metrics.record_scraped_launches(source, len(result))
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                error_type = type(e).__name__
                
                metrics.record_scraping_request(source, 'error')
                metrics.record_scraping_duration(source, duration)
                metrics.record_scraping_error(source, error_type)
                
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def track_database_metrics(operation: str, table: str):
    """Decorator to automatically track database metrics."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            metrics = get_metrics_collector()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                metrics.record_database_operation(operation, table, 'success')
                metrics.record_database_query_duration(operation, table, duration)
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                metrics.record_database_operation(operation, table, 'error')
                metrics.record_database_query_duration(operation, table, duration)
                
                raise
        
        return wrapper
    
    return decorator


def track_celery_metrics(task_name: str):
    """Decorator to automatically track Celery task metrics."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            metrics = get_metrics_collector()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                metrics.record_celery_task(task_name, 'success')
                metrics.record_celery_task_duration(task_name, duration)
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                metrics.record_celery_task(task_name, 'error')
                metrics.record_celery_task_duration(task_name, duration)
                
                raise
        
        return wrapper
    
    return decorator


@contextmanager
def track_processing_time():
    """Context manager to track data processing time."""
    metrics = get_metrics_collector()
    start_time = time.time()
    
    try:
        yield
    finally:
        duration = time.time() - start_time
        metrics.record_processing_duration(duration)


# Import asyncio at the end to avoid circular imports
import asyncio