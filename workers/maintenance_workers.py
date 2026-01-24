"""
Maintenance Workers - фоновые задачи обслуживания
"""
from celery_app import celery
from database import db
from models.proxy import Proxy
from models.account import Account
from utils.telethon_helper import verify_session
from datetime import datetime
import asyncio
import requests


@celery.task
def auto_rotate_mobile_proxies():
    """
    Automatic rotation of mobile proxies (API-based only)
    Run every 15 minutes
    Auto-rotating proxies (DataImpulse) are skipped - they rotate on every request
    """
    from app import app
    
    with app.app_context():
        # Only get API-based mobile proxies
        proxies = Proxy.query.filter_by(
            is_mobile=True,
            rotation_type="api",
            status="active"
        ).all()
        
        # Count auto-rotating proxies (for info)
        auto_proxies = Proxy.query.filter_by(
            is_mobile=True,
            rotation_type="auto",
            status="active"
        ).count()
        
        rotated = 0
        for proxy in proxies:
            if not proxy.rotation_url:
                continue
            
            # Check if rotation interval passed
            if proxy.last_rotation:
                elapsed = (datetime.utcnow() - proxy.last_rotation).total_seconds()
                if elapsed < proxy.rotation_interval:
                    continue
            
            # Rotate proxy via API
            try:
                response = requests.get(proxy.rotation_url, timeout=10)
                if response.status_code == 200:
                    proxy.last_rotation = datetime.utcnow()
                    rotated += 1
                    print(f"✅ Rotated API proxy {proxy.host}:{proxy.port}")
            except Exception as e:
                print(f"❌ Error rotating proxy {proxy.id}: {e}")
        
        db.session.commit()
        
        if auto_proxies > 0:
            print(f"ℹ️  {auto_proxies} auto-rotating proxies (no rotation needed)")
        
        return {"rotated": rotated, "api_proxies": len(proxies), "auto_proxies": auto_proxies}


@celery.task
def check_account_health():
    """
    Check health of all accounts
    Run every hour
    """
    from app import app
    
    with app.app_context():
        accounts = Account.query.filter_by(status="active").all()
        
        healthy = 0
        unhealthy = 0
        
        for account in accounts:
            try:
                # Use a new loop or the one from app context if available? 
                # verify_session is async. We are in a sync celery task.
                # asyncio.run() creates a new loop.
                result = asyncio.run(verify_session(account.id))
                
                if result["success"]:
                    account.health_score = min(account.health_score + 5, 100)
                    healthy += 1
                else:
                    account.health_score = max(account.health_score - 10, 0)
                    unhealthy += 1
                    
                    if account.health_score < 30:
                        account.status = "unhealthy"
                        
            except Exception as e:
                print(f"Error checking account {account.id}: {e}")
                account.health_score = max(account.health_score - 20, 0)
                unhealthy += 1
        
        db.session.commit()
        
        return {
            "healthy": healthy,
            "unhealthy": unhealthy,
            "total": len(accounts)
        }


@celery.task
def reset_cooldown_accounts():
    """
    Reset accounts from cooldown status
    Run every 30 minutes
    """
    from app import app
    from datetime import timedelta
    
    with app.app_context():
        # Reset accounts that were in cooldown for more than 1 hour
        threshold = datetime.utcnow() - timedelta(hours=1)
        
        accounts = Account.query.filter_by(status="cooldown").all()
        
        reset = 0
        for account in accounts:
            # Simple reset after 1 hour
            # In production should check last_activity timestamp
            account.status = "active"
            reset += 1
        
        db.session.commit()
        
        return {"reset": reset}


@celery.task
def aggregate_daily_stats():
    """
    Aggregate daily statistics
    Run daily at midnight
    """
    from app import app
    from models.campaign import InviteCampaign, InviteLog
    from models.dm_campaign import DMCampaign
    from sqlalchemy import func
    
    with app.app_context():
        today = datetime.utcnow().date()
        
        # Invite campaigns stats
        invite_stats = db.session.query(
            func.count(InviteLog.id).label("total_invites"),
            func.sum(db.case((InviteLog.status == "success", 1), else_=0)).label("successful")
        ).filter(
            func.date(InviteLog.timestamp) == today
        ).first()
        
        # DM campaigns stats  
        dm_campaigns = DMCampaign.query.all()
        dm_sent_today = sum(c.sent_count for c in dm_campaigns)
        
        print(f"Daily stats: {invite_stats.total_invites} invites, {dm_sent_today} DMs")
        
        return {
            "date": str(today),
            "invites": invite_stats.total_invites or 0,
            "invite_success": invite_stats.successful or 0,
            "dms_sent": dm_sent_today
        }


@celery.task
def cleanup_old_logs():
    """
    Clean up old logs
    Run weekly
    """
    from app import app
    from datetime import timedelta
    from models.campaign import InviteLog
    
    with app.app_context():
        # Delete logs older than 90 days
        threshold = datetime.utcnow() - timedelta(days=90)
        
        deleted = InviteLog.query.filter(
            InviteLog.timestamp < threshold
        ).delete()
        
        db.session.commit()
        
        return {"deleted": deleted}


@celery.task
def test_all_proxies():
    """
    Test all proxies
    Run every 6 hours
    """
    from app import app
    
    with app.app_context():
        proxies = Proxy.query.filter_by(status="active").all()
        
        working = 0
        failed = 0
        
        for proxy in proxies:
            try:
                # Test proxy with simple HTTP request
                proxy_url = f"{proxy.type}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
                
                response = requests.get(
                    "https://api.ipify.org?format=json",
                    proxies={"http": proxy_url, "https": proxy_url},
                    timeout=10
                )
                
                if response.status_code == 200:
                    proxy.current_ip = response.json()["ip"]
                    working += 1
                else:
                    proxy.status = "error"
                    failed += 1
                    
            except Exception as e:
                proxy.status = "error"
                failed += 1
                print(f"Proxy {proxy.id} failed: {e}")
        
        db.session.commit()
        
        return {
            "working": working,
            "failed": failed,
            "total": len(proxies)
        }
