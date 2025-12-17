from celery_app import celery
from app import db
from models.proxy import Proxy
from models.account import Account
from models.analytics import CampaignStats
from utils.proxy_helper import rotate_mobile_proxy
from utils.telethon_helper import verify_session
from datetime import datetime, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)


@celery.task
def auto_rotate_mobile_proxies():
    """Automatically rotate mobile proxies based on interval"""
    
    logger.info("Auto-rotating mobile proxies")
    
    proxies = Proxy.query.filter_by(
        is_mobile=True,
        status='active'
    ).all()
    
    for proxy in proxies:
        try:
            # Check if rotation interval passed
            if proxy.last_rotation:
                elapsed = (datetime.utcnow() - proxy.last_rotation).total_seconds()
                if elapsed < proxy.rotation_interval:
                    continue
            
            logger.info(f"Rotating proxy {proxy.id}")
            result = rotate_mobile_proxy(proxy)
            
            if result['success']:
                logger.info(f"Proxy {proxy.id} rotated. New IP: {result['new_ip']}")
            else:
                logger.warning(f"Failed to rotate proxy {proxy.id}: {result['error']}")
                
        except Exception as e:
            logger.error(f"Error rotating proxy {proxy.id}: {str(e)}")


@celery.task
def check_account_health():
    """Check health of all accounts"""
    
    logger.info("Checking account health")
    
    accounts = Account.query.filter_by(status='active').all()
    
    for account in accounts:
        try:
            result = asyncio.run(verify_session(account.id))
            
            if result['success']:
                account.health_score = min(account.health_score + 5, 100)
                logger.info(f"Account {account.id} is healthy")
            else:
                account.health_score = max(account.health_score - 20, 0)
                if account.health_score < 30:
                    account.status = 'invalid'
                logger.warning(f"Account {account.id} health check failed: {result['error']}")
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error checking account {account.id}: {str(e)}")


@celery.task
def reset_daily_counters():
    """Reset daily counters for all accounts"""
    
    logger.info("Resetting daily counters")
    
    Account.query.update({
        Account.messages_sent_today: 0,
        Account.invites_sent_today: 0
    })
    db.session.commit()


@celery.task
def aggregate_daily_stats():
    """Aggregate daily statistics"""
    
    logger.info("Aggregating daily stats")
    
    from models.campaign import InviteCampaign, InviteLog
    from models.dm_campaign import DMCampaign, DMTarget
    from sqlalchemy import func
    
    yesterday = (datetime.utcnow() - timedelta(days=1)).date()
    
    # Aggregate invite campaigns
    invite_stats = db.session.query(
        InviteLog.campaign_id,
        func.count(InviteLog.id).label('total'),
        func.sum(func.cast(InviteLog.status == 'success', db.Integer)).label('success')
    ).filter(
        func.date(InviteLog.timestamp) == yesterday
    ).group_by(InviteLog.campaign_id).all()
    
    for stat in invite_stats:
        success_rate = (stat.success / stat.total * 100) if stat.total > 0 else 0
        
        campaign_stat = CampaignStats(
            campaign_id=stat.campaign_id,
            campaign_type='invite',
            date=yesterday,
            sent_count=stat.total,
            error_count=stat.total - stat.success,
            success_rate=success_rate
        )
        db.session.add(campaign_stat)
    
    db.session.commit()
    logger.info("Daily stats aggregated")


@celery.task
def cleanup_old_logs():
    """Cleanup logs older than 90 days"""
    
    logger.info("Cleaning up old logs")
    
    from models.campaign import InviteLog
    
    cutoff_date = datetime.utcnow() - timedelta(days=90)
    
    deleted = InviteLog.query.filter(
        InviteLog.timestamp < cutoff_date
    ).delete()
    
    db.session.commit()
    logger.info(f"Deleted {deleted} old log entries")


@celery.task
def warmup_account_activity():
    """Simulate human-like activity for warming up accounts"""
    
    logger.info("Running warmup activity")
    
    accounts = Account.query.filter_by(status='warming_up').all()
    
    for account in accounts:
        try:
            # Placeholder for warmup activities:
            # - Read messages from subscribed channels
            # - Send reactions
            # - Update last_activity
            
            account.last_activity = datetime.utcnow()
            account.warm_up_days_completed = min(account.warm_up_days_completed + 1, 7)
            
            if account.warm_up_days_completed >= 7:
                account.status = 'active'
            
            db.session.commit()
            logger.info(f"Account {account.id} warmup activity completed")
            
        except Exception as e:
            logger.error(f"Error in warmup activity for account {account.id}: {str(e)}")
