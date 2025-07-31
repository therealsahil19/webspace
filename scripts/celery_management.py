#!/usr/bin/env python3
"""
Celery management script for SpaceX Launch Tracker.
Provides utilities for starting workers, monitoring tasks, and managing the task system.
"""
import os
import sys
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.celery_app import celery_app
from src.tasks.task_monitoring import TaskMonitor, get_task_monitor
from src.tasks.task_lock import TaskLock
from src.tasks.scraping_tasks import manual_refresh, health_check


def start_worker(queues=None, concurrency=None, loglevel="info"):
    """
    Start a Celery worker.
    
    Args:
        queues: Comma-separated list of queues to consume
        concurrency: Number of concurrent worker processes
        loglevel: Logging level
    """
    print("Starting Celery worker...")
    
    # Build worker command arguments
    worker_args = [
        'worker',
        f'--loglevel={loglevel}',
        '--without-gossip',
        '--without-mingle',
        '--without-heartbeat'
    ]
    
    if queues:
        worker_args.append(f'--queues={queues}')
    else:
        worker_args.append('--queues=default,scraping,monitoring')
    
    if concurrency:
        worker_args.append(f'--concurrency={concurrency}')
    
    # Start worker
    celery_app.worker_main(worker_args)


def start_beat(loglevel="info"):
    """
    Start Celery Beat scheduler.
    
    Args:
        loglevel: Logging level
    """
    print("Starting Celery Beat scheduler...")
    
    beat_args = [
        'beat',
        f'--loglevel={loglevel}',
        '--schedule=/tmp/celerybeat-schedule'
    ]
    
    celery_app.start(beat_args)


def start_flower(port=5555):
    """
    Start Flower monitoring tool.
    
    Args:
        port: Port to run Flower on
    """
    print(f"Starting Flower monitoring on port {port}...")
    
    flower_args = [
        'flower',
        f'--port={port}',
        '--broker=redis://localhost:6379/0'
    ]
    
    celery_app.start(flower_args)


def monitor_tasks():
    """Display real-time task monitoring information."""
    monitor = get_task_monitor()
    
    print("=== SpaceX Launch Tracker - Task Monitor ===")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    # Get comprehensive status
    try:
        status = monitor.get_comprehensive_status()
        
        # Display worker stats
        worker_stats = status.get('worker_stats', {})
        print(f"Workers Online: {worker_stats.get('online_workers', 0)}/{worker_stats.get('total_workers', 0)}")
        
        if worker_stats.get('workers'):
            print("\nWorker Details:")
            for worker_name, worker_info in worker_stats['workers'].items():
                print(f"  {worker_name}: {worker_info['status']}")
                print(f"    Active Tasks: {worker_info.get('active_tasks', 0)}")
                print(f"    Reserved Tasks: {worker_info.get('reserved_tasks', 0)}")
        
        # Display active tasks
        active_tasks = status.get('active_tasks', [])
        print(f"\nActive Tasks: {len(active_tasks)}")
        for task in active_tasks:
            print(f"  {task['task_id']}: {task['name']} (Worker: {task.get('worker', 'unknown')})")
            if task.get('timestamp'):
                print(f"    Started: {task['timestamp']}")
        
        # Display scheduled tasks
        scheduled_tasks = status.get('scheduled_tasks', [])
        print(f"\nScheduled Tasks: {len(scheduled_tasks)}")
        for task in scheduled_tasks:
            print(f"  {task['task_id']}: {task['name']}")
            if task.get('eta'):
                print(f"    ETA: {task['eta']}")
        
        # Display system health
        health = status.get('system_health', {})
        print(f"\nSystem Health: {health.get('status', 'unknown').upper()}")
        if health.get('issues'):
            print("  Issues:")
            for issue in health['issues']:
                print(f"    - {issue}")
        
    except Exception as e:
        print(f"Error getting task status: {e}")


def trigger_manual_refresh(sources=None):
    """
    Trigger a manual data refresh.
    
    Args:
        sources: Optional list of sources to refresh
    """
    print("Triggering manual data refresh...")
    
    try:
        # Submit manual refresh task
        task = manual_refresh.delay(sources=sources)
        print(f"Manual refresh task submitted: {task.id}")
        
        # Wait for completion and show progress
        print("Waiting for task completion...")
        start_time = time.time()
        
        while not task.ready():
            elapsed = time.time() - start_time
            print(f"  Running for {elapsed:.1f}s...", end='\r')
            time.sleep(1)
        
        print()  # New line after progress
        
        if task.successful():
            result = task.result
            print("Manual refresh completed successfully!")
            print(f"  Launches processed: {result.get('launches_processed', 0)}")
            print(f"  Launches created: {result.get('launches_created', 0)}")
            print(f"  Launches updated: {result.get('launches_updated', 0)}")
            print(f"  Duration: {result.get('duration_seconds', 0):.2f}s")
        else:
            print(f"Manual refresh failed: {task.result}")
            
    except Exception as e:
        print(f"Error triggering manual refresh: {e}")


def run_health_check():
    """Run a health check and display results."""
    print("Running system health check...")
    
    try:
        task = health_check.delay()
        result = task.get(timeout=30)  # Wait up to 30 seconds
        
        print(f"Health Check Status: {result['status'].upper()}")
        print(f"Timestamp: {result['timestamp']}")
        
        if 'checks' in result:
            print("\nComponent Health:")
            for component, check_result in result['checks'].items():
                status = check_result.get('status', 'unknown')
                print(f"  {component.title()}: {status.upper()}")
                
                if status == 'unhealthy' and 'error' in check_result:
                    print(f"    Error: {check_result['error']}")
                elif component == 'database' and 'total_launches' in check_result:
                    print(f"    Total Launches: {check_result['total_launches']}")
        
    except Exception as e:
        print(f"Health check failed: {e}")


def list_locks():
    """List all active task locks."""
    print("Active Task Locks:")
    
    try:
        task_lock = TaskLock()
        locks = task_lock.get_all_locks()
        
        if not locks:
            print("  No active locks")
            return
        
        for lock_key, lock_info in locks.items():
            print(f"  {lock_key}:")
            print(f"    Lock ID: {lock_info['lock_id']}")
            print(f"    TTL: {lock_info['ttl_seconds']}s")
            if lock_info.get('expires_at'):
                expires_at = datetime.fromtimestamp(lock_info['expires_at'], tz=timezone.utc)
                print(f"    Expires: {expires_at.isoformat()}")
        
    except Exception as e:
        print(f"Error listing locks: {e}")


def force_release_lock(lock_key):
    """
    Force release a task lock.
    
    Args:
        lock_key: Lock key to release
    """
    print(f"Force releasing lock: {lock_key}")
    
    try:
        task_lock = TaskLock()
        success = task_lock.force_release_lock(lock_key)
        
        if success:
            print("Lock released successfully")
        else:
            print("Failed to release lock (may not exist)")
            
    except Exception as e:
        print(f"Error releasing lock: {e}")


def cancel_task(task_id, terminate=False):
    """
    Cancel a running task.
    
    Args:
        task_id: Task ID to cancel
        terminate: Whether to terminate if running
    """
    print(f"Cancelling task: {task_id}")
    
    try:
        monitor = get_task_monitor()
        result = monitor.cancel_task(task_id, terminate=terminate)
        
        if result['status'] == 'cancelled':
            print("Task cancelled successfully")
        else:
            print(f"Failed to cancel task: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"Error cancelling task: {e}")


def show_task_stats():
    """Show detailed task statistics."""
    print("=== Task Statistics ===")
    
    try:
        monitor = get_task_monitor()
        stats = monitor.get_task_statistics(hours=24)
        
        print(f"Time Period: {stats.get('time_period_hours', 0)} hours")
        print(f"Total Tasks: {stats.get('total_tasks', 0)}")
        print(f"Successful Tasks: {stats.get('successful_tasks', 0)}")
        print(f"Failed Tasks: {stats.get('failed_tasks', 0)}")
        print(f"Retry Tasks: {stats.get('retry_tasks', 0)}")
        print(f"Average Runtime: {stats.get('average_runtime', 0):.2f}s")
        
        if stats.get('task_breakdown'):
            print("\nTask Breakdown:")
            for task_name, count in stats['task_breakdown'].items():
                print(f"  {task_name}: {count}")
        
        if stats.get('error_breakdown'):
            print("\nError Breakdown:")
            for error_type, count in stats['error_breakdown'].items():
                print(f"  {error_type}: {count}")
        
    except Exception as e:
        print(f"Error getting task statistics: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SpaceX Launch Tracker - Celery Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s worker --queues scraping,monitoring --concurrency 2
  %(prog)s beat
  %(prog)s monitor
  %(prog)s refresh --sources spacex,nasa
  %(prog)s health
  %(prog)s locks
  %(prog)s cancel-task abc123 --terminate
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Worker command
    worker_parser = subparsers.add_parser('worker', help='Start Celery worker')
    worker_parser.add_argument('--queues', help='Comma-separated list of queues')
    worker_parser.add_argument('--concurrency', type=int, help='Number of worker processes')
    worker_parser.add_argument('--loglevel', default='info', help='Log level')
    
    # Beat command
    beat_parser = subparsers.add_parser('beat', help='Start Celery Beat scheduler')
    beat_parser.add_argument('--loglevel', default='info', help='Log level')
    
    # Flower command
    flower_parser = subparsers.add_parser('flower', help='Start Flower monitoring')
    flower_parser.add_argument('--port', type=int, default=5555, help='Port to run on')
    
    # Monitor command
    subparsers.add_parser('monitor', help='Show task monitoring information')
    
    # Manual refresh command
    refresh_parser = subparsers.add_parser('refresh', help='Trigger manual data refresh')
    refresh_parser.add_argument('--sources', help='Comma-separated list of sources')
    
    # Health check command
    subparsers.add_parser('health', help='Run system health check')
    
    # Locks command
    subparsers.add_parser('locks', help='List active task locks')
    
    # Force release lock command
    release_parser = subparsers.add_parser('release-lock', help='Force release a task lock')
    release_parser.add_argument('lock_key', help='Lock key to release')
    
    # Cancel task command
    cancel_parser = subparsers.add_parser('cancel-task', help='Cancel a running task')
    cancel_parser.add_argument('task_id', help='Task ID to cancel')
    cancel_parser.add_argument('--terminate', action='store_true', help='Terminate if running')
    
    # Statistics command
    subparsers.add_parser('stats', help='Show task statistics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Execute commands
    try:
        if args.command == 'worker':
            start_worker(args.queues, args.concurrency, args.loglevel)
        elif args.command == 'beat':
            start_beat(args.loglevel)
        elif args.command == 'flower':
            start_flower(args.port)
        elif args.command == 'monitor':
            monitor_tasks()
        elif args.command == 'refresh':
            sources = args.sources.split(',') if args.sources else None
            trigger_manual_refresh(sources)
        elif args.command == 'health':
            run_health_check()
        elif args.command == 'locks':
            list_locks()
        elif args.command == 'release-lock':
            force_release_lock(args.lock_key)
        elif args.command == 'cancel-task':
            cancel_task(args.task_id, args.terminate)
        elif args.command == 'stats':
            show_task_stats()
        else:
            print(f"Unknown command: {args.command}")
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()