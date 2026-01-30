from database import db
from models.campaign import InviteCampaign, CampaignAccount
from models.account import Account
from datetime import datetime
from workers.invite_worker import run_invite_campaign

class CampaignManager:
    @staticmethod
    def create_campaign(name, description, channel_id, strategy, account_ids):
        campaign = InviteCampaign(
            name=name,
            description=description,
            channel_id=int(channel_id),
            strategy=strategy
        )
        
        # Set delays based on strategy
        if strategy == 'safe':
            campaign.delay_min = 60
            campaign.delay_max = 120
            campaign.invites_per_hour_min = 3
            campaign.invites_per_hour_max = 5
        elif strategy == 'normal':
            campaign.delay_min = 45
            campaign.delay_max = 90
            campaign.invites_per_hour_min = 5
            campaign.invites_per_hour_max = 10
        elif strategy == 'aggressive':
            campaign.delay_min = 30
            campaign.delay_max = 60
            campaign.invites_per_hour_min = 8
            campaign.invites_per_hour_max = 15
        
        db.session.add(campaign)
        db.session.flush()
        
        # Assign accounts
        for account_id in account_ids:
            ca = CampaignAccount(
                campaign_id=campaign.id,
                account_id=int(account_id)
            )
            db.session.add(ca)
        
        db.session.commit()
        return campaign

    @staticmethod
    def update_settings(campaign_id, data):
        campaign = InviteCampaign.query.get_or_404(campaign_id)
        
        if 'name' in data: campaign.name = data['name']
        if 'description' in data: campaign.description = data['description']
        if 'strategy' in data: campaign.strategy = data['strategy']
        if 'delay_min' in data: campaign.delay_min = int(data['delay_min'])
        if 'delay_max' in data: campaign.delay_max = int(data['delay_max'])
        if 'invites_per_hour_min' in data: campaign.invites_per_hour_min = int(data['invites_per_hour_min'])
        if 'invites_per_hour_max' in data: campaign.invites_per_hour_max = int(data['invites_per_hour_max'])
        if 'burst_limit' in data: campaign.burst_limit = int(data['burst_limit'])
        if 'burst_pause_minutes' in data: campaign.burst_pause_minutes = int(data['burst_pause_minutes'])
        
        if 'working_hours_start' in data and data['working_hours_start']:
            campaign.working_hours_start = datetime.strptime(data['working_hours_start'], "%H:%M").time()
        if 'working_hours_end' in data and data['working_hours_end']:
            campaign.working_hours_end = datetime.strptime(data['working_hours_end'], "%H:%M").time()
            
        if 'human_like_behavior' in data:
            campaign.human_like_behavior = bool(data['human_like_behavior'])
        if 'auto_pause_on_errors' in data:
            campaign.auto_pause_on_errors = bool(data['auto_pause_on_errors'])
            
        db.session.commit()
        return campaign

    @staticmethod
    def start_campaign(campaign_id):
        campaign = InviteCampaign.query.get_or_404(campaign_id)
        
        if campaign.status == "active":
            return False, "Campaign is already running"
        
        campaign.status = "active"
        campaign.started_at = datetime.now()
        db.session.commit()
        
        # Trigger first invite immediately
        run_invite_campaign.apply_async((campaign_id,), countdown=0)
        return True, "Campaign started"

    @staticmethod
    def pause_campaign(campaign_id):
        campaign = InviteCampaign.query.get_or_404(campaign_id)
        campaign.status = 'paused'
        campaign.paused_at = datetime.utcnow()
        db.session.commit()
        return True

    @staticmethod
    def stop_campaign(campaign_id):
        campaign = InviteCampaign.query.get_or_404(campaign_id)
        campaign.status = 'stopped'
        campaign.completed_at = datetime.utcnow()
        db.session.commit()
        return True

    @staticmethod
    def assign_accounts(campaign_id, account_ids):
        count = 0
        for account_id in account_ids:
            existing = CampaignAccount.query.filter_by(
                campaign_id=campaign_id,
                account_id=int(account_id)
            ).first()
            
            if not existing:
                ca = CampaignAccount(
                    campaign_id=campaign_id,
                    account_id=int(account_id),
                    status="active"
                )
                db.session.add(ca)
                count += 1
        
        db.session.commit()
        return count

    @staticmethod
    def remove_account(campaign_id, account_id):
        ca = CampaignAccount.query.filter_by(
            campaign_id=campaign_id,
            account_id=account_id
        ).first()
        
        if ca:
            db.session.delete(ca)
            db.session.commit()
            return True
        return False
