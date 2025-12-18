"""
Campaign Scheduler - автозапуск активных кампаний
"""
from celery_app import celery
from database import db
from models.campaign import InviteCampaign
from datetime import datetime


@celery.task
def start_active_campaigns():
    """
    Проверяет активные кампании и запускает workers если нужно
    Запускается каждую минуту через Celery Beat
    """
    from workers.invite_worker import run_invite_campaign
    
    # Найти все активные кампании
    active_campaigns = InviteCampaign.query.filter_by(status='active').all()
    
    started = []
    for campaign in active_campaigns:
        # Проверить есть ли уже запущенный task для этой кампании
        # Можно проверить по campaign.worker_task_id если добавить это поле
        
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


@celery.task
def check_campaign_status():
    """
    Проверяет статус кампаний и обновляет если завершены
    """
    active_campaigns = InviteCampaign.query.filter_by(status='active').all()
    
    completed = []
    for campaign in active_campaigns:
        # Проверить есть ли ещё pending targets
        from models.campaign import SourceUser
        pending_count = SourceUser.query.filter_by(
            campaign_id=campaign.id,
            status='pending'
        ).count()
        
        if pending_count == 0:
            campaign.status = 'completed'
            campaign.completed_at = datetime.utcnow()
            db.session.commit()
            completed.append(campaign.id)
            print(f"Campaign {campaign.id} completed")
    
    return {
        'checked': len(active_campaigns),
        'completed': completed
    }
