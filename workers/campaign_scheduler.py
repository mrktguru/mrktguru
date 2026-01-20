"""
Campaign Scheduler - автозапуск активных кампаний
"""
from celery_app import celery
from database import db
from datetime import datetime


@celery.task
def start_active_campaigns():
    """
    Проверяет активные кампании и запускает workers если нужно
    Запускается каждую минуту через Celery Beat
    """
    # Import here to avoid circular imports
    from app import app
    from models.campaign import InviteCampaign
    from models.dm_campaign import DMCampaign
    from workers.invite_worker import run_invite_campaign
    from workers.dm_worker import run_dm_campaign
    
    with app.app_context():
        started = []
        
        # ========== INVITE CAMPAIGNS ==========
        invite_campaigns = InviteCampaign.query.filter_by(status='active').all()
        
        for campaign in invite_campaigns:
            # Запустить worker
            task = run_invite_campaign.delay(campaign.id)
            started.append({
                'type': 'invite',
                'campaign_id': campaign.id,
                'task_id': task.id,
                'name': campaign.name
            })
            
            print(f"Started INVITE worker for campaign {campaign.id}: {campaign.name}")
        
        # ========== DM CAMPAIGNS ==========
        dm_campaigns = DMCampaign.query.filter_by(status='active').all()
        
        for campaign in dm_campaigns:
            # Check if already running (avoid duplicates)
            # TODO: Add task state tracking
            
            # Запустить worker
            task = run_dm_campaign.delay(campaign.id)
            started.append({
                'type': 'dm',
                'campaign_id': campaign.id,
                'task_id': task.id,
                'name': campaign.name
            })
            
            print(f"Started DM worker for campaign {campaign.id}: {campaign.name}")
        
        return {
            'checked_at': datetime.now().isoformat(),
            'started_campaigns': started,
            'count': len(started)
        }
