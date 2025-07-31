# Logging and Monitoring Implementation

This document describes the comprehensive logging and monitoring system implemented for the SpaceX Launch Tracker application.

## Overview

The logging and monitoring system provides:

- **Structured Logging**: Using structlog for consistent, searchable log output
- **Metrics Collection**: Prometheus-compatible metrics for performance monitoring
- **Health Checks**: Comprehensive health monitoring for all system components
- **Error Tracking**: Sentry integration for error tracking and alerting
- **Log Management**: Automated log rotation and retention policies

## Components

### 1. Structured Logging (`src/logging_config.py`)

#### Features
- JSON and console output formats
- Automatic timestamp and service context addition
- Sensitive data filtering
- File-based logging with rotation
- Sentry integration for error tracking
- Third-party library log level management

#### Usage
```python
from src.logging_config import get_logger, LogContext, TimedOperation

logger = get_logger(__name__, component="my_component")

# Basic logging
logger.info("Operation started", user_id=123, operation="data_sync")

# Context logging
with LogContext(logger, request_id="req-123") as log:
    log.info("Processing request")

# Timed operations
with TimedOperation(logger, "database_query", table="launches"):
    # Database operation here
    pass
```

#### Configuration
Environment variables:
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `LOG_FORMAT`: Output format (json, console)
- `LOG_DIR`: Directory for log files
- `ENABLE_FILE_LOGGING`: Enable file logging (true/false)
- `SENTRY_DSN`: Sentry DSN for error tracking
- `ENVIRONMENT`: Environment name for Sentry

### 2. Metrics Collection (`src/monitoring/metrics.py`)

#### Features
- Prometheus-compatible metrics
- Automatic metric collection decorators
- Scraping performance metrics
- API performance metrics
- Database operation metrics
- Celery task metrics
- System health metrics

#### Metrics Types
- **Counters**: Total requests, errors, tasks executed
- **Histograms**: Response times, processing durations
- **Gauges**: Active connections, queue sizes, data freshness
- **Enums**: Health status indicators

#### Usage
```python
from src.monitoring.metrics import get_metrics_collector, track_scraping_metrics

metrics = get_metrics_collector()

# Manual metrics recording
metrics.record_http_request('GET', '/api/launches', 200)
metrics.record_scraping_duration('spacex', 2.5)

# Automatic metrics with decorators
@track_scraping_metrics('spacex')
async def scrape_spacex_data():
    # Scraping logic here
    return data
```

#### Available Metrics
- `scraping_requests_total`: Total scraping requests by source and status
- `scraping_duration_seconds`: Time spent scraping by source
- `http_requests_total`: HTTP requests by method, endpoint, and status
- `database_operations_total`: Database operations by type and status
- `celery_tasks_total`: Celery tasks by name and status
- `system_health_status`: Overall system health
- `launches_in_database_total`: Total launches in database

### 3. Health Checks (`src/monitoring/health_checks.py`)

#### Features
- Comprehensive component health monitoring
- Async health check execution
- Configurable health check thresholds
- Automatic metrics integration
- Detailed health status reporting

#### Health Checks
- **Database**: Connectivity, query performance, connection pool status
- **Redis**: Connectivity, read/write operations, memory usage
- **Scraping Freshness**: Data age, update frequency
- **Celery Workers**: Worker status, queue sizes
- **Data Quality**: Completeness metrics, validation rates
- **System Resources**: Disk space, memory usage

#### Usage
```python
from src.monitoring.health_checks import get_health_checker

checker = get_health_checker()

# Run individual check
result = await checker.run_check('database')

# Run all checks
all_results = await checker.run_all_checks()

# Get overall health status
health_status = await checker.get_overall_health()
```

### 4. Log Management (`src/monitoring/log_management.py`)

#### Features
- Automatic log rotation
- Configurable retention policies
- Log compression
- Size-based cleanup
- Log statistics and monitoring

#### Configuration
```python
from src.monitoring.log_management import LogRetentionPolicy

policy = LogRetentionPolicy(
    max_age_days=30,           # Delete logs older than 30 days
    max_size_mb=1000,          # Keep total log size under 1GB
    compress_after_days=7,     # Compress logs older than 7 days
    delete_after_days=30,      # Delete logs older than 30 days
    keep_minimum_files=5       # Always keep at least 5 files
)
```

### 5. Health API Endpoints (`src/api/health.py`)

#### Endpoints
- `GET /health/`: Basic health check for load balancers
- `GET /health/detailed`: Comprehensive health status
- `GET /health/live`: Kubernetes liveness probe
- `GET /health/ready`: Kubernetes readiness probe
- `GET /health/metrics`: Prometheus metrics endpoint
- `GET /health/check/{check_name}`: Individual health check
- `GET /health/admin/status`: Admin health dashboard (requires auth)

## Integration

### FastAPI Integration

The health endpoints are automatically included in the main FastAPI application:

```python
from src.api.health import router as health_router
app.include_router(health_router)
```

### Celery Integration

Logging and metrics are integrated into Celery tasks:

```python
from src.logging_config import get_logger, LogContext
from src.monitoring.metrics import track_celery_metrics

@celery_app.task
@track_celery_metrics('my_task')
def my_task():
    logger = get_logger(__name__)
    with LogContext(logger, task_id=self.request.id):
        # Task logic here
        pass
```

### Scheduled Tasks

The system includes automated maintenance tasks:

- **Log Rotation**: Daily at 3 AM
- **Health Checks**: Every 15 minutes
- **Cache Warming**: Every 2 hours
- **Database Optimization**: Weekly on Sunday at 2 AM

## Monitoring Setup

### Prometheus Configuration

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'spacex-tracker'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/health/metrics'
    scrape_interval: 30s
```

### Grafana Dashboard

Key metrics to monitor:
- Request rate and response times
- Scraping success rates and durations
- Database query performance
- System health status
- Error rates and types

### Alerting Rules

Example Prometheus alerting rules:

```yaml
groups:
  - name: spacex-tracker
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status_code=~"5.."}[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: High error rate detected
      
      - alert: ScrapingFailure
        expr: increase(scraping_requests_total{status="error"}[1h]) > 5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: Multiple scraping failures detected
```

## Best Practices

### Logging
- Use structured logging with consistent field names
- Include relevant context (user_id, request_id, etc.)
- Log at appropriate levels (DEBUG for development, INFO for operations)
- Avoid logging sensitive information

### Metrics
- Use consistent naming conventions
- Include relevant labels for filtering
- Monitor both technical and business metrics
- Set up alerting for critical metrics

### Health Checks
- Keep checks lightweight and fast
- Include both technical and functional checks
- Set appropriate thresholds for degraded vs unhealthy
- Monitor check execution times

### Error Handling
- Use structured error information
- Include context for debugging
- Set up appropriate alerting
- Monitor error patterns and trends

## Troubleshooting

### Common Issues

1. **High Memory Usage**: Check log retention policies and metrics cardinality
2. **Slow Health Checks**: Review check implementations and database queries
3. **Missing Metrics**: Verify decorator usage and metric registration
4. **Log Rotation Issues**: Check disk space and file permissions

### Debug Commands

```bash
# Check log files
ls -la logs/

# View recent logs
tail -f logs/spacex_tracker.log

# Check metrics endpoint
curl http://localhost:8000/health/metrics

# Check health status
curl http://localhost:8000/health/detailed
```

## Dependencies

Required packages:
- `structlog`: Structured logging
- `prometheus-client`: Metrics collection
- `sentry-sdk[fastapi]`: Error tracking
- `psutil`: System monitoring (optional)

## Configuration Files

The system uses the following configuration:
- Environment variables for basic settings
- `LogConfig` class for logging configuration
- `LogRetentionPolicy` for log management
- Celery beat schedule for automated tasks

This comprehensive logging and monitoring system provides full observability into the SpaceX Launch Tracker application, enabling proactive monitoring, debugging, and performance optimization.