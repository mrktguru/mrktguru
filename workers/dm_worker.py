from celery_app import celery
from app import db
from models.dm_campaign import DMCampaign, DMCampaignAccount, DMTarget, DMMessage
from models.account import Account
from utils.telethon_helper import send_message
from utils.validators import is_working_hours
from utils.notifications import notify_dm_campaign_limit_reached
import asyncio
import time
import random
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def personalize_message(template, target):
    """Replace variables in message template"""
    message = template
    
    # Basic variables
    message = message.replace('{{first_name}}', target.first_name or target.username or 'friend')
    message = message.replace('{{last_name}}', target.last_name or '')
    message = message.replace('{{username}}', target.username or '')
    
    # Custom data from CSV
    if target.custom_data:
        for key, value in target.custom_data.items():
            message = message.replace(f'{{{{{key}}}}}', str(value))
    
    return message


@celery.task(bind=True)
def run_dm_campaign(self, campaign_id):
    """Main DM campaign worker"""
    
    logger.info(f"Starting DM campaign {campaign_id}")
    
    campaign = DMCampaign.query.get(campaign_id)
    if not campaign:
        logger.error(f"DM Campaign {campaign_id} not found")
        return
    
    accounts = [ca.account for ca in campaign.dm_campaign_accounts.all() if ca.status == 'active']
    if not accounts:
        logger.error(f"No active accounts for DM campaign {campaign_id}")
        campaign.status = 'stopped'
        db.session.commit()
        return
    
    current_account_index = 0
    
    while campaign.status == 'active':
        # Refresh campaign
        db.session.refresh(campaign)
        
        # Check working hours
        if not is_working_hours(campaign):
            logger.info(f"DM Campaign {campaign_id} outside working hours")
            time.sleep(60)
            continue
        
        # Round-robin account selection
        account = accounts[current_account_index]
        current_account_index = (current_account_index + 1) % len(accounts)
        
        # Check account limit
        campaign_account = DMCampaignAccount.query.filter_by(
            campaign_id=campaign_id,
            account_id=account.id
        ).first()
        
        if campaign_account.messages_sent >= campaign.messages_per_account_limit:
            campaign_account.status = 'limit_reached'
            db.session.commit()
            
            # Check if all accounts reached limit
            all_at_limit = all(
                ca.status == 'limit_reached' 
                for ca in campaign.dm_campaign_accounts.all()
            )
            
            if all_at_limit:
                campaign.status = 'limit_reached'
                db.session.commit()
                notify_dm_campaign_limit_reached(campaign_id)
                logger.info(f"DM Campaign {campaign_id} - all accounts reached limit")
                break
            
            continue
        
        # Get next target
        target = DMTarget.query.filter_by(
            campaign_id=campaign_id,
            status='new'
        ).first()
        
        if not target:
            campaign.status = 'completed'
            campaign.completed_at = datetime.utcnow()
            db.session.commit()
            logger.info(f"DM Campaign {campaign_id} completed")
            break
        
        # Personalize message
        message_text = personalize_message(campaign.message_text, target)
        
        # Send DM
        try:
            result = asyncio.run(send_message(
                account.id,
                target.username,
                message_text,
                campaign.media_file_path
            ))
            
            if result['success']:
                target.status = 'sent'
                target.sent_at = datetime.utcnow()
                target.sent_by_account_id = account.id
                campaign.sent_count += 1
                campaign_account.messages_sent += 1
                
                # Save message to history
                dm_msg = DMMessage(
                    campaign_id=campaign_id,
                    target_id=target.id,
                    account_id=account.id,
                    direction='outgoing',
                    message_text=message_text,
                    has_media=(campaign.media_type != 'none'),
                    media_type=campaign.media_type,
                    telegram_message_id=result['message_id']
                )
                db.session.add(dm_msg)
                
                logger.info(f"Sent DM to {target.username}")
            else:
                target.status = 'error'
                target.error_message = result['error']
                campaign.error_count += 1
                logger.warning(f"Failed to send DM to {target.username}: {result['error']}")
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error in DM campaign {campaign_id}: {str(e)}")
            target.status = 'error'
            target.error_message = str(e)
            campaign.error_count += 1
            db.session.commit()
        
        # Apply delay
        delay = random.randint(campaign.delay_min, campaign.delay_max)
        logger.debug(f"Sleeping {delay}s...")
        time.sleep(delay)
    
    logger.info(f"DM campaign {campaign_id} finished")
