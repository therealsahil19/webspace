"""
Task monitoring and logging utilities for Celery tasks.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from celery import states
from celery.events.state import State
from celery.events import Event

from src.celery_app import celery_app

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"


@dataclass
class TaskInfo:
    """Task information container."""
    task_id: str
    name: str
    status: TaskStatus
    worker: Optional[str] = None
    timestamp: Optional[datetime] = None
    runtime: Optional[float] = None
    args: Optional[tuple] = None
    kwargs: Optional[dict] = None
    result: Optional[Any] = None
    exception: Optional[str] = None
    traceback: Optional[str] = None
    retries: int = 0
    eta: Optional[datetime] = None
    expires: Optional[datetime] = None


class TaskMonitor:
    """Monitor and track Celery task execution."""
    
    def __init__(self):
        """Initialize task monitor."""
        self.task_history: List[TaskInfo] = []
        self.max_history_size = 1000
    
    def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        """
        Get detailed information about a specific task.
        
        Args:
            task_id: Task ID to query
            
        Returns:
            TaskInfo object or None if task not found
        """
        try:
            result = celery_app.AsyncResult(task_id)
            
            task_info = TaskInfo(
                task_id=task_id,
                name=result.name or "unknown",
                status=TaskStatus(result.status),
                result=result.result if result.ready() else None,
                exception=str(result.result) if result.failed() else None,
                traceback=result.traceback if result.failed() else None
            )
            
            # Add timing information if available
            if result.date_done:
                task_info.timestamp = result.date_done
            
            return task_info
            
        except Exception as e:
            logger.error(f"Error getting task info for {task_id}: {e}")
            return None
    
    def get_active_tasks(self) -> List[TaskInfo]:
        """
        Get list of currently active tasks.
        
        Returns:
            List of TaskInfo objects for active tasks
        """
        try:
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            
            if not active_tasks:
                return []
            
            task_list = []
            for worker, tasks in active_tasks.items():
                for task_data in tasks:
                    task_info = TaskInfo(
                        task_id=task_data['id'],
                        name=task_data['name'],
                        status=TaskStatus.STARTED,
                        worker=worker,
                        args=tuple(task_data.get('args', [])),
                        kwargs=task_data.get('kwargs', {}),
                        timestamp=datetime.fromtimestamp(
                            task_data['time_start'], 
                            tz=timezone.utc
                        ) if task_data.get('time_start') else None
                    )
                    task_list.append(task_info)
            
            return task_list
            
        except Exception as e:
            logger.error(f"Error getting active tasks: {e}")
            return []
    
    def get_scheduled_tasks(self) -> List[TaskInfo]:
        """
        Get list of scheduled tasks.
        
        Returns:
            List of TaskInfo objects for scheduled tasks
        """
        try:
            inspect = celery_app.control.inspect()
            scheduled_tasks = inspect.scheduled()
            
            if not scheduled_tasks:
                return []
            
            task_list = []
            for worker, tasks in scheduled_tasks.items():
                for task_data in tasks:
                    task_info = TaskInfo(
                        task_id=task_data['request']['id'],
                        name=task_data['request']['task'],
                        status=TaskStatus.PENDING,
                        worker=worker,
                        args=tuple(task_data['request'].get('args', [])),
                        kwargs=task_data['request'].get('kwargs', {}),
                        eta=datetime.fromtimestamp(
                            task_data['eta'], 
                            tz=timezone.utc
                        ) if task_data.get('eta') else None
                    )
                    task_list.append(task_info)
            
            return task_list
            
        except Exception as e:
            logger.error(f"Error getting scheduled tasks: {e}")
            return []
    
    def get_reserved_tasks(self) -> List[TaskInfo]:
        """
        Get list of reserved (queued) tasks.
        
        Returns:
            List of TaskInfo objects for reserved tasks
        """
        try:
            inspect = celery_app.control.inspect()
            reserved_tasks = inspect.reserved()
            
            if not reserved_tasks:
                return []
            
            task_list = []
            for worker, tasks in reserved_tasks.items():
                for task_data in tasks:
                    task_info = TaskInfo(
                        task_id=task_data['id'],
                        name=task_data['name'],
                        status=TaskStatus.PENDING,
                        worker=worker,
                        args=tuple(task_data.get('args', [])),
                        kwargs=task_data.get('kwargs', {})
                    )
                    task_list.append(task_info)
            
            return task_list
            
        except Exception as e:
            logger.error(f"Error getting reserved tasks: {e}")
            return []
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """
        Get statistics about Celery workers.
        
        Returns:
            Dictionary with worker statistics
        """
        try:
            inspect = celery_app.control.inspect()
            
            # Get worker statistics
            stats = inspect.stats()
            active = inspect.active()
            reserved = inspect.reserved()
            
            worker_info = {}
            
            if stats:
                for worker, worker_stats in stats.items():
                    worker_info[worker] = {
                        'status': 'online',
                        'pool': worker_stats.get('pool', {}),
                        'total_tasks': worker_stats.get('total', {}),
                        'active_tasks': len(active.get(worker, [])) if active else 0,
                        'reserved_tasks': len(reserved.get(worker, [])) if reserved else 0,
                        'load_avg': worker_stats.get('rusage', {}).get('utime', 0),
                        'memory_usage': worker_stats.get('rusage', {}).get('maxrss', 0)
                    }
            
            return {
                'workers': worker_info,
                'total_workers': len(worker_info),
                'online_workers': len([w for w in worker_info.values() if w['status'] == 'online'])
            }
            
        except Exception as e:
            logger.error(f"Error getting worker stats: {e}")
            return {'workers': {}, 'total_workers': 0, 'online_workers': 0}
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get statistics about task queues.
        
        Returns:
            Dictionary with queue statistics
        """
        try:
            # Get queue lengths (this requires additional setup with Redis)
            # For now, return basic queue information
            queues = ['default', 'scraping', 'monitoring']
            
            queue_stats = {}
            for queue in queues:
                # This would require Redis inspection to get actual queue lengths
                queue_stats[queue] = {
                    'name': queue,
                    'length': 0,  # Placeholder
                    'consumers': 0  # Placeholder
                }
            
            return {
                'queues': queue_stats,
                'total_queues': len(queues)
            }
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {'queues': {}, 'total_queues': 0}
    
    def get_task_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get task execution statistics for the specified time period.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with task statistics
        """
        try:
            # This would require a task result backend or custom logging
            # For now, return basic statistics structure
            
            stats = {
                'time_period_hours': hours,
                'total_tasks': 0,
                'successful_tasks': 0,
                'failed_tasks': 0,
                'retry_tasks': 0,
                'average_runtime': 0.0,
                'task_breakdown': {},
                'error_breakdown': {},
                'hourly_distribution': {}
            }
            
            # In a real implementation, this would query the result backend
            # or a custom task logging system
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting task statistics: {e}")
            return {}
    
    def cancel_task(self, task_id: str, terminate: bool = False) -> Dict[str, Any]:
        """
        Cancel a running or pending task.
        
        Args:
            task_id: Task ID to cancel
            terminate: Whether to terminate if task is running
            
        Returns:
            Dictionary with cancellation result
        """
        try:
            celery_app.control.revoke(task_id, terminate=terminate)
            
            return {
                'status': 'cancelled',
                'task_id': task_id,
                'terminated': terminate,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}")
            return {
                'status': 'error',
                'task_id': task_id,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status including all task and worker information.
        
        Returns:
            Dictionary with complete system status
        """
        try:
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'active_tasks': [asdict(task) for task in self.get_active_tasks()],
                'scheduled_tasks': [asdict(task) for task in self.get_scheduled_tasks()],
                'reserved_tasks': [asdict(task) for task in self.get_reserved_tasks()],
                'worker_stats': self.get_worker_stats(),
                'queue_stats': self.get_queue_stats(),
                'task_statistics': self.get_task_statistics(),
                'system_health': self._check_system_health()
            }
            
        except Exception as e:
            logger.error(f"Error getting comprehensive status: {e}")
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': str(e)
            }
    
    def _check_system_health(self) -> Dict[str, Any]:
        """
        Check overall system health.
        
        Returns:
            Dictionary with health status
        """
        try:
            worker_stats = self.get_worker_stats()
            active_tasks = self.get_active_tasks()
            
            # Basic health checks
            health_status = 'healthy'
            issues = []
            
            # Check if workers are online
            if worker_stats['online_workers'] == 0:
                health_status = 'critical'
                issues.append('No workers online')
            
            # Check for stuck tasks (running for more than 2 hours)
            current_time = datetime.now(timezone.utc)
            for task in active_tasks:
                if task.timestamp:
                    runtime = (current_time - task.timestamp).total_seconds()
                    if runtime > 7200:  # 2 hours
                        health_status = 'warning'
                        issues.append(f'Task {task.task_id} running for {runtime/3600:.1f} hours')
            
            return {
                'status': health_status,
                'issues': issues,
                'workers_online': worker_stats['online_workers'],
                'active_tasks_count': len(active_tasks),
                'last_check': current_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            return {
                'status': 'unknown',
                'error': str(e),
                'last_check': datetime.now(timezone.utc).isoformat()
            }


class TaskLogger:
    """Enhanced logging for Celery tasks."""
    
    def __init__(self, task_name: str, task_id: str):
        """
        Initialize task logger.
        
        Args:
            task_name: Name of the task
            task_id: Task ID
        """
        self.task_name = task_name
        self.task_id = task_id
        self.logger = logging.getLogger(f"task.{task_name}")
        self.start_time = datetime.now(timezone.utc)
    
    def info(self, message: str, **kwargs):
        """Log info message with task context."""
        self._log('info', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with task context."""
        self._log('warning', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with task context."""
        self._log('error', message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with task context."""
        self._log('debug', message, **kwargs)
    
    def _log(self, level: str, message: str, **kwargs):
        """Internal logging method with task context."""
        extra = {
            'task_name': self.task_name,
            'task_id': self.task_id,
            'runtime': (datetime.now(timezone.utc) - self.start_time).total_seconds(),
            **kwargs
        }
        
        log_method = getattr(self.logger, level)
        log_method(f"[{self.task_id}] {message}", extra=extra)
    
    def log_task_start(self, args=None, kwargs=None):
        """Log task start with parameters."""
        self.info(
            f"Task started: {self.task_name}",
            args=args,
            kwargs=kwargs
        )
    
    def log_task_success(self, result=None, **metrics):
        """Log successful task completion."""
        runtime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        self.info(
            f"Task completed successfully in {runtime:.2f}s",
            result=result,
            runtime=runtime,
            **metrics
        )
    
    def log_task_failure(self, exception: Exception, **context):
        """Log task failure with exception details."""
        runtime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        self.error(
            f"Task failed after {runtime:.2f}s: {str(exception)}",
            exception_type=type(exception).__name__,
            runtime=runtime,
            **context
        )
    
    def log_task_retry(self, exception: Exception, retry_count: int, **context):
        """Log task retry attempt."""
        runtime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        self.warning(
            f"Task retry #{retry_count} after {runtime:.2f}s: {str(exception)}",
            exception_type=type(exception).__name__,
            retry_count=retry_count,
            runtime=runtime,
            **context
        )


# Utility functions
def create_task_logger(task_name: str, task_id: str) -> TaskLogger:
    """Create a task logger instance."""
    return TaskLogger(task_name, task_id)


def get_task_monitor() -> TaskMonitor:
    """Get a task monitor instance."""
    return TaskMonitor()


# Example usage
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Test task monitoring
    monitor = TaskMonitor()
    
    # Get comprehensive status
    status = monitor.get_comprehensive_status()
    print(f"System status: {status}")
    
    # Test task logger
    task_logger = TaskLogger("test_task", "test_123")
    task_logger.log_task_start(args=("arg1",), kwargs={"key": "value"})
    task_logger.info("Processing data...")
    task_logger.log_task_success(result={"processed": 100})