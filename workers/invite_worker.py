from celery_app import celery
from app import db
from models.campaign import InviteCampaign, CampaignAccount, SourceUser, InviteLog
from models.account import Account
from utils.telethon_helper import send_invite
from utils.validators import is_working_hours
from utils.notifications import notify_campaign_completed, notify_account_flood_wait
import asyncio
import time
import random
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@celery.task(bind=True)
def run_invite_campaign(self, campaign_id):
    """Main invite campaign worker"""
    
    logger.info(f"Starting invite campaign {campaign_id}")
    
    campaign = InviteCampaign.query.get(campaign_id)
    if not campaign:
        logger.error(f"Campaign {campaign_id} not found")
        return
    
    accounts = [ca.account for ca in campaign.campaign_accounts.all() if ca.status == 'active']
    if not accounts:
        logger.error(f"No active accounts for campaign {campaign_id}")
        campaign.status = 'stopped'
        db.session.commit()
        return
    
    current_account_index = 0
    
    while campaign.status == 'active':
        # Refresh campaign status
        db.session.refresh(campaign)
        
        # Check working hours
        if not is_working_hours(campaign):
            logger.info(f"Campaign {campaign_id} outside working hours, sleeping...")
            time.sleep(60)
            continue
        
        # Round-robin account selection
        account = accounts[current_account_index]
        current_account_index = (current_account_index + 1) % len(accounts)
        
        # Check account daily limit
        if account.invites_sent_today >= 30:  # Max 30 invites per day per account
            logger.info(f"Account {account.id} reached daily limit")
            continue
        
        # Check cooldown
        if account.cooldown_until and datetime.utcnow() < account.cooldown_until:
            logger.info(f"Account {account.id} in cooldown")
            continue
        
        # Get next pending target (highest priority)
        target = SourceUser.query.filter_by(
            campaign_id=campaign_id,
            status='pending'
        ).order_by(SourceUser.priority_score.desc()).first()
        
        if not target:
            logger.info(f"Campaign {campaign_id} has no more targets")
            campaign.status = 'completed'
            campaign.completed_at = datetime.utcnow()
            db.session.commit()
            notify_campaign_completed(campaign_id, 'invite', {
                'invited': campaign.invited_count,
                'failed': campaign.failed_count
            })
            break
        
        # Send invite
        try:
            result = asyncio.run(send_invite(account.id, campaign.channel_id, target.user_id))
            
            # Log result
            log = InviteLog(
                campaign_id=campaign_id,
                account_id=account.id,
                target_user_id=target.user_id,
                status=result.get('error_type', 'success') if not result['success'] else 'success',
                details=result.get('error')
            )
            db.session.add(log)
            
            # Update target and stats
            if result['success']:
                target.status = 'invited'
                target.invited_at = datetime.utcnow()
                target.invited_by_account_id = account.id
                campaign.invited_count += 1
                account.invites_sent_today += 1
                logger.info(f"Invited user {target.user_id} successfully")
            else:
                target.status = 'failed'
                target.error_message = result['error']
                campaign.failed_count += 1
                logger.warning(f"Failed to invite user {target.user_id}: {result['error']}")
                
                # Handle FloodWait
                if result.get('error_type') == 'flood_wait':
                    seconds = result.get('seconds', 3600)
                    account.cooldown_until = datetime.utcnow() + timedelta(seconds=seconds)
                    account.status = 'cooldown'
                    notify_account_flood_wait(account.id, seconds)
                    logger.warning(f"Account {account.id} FloodWait: {seconds}s")
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error in invite campaign {campaign_id}: {str(e)}")
            target.status = 'failed'
            target.error_message = str(e)
            campaign.failed_count += 1
            db.session.commit()
        
        # Apply delay
        delay = random.randint(campaign.delay_min, campaign.delay_max)
        logger.debug(f"Sleeping {delay}s...")
        time.sleep(delay)
        
        # Burst pause
        if account.invites_sent_today % campaign.burst_limit == 0 and account.invites_sent_today > 0:
            pause_seconds = campaign.burst_pause_minutes * 60
            logger.info(f"Burst limit reached, pausing {pause_seconds}s")
            time.sleep(pause_seconds)
    
    logger.info(f"Invite campaign {campaign_id} finished")
