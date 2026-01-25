"""
Celery Application Configuration
"""
# 🔥 Monkey Patching for Gevent (Must be first)
from gevent import monkey
monkey.patch_all()

from celery import Celery
from celery.schedules import crontab
import os
import sys

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# List of modules that contain tasks
TASK_MODULES = [
    "workers.invite_worker",
    "workers.dm_worker", 
    "workers.parser_worker",
    "workers.maintenance_workers",
    "workers.campaign_scheduler",
    "workers.warmup_worker",
    "workers.scheduler_worker"
]

# Initialize Celery
celery = Celery(
    "telegram_system",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=TASK_MODULES
)

# Configuration
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)

# Periodic Tasks Schedule
celery.conf.beat_schedule = {
    # Proxy rotation every 15 minutes (DISABLED)
    # "rotate-mobile-proxies": {
    #     "task": "workers.maintenance_workers.auto_rotate_mobile_proxies",
    #     "schedule": crontab(minute="*/15"),
    # },
    
    # Account health check every hour (DISABLED)
    # "check-account-health": {
    #     "task": "workers.maintenance_workers.check_account_health",
    #     "schedule": crontab(minute=0),
    # },
    
    # Reset cooldown accounts every 30 minutes
    "reset-cooldown-accounts": {
        "task": "workers.maintenance_workers.reset_cooldown_accounts",
        "schedule": crontab(minute="*/30"),
    },
    
    # Test all proxies every 6 hours
    "test-all-proxies": {
        "task": "workers.maintenance_workers.test_all_proxies",
        "schedule": crontab(hour="*/6", minute=0),
    },
    
    # Daily statistics at midnight
    "aggregate-daily-stats": {
        "task": "workers.maintenance_workers.aggregate_daily_stats",
        "schedule": crontab(hour=0, minute=5),
    },
    
    # Reset daily counters at midnight
    "reset-daily-counters": {
        "task": "workers.invite_worker.reset_daily_counters",
        "schedule": crontab(hour=0, minute=0),
    },
    
    # Start active campaigns every minute
    "start-active-campaigns": {
        "task": "workers.campaign_scheduler.start_active_campaigns",
        "schedule": crontab(),
    },
    # Clean up old logs weekly (Sunday at 2 AM)
    "cleanup-old-logs": {
        "task": "workers.maintenance_workers.cleanup_old_logs",
        "schedule": crontab(day_of_week=0, hour=2, minute=0),
    },
    
    # Clean up old parse jobs weekly (Sunday at 3 AM)
    "cleanup-old-parse-jobs": {
        "task": "workers.parser_worker.cleanup_old_parse_jobs",
        "schedule": crontab(day_of_week=0, hour=3, minute=0),
    },
    
    # Schedule daily warmup activities (every day at 8 AM)
    "schedule-daily-warmup": {
        "task": "workers.warmup_worker.schedule_daily_warmup",
        "schedule": crontab(hour=8, minute=0),
    },
    
    # Update warmup day counters (every day at midnight)
    "update-warmup-counters": {
        "task": "workers.warmup_worker.update_warmup_day_counters",
        "schedule": crontab(hour=0, minute=1),
    },
    
    # Check warmup schedules (every minute)
    "check-warmup-schedules": {
        "task": "workers.scheduler_worker.check_warmup_schedules",
        "schedule": crontab(),  # Every minute
    },
}

if __name__ == "__main__":
    celery.start()
