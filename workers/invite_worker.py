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


@celery.task(bind=True)
def run_invite_campaign(self, campaign_id):
    """
    Invite one user and schedule next invite
    
    Args:
        campaign_id: ID of campaign to run
    """
    from app import app as flask_app
    
    with flask_app.app_context():
        campaign = InviteCampaign.query.get(campaign_id)
        if not campaign or campaign.status != "active":
            return {"status": "stopped", "message": "Campaign not active"}
            
        # Check working hours
        if not is_working_hours(campaign):
            print("Outside working hours, retry in 60 seconds")
            # Retry after 60 seconds
            run_invite_campaign.apply_async((campaign_id,), countdown=60)
            return {"status": "waiting", "message": "Outside working hours"}
            
        # Get assigned accounts
        campaign_accounts = CampaignAccount.query.filter_by(
            campaign_id=campaign_id,
            status="active"
        ).all()
            
        if not campaign_accounts:
            return {"error": "No active accounts assigned"}
            
        accounts = [ca.account for ca in campaign_accounts]
        
        # Get account for this invite (round-robin based on invited_count)
        account_index = campaign.invited_count % len(accounts)
        account = accounts[account_index]
                
        # Check account daily limit
        if account.invites_sent_today >= get_daily_limit(account, campaign):
            print(f"Account {account.phone} reached daily limit")
            # Try next account or wait
            if len(accounts) > 1:
                # Force next account
                campaign.invited_count += 1
                db.session.commit()
                run_invite_campaign.apply_async((campaign_id,), countdown=5)
            else:
                run_invite_campaign.apply_async((campaign_id,), countdown=3600)
            return {"status": "limit_reached"}
                
        # Get next pending target
        target = SourceUser.query.filter_by(
            campaign_id=campaign_id,
            status="pending"
        ).order_by(SourceUser.priority_score.desc()).first()
                
        if not target:
            print("No more targets, campaign completed")
            campaign.status = "completed"
            db.session.commit()
            return {"status": "completed"}
                
        # Send invite
        print(f"[Campaign {campaign_id}] Inviting {target.username} using {account.phone}")
        # Extract username from channel URL
        channel_username = campaign.channel.username
        if "t.me/" in channel_username:
            channel_username = channel_username.split("t.me/")[-1]
        
        print(f"DEBUG: channel_username = {channel_username}")
        result = asyncio.run(send_invite(
            account.id,
            channel_username,
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
            print(f"✅ Successfully invited {target.username}")
                    
        elif result["status"] == "flood_wait":
            # Put account on cooldown
            account.status = "cooldown"
            print(f"⚠️  Account {account.phone} got FloodWait, cooling down")
            # Mark target as failed for now
            target.status = "failed"
            target.error_message = "FloodWait"
            campaign.failed_count += 1
                    
        else:
            target.status = "failed"
            target.error_message = result.get("error")
            campaign.failed_count += 1
            print(f"❌ Failed to invite {target.username}: {result.get('error')}")
                
        db.session.commit()
                
        # Calculate delay for next invite
        delay = random.randint(campaign.delay_min, campaign.delay_max)
        
        # Check burst limit
        if (campaign.invited_count % campaign.burst_limit) == 0 and campaign.invited_count > 0:
            burst_pause = campaign.burst_pause_minutes * 60
            print(f"💤 Burst limit reached, pausing {campaign.burst_pause_minutes} minutes")
            delay = burst_pause
        
        print(f"⏱️  Next invite in {delay} seconds...")
        
        # Schedule next invite
        run_invite_campaign.apply_async((campaign_id,), countdown=delay)
            
        return {
            "status": "success",
            "invited": target.username,
            "next_in": delay
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
    from app import app as flask_app
    
    with flask_app.app_context():
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
    from app import app as flask_app
    
    with flask_app.app_context():
        accounts = Account.query.all()
        for account in accounts:
            account.invites_sent_today = 0
            account.messages_sent_today = 0
        
        db.session.commit()
        return {"reset": len(accounts)}
