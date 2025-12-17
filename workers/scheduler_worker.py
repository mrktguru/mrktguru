from celery_app import celery
from app import db
from models.automation import ScheduledTask, AutoAction
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@celery.task
def execute_scheduled_tasks():
    """Execute pending scheduled tasks"""
    
    now = datetime.utcnow()
    
    tasks = ScheduledTask.query.filter(
        ScheduledTask.scheduled_for <= now,
        ScheduledTask.status == 'pending'
    ).all()
    
    for task in tasks:
        try:
            logger.info(f"Executing scheduled task {task.id}: {task.task_type}")
            
            # Execute based on task type
            if task.task_type == 'subscribe_channel':
                execute_subscribe_task(task)
            elif task.task_type == 'post_message':
                execute_post_task(task)
            elif task.task_type == 'start_campaign':
                execute_start_campaign_task(task)
            # Add more task types as needed
            
            task.status = 'completed'
            task.executed_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error executing task {task.id}: {str(e)}")
            task.status = 'failed'
            task.error_message = str(e)
        
        db.session.commit()


def execute_subscribe_task(task):
    """Execute channel subscription task"""
    # Implementation placeholder
    pass


def execute_post_task(task):
    """Execute post message task"""
    # Implementation placeholder
    pass


def execute_start_campaign_task(task):
    """Execute start campaign task"""
    from models.campaign import InviteCampaign
    from workers.invite_worker import run_invite_campaign
    
    campaign = InviteCampaign.query.get(task.entity_id)
    if campaign:
        campaign.status = 'active'
        campaign.started_at = datetime.utcnow()
        db.session.commit()
        run_invite_campaign.delay(campaign.id)


@celery.task
def check_auto_actions():
    """Check if any auto-action triggers are met"""
    
    actions = AutoAction.query.filter_by(is_enabled=True).all()
    
    for action in actions:
        try:
            if check_trigger(action):
                logger.info(f"Auto-action triggered: {action.name}")
                execute_action(action)
        except Exception as e:
            logger.error(f"Error checking auto-action {action.id}: {str(e)}")


def check_trigger(action):
    """Check if trigger condition is met"""
    trigger_type = action.trigger_type
    condition = action.trigger_condition
    
    if trigger_type == 'campaign_progress':
        from models.campaign import InviteCampaign
        campaign_id = condition.get('campaign_id')
        threshold = condition.get('threshold', 50)
        
        campaign = InviteCampaign.query.get(campaign_id)
        if campaign and campaign.total_targets > 0:
            progress = (campaign.invited_count / campaign.total_targets) * 100
            return progress >= threshold
    
    elif trigger_type == 'account_health':
        from models.account import Account
        account_id = condition.get('account_id')
        threshold = condition.get('threshold', 50)
        
        account = Account.query.get(account_id)
        if account:
            return account.health_score < threshold
    
    return False


def execute_action(action):
    """Execute auto-action"""
    action_type = action.action_type
    params = action.action_params
    
    if action_type == 'pause_account':
        from models.account import Account
        account = Account.query.get(params.get('account_id'))
        if account:
            account.status = 'cooldown'
            db.session.commit()
    
    elif action_type == 'send_notification':
        from utils.notifications import send_notification
        send_notification(params.get('message', 'Auto-action triggered'))
    
    # Add more action types as needed
