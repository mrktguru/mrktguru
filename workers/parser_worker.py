from celery_app import celery
from app import db
from models.parser import ParsedUserLibrary, ParseJob
from models.campaign import SourceUser
from utils.telethon_helper import parse_channel_members
from models.blacklist import GlobalBlacklist
import asyncio
import logging

logger = logging.getLogger(__name__)


@celery.task
def parse_users_for_campaign(campaign_id, channel_username):
    """Parse users from channel for invite campaign"""
    from models.campaign import InviteCampaign
    
    logger.info(f"Parsing users from {channel_username} for campaign {campaign_id}")
    
    campaign = InviteCampaign.query.get(campaign_id)
    if not campaign:
        return
    
    # Get first account from campaign to use for parsing
    if not campaign.campaign_accounts.count():
        logger.error(f"No accounts assigned to campaign {campaign_id}")
        return
    
    account = campaign.campaign_accounts.first().account
    
    # Parse members
    result = asyncio.run(parse_channel_members(account.id, channel_username))
    
    if not result['success']:
        logger.error(f"Failed to parse {channel_username}: {result['error']}")
        return
    
    users = result['users']
    logger.info(f"Parsed {len(users)} users from {channel_username}")
    
    # Filter and add to campaign
    added = 0
    for user_data in users:
        # Skip bots
        if user_data['is_bot']:
            continue
        
        # Skip blacklisted
        if GlobalBlacklist.query.filter_by(user_id=user_data['user_id']).first():
            continue
        
        # Check if already in campaign
        existing = SourceUser.query.filter_by(
            campaign_id=campaign_id,
            user_id=user_data['user_id']
        ).first()
        
        if existing:
            continue
        
        # Calculate priority score
        score = 50
        if user_data['has_photo']:
            score += 20
        if user_data['is_premium']:
            score += 15
        if user_data['username']:
            score += 10
        
        # Add to campaign
        source_user = SourceUser(
            campaign_id=campaign_id,
            user_id=user_data['user_id'],
            username=user_data['username'],
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            source=channel_username,
            priority_score=min(score, 100)
        )
        db.session.add(source_user)
        added += 1
    
    # Update campaign total
    campaign.total_targets = SourceUser.query.filter_by(campaign_id=campaign_id).count()
    db.session.commit()
    
    logger.info(f"Added {added} users to campaign {campaign_id}")


@celery.task
def execute_parse_job(job_id):
    """Execute parsing job"""
    
    job = ParseJob.query.get(job_id)
    if not job:
        return
    
    job.status = 'running'
    from datetime import datetime
    job.started_at = datetime.utcnow()
    db.session.commit()
    
    try:
        collection_name = job.filters.get('collection_name', 'Default')
        
        for channel_username in job.source_channels:
            logger.info(f"Parsing {channel_username} for job {job_id}")
            
            result = asyncio.run(parse_channel_members(job.account_id, channel_username))
            
            if not result['success']:
                logger.error(f"Failed to parse {channel_username}: {result['error']}")
                continue
            
            users = result['users']
            job.total_parsed += len(users)
            
            # Add to library
            for user_data in users:
                # Skip bots
                if user_data['is_bot']:
                    continue
                
                # Skip blacklisted
                if GlobalBlacklist.query.filter_by(user_id=user_data['user_id']).first():
                    continue
                
                # Check if already in library
                existing = ParsedUserLibrary.query.filter_by(
                    collection_name=collection_name,
                    user_id=user_data['user_id']
                ).first()
                
                if existing:
                    continue
                
                # Add to library
                parsed_user = ParsedUserLibrary(
                    collection_name=collection_name,
                    user_id=user_data['user_id'],
                    username=user_data['username'],
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                    source_channel=channel_username,
                    has_profile_photo=user_data['has_photo'],
                    is_premium=user_data['is_premium'],
                    metadata=user_data
                )
                db.session.add(parsed_user)
                job.total_valid += 1
        
        job.status = 'completed'
        job.completed_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Parse job {job_id} completed: {job.total_valid} users")
        
    except Exception as e:
        logger.error(f"Error in parse job {job_id}: {str(e)}")
        job.status = 'failed'
        job.error_message = str(e)
        db.session.commit()
