"""
Warmup Worker - background tasks for account warmup and ongoing activity simulation
"""
from celery_app import celery
from database import db
from datetime import datetime, timedelta
import asyncio
import random
import logging

logger = logging.getLogger(__name__)

# Conversation templates for warmup
CONVERSATION_STARTERS = [
    "Привет! Как дела?",
    "Привет! Что нового?",
    "Видел новости сегодня?",
    "Как выходные прошли?",
    "Что думаешь о погоде?",
]

CONVERSATION_REPLIES = [
    "Привет! Все отлично, у тебя как?",
    "Норм, ничего особенного",
    "Да, интересно было",
    "Спасибо, посмотрю",
    "Согласен!",
    "Неплохо, спасибо",
]

# Reaction emojis for warmup
WARMUP_REACTIONS = ["👍", "❤️", "🔥", "😂", "👏", "🤔"]


@celery.task(bind=True)
def run_warmup_activity(self, account_id):
    """
    Run warmup activity for a single account
    
    This task performs one "session" of warmup activity:
    - Reading posts from assigned channels
    - Occasionally reacting to posts
    - Potentially having a conversation with paired accounts
    
    Args:
        account_id: Account ID to run warmup for
    """
    from app import app
    from models.account import Account
    from models.warmup import WarmupActivity, AccountWarmupChannel, ConversationPair
    from utils.telethon_helper import (
        read_channel_posts,
        react_to_post,
        send_conversation_message
    )
    
    with app.app_context():
        account = Account.query.get(account_id)
        if not account:
            logger.error(f"Account {account_id} not found")
            return {"error": "Account not found"}
        
        # Check if account is eligible for warmup
        if account.status not in ['warming_up', 'active']:
            logger.info(f"Account {account_id} status is {account.status}, skipping warmup")
            return {"skipped": True, "reason": f"Status is {account.status}"}
        
        # Determine intensity based on status
        if account.status == 'warming_up':
            actions_count = random.randint(3, 5)
            reaction_probability = 0.2
        else:  # active
            actions_count = random.randint(5, 12)
            reaction_probability = 0.35
        
        actions_performed = []
        
        # Get warmup channels for this account
        warmup_channels = AccountWarmupChannel.query.filter_by(
            account_id=account_id,
            is_active=True
        ).all()
        
        if not warmup_channels:
            logger.warning(f"Account {account_id} has no warmup channels assigned")
            # Log activity
            activity = WarmupActivity(
                account_id=account_id,
                day=account.warm_up_days_completed,
                action_type='no_channels',
                status='skipped',
                details='No warmup channels assigned'
            )
            db.session.add(activity)
            db.session.commit()
            return {"skipped": True, "reason": "No warmup channels"}
        
        # Select random channels for this session
        channels_to_read = random.sample(
            warmup_channels,
            min(random.randint(1, 3), len(warmup_channels))
        )
        
        # Read posts from selected channels
        for channel_record in channels_to_read:
            channel = channel_record.channel_username
            posts_count = random.randint(5, 15)
            delay = random.randint(3, 8)
            
            try:
                result = asyncio.run(read_channel_posts(
                    account_id,
                    channel,
                    count=posts_count,
                    delay_between=delay
                ))
                
                status = 'success' if result['success'] else 'failed'
                
                # Log activity
                activity = WarmupActivity(
                    account_id=account_id,
                    day=account.warm_up_days_completed,
                    action_type='read_posts',
                    target=channel,
                    status=status,
                    details=f"Read {result.get('posts_read', 0)} posts" if result['success'] else result.get('error')
                )
                db.session.add(activity)
                
                actions_performed.append({
                    'type': 'read_posts',
                    'channel': channel,
                    'status': status,
                    'posts': result.get('posts_read', 0)
                })
                
                # Maybe react to a post
                if result['success'] and random.random() < reaction_probability:
                    reaction = random.choice(WARMUP_REACTIONS)
                    react_result = asyncio.run(react_to_post(
                        account_id,
                        channel,
                        reaction=reaction
                    ))
                    
                    react_activity = WarmupActivity(
                        account_id=account_id,
                        day=account.warm_up_days_completed,
                        action_type='react',
                        target=channel,
                        status='success' if react_result['success'] else 'failed',
                        details=f"Reaction: {reaction}" if react_result['success'] else react_result.get('error')
                    )
                    db.session.add(react_activity)
                    
                    actions_performed.append({
                        'type': 'react',
                        'channel': channel,
                        'reaction': reaction,
                        'status': 'success' if react_result['success'] else 'failed'
                    })
                
                # Update last read timestamp
                channel_record.last_read_at = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Error reading channel {channel}: {e}")
                activity = WarmupActivity(
                    account_id=account_id,
                    day=account.warm_up_days_completed,
                    action_type='read_posts',
                    target=channel,
                    status='failed',
                    details=str(e)
                )
                db.session.add(activity)
            
            # Delay between channels
            if channel_record != channels_to_read[-1]:
                asyncio.run(asyncio.sleep(random.randint(30, 120)))
        
        # Check for conversation pairs (once every 2-3 days on average)
        if random.random() < 0.4:  # ~40% chance per day = every 2-3 days
            # Get conversation pairs for this account
            pairs = ConversationPair.query.filter(
                db.or_(
                    ConversationPair.account_a_id == account_id,
                    ConversationPair.account_b_id == account_id
                ),
                ConversationPair.is_active == True
            ).all()
            
            if pairs:
                pair = random.choice(pairs)
                # Determine partner
                partner_id = pair.account_b_id if pair.account_a_id == account_id else pair.account_a_id
                
                # Check if partner is also active
                partner = Account.query.get(partner_id)
                if partner and partner.status in ['warming_up', 'active']:
                    # Start a short conversation
                    message = random.choice(CONVERSATION_STARTERS)
                    try:
                        result = asyncio.run(send_conversation_message(
                            account_id,
                            partner_id,
                            message
                        ))
                        
                        conv_activity = WarmupActivity(
                            account_id=account_id,
                            day=account.warm_up_days_completed,
                            action_type='conversation',
                            target=str(partner_id),
                            status='success' if result['success'] else 'failed',
                            details=f"Sent: {message[:50]}..." if result['success'] else result.get('error')
                        )
                        db.session.add(conv_activity)
                        
                        if result['success']:
                            pair.last_conversation_at = datetime.utcnow()
                            pair.conversation_count += 1
                            
                            # Schedule partner's reply
                            reply_delay = random.randint(60, 300)  # 1-5 minutes
                            send_warmup_reply.apply_async(
                                (partner_id, account_id),
                                countdown=reply_delay
                            )
                        
                        actions_performed.append({
                            'type': 'conversation',
                            'partner': partner_id,
                            'status': 'success' if result['success'] else 'failed'
                        })
                        
                    except Exception as e:
                        logger.error(f"Error sending conversation message: {e}")
        
        # Update account's last activity
        account.last_activity = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"Warmup completed for account {account_id}: {len(actions_performed)} actions")
        
        return {
            "account_id": account_id,
            "actions": actions_performed,
            "count": len(actions_performed)
        }


@celery.task
def send_warmup_reply(account_id, to_account_id):
    """
    Send a reply in a warmup conversation
    
    Args:
        account_id: Replying account ID
        to_account_id: Original sender account ID
    """
    from app import app
    from models.account import Account
    from models.warmup import WarmupActivity
    from utils.telethon_helper import send_conversation_message
    
    with app.app_context():
        account = Account.query.get(account_id)
        if not account or account.status not in ['warming_up', 'active']:
            return {"skipped": True}
        
        message = random.choice(CONVERSATION_REPLIES)
        
        try:
            result = asyncio.run(send_conversation_message(
                account_id,
                to_account_id,
                message
            ))
            
            activity = WarmupActivity(
                account_id=account_id,
                day=account.warm_up_days_completed,
                action_type='conversation_reply',
                target=str(to_account_id),
                status='success' if result['success'] else 'failed',
                details=f"Reply: {message[:50]}..."
            )
            db.session.add(activity)
            db.session.commit()
            
            return {"success": result['success']}
            
        except Exception as e:
            logger.error(f"Error sending reply: {e}")
            return {"error": str(e)}


@celery.task
def schedule_daily_warmup():
    """
    Schedule warmup activities for all eligible accounts
    
    Run daily (e.g., at 08:00) to schedule warmup for the entire day.
    Each account gets a random time slot within the day.
    """
    from app import app
    from models.account import Account
    
    with app.app_context():
        # Get all accounts eligible for warmup (warming_up or active, not paused)
        accounts = Account.query.filter(
            Account.status.in_(['warming_up', 'active'])
        ).all()
        
        scheduled = 0
        
        for account in accounts:
            # Random delay: 0 to 14 hours (spread throughout the day)
            random_delay = random.randint(0, 14 * 3600)
            
            # Schedule warmup task
            run_warmup_activity.apply_async(
                (account.id,),
                countdown=random_delay
            )
            scheduled += 1
            
            # For active accounts, maybe schedule a second session
            if account.status == 'active' and random.random() < 0.3:
                second_delay = random_delay + random.randint(4 * 3600, 8 * 3600)
                run_warmup_activity.apply_async(
                    (account.id,),
                    countdown=second_delay
                )
        
        logger.info(f"Scheduled warmup for {scheduled} accounts")
        
        return {"scheduled": scheduled}


@celery.task
def update_warmup_day_counters():
    """
    Update warmup day counters for accounts in warming_up status
    
    Run daily at midnight to increment warm_up_days_completed.
    After 7-10 days, automatically transition to 'active' status.
    """
    from app import app
    from models.account import Account
    from config import Config
    
    with app.app_context():
        accounts = Account.query.filter_by(status='warming_up').all()
        
        transitioned = 0
        updated = 0
        
        for account in accounts:
            account.warm_up_days_completed += 1
            updated += 1
            
            # Check if warmup is complete (default 7 days)
            warmup_days = getattr(Config, 'WARMUP_DAYS', 7)
            if account.warm_up_days_completed >= warmup_days:
                account.status = 'active'
                transitioned += 1
                logger.info(f"Account {account.id} completed warmup, now active")
        
        db.session.commit()
        
        logger.info(f"Updated {updated} accounts, {transitioned} transitioned to active")
        
        return {"updated": updated, "transitioned": transitioned}
