# Task Scheduling System

The SpaceX Launch Tracker uses Celery for distributed task scheduling and execution. This document describes the task system architecture, configuration, and usage.

## Overview

The task scheduling system handles:
- Periodic scraping of launch data (every 6 hours)
- Manual data refresh triggers
- System health monitoring
- Task locking to prevent overlapping operations
- Comprehensive logging and monitoring

## Architecture

### Components

1. **Celery App** (`src/celery_app.py`)
   - Main Celery application configuration
   - Task routing and queue management
   - Beat schedule for periodic tasks

2. **Scraping Tasks** (`src/tasks/scraping_tasks.py`)
   - Main scraping task implementation
   - Manual refresh functionality
   - Health check tasks

3. **Task Locking** (`src/tasks/task_lock.py`)
   - Redis-based distributed locking
   - Prevents overlapping scraping operations
   - Lock management utilities

4. **Task Monitoring** (`src/tasks/task_monitoring.py`)
   - Task status monitoring
   - Worker statistics
   - System health checks

5. **Management CLI** (`scripts/celery_management.py`)
   - Worker and beat management
   - Task monitoring and control
   - System administration

## Configuration

### Celery Configuration

The Celery app is configured with:
- **Broker**: Redis (default: `redis://localhost:6379/0`)
- **Result Backend**: Redis
- **Serialization**: JSON
- **Timezone**: UTC
- **Queues**: `default`, `scraping`, `monitoring`

### Task Routing

Tasks are routed to specific queues:
- `scraping`: Data scraping tasks
- `monitoring`: Health checks and monitoring
- `default`: General tasks

### Beat Schedule

Periodic tasks are scheduled as follows:
- **Data Scraping**: Every 6 hours (`0 */6 * * *`)
- **Health Check**: Every 15 minutes (`*/15 * * * *`)

## Usage

### Starting Services

#### Using Docker Compose (Recommended)

```bash
# Start all services including Celery worker and beat
docker-compose up -d

# View logs
docker-compose logs -f celery-worker
docker-compose logs -f celery-beat
```

#### Manual Startup

```bash
# Start Redis (required)
redis-server

# Start Celery worker
python scripts/celery_management.py worker

# Start Celery beat (in another terminal)
python scripts/celery_management.py beat

# Start Flower monitoring (optional)
python scripts/celery_management.py flower
```

### Management Commands

The `scripts/celery_management.py` script provides various management commands:

#### Worker Management

```bash
# Start worker with specific queues
python scripts/celery_management.py worker --queues scraping,monitoring

# Start worker with custom concurrency
python scripts/celery_management.py worker --concurrency 4

# Start beat scheduler
python scripts/celery_management.py beat
```

#### Task Monitoring

```bash
# Show real-time task monitoring
python scripts/celery_management.py monitor

# Run health check
python scripts/celery_management.py health

# Show task statistics
python scripts/celery_management.py stats
```

#### Manual Operations

```bash
# Trigger manual data refresh
python scripts/celery_management.py refresh

# Refresh specific sources only
python scripts/celery_management.py refresh --sources spacex,nasa

# Cancel a running task
python scripts/celery_management.py cancel-task <task_id>

# Cancel and terminate a task
python scripts/celery_management.py cancel-task <task_id> --terminate
```

#### Lock Management

```bash
# List active locks
python scripts/celery_management.py locks

# Force release a lock (use with caution)
python scripts/celery_management.py release-lock scraping_task_lock
```

### Monitoring with Flower

Flower provides a web-based monitoring interface:

```bash
# Start Flower
python scripts/celery_management.py flower

# Access at http://localhost:5555
```

## Task Details

### Main Scraping Task

The primary scraping task (`scrape_launch_data`) performs:

1. **Lock Acquisition**: Prevents overlapping scraping operations
2. **Data Scraping**: Uses UnifiedScraper to collect data from all sources
3. **Data Processing**: Validates, deduplicates, and reconciles data
4. **Data Persistence**: Saves processed data to the database
5. **Statistics Generation**: Creates comprehensive execution statistics

### Manual Refresh Task

The manual refresh task (`manual_refresh`) allows immediate data updates:
- Can target specific sources
- Bypasses normal scheduling constraints
- Provides immediate feedback on results

### Health Check Task

The health check task (`health_check`) monitors:
- Database connectivity
- Redis connectivity
- Recent scraping activity
- System component status

## Error Handling

### Retry Logic

Tasks implement automatic retry with exponential backoff:
- Maximum 3 retries
- Exponential backoff: 1, 2, 4 minutes
- Comprehensive error logging

### Lock Timeouts

Task locks have configurable timeouts:
- Default lock timeout: 1 hour
- Blocking timeout: 10 seconds
- Automatic lock expiration

### Graceful Degradation

The system handles failures gracefully:
- Failed sources don't block other sources
- Validation errors are logged but don't stop processing
- Database errors trigger transaction rollbacks

## Logging

### Structured Logging

All tasks use structured logging with:
- Task ID and name
- Execution timestamps
- Performance metrics
- Error details and stack traces

### Log Levels

- **INFO**: Normal operation, task completion
- **WARNING**: Retries, degraded performance
- **ERROR**: Task failures, system errors
- **DEBUG**: Detailed execution information

### Log Locations

- **Docker**: Logs are available via `docker-compose logs`
- **Local**: Logs go to console and can be redirected to files

## Performance Monitoring

### Metrics Tracked

- Task execution time
- Success/failure rates
- Queue lengths
- Worker utilization
- Memory usage

### Health Indicators

- Workers online/offline
- Task completion rates
- Error frequencies
- Lock contention

## Troubleshooting

### Common Issues

1. **No Workers Online**
   ```bash
   # Check worker status
   python scripts/celery_management.py monitor
   
   # Restart workers
   docker-compose restart celery-worker
   ```

2. **Tasks Stuck**
   ```bash
   # Check active tasks
   python scripts/celery_management.py monitor
   
   # Cancel stuck task
   python scripts/celery_management.py cancel-task <task_id> --terminate
   ```

3. **Lock Contention**
   ```bash
   # Check active locks
   python scripts/celery_management.py locks
   
   # Force release if needed
   python scripts/celery_management.py release-lock scraping_task_lock
   ```

4. **Redis Connection Issues**
   ```bash
   # Check Redis status
   redis-cli ping
   
   # Restart Redis
   docker-compose restart redis
   ```

### Debug Mode

Enable debug logging for detailed information:

```bash
python scripts/celery_management.py worker --loglevel=debug
```

## Security Considerations

### Redis Security

- Redis should not be exposed to the internet
- Use Redis AUTH if needed
- Consider Redis SSL/TLS for production

### Task Security

- Tasks run with application privileges
- Validate all task inputs
- Sanitize data before processing

### Lock Security

- Locks use unique identifiers
- Automatic expiration prevents deadlocks
- Force release requires explicit action

## Production Deployment

### Scaling

- Run multiple workers for increased throughput
- Use different queues for task prioritization
- Monitor resource usage and scale accordingly

### High Availability

- Use Redis Sentinel or Cluster for Redis HA
- Run multiple beat schedulers with leader election
- Implement proper health checks and monitoring

### Monitoring

- Set up alerts for task failures
- Monitor queue lengths and processing times
- Track system resource usage

## Development

### Adding New Tasks

1. Create task function in appropriate module
2. Add task routing configuration
3. Update beat schedule if periodic
4. Add tests for task functionality
5. Update documentation

### Testing

Run the task scheduling tests:

```bash
# Run all task tests
pytest tests/test_task_scheduling.py -v

# Run specific test categories
pytest tests/test_task_scheduling.py::TestTaskLock -v
pytest tests/test_task_scheduling.py::TestScrapingTasks -v
```

### Local Development

For local development without Docker:

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis locally
redis-server

# Start worker in development mode
PYTHONPATH=. python scripts/celery_management.py worker --loglevel=debug
```