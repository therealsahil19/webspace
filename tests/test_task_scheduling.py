"""
Tests for Celery task scheduling and execution.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta

from src.tasks.scraping_tasks import (
    scrape_launch_data,
    manual_refresh,
    health_check,
    _execute_scraping_pipeline,
    _scrape_all_sources,
    _process_scraped_data,
    _persist_processed_data,
    get_task_status,
    get_active_tasks,
    cancel_task
)
from src.tasks.task_lock import TaskLock, TaskLockError
from src.tasks.task_monitoring import TaskMonitor, TaskLogger, TaskInfo, TaskStatus
from src.celery_app import celery_app


class TestTaskLock:
    """Test task locking mechanism."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        with patch('src.tasks.task_lock.redis.from_url') as mock_redis:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client
            yield mock_client
    
    def test_task_lock_initialization(self, mock_redis):
        """Test TaskLock initialization."""
        task_lock = TaskLock()
        assert task_lock.redis_client == mock_redis
        mock_redis.ping.assert_called_once()
    
    def test_acquire_lock_success(self, mock_redis):
        """Test successful lock acquisition."""
        mock_redis.set.return_value = True
        task_lock = TaskLock()
        
        with task_lock.acquire_lock("test_lock", timeout=60):
            mock_redis.set.assert_called_once()
            args, kwargs = mock_redis.set.call_args
            assert args[0] == "test_lock"
            assert kwargs['nx'] is True
            assert kwargs['ex'] == 60
    
    def test_acquire_lock_failure(self, mock_redis):
        """Test lock acquisition failure."""
        mock_redis.set.return_value = False
        mock_redis.get.return_value = "existing_lock_id"
        mock_redis.ttl.return_value = 300
        
        task_lock = TaskLock()
        
        with pytest.raises(TaskLockError):
            with task_lock.acquire_lock("test_lock", timeout=60, blocking_timeout=0.1):
                pass
    
    def test_release_lock(self, mock_redis):
        """Test lock release."""
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        
        task_lock = TaskLock()
        
        with task_lock.acquire_lock("test_lock", timeout=60):
            pass
        
        # Verify eval was called for lock release
        mock_redis.eval.assert_called()
    
    def test_is_locked(self, mock_redis):
        """Test lock existence check."""
        mock_redis.exists.return_value = 1
        task_lock = TaskLock()
        
        assert task_lock.is_locked("test_lock") is True
        mock_redis.exists.assert_called_with("test_lock")
    
    def test_force_release_lock(self, mock_redis):
        """Test force lock release."""
        mock_redis.delete.return_value = 1
        task_lock = TaskLock()
        
        result = task_lock.force_release_lock("test_lock")
        assert result is True
        mock_redis.delete.assert_called_with("test_lock")


class TestScrapingTasks:
    """Test Celery scraping tasks."""
    
    @pytest.fixture
    def mock_task_lock(self):
        """Mock task lock."""
        with patch('src.tasks.scraping_tasks.TaskLock') as mock_lock_class:
            mock_lock = Mock()
            mock_lock_class.return_value = mock_lock
            
            # Mock context manager
            mock_context = Mock()
            mock_lock.acquire_lock.return_value.__enter__ = Mock(return_value=mock_context)
            mock_lock.acquire_lock.return_value.__exit__ = Mock(return_value=None)
            
            yield mock_lock
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        with patch('src.tasks.scraping_tasks.get_db_session') as mock_session:
            session = Mock()
            mock_session.return_value.__enter__ = Mock(return_value=session)
            mock_session.return_value.__exit__ = Mock(return_value=None)
            yield session
    
    @pytest.fixture
    def mock_unified_scraper(self):
        """Mock unified scraper."""
        with patch('src.tasks.scraping_tasks.UnifiedScraper') as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper_class.return_value.__aenter__ = AsyncMock(return_value=mock_scraper)
            mock_scraper_class.return_value.__aexit__ = AsyncMock(return_value=None)
            yield mock_scraper
    
    @pytest.fixture
    def mock_data_pipeline(self):
        """Mock data processing pipeline."""
        with patch('src.tasks.scraping_tasks.DataProcessingPipeline') as mock_pipeline_class:
            mock_pipeline = Mock()
            mock_pipeline_class.return_value = mock_pipeline
            yield mock_pipeline
    
    @pytest.fixture
    def mock_launch_repository(self):
        """Mock launch repository."""
        with patch('src.tasks.scraping_tasks.LaunchRepository') as mock_repo_class:
            mock_repo = Mock()
            mock_repo_class.return_value = mock_repo
            yield mock_repo
    
    def test_scrape_launch_data_success(self, mock_task_lock, mock_unified_scraper, 
                                       mock_data_pipeline, mock_launch_repository, mock_db_session):
        """Test successful scrape_launch_data task."""
        # Setup mocks
        mock_unified_scraper.get_comprehensive_data.return_value = {
            'launches': [Mock(model_dump=Mock(return_value={'slug': 'test-launch'}))],
            'metadata': {'total_launches': 1},
            'source_data': []
        }
        
        mock_processing_result = Mock()
        mock_processing_result.processed_launches = [Mock()]
        mock_processing_result.conflicts = []
        mock_processing_result.validation_errors = []
        mock_processing_result.processing_stats = {'validation_success_rate': 1.0}
        mock_processing_result.processing_time = 1.5
        
        mock_data_pipeline.process_scraped_data.return_value = mock_processing_result
        mock_launch_repository.batch_upsert_launches.return_value = {
            'created': 1, 'updated': 0, 'total': 1
        }
        
        # Create a mock task instance
        mock_task = Mock()
        mock_task.request.id = "test_task_id"
        mock_task.request.retries = 0
        mock_task.max_retries = 3
        mock_task.task_lock = mock_task_lock
        
        # Execute task
        result = scrape_launch_data(mock_task)
        
        # Verify result
        assert result['status'] == 'success'
        assert result['task_id'] == "test_task_id"
        assert 'scraping_results' in result
        assert 'processing_results' in result
        assert 'persistence_results' in result
    
    def test_scrape_launch_data_lock_failure(self, mock_task_lock):
        """Test scrape_launch_data with lock acquisition failure."""
        mock_task_lock.acquire_lock.side_effect = TaskLockError("Lock already held")
        
        mock_task = Mock()
        mock_task.request.id = "test_task_id"
        mock_task.task_lock = mock_task_lock
        
        result = scrape_launch_data(mock_task)
        
        assert result['status'] == 'skipped'
        assert result['reason'] == 'Another scraping task is already running'
    
    def test_manual_refresh_success(self, mock_unified_scraper, mock_data_pipeline, 
                                   mock_launch_repository, mock_db_session):
        """Test successful manual_refresh task."""
        # Setup mocks
        mock_unified_scraper.get_comprehensive_data.return_value = {
            'launches': [Mock(model_dump=Mock(return_value={'slug': 'test-launch'}))],
            'metadata': {'total_launches': 1}
        }
        
        mock_processing_result = Mock()
        mock_processing_result.processed_launches = [Mock()]
        mock_processing_result.conflicts = []
        
        mock_data_pipeline.process_scraped_data.return_value = mock_processing_result
        mock_launch_repository.batch_upsert_launches.return_value = {
            'created': 1, 'updated': 0, 'total': 1
        }
        
        mock_task = Mock()
        mock_task.request.id = "manual_task_id"
        
        result = manual_refresh(mock_task, sources=['spacex'])
        
        assert result['status'] == 'success'
        assert result['task_id'] == "manual_task_id"
        assert result['sources_requested'] == ['spacex']
    
    def test_health_check_success(self, mock_db_session, mock_launch_repository):
        """Test successful health_check task."""
        mock_launch_repository.get_launch_statistics.return_value = {
            'total_launches': 100,
            'latest_launch_date': datetime.now(timezone.utc)
        }
        
        with patch('src.tasks.scraping_tasks.celery_app.control.inspect') as mock_inspect:
            mock_inspect.return_value.ping.return_value = True
            
            mock_task = Mock()
            mock_task.request.id = "health_task_id"
            
            result = health_check(mock_task)
            
            assert result['status'] == 'healthy'
            assert result['task_id'] == "health_task_id"
            assert 'checks' in result
            assert result['checks']['database']['status'] == 'healthy'
    
    def test_health_check_database_failure(self, mock_db_session):
        """Test health_check with database failure."""
        mock_db_session.side_effect = Exception("Database connection failed")
        
        mock_task = Mock()
        mock_task.request.id = "health_task_id"
        
        result = health_check(mock_task)
        
        assert result['status'] == 'degraded'
        assert result['checks']['database']['status'] == 'unhealthy'
    
    @pytest.mark.asyncio
    async def test_scrape_all_sources(self, mock_unified_scraper):
        """Test _scrape_all_sources function."""
        mock_launch = Mock()
        mock_launch.model_dump.return_value = {'slug': 'test-launch', 'mission_name': 'Test Mission'}
        
        mock_unified_scraper.get_comprehensive_data.return_value = {
            'launches': [mock_launch],
            'metadata': {'total_launches': 1, 'scraping_duration': 5.0},
            'source_data': []
        }
        
        result = await _scrape_all_sources()
        
        assert 'raw_data' in result
        assert len(result['raw_data']) == 1
        assert result['metadata']['total_launches'] == 1
    
    @pytest.mark.asyncio
    async def test_process_scraped_data(self, mock_data_pipeline):
        """Test _process_scraped_data function."""
        raw_data = [({'slug': 'test-launch'}, {'source_name': 'test'})]
        
        mock_result = Mock()
        mock_result.processed_launches = [Mock()]
        mock_result.conflicts = []
        mock_result.validation_errors = []
        mock_result.processing_stats = {}
        mock_result.processing_time = 1.0
        
        mock_data_pipeline.process_scraped_data.return_value = mock_result
        
        result = await _process_scraped_data(raw_data)
        
        assert 'processed_launches' in result
        assert len(result['processed_launches']) == 1
        assert result['processing_time'] == 1.0
    
    @pytest.mark.asyncio
    async def test_persist_processed_data(self, mock_db_session, mock_launch_repository):
        """Test _persist_processed_data function."""
        launches = [Mock()]
        conflicts = []
        
        mock_launch_repository.batch_upsert_launches.return_value = {
            'created': 1, 'updated': 0, 'total': 1
        }
        
        result = await _persist_processed_data(launches, conflicts)
        
        assert result['launches_created'] == 1
        assert result['launches_updated'] == 0
        assert result['total_launches'] == 1


class TestTaskMonitoring:
    """Test task monitoring functionality."""
    
    @pytest.fixture
    def mock_celery_app(self):
        """Mock Celery app."""
        with patch('src.tasks.task_monitoring.celery_app') as mock_app:
            yield mock_app
    
    def test_task_monitor_get_task_info(self, mock_celery_app):
        """Test TaskMonitor.get_task_info."""
        mock_result = Mock()
        mock_result.name = "test_task"
        mock_result.status = "SUCCESS"
        mock_result.ready.return_value = True
        mock_result.result = {"status": "completed"}
        mock_result.failed.return_value = False
        mock_result.date_done = datetime.now(timezone.utc)
        
        mock_celery_app.AsyncResult.return_value = mock_result
        
        monitor = TaskMonitor()
        task_info = monitor.get_task_info("test_task_id")
        
        assert task_info is not None
        assert task_info.task_id == "test_task_id"
        assert task_info.name == "test_task"
        assert task_info.status == TaskStatus.SUCCESS
    
    def test_task_monitor_get_active_tasks(self, mock_celery_app):
        """Test TaskMonitor.get_active_tasks."""
        mock_inspect = Mock()
        mock_inspect.active.return_value = {
            'worker1': [
                {
                    'id': 'task1',
                    'name': 'test_task',
                    'args': [],
                    'kwargs': {},
                    'time_start': datetime.now(timezone.utc).timestamp()
                }
            ]
        }
        mock_celery_app.control.inspect.return_value = mock_inspect
        
        monitor = TaskMonitor()
        active_tasks = monitor.get_active_tasks()
        
        assert len(active_tasks) == 1
        assert active_tasks[0].task_id == 'task1'
        assert active_tasks[0].name == 'test_task'
        assert active_tasks[0].status == TaskStatus.STARTED
    
    def test_task_monitor_get_worker_stats(self, mock_celery_app):
        """Test TaskMonitor.get_worker_stats."""
        mock_inspect = Mock()
        mock_inspect.stats.return_value = {
            'worker1': {
                'pool': {'max-concurrency': 4},
                'total': {'tasks.test_task': 10},
                'rusage': {'utime': 1.5, 'maxrss': 1024}
            }
        }
        mock_inspect.active.return_value = {'worker1': []}
        mock_inspect.reserved.return_value = {'worker1': []}
        
        mock_celery_app.control.inspect.return_value = mock_inspect
        
        monitor = TaskMonitor()
        stats = monitor.get_worker_stats()
        
        assert 'workers' in stats
        assert 'worker1' in stats['workers']
        assert stats['workers']['worker1']['status'] == 'online'
        assert stats['total_workers'] == 1
        assert stats['online_workers'] == 1
    
    def test_task_monitor_cancel_task(self, mock_celery_app):
        """Test TaskMonitor.cancel_task."""
        mock_control = Mock()
        mock_celery_app.control = mock_control
        
        monitor = TaskMonitor()
        result = monitor.cancel_task("test_task_id", terminate=True)
        
        assert result['status'] == 'cancelled'
        assert result['task_id'] == 'test_task_id'
        assert result['terminated'] is True
        mock_control.revoke.assert_called_with("test_task_id", terminate=True)
    
    def test_task_logger_initialization(self):
        """Test TaskLogger initialization."""
        logger = TaskLogger("test_task", "task_123")
        
        assert logger.task_name == "test_task"
        assert logger.task_id == "task_123"
        assert logger.start_time is not None
    
    def test_task_logger_logging_methods(self):
        """Test TaskLogger logging methods."""
        with patch('src.tasks.task_monitoring.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            task_logger = TaskLogger("test_task", "task_123")
            
            task_logger.info("Test info message")
            task_logger.warning("Test warning message")
            task_logger.error("Test error message")
            
            # Verify logger methods were called
            mock_logger.info.assert_called()
            mock_logger.warning.assert_called()
            mock_logger.error.assert_called()
    
    def test_task_logger_task_lifecycle(self):
        """Test TaskLogger task lifecycle logging."""
        with patch('src.tasks.task_monitoring.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            task_logger = TaskLogger("test_task", "task_123")
            
            # Test task start logging
            task_logger.log_task_start(args=("arg1",), kwargs={"key": "value"})
            mock_logger.info.assert_called()
            
            # Test task success logging
            task_logger.log_task_success(result={"processed": 100})
            assert mock_logger.info.call_count == 2
            
            # Test task failure logging
            exception = Exception("Test error")
            task_logger.log_task_failure(exception)
            mock_logger.error.assert_called()
            
            # Test task retry logging
            task_logger.log_task_retry(exception, retry_count=1)
            mock_logger.warning.assert_called()


class TestCeleryConfiguration:
    """Test Celery app configuration."""
    
    def test_celery_app_configuration(self):
        """Test Celery app is properly configured."""
        assert celery_app.conf.task_serializer == 'json'
        assert celery_app.conf.accept_content == ['json']
        assert celery_app.conf.result_serializer == 'json'
        assert celery_app.conf.timezone == 'UTC'
        assert celery_app.conf.enable_utc is True
    
    def test_celery_beat_schedule(self):
        """Test Celery Beat schedule configuration."""
        beat_schedule = celery_app.conf.beat_schedule
        
        assert 'scrape-launch-data' in beat_schedule
        assert 'health-check' in beat_schedule
        
        scrape_task = beat_schedule['scrape-launch-data']
        assert scrape_task['task'] == 'src.tasks.scraping_tasks.scrape_launch_data'
        assert scrape_task['options']['queue'] == 'scraping'
        
        health_task = beat_schedule['health-check']
        assert health_task['task'] == 'src.tasks.scraping_tasks.health_check'
        assert health_task['options']['queue'] == 'monitoring'
    
    def test_celery_task_routes(self):
        """Test Celery task routing configuration."""
        task_routes = celery_app.conf.task_routes
        
        assert 'src.tasks.scraping_tasks.scrape_launch_data' in task_routes
        assert task_routes['src.tasks.scraping_tasks.scrape_launch_data']['queue'] == 'scraping'
        
        assert 'src.tasks.scraping_tasks.manual_refresh' in task_routes
        assert task_routes['src.tasks.scraping_tasks.manual_refresh']['queue'] == 'scraping'
        
        assert 'src.tasks.scraping_tasks.health_check' in task_routes
        assert task_routes['src.tasks.scraping_tasks.health_check']['queue'] == 'monitoring'


# Integration tests (would require actual Redis and database)
@pytest.mark.integration
class TestTaskIntegration:
    """Integration tests for task system."""
    
    @pytest.mark.skip(reason="Requires Redis and database setup")
    def test_full_scraping_pipeline(self):
        """Test complete scraping pipeline integration."""
        # This would test the actual task execution with real dependencies
        pass
    
    @pytest.mark.skip(reason="Requires Redis setup")
    def test_task_locking_integration(self):
        """Test task locking with real Redis."""
        # This would test actual Redis-based locking
        pass
    
    @pytest.mark.skip(reason="Requires Celery worker")
    def test_celery_task_execution(self):
        """Test actual Celery task execution."""
        # This would test tasks running in actual Celery workers
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])