from datetime import datetime
from models.campaign import InviteCampaign
from models.dm_campaign import DMCampaign
from workers.invite_worker import run_invite_campaign
from workers.dm_worker import run_dm_campaign

def check_and_start_campaigns(app):
    """
    Checks active campaigns and starts workers if needed.
    """
    with app.app_context():
        started = []
        
        # ========== INVITE CAMPAIGNS ==========
        invite_campaigns = InviteCampaign.query.filter_by(status='active').all()
        
        for campaign in invite_campaigns:
            # TODO: Check if task is already running using Redis or Celery Inspector to avoid duplicates
            
            task = run_invite_campaign.delay(campaign.id)
            started.append({
                'type': 'invite',
                'campaign_id': campaign.id,
                'task_id': task.id,
                'name': campaign.name
            })
            print(f"[CampaignScheduler] Started INVITE worker for campaign {campaign.id}: {campaign.name}")
        
        # ========== DM CAMPAIGNS ==========
        try:
            dm_campaigns = DMCampaign.query.filter_by(status='active').all()
            for campaign in dm_campaigns:
                 task = run_dm_campaign.delay(campaign.id)
                 started.append({
                     'type': 'dm',
                     'campaign_id': campaign.id,
                     'task_id': task.id,
                     'name': campaign.name
                 })
                 print(f"[CampaignScheduler] Started DM worker for campaign {campaign.id}: {campaign.name}")
        except Exception as e:
            print(f"[CampaignScheduler] Error checking DM campaigns: {e}")

        return {
            'checked_at': datetime.now().isoformat(),
            'started_campaigns': started,
            'count': len(started)
        }
