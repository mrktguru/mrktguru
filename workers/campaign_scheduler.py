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
    from workers.invite_worker import run_invite_campaign
    
    with app.app_context():
        # Найти все активные кампании
        active_campaigns = InviteCampaign.query.filter_by(status='active').all()
        
        started = []
        for campaign in active_campaigns:
            # Запустить worker
            task = run_invite_campaign.delay(campaign.id)
            started.append({
                'campaign_id': campaign.id,
                'task_id': task.id,
                'name': campaign.name
            })
            
            print(f"Started worker for campaign {campaign.id}: {campaign.name}")
        
        return {
            'checked_at': datetime.now().isoformat(),
            'started_campaigns': started,
            'count': len(started)
        }
