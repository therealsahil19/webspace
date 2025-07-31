"""
Tests for logging and monitoring functionality.
"""

import pytest
import tempfile
import time
import asyncio
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock

from src.logging_config import (
    LogConfig, setup_logging, get_logger, LogContext, TimedOperation,
    log_function_call, log_async_function_call
)
from src.monitoring.metrics import MetricsCollector, get_metrics_collector, track_scraping_metrics
from src.monitoring.health_checks import HealthChecker, HealthStatus, HealthCheckResult
from src.monitoring.log_management import LogManager, LogRetentionPolicy


class TestLogConfig:
    """Test logging configuration."""
    
    def test_default_config(self):
        """Test default logging configuration."""
        config = LogConfig()
        
        assert config.log_level == 'INFO'
        assert config.log_format in ['json', 'console']
        assert config.enable_file_logging is True
        assert config.max_log_size > 0
        assert config.backup_count > 0
    
    def test_environment_config(self, monkeypatch):
        """Test configuration from environment variables."""
        monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
        monkeypatch.setenv('LOG_FORMAT', 'console')
        monkeypatch.setenv('ENABLE_FILE_LOGGING', 'false')
        monkeypatch.setenv('MAX_LOG_SIZE_MB', '50')
        
        config = LogConfig()
        
        assert config.log_level == 'DEBUG'
        assert config.log_format == 'console'
        assert config.enable_file_logging is False
        assert config.max_log_size == 50 * 1024 * 1024


class TestStructuredLogging:
    """Test structured logging functionality."""
    
    def test_get_logger(self):
        """Test logger creation."""
        logger = get_logger(__name__)
        assert logger is not None
        
        logger_with_component = get_logger(__name__, component="test")
        assert logger_with_component is not None
    
    def test_log_context(self):
        """Test log context manager."""
        logger = get_logger(__name__)
        
        with LogContext(logger, test_key="test_value") as context_logger:
            assert context_logger is not None
            # Context logger should have the bound context
    
    def test_timed_operation(self):
        """Test timed operation context manager."""
        logger = get_logger(__name__)
        
        with TimedOperation(logger, "test_operation", test_param="value"):
            time.sleep(0.1)  # Simulate work
        
        # Should log start and completion
    
    def test_function_call_decorator(self):
        """Test function call logging decorator."""
        logger = get_logger(__name__)
        
        @log_function_call(logger)
        def test_function(x, y=None):
            return x + (y or 0)
        
        result = test_function(1, y=2)
        assert result == 3
    
    def test_async_function_call_decorator(self):
        """Test async function call logging decorator."""
        logger = get_logger(__name__)
        
        @log_async_function_call(logger)
        async def test_async_function(x, y=None):
            await asyncio.sleep(0.01)
            return x + (y or 0)
        
        async def run_test():
            result = await test_async_function(1, y=2)
            assert result == 3
        
        asyncio.run(run_test())


class TestMetricsCollector:
    """Test metrics collection functionality."""
    
    def test_metrics_collector_initialization(self):
        """Test metrics collector initialization."""
        collector = MetricsCollector()
        assert collector is not None
        assert collector.registry is not None
    
    def test_scraping_metrics(self):
        """Test scraping metrics recording."""
        collector = MetricsCollector()
        
        # Record scraping metrics
        collector.record_scraping_request('spacex', 'success')
        collector.record_scraping_duration('spacex', 1.5)
        collector.record_scraped_launches('spacex', 10)
        collector.record_scraping_error('nasa', 'timeout')
        collector.update_last_successful_scrape('spacex')
        
        # Get metrics output
        metrics_output = collector.get_metrics()
        assert 'scraping_requests_total' in metrics_output
        assert 'scraping_duration_seconds' in metrics_output
    
    def test_database_metrics(self):
        """Test database metrics recording."""
        collector = MetricsCollector()
        
        collector.record_database_operation('select', 'launches', 'success')
        collector.record_database_query_duration('select', 'launches', 0.05)
        collector.update_active_connections(5)
        
        metrics_output = collector.get_metrics()
        assert 'database_operations_total' in metrics_output
        assert 'database_query_duration_seconds' in metrics_output
    
    def test_api_metrics(self):
        """Test API metrics recording."""
        collector = MetricsCollector()
        
        collector.record_http_request('GET', '/api/launches', 200)
        collector.record_http_duration('GET', '/api/launches', 0.1)
        collector.increment_active_requests()
        collector.decrement_active_requests()
        
        metrics_output = collector.get_metrics()
        assert 'http_requests_total' in metrics_output
        assert 'http_request_duration_seconds' in metrics_output
    
    def test_celery_metrics(self):
        """Test Celery metrics recording."""
        collector = MetricsCollector()
        
        collector.record_celery_task('scrape_launch_data', 'success')
        collector.record_celery_task_duration('scrape_launch_data', 30.0)
        collector.update_queue_size('scraping', 3)
        
        metrics_output = collector.get_metrics()
        assert 'celery_tasks_total' in metrics_output
        assert 'celery_task_duration_seconds' in metrics_output
    
    def test_health_metrics(self):
        """Test health metrics recording."""
        collector = MetricsCollector()
        
        collector.update_system_health('healthy')
        collector.update_component_health('database', 'healthy')
        collector.update_component_health('redis', 'degraded')
        
        metrics_output = collector.get_metrics()
        assert 'system_health_status' in metrics_output
        assert 'component_health_status' in metrics_output
    
    def test_launch_data_metrics(self):
        """Test launch data metrics recording."""
        collector = MetricsCollector()
        
        collector.update_launches_count(150)
        collector.update_upcoming_launches_count(5)
        collector.update_data_freshness(datetime.now(timezone.utc) - timedelta(hours=2))
        
        metrics_output = collector.get_metrics()
        assert 'launches_in_database_total' in metrics_output
        assert 'upcoming_launches_total' in metrics_output
    
    def test_track_scraping_metrics_decorator(self):
        """Test scraping metrics decorator."""
        @track_scraping_metrics('test_source')
        async def test_scraping_function():
            await asyncio.sleep(0.01)
            return ['launch1', 'launch2']
        
        async def run_test():
            result = await test_scraping_function()
            assert len(result) == 2
        
        asyncio.run(run_test())


class TestHealthChecker:
    """Test health check functionality."""
    
    def test_health_checker_initialization(self):
        """Test health checker initialization."""
        checker = HealthChecker()
        assert checker is not None
        assert len(checker.checks) > 0
    
    def test_health_check_result(self):
        """Test health check result structure."""
        result = HealthCheckResult(
            name='test_check',
            status=HealthStatus.HEALTHY,
            message='Test is healthy',
            details={'test': 'value'},
            duration_ms=10.0,
            timestamp=datetime.now(timezone.utc)
        )
        
        result_dict = result.to_dict()
        assert result_dict['name'] == 'test_check'
        assert result_dict['status'] == 'healthy'
        assert 'timestamp' in result_dict
    
    @pytest.mark.asyncio
    async def test_run_individual_check(self):
        """Test running individual health checks."""
        checker = HealthChecker()
        
        # Mock a simple check
        async def mock_check():
            return HealthCheckResult(
                name='mock_check',
                status=HealthStatus.HEALTHY,
                message='Mock check passed',
                details={},
                duration_ms=1.0,
                timestamp=datetime.now(timezone.utc)
            )
        
        checker.register_check('mock_check', mock_check)
        result = await checker.run_check('mock_check')
        
        assert result.name == 'mock_check'
        assert result.status == HealthStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_run_all_checks(self):
        """Test running all health checks."""
        checker = HealthChecker()
        
        # Mock database and Redis to avoid actual connections
        with patch('src.monitoring.health_checks.get_db_session'), \
             patch('src.monitoring.health_checks.get_redis_client'):
            
            results = await checker.run_all_checks()
            assert isinstance(results, dict)
            assert len(results) > 0
    
    @pytest.mark.asyncio
    async def test_overall_health_status(self):
        """Test overall health status calculation."""
        checker = HealthChecker()
        
        # Mock all checks to return healthy status
        async def healthy_check():
            return HealthCheckResult(
                name='healthy_check',
                status=HealthStatus.HEALTHY,
                message='All good',
                details={},
                duration_ms=1.0,
                timestamp=datetime.now(timezone.utc)
            )
        
        # Replace all checks with healthy mock
        checker.checks = {
            'check1': healthy_check,
            'check2': healthy_check,
        }
        
        overall_health = await checker.get_overall_health()
        assert overall_health['status'] == 'healthy'
        assert 'checks' in overall_health
        assert 'summary' in overall_health


class TestLogManager:
    """Test log management functionality."""
    
    def test_log_manager_initialization(self):
        """Test log manager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            manager = LogManager(log_dir)
            
            assert manager.log_dir == log_dir
            assert manager.retention_policy is not None
    
    def test_log_retention_policy(self):
        """Test log retention policy configuration."""
        policy = LogRetentionPolicy(
            max_age_days=14,
            max_size_mb=500,
            compress_after_days=3,
            delete_after_days=14
        )
        
        assert policy.max_age_days == 14
        assert policy.max_size_mb == 500
        assert policy.compress_after_days == 3
        assert policy.delete_after_days == 14
    
    def test_get_log_files(self):
        """Test getting log files from directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            manager = LogManager(log_dir)
            
            # Create test log files
            (log_dir / 'test.log').touch()
            (log_dir / 'test.log.1').touch()
            (log_dir / 'other.log').touch()
            
            log_files = manager.get_log_files()
            assert len(log_files) >= 3
    
    def test_log_file_info(self):
        """Test getting log file information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            manager = LogManager(log_dir)
            
            # Create test log file
            test_file = log_dir / 'test.log'
            test_file.write_text('test log content')
            
            info = manager.get_log_file_info(test_file)
            assert 'size_bytes' in info
            assert 'modified_time' in info
            assert 'age_days' in info
    
    def test_log_statistics(self):
        """Test getting log statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            manager = LogManager(log_dir)
            
            # Create test log files
            (log_dir / 'app.log').write_text('app log content')
            (log_dir / 'error.log').write_text('error log content')
            
            stats = manager.get_log_statistics()
            assert 'total_files' in stats
            assert 'total_size_mb' in stats
            assert 'file_types' in stats
            assert stats['total_files'] >= 2


class TestIntegration:
    """Integration tests for logging and monitoring."""
    
    def test_logging_with_metrics(self):
        """Test that logging and metrics work together."""
        logger = get_logger(__name__)
        metrics = get_metrics_collector()
        
        # Log some events and record metrics
        logger.info("Test log message", component="test")
        metrics.record_http_request('GET', '/test', 200)
        
        # Verify metrics were recorded
        metrics_output = metrics.get_metrics()
        assert 'http_requests_total' in metrics_output
    
    @pytest.mark.asyncio
    async def test_health_checks_with_metrics(self):
        """Test that health checks update metrics."""
        checker = HealthChecker()
        metrics = get_metrics_collector()
        
        # Mock a simple health check
        async def mock_healthy_check():
            return HealthCheckResult(
                name='mock_check',
                status=HealthStatus.HEALTHY,
                message='All good',
                details={},
                duration_ms=1.0,
                timestamp=datetime.now(timezone.utc)
            )
        
        checker.register_check('mock_check', mock_healthy_check)
        await checker.run_all_checks()
        
        # Verify metrics were updated
        metrics_output = metrics.get_metrics()
        assert 'system_health_status' in metrics_output
    
    def test_log_management_integration(self):
        """Test log management with actual log files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            
            # Set up logging to use temp directory
            config = LogConfig()
            config.log_dir = log_dir
            config.enable_file_logging = True
            
            # Create log manager
            manager = LogManager(log_dir)
            
            # Create some test log files with different ages
            old_file = log_dir / 'old.log'
            old_file.write_text('old log content')
            
            # Modify file time to make it appear old
            old_time = time.time() - (10 * 24 * 3600)  # 10 days ago
            os.utime(old_file, (old_time, old_time))
            
            recent_file = log_dir / 'recent.log'
            recent_file.write_text('recent log content')
            
            # Get statistics
            stats = manager.get_log_statistics()
            assert stats['total_files'] >= 2
            
            # Test cleanup (dry run)
            cleanup_results = manager.cleanup_logs(dry_run=True)
            assert 'dry_run' in cleanup_results


if __name__ == '__main__':
    pytest.main([__file__])