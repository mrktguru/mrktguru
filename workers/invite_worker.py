"""
Invite Campaign Worker - отправка приглашений
"""
from celery_app import celery
from database import db
from models.campaign import InviteCampaign, CampaignAccount, SourceUser, InviteLog
from models.account import Account
from utils.telethon_helper import send_invite
from datetime import datetime, time as dt_time
import time
import random
import asyncio

# Import Flask app for context
# Flask app context handled by database.py


@celery.task(bind=True)
def run_invite_campaign(self, campaign_id):
    """
    Main invite campaign worker
    
    Args:
        campaign_id: ID of campaign to run
    """
    campaign = InviteCampaign.query.get(campaign_id)
    # Use database session directly
    if not campaign:
        return {"error": "Campaign not found"}
        
    # Get assigned accounts
    campaign_accounts = CampaignAccount.query.filter_by(
        campaign_id=campaign_id,
        status="active"
    ).all()
        
    if not campaign_accounts:
        return {"error": "No active accounts assigned"}
        
    accounts = [ca.account for ca in campaign_accounts]
    current_account_index = 0
        
    print(f"Starting invite campaign {campaign_id} with {len(accounts)} accounts")
        
    # Main loop
    while campaign.status == "active":
        # Refresh campaign status
        db.session.refresh(campaign)
            
        # Check working hours
        if not is_working_hours(campaign):
            print("Outside working hours, waiting...")
            time.sleep(60)
            continue
            
        # Round-robin account selection
        account = accounts[current_account_index]
        current_account_index = (current_account_index + 1) % len(accounts)
            
        # Check account daily limit
        if account.invites_sent_today >= get_daily_limit(account, campaign):
            print(f"Account {account.phone} reached daily limit")
            continue
            
        # Get next target (highest priority score)
        target = SourceUser.query.filter_by(
            campaign_id=campaign_id,
            status="pending"
        ).order_by(SourceUser.priority_score.desc()).first()
            
        if not target:
            print("No more targets, campaign completed")
            campaign.status = "completed"
            db.session.commit()
            break
            
        # Send invite
        print(f"Inviting user {target.username} using account {account.phone}")
        result = asyncio.run(send_invite(
            account.id,
            campaign.channel.username,
            target.user_id
        ))
            
        # Log result
        log_invite_result(campaign_id, account.id, target, result)
            
        # Update stats
        if result["status"] == "success":
            target.status = "invited"
            target.invited_at = datetime.utcnow()
            target.invited_by_account_id = account.id
            campaign.invited_count += 1
            account.invites_sent_today += 1
                
        elif result["status"] == "flood_wait":
            # Put account on cooldown
            account.status = "cooldown"
            print(f"Account {account.phone} got FloodWait, cooling down")
                
        else:
            target.status = "failed"
            target.error_message = result.get("error")
            campaign.failed_count += 1
            
        db.session.commit()
            
        # Apply delay
        delay = random.randint(campaign.delay_min, campaign.delay_max)
        print(f"Waiting {delay} seconds...")
        time.sleep(delay)
            
        # Check burst limit
        if account.invites_sent_today % campaign.burst_limit == 0:
            burst_pause = campaign.burst_pause_minutes * 60
            print(f"Burst limit reached, pausing {campaign.burst_pause_minutes} minutes")
            time.sleep(burst_pause)
        
    return {
        "status": "completed",
        "invited": campaign.invited_count,
        "failed": campaign.failed_count
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
        # Handle overnight range
        return now >= start or now <= end


def get_daily_limit(account, campaign):
    """Get daily invite limit for account"""
    # Base limit from campaign strategy
    if campaign.strategy == "safe":
        return random.randint(campaign.invites_per_hour_min * 8, campaign.invites_per_hour_max * 8)
    elif campaign.strategy == "normal":
        return random.randint(campaign.invites_per_hour_min * 12, campaign.invites_per_hour_max * 12)
    elif campaign.strategy == "aggressive":
        return random.randint(campaign.invites_per_hour_min * 16, campaign.invites_per_hour_max * 16)
    else:
        return 100  # Default


def log_invite_result(campaign_id, account_id, target, result):
    """Log invite operation"""
    log = InviteLog(
        campaign_id=campaign_id,
        account_id=account_id,
        target_user_id=target.user_id,
        status=result["status"],
        details=result.get("error")
    )
    db.session.add(log)
    db.session.commit()


@celery.task
def reset_daily_counters():
    """
    Reset daily invite counters for all accounts
    Run daily at midnight
    """
    accounts = Account.query.all()
    for account in accounts:
        account.invites_sent_today = 0
        account.messages_sent_today = 0
    
    db.session.commit()
    return {"reset": len(accounts)}
