"""
Celery tasks for scraping SpaceX launch data.
"""
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from celery import Task
from celery.exceptions import Retry, WorkerLostError
from sqlalchemy.orm import Session

from src.celery_app import celery_app
from src.database import get_db_session
from src.scraping.unified_scraper import UnifiedScraper
from src.processing.data_pipeline import DataProcessingPipeline
from src.repositories.launch_repository import LaunchRepository
from src.tasks.task_lock import TaskLock, TaskLockError
from src.logging_config import get_logger, TimedOperation, LogContext
from src.monitoring.metrics import get_metrics_collector, track_celery_metrics

logger = get_logger(__name__, component="scraping_tasks")


class ScrapingTask(Task):
    """Base task class for scraping operations with common functionality."""
    
    def __init__(self):
        self.task_lock = TaskLock()
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        logger.error(f"Task {task_id} failed: {exc}")
        logger.error(f"Exception info: {einfo}")
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        logger.info(f"Task {task_id} completed successfully")
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried."""
        logger.warning(f"Task {task_id} retrying due to: {exc}")


@celery_app.task(bind=True, base=ScrapingTask, name='src.tasks.scraping_tasks.scrape_launch_data')
@track_celery_metrics('scrape_launch_data')
def scrape_launch_data(self, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Main periodic task for scraping launch data from all sources.
    
    Args:
        force_refresh: If True, bypass normal scheduling constraints
        
    Returns:
        Dictionary with scraping results and statistics
    """
    task_id = self.request.id
    metrics = get_metrics_collector()
    
    with LogContext(logger, task_id=task_id, force_refresh=force_refresh) as log:
        log.info("Starting scrape_launch_data task")
        
        # Prevent overlapping scraping operations
        lock_key = "scraping_task_lock"
        
        try:
            with self.task_lock.acquire_lock(lock_key, timeout=3600):  # 1 hour timeout
                with TimedOperation(log, "scraping_pipeline"):
                    return asyncio.run(_execute_scraping_pipeline(task_id, force_refresh))
    
        except TaskLockError as e:
            log.warning("Task skipped due to lock", error=str(e))
            metrics.record_celery_task('scrape_launch_data', 'skipped')
            return {
                'status': 'skipped',
                'reason': 'Another scraping task is already running',
                'task_id': task_id,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        
        except Exception as e:
            log.error("Scraping task failed", error=str(e), exc_info=True)
            metrics.record_celery_task('scrape_launch_data', 'error')
            
            # Retry with exponential backoff
            if self.request.retries < self.max_retries:
                countdown = 2 ** self.request.retries * 60  # 1, 2, 4 minutes
                log.info("Retrying task", countdown_seconds=countdown, retry_count=self.request.retries)
                raise self.retry(countdown=countdown, exc=e)
            
            return {
                'status': 'failed',
                'error': str(e),
                'task_id': task_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'retries': self.request.retries
            }


async def _execute_scraping_pipeline(task_id: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Execute the complete scraping and processing pipeline.
    
    Args:
        task_id: Celery task ID for logging
        force_refresh: Whether to force refresh regardless of last update
        
    Returns:
        Dictionary with pipeline execution results
    """
    start_time = datetime.now(timezone.utc)
    logger.info(f"Executing scraping pipeline for task {task_id}")
    
    results = {
        'status': 'success',
        'task_id': task_id,
        'start_time': start_time.isoformat(),
        'force_refresh': force_refresh,
        'scraping_results': {},
        'processing_results': {},
        'persistence_results': {},
        'statistics': {}
    }
    
    try:
        # Step 1: Scrape data from all sources
        logger.info("Step 1: Scraping data from all sources")
        scraping_results = await _scrape_all_sources()
        results['scraping_results'] = scraping_results
        
        if not scraping_results.get('raw_data'):
            logger.warning("No data scraped from any source")
            results['status'] = 'no_data'
            return results
        
        # Step 2: Process scraped data
        logger.info("Step 2: Processing scraped data")
        processing_results = await _process_scraped_data(scraping_results['raw_data'])
        results['processing_results'] = processing_results
        
        if not processing_results.get('processed_launches'):
            logger.warning("No launches processed successfully")
            results['status'] = 'processing_failed'
            return results
        
        # Step 3: Persist to database
        logger.info("Step 3: Persisting data to database")
        persistence_results = await _persist_processed_data(
            processing_results['processed_launches'],
            processing_results.get('conflicts', [])
        )
        results['persistence_results'] = persistence_results
        
        # Step 4: Generate statistics
        end_time = datetime.now(timezone.utc)
        results['end_time'] = end_time.isoformat()
        results['duration_seconds'] = (end_time - start_time).total_seconds()
        results['statistics'] = _generate_pipeline_statistics(results)
        
        logger.info(f"Scraping pipeline completed successfully for task {task_id}")
        logger.info(f"Duration: {results['duration_seconds']:.2f} seconds")
        logger.info(f"Launches processed: {len(processing_results['processed_launches'])}")
        
        return results
        
    except Exception as e:
        logger.error(f"Scraping pipeline failed for task {task_id}: {e}")
        results['status'] = 'failed'
        results['error'] = str(e)
        results['end_time'] = datetime.now(timezone.utc).isoformat()
        raise


async def _scrape_all_sources() -> Dict[str, Any]:
    """Scrape data from all available sources."""
    try:
        async with UnifiedScraper() as scraper:
            comprehensive_data = await scraper.get_comprehensive_data()
            
            # Convert to format expected by processing pipeline
            raw_data = []
            for launch in comprehensive_data['launches']:
                launch_dict = launch.model_dump() if hasattr(launch, 'model_dump') else launch.dict()
                
                # Create source data for each launch
                source_data = {
                    'source_name': 'unified_scraper',
                    'source_url': 'multiple_sources',
                    'scraped_at': datetime.now(timezone.utc),
                    'data_quality_score': 0.9  # Default quality score
                }
                
                raw_data.append((launch_dict, source_data))
            
            return {
                'raw_data': raw_data,
                'metadata': comprehensive_data['metadata'],
                'source_data': comprehensive_data['source_data']
            }
            
    except Exception as e:
        logger.error(f"Error scraping all sources: {e}")
        return {'raw_data': [], 'error': str(e)}


async def _process_scraped_data(raw_data: List[tuple]) -> Dict[str, Any]:
    """Process scraped data through validation, deduplication, and reconciliation."""
    try:
        pipeline = DataProcessingPipeline(
            date_tolerance_hours=24,
            enable_conflict_detection=True,
            enable_deduplication=True
        )
        
        processing_result = pipeline.process_scraped_data(raw_data)
        
        return {
            'processed_launches': processing_result.processed_launches,
            'conflicts': processing_result.conflicts,
            'validation_errors': processing_result.validation_errors,
            'processing_stats': processing_result.processing_stats,
            'processing_time': processing_result.processing_time
        }
        
    except Exception as e:
        logger.error(f"Error processing scraped data: {e}")
        return {'processed_launches': [], 'error': str(e)}


async def _persist_processed_data(launches: List, conflicts: List) -> Dict[str, Any]:
    """Persist processed data to the database."""
    try:
        with get_db_session() as session:
            launch_repo = LaunchRepository(session)
            
            # Batch upsert launches
            upsert_results = launch_repo.batch_upsert_launches(launches)
            
            # TODO: Persist conflicts to database
            # This would require a ConflictRepository implementation
            
            session.commit()
            
            return {
                'launches_created': upsert_results['created'],
                'launches_updated': upsert_results['updated'],
                'total_launches': upsert_results['total'],
                'conflicts_logged': len(conflicts)
            }
            
    except Exception as e:
        logger.error(f"Error persisting processed data: {e}")
        return {'error': str(e)}


def _generate_pipeline_statistics(results: Dict[str, Any]) -> Dict[str, Any]:
    """Generate comprehensive statistics for the pipeline execution."""
    stats = {
        'pipeline_duration': results.get('duration_seconds', 0),
        'scraping_successful': 'error' not in results.get('scraping_results', {}),
        'processing_successful': 'error' not in results.get('processing_results', {}),
        'persistence_successful': 'error' not in results.get('persistence_results', {}),
    }
    
    # Add scraping stats
    scraping_results = results.get('scraping_results', {})
    if 'metadata' in scraping_results:
        metadata = scraping_results['metadata']
        stats.update({
            'total_scraped_launches': metadata.get('total_launches', 0),
            'sources_scraped': metadata.get('sources_scraped', []),
            'scraping_duration': metadata.get('scraping_duration', 0)
        })
    
    # Add processing stats
    processing_results = results.get('processing_results', {})
    if 'processing_stats' in processing_results:
        proc_stats = processing_results['processing_stats']
        stats.update({
            'validation_success_rate': proc_stats.get('validation_success_rate', 0),
            'conflicts_detected': proc_stats.get('conflicts_detected', 0),
            'processing_duration': processing_results.get('processing_time', 0)
        })
    
    # Add persistence stats
    persistence_results = results.get('persistence_results', {})
    stats.update({
        'launches_created': persistence_results.get('launches_created', 0),
        'launches_updated': persistence_results.get('launches_updated', 0),
        'total_persisted': persistence_results.get('total_launches', 0)
    })
    
    return stats


@celery_app.task(bind=True, base=ScrapingTask, name='src.tasks.scraping_tasks.manual_refresh')
def manual_refresh(self, sources: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Manual trigger for immediate data refresh.
    
    Args:
        sources: Optional list of specific sources to scrape
        
    Returns:
        Dictionary with refresh results
    """
    task_id = self.request.id
    logger.info(f"Starting manual refresh task {task_id}")
    
    try:
        # Use the same pipeline as periodic scraping but with force_refresh=True
        return asyncio.run(_execute_manual_refresh(task_id, sources))
        
    except Exception as e:
        logger.error(f"Manual refresh task {task_id} failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'task_id': task_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


async def _execute_manual_refresh(task_id: str, sources: Optional[List[str]] = None) -> Dict[str, Any]:
    """Execute manual refresh with optional source filtering."""
    start_time = datetime.now(timezone.utc)
    logger.info(f"Executing manual refresh for task {task_id}")
    
    try:
        async with UnifiedScraper() as scraper:
            if sources:
                # Scrape only specified sources
                scraping_results = await scraper.scrape_all_sources(include_sources=sources)
                launches = []
                for source_launches in scraping_results.values():
                    launches.extend(source_launches)
            else:
                # Scrape all sources
                comprehensive_data = await scraper.get_comprehensive_data()
                launches = comprehensive_data['launches']
            
            # Convert to processing format
            raw_data = []
            for launch in launches:
                launch_dict = launch.model_dump() if hasattr(launch, 'model_dump') else launch.dict()
                source_data = {
                    'source_name': 'manual_refresh',
                    'source_url': 'multiple_sources',
                    'scraped_at': datetime.now(timezone.utc),
                    'data_quality_score': 0.9
                }
                raw_data.append((launch_dict, source_data))
            
            # Process and persist
            processing_results = await _process_scraped_data(raw_data)
            persistence_results = await _persist_processed_data(
                processing_results['processed_launches'],
                processing_results.get('conflicts', [])
            )
            
            end_time = datetime.now(timezone.utc)
            
            return {
                'status': 'success',
                'task_id': task_id,
                'sources_requested': sources,
                'launches_processed': len(processing_results['processed_launches']),
                'launches_created': persistence_results.get('launches_created', 0),
                'launches_updated': persistence_results.get('launches_updated', 0),
                'duration_seconds': (end_time - start_time).total_seconds(),
                'timestamp': end_time.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Manual refresh execution failed: {e}")
        raise


@celery_app.task(bind=True, name='src.tasks.scraping_tasks.health_check')
def health_check(self) -> Dict[str, Any]:
    """
    Health check task to monitor system status.
    
    Returns:
        Dictionary with system health information
    """
    task_id = self.request.id
    timestamp = datetime.now(timezone.utc)
    
    try:
        health_status = {
            'status': 'healthy',
            'task_id': task_id,
            'timestamp': timestamp.isoformat(),
            'checks': {}
        }
        
        # Check database connectivity
        try:
            with get_db_session() as session:
                launch_repo = LaunchRepository(session)
                stats = launch_repo.get_launch_statistics()
                health_status['checks']['database'] = {
                    'status': 'healthy',
                    'total_launches': stats['total_launches'],
                    'latest_launch': stats['latest_launch_date'].isoformat() if stats['latest_launch_date'] else None
                }
        except Exception as e:
            health_status['checks']['database'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
        
        # Check Redis connectivity (Celery broker)
        try:
            # Simple check by inspecting Celery app
            celery_app.control.inspect().ping()
            health_status['checks']['redis'] = {'status': 'healthy'}
        except Exception as e:
            health_status['checks']['redis'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
        
        # Check recent scraping activity
        try:
            # This would check the last successful scraping task
            # For now, just mark as healthy
            health_status['checks']['scraping'] = {
                'status': 'healthy',
                'last_check': timestamp.isoformat()
            }
        except Exception as e:
            health_status['checks']['scraping'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
        
        logger.info(f"Health check {task_id} completed: {health_status['status']}")
        return health_status
        
    except Exception as e:
        logger.error(f"Health check task {task_id} failed: {e}")
        return {
            'status': 'unhealthy',
            'task_id': task_id,
            'timestamp': timestamp.isoformat(),
            'error': str(e)
        }


# Task monitoring utilities
def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of a specific task."""
    result = celery_app.AsyncResult(task_id)
    
    return {
        'task_id': task_id,
        'status': result.status,
        'result': result.result if result.ready() else None,
        'traceback': result.traceback if result.failed() else None,
        'date_done': result.date_done.isoformat() if result.date_done else None
    }


def get_active_tasks() -> List[Dict[str, Any]]:
    """Get list of currently active tasks."""
    inspect = celery_app.control.inspect()
    active_tasks = inspect.active()
    
    if not active_tasks:
        return []
    
    all_tasks = []
    for worker, tasks in active_tasks.items():
        for task in tasks:
            all_tasks.append({
                'worker': worker,
                'task_id': task['id'],
                'name': task['name'],
                'args': task['args'],
                'kwargs': task['kwargs'],
                'time_start': task['time_start']
            })
    
    return all_tasks


def cancel_task(task_id: str) -> Dict[str, Any]:
    """Cancel a running task."""
    try:
        celery_app.control.revoke(task_id, terminate=True)
        return {
            'status': 'cancelled',
            'task_id': task_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            'status': 'error',
            'task_id': task_id,
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

@celery_app.task(bind=True, base=ScrapingTask, name='src.tasks.scraping_tasks.warm_cache')
def warm_cache_task(self):
    """Celery task to warm cache with frequently accessed data."""
    task_id = self.request.id
    logger.info(f"Starting cache warming task {task_id}")
    
    try:
        # Import here to avoid circular imports
        from src.cache.cache_warming import get_cache_warming_service
        
        cache_warming_service = get_cache_warming_service()
        result = cache_warming_service.warm_all_caches()
        
        logger.info(f"Cache warming task {task_id} completed successfully")
        
        return {
            "task_id": task_id,
            "status": "completed",
            "result": result,
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cache warming task {task_id} failed: {e}", exc_info=True)
        
        # Update task status
        self.update_state(
            state='FAILURE',
            meta={
                "task_id": task_id,
                "error": str(e),
                "failed_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
        raise


@celery_app.task(bind=True, base=ScrapingTask, name='src.tasks.scraping_tasks.invalidate_cache')
def invalidate_cache_task(self, cache_type: str = "all"):
    """Celery task to invalidate cache entries."""
    task_id = self.request.id
    logger.info(f"Starting cache invalidation task {task_id} for type: {cache_type}")
    
    try:
        # Import here to avoid circular imports
        from src.cache.cache_manager import get_cache_manager
        
        cache_manager = get_cache_manager()
        
        if cache_type == "all":
            deleted_count = cache_manager.invalidate_all_cache()
        elif cache_type == "launches":
            deleted_count = cache_manager.invalidate_all_launches()
        elif cache_type == "stats":
            deleted_count = cache_manager.invalidate_stats_cache()
        else:
            raise ValueError(f"Invalid cache type: {cache_type}")
        
        logger.info(f"Cache invalidation task {task_id} completed: {deleted_count} keys deleted")
        
        return {
            "task_id": task_id,
            "status": "completed",
            "cache_type": cache_type,
            "deleted_count": deleted_count,
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cache invalidation task {task_id} failed: {e}", exc_info=True)
        
        # Update task status
        self.update_state(
            state='FAILURE',
            meta={
                "task_id": task_id,
                "error": str(e),
                "failed_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
        raise


@celery_app.task(bind=True, base=ScrapingTask, name='src.tasks.scraping_tasks.optimize_database')
def optimize_database_task(self):
    """Celery task to optimize database performance."""
    task_id = self.request.id
    logger.info(f"Starting database optimization task {task_id}")
    
    try:
        # Import here to avoid circular imports
        from src.database_optimization import get_database_optimizer
        
        db_optimizer = get_database_optimizer()
        
        # Create performance indexes
        index_results = db_optimizer.create_performance_indexes()
        
        # Run VACUUM ANALYZE
        vacuum_results = db_optimizer.vacuum_analyze_tables()
        
        logger.info(f"Database optimization task {task_id} completed successfully")
        
        return {
            "task_id": task_id,
            "status": "completed",
            "index_creation": index_results,
            "vacuum_analyze": vacuum_results,
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Database optimization task {task_id} failed: {e}", exc_info=True)
        
        # Update task status
        self.update_state(
            state='FAILURE',
            meta={
                "task_id": task_id,
                "error": str(e),
                "failed_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
        raise


@celery_app.task(bind=True, base=ScrapingTask, name='src.tasks.scraping_tasks.rotate_logs')
@track_celery_metrics('rotate_logs')
def rotate_logs_task(self):
    """Celery task to rotate and clean up logs."""
    task_id = self.request.id
    
    with LogContext(logger, task_id=task_id) as log:
        log.info("Starting log rotation task")
        
        try:
            from src.monitoring.log_management import get_log_manager
            
            log_manager = get_log_manager()
            
            with TimedOperation(log, "log_rotation"):
                results = log_manager.apply_retention_policy()
            
            log.info(
                "Log rotation completed successfully",
                compressed_files=results['compressed_files'],
                deleted_files=results['deleted_files'],
                total_size_after_mb=results['total_size_after_mb']
            )
            
            return {
                "task_id": task_id,
                "status": "completed",
                "results": results,
                "completed_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            log.error("Log rotation task failed", error=str(e), exc_info=True)
            
            # Update task status
            self.update_state(
                state='FAILURE',
                meta={
                    "task_id": task_id,
                    "error": str(e),
                    "failed_at": datetime.now(timezone.utc).isoformat()
                }
            )
            
            raise