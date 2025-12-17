from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Celery
celery = Celery(
    'telegram_system',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

# Celery configuration
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
)

# Periodic tasks schedule
celery.conf.beat_schedule = {
    # Rotate mobile proxies every 15 minutes
    'rotate-mobile-proxies': {
        'task': 'workers.maintenance_workers.auto_rotate_mobile_proxies',
        'schedule': crontab(minute='*/15'),
    },
    
    # Check account health every hour
    'check-account-health': {
        'task': 'workers.maintenance_workers.check_account_health',
        'schedule': crontab(minute=0),
    },
    
    # Execute scheduled tasks every minute
    'execute-scheduled-tasks': {
        'task': 'workers.scheduler_worker.execute_scheduled_tasks',
        'schedule': crontab(minute='*'),
    },
    
    # Check auto-actions every 5 minutes
    'check-auto-actions': {
        'task': 'workers.scheduler_worker.check_auto_actions',
        'schedule': crontab(minute='*/5'),
    },
    
    # Aggregate daily statistics at midnight
    'aggregate-daily-stats': {
        'task': 'workers.maintenance_workers.aggregate_daily_stats',
        'schedule': crontab(hour=0, minute=5),
    },
    
    # Reset daily counters at midnight
    'reset-daily-counters': {
        'task': 'workers.maintenance_workers.reset_daily_counters',
        'schedule': crontab(hour=0, minute=1),
    },
    
    # Cleanup old logs weekly (Sunday at 2 AM)
    'cleanup-old-logs': {
        'task': 'workers.maintenance_workers.cleanup_old_logs',
        'schedule': crontab(day_of_week=0, hour=2),
    },
    
    # Account warm-up activity every 2 hours
    'warmup-activity': {
        'task': 'workers.maintenance_workers.warmup_account_activity',
        'schedule': crontab(minute=0, hour='*/2'),
    },
    
    # Check and restart DM reply listeners every hour
    'check-dm-listeners': {
        'task': 'workers.dm_reply_listener.check_and_restart_listeners',
        'schedule': crontab(minute=30),  # Every hour at :30
    },
}

# Auto-discover tasks from workers module
celery.autodiscover_tasks(['workers'])

if __name__ == '__main__':
    celery.start()
