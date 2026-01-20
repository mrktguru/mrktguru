"""
DM Campaign Worker - отправка Direct Messages
"""
from celery_app import celery
from database import db
from models.dm_campaign import DMCampaign, DMCampaignAccount, DMTarget
from models.account import Account
from utils.telethon_helper import send_dm
from datetime import datetime
import time
import random
import asyncio


@celery.task(bind=True)
def run_dm_campaign(self, campaign_id):
    """
    Main DM campaign worker
    
    Args:
        campaign_id: ID of campaign to run
    """
    from app import app
    
    with app.app_context():
        campaign = DMCampaign.query.get(campaign_id)
        if not campaign:
            return {"error": "Campaign not found"}
        
        # Get assigned accounts
        campaign_accounts = DMCampaignAccount.query.filter_by(
            campaign_id=campaign_id
        ).filter(DMCampaignAccount.status != "limit_reached").all()
        
        if not campaign_accounts:
            return {"error": "No active accounts"}
        
        accounts = [ca.account for ca in campaign_accounts]
        current_account_index = 0
        
        print(f"Starting DM campaign {campaign_id} with {len(accounts)} accounts")
        
        # Main loop
        while campaign.status == "active":
            # Refresh campaign
            db.session.refresh(campaign)
            
            # Check working hours
            if not is_working_hours(campaign):
                print("Outside working hours, waiting...")
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
                campaign_account.status = "limit_reached"
                db.session.commit()
                
                # Check if all accounts reached limit
                active_accounts = DMCampaignAccount.query.filter_by(
                    campaign_id=campaign_id
                ).filter(DMCampaignAccount.status != "limit_reached").count()
                
                if active_accounts == 0:
                    print("All accounts reached limit")
                    campaign.status = "limit_reached"
                    db.session.commit()
                    break
                
                continue
            
            # Get next target
            target = DMTarget.query.filter_by(
                campaign_id=campaign_id,
                status="new"
            ).first()
            
            if not target:
                print("No more targets, campaign completed")
                campaign.status = "completed"
                db.session.commit()
                break
            
            # Personalize message
            message_text = personalize_message(campaign.message_text, target)
            
            # Send DM
            print(f"Sending DM to @{target.username} using account {account.phone}")
            result = asyncio.run(send_dm(
                account.id,
                target.username,
                message_text,
                campaign.media_file_path
            ))
            
            # Update status
            if result.get("success"):
                target.status = "sent"
                target.sent_at = datetime.utcnow()
                target.sent_by_account_id = account.id
                campaign.sent_count += 1
                campaign_account.messages_sent += 1
                
                print(f"✅ DM sent successfully to @{target.username}")
                
            else:
                # Check if it's a flood wait error
                error_msg = result.get("error", "")
                if "FloodWait" in str(error_msg) or "flood" in str(error_msg).lower():
                    account.status = "cooldown"
                    print(f"❌ Account {account.phone} got FloodWait")
                
                target.status = "error"
                target.error_message = error_msg
                campaign.error_count += 1
                
                print(f"❌ Error sending to @{target.username}: {error_msg}")
            
            db.session.commit()
            
            # Apply delay
            delay = random.randint(campaign.delay_min, campaign.delay_max)
            print(f"Waiting {delay} seconds...")
            time.sleep(delay)
        
        return {
            "status": "completed",
            "sent": campaign.sent_count,
            "errors": campaign.error_count
        }


def is_working_hours(campaign):
    """Check if current time is within working hours"""
    if not campaign.working_hours_start or not campaign.working_hours_end:
        return True
    
    now = datetime.now().time()
    start = campaign.working_hours_start
    end = campaign.working_hours_end
    
    if start <= end:
        return start <= now <= end
    else:
        return now >= start or now <= end


def personalize_message(template, target):
    """
    Replace variables in message template
    
    Args:
        template: Message template
        target: DMTarget object
        
    Returns:
        Personalized message
    """
    message = template
    
    # Replace variables
    message = message.replace("{{first_name}}", target.first_name or "friend")
    message = message.replace("{{last_name}}", target.last_name or "")
    message = message.replace("{{username}}", target.username or "")
    
    # Custom fields from CSV
    if target.custom_data:
        for key, value in target.custom_data.items():
            message = message.replace(f"{{{{{key}}}}}", str(value))
    
    return message
