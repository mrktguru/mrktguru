"""
Campaign Scheduler - Facade (Refactored)
Delegates logic to modules.campaigns.scheduler
"""
from celery_app import celery
from modules.campaigns.scheduler import check_and_start_campaigns

@celery.task
def start_active_campaigns():
    """
    Checks active campaigns and starts workers if needed.
    """
    # Import app here to avoid circular imports if any, though check_and_start_campaigns takes app
    from app import app
    return check_and_start_campaigns(app)
