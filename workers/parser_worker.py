"""
Parser Worker - background парсинг пользователей
"""
from celery_app import celery
from database import db
from models.parser import ParseJob, ParsedUserLibrary
from models.account import Account
from utils.telethon_helper import parse_channel_members
from datetime import datetime
import asyncio


@celery.task(bind=True)
def run_parse_job(self, job_id):
    """
    Run parse job in background
    
    Args:
        job_id: ParseJob ID
    """
    job = ParseJob.query.get(job_id)
    if not job:
        return {"error": "Job not found"}
    
    # Update status
    job.status = "running"
    job.started_at = datetime.utcnow()
    db.session.commit()
    
    try:
        if job.job_type == "single" or job.job_type == "multi_channel":
            result = asyncio.run(parse_multi_channel(job))
        elif job.job_type == "by_activity":
            result = asyncio.run(parse_by_activity(job))
        elif job.job_type == "by_keyword":
            result = asyncio.run(parse_by_keyword(job))
        else:
            raise ValueError(f"Unknown job type: {job.job_type}")
        
        # Update job
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.total_parsed = result["total_parsed"]
        job.total_valid = result["total_valid"]
        db.session.commit()
        
        return result
        
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()
        db.session.commit()
        
        return {"error": str(e)}


async def parse_multi_channel(job):
    """Parse from multiple channels"""
    collection_name = job.filters.get("collection_name", "Default")
    
    all_users = {}  # user_id -> user_data
    total_parsed = 0
    
    for channel in job.source_channels:
        try:
            users = await parse_channel_members(
                job.account_id,
                channel,
                limit=10000,
                filters=job.filters
            )
            
            total_parsed += len(users)
            
            # Deduplicate
            for user in users:
                if user["user_id"] not in all_users:
                    all_users[user["user_id"]] = user
                    all_users[user["user_id"]]["sources"] = [channel]
                else:
                    all_users[user["user_id"]]["sources"].append(channel)
                    
        except Exception as e:
            print(f"Error parsing {channel}: {e}")
    
    # Save to library
    saved = 0
    for user_data in all_users.values():
        # Check if already exists
        existing = ParsedUserLibrary.query.filter_by(
            user_id=user_data["user_id"]
        ).first()
        
        if not existing:
            parsed_user = ParsedUserLibrary(
                collection_name=collection_name,
                user_id=user_data["user_id"],
                username=user_data["username"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                source_channel=", ".join(user_data["sources"]),
                has_profile_photo=user_data["has_photo"],
                is_premium=user_data["is_premium"],
                extra_data={"sources": user_data["sources"]}
            )
            db.session.add(parsed_user)
            saved += 1
    
    db.session.commit()
    
    return {
        "total_parsed": total_parsed,
        "total_valid": saved
    }


async def parse_by_activity(job):
    """Parse users by activity"""
    # TODO: Implement activity-based parsing
    # This requires fetching messages and counting activity
    return {
        "total_parsed": 0,
        "total_valid": 0
    }


async def parse_by_keyword(job):
    """Parse users by keyword"""
    # TODO: Implement keyword-based parsing
    # This requires searching messages and bios
    return {
        "total_parsed": 0,
        "total_valid": 0
    }


@celery.task
def cleanup_old_parse_jobs():
    """
    Clean up old completed/failed parse jobs
    Run weekly
    """
    from datetime import timedelta
    
    threshold = datetime.utcnow() - timedelta(days=30)
    
    deleted = ParseJob.query.filter(
        ParseJob.status.in_(["completed", "failed"]),
        ParseJob.completed_at < threshold
    ).delete()
    
    db.session.commit()
    
    return {"deleted": deleted}


@celery.task
def parse_users_for_campaign(campaign_id, source_channel, limit=1000, filters=None):
    """
    Task to parse users from a channel and add them to a campaign.
    """
    from models.campaign import InviteCampaign, SourceUser
    
    # We import here to avoid circular dependencies
    campaign = InviteCampaign.query.get(campaign_id)
    if not campaign:
        return {"status": "error", "error": f"Campaign {campaign_id} not found"}
        
    # Find an account to use for parsing
    account = Account.query.filter_by(status='active').first()
    if not account:
        return {"status": "error", "error": "No active account found for parsing"}
        
    try:
        # Use existing utility
        users = asyncio.run(parse_channel_members(
            account.id, 
            source_channel, 
            filters=filters
        ))
        
        # Process and save
        count = 0
        for u in users:
            if not u.get('username'): continue
            
            existing = SourceUser.query.filter_by(
                campaign_id=campaign_id,
                username=u['username']
            ).first()
            
            if not existing:
                source_user = SourceUser(
                    campaign_id=campaign_id,
                    username=u['username'],
                    user_id=u['user_id'],
                    first_name=u['first_name'],
                    last_name=u['last_name'],
                    source=f"parse:{source_channel}",
                    status="pending"
                )
                db.session.add(source_user)
                count += 1
        
        db.session.commit()
        return {"status": "success", "parsed": len(users), "added": count}
        
    except Exception as e:
        return {"status": "error", "error": str(e)}
