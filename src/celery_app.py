"""
Celery application configuration for SpaceX Launch Tracker.
"""
import os
from celery import Celery
from celery.schedules import crontab
from kombu import Queue

# Create Celery app
celery_app = Celery('spacex_launch_tracker')

# Configuration
celery_app.conf.update(
    # Broker settings
    broker_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'src.tasks.scraping_tasks.scrape_launch_data': {'queue': 'scraping'},
        'src.tasks.scraping_tasks.manual_refresh': {'queue': 'scraping'},
        'src.tasks.scraping_tasks.health_check': {'queue': 'monitoring'},
        'src.tasks.scraping_tasks.warm_cache': {'queue': 'maintenance'},
        'src.tasks.scraping_tasks.invalidate_cache': {'queue': 'maintenance'},
        'src.tasks.scraping_tasks.optimize_database': {'queue': 'maintenance'},
        'src.tasks.scraping_tasks.rotate_logs': {'queue': 'maintenance'},
    },
    
    # Queue configuration
    task_default_queue='default',
    task_queues=(
        Queue('default'),
        Queue('scraping'),
        Queue('monitoring'),
        Queue('maintenance'),
    ),
    
    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # Task execution settings
    task_soft_time_limit=1800,  # 30 minutes
    task_time_limit=2400,       # 40 minutes
    task_reject_on_worker_lost=True,
    
    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'scrape-launch-data': {
            'task': 'src.tasks.scraping_tasks.scrape_launch_data',
            'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
            'options': {'queue': 'scraping'}
        },
        'health-check': {
            'task': 'src.tasks.scraping_tasks.health_check',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
            'options': {'queue': 'monitoring'}
        },
        'warm-cache': {
            'task': 'src.tasks.scraping_tasks.warm_cache',
            'schedule': crontab(minute=30, hour='*/2'),  # Every 2 hours at :30
            'options': {'queue': 'maintenance'}
        },
        'optimize-database': {
            'task': 'src.tasks.scraping_tasks.optimize_database',
            'schedule': crontab(minute=0, hour=2, day_of_week=0),  # Weekly on Sunday at 2 AM
            'options': {'queue': 'maintenance'}
        },
        'rotate-logs': {
            'task': 'src.tasks.scraping_tasks.rotate_logs',
            'schedule': crontab(minute=0, hour=3),  # Daily at 3 AM
            'options': {'queue': 'maintenance'}
        },
    },
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Security
    worker_hijack_root_logger=False,
    worker_log_color=False,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(['src.tasks'])

if __name__ == '__main__':
    celery_app.start()