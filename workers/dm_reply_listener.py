from celery_app import celery
from app import db
from models.dm_campaign import DMCampaign, DMTarget, DMMessage
from models.account import Account
from utils.telethon_helper import get_telethon_client
from utils.notifications import notify_dm_reply
from telethon import events
import asyncio
import logging

logger = logging.getLogger(__name__)


@celery.task
def start_dm_reply_listeners():
    """Start reply listeners for all active DM campaigns"""
    
    # Get all active DM campaigns
    active_campaigns = DMCampaign.query.filter_by(status='active').all()
    
    if not active_campaigns:
        logger.info("No active DM campaigns, skipping reply listeners")
        return
    
    # Get all accounts used in active campaigns
    account_ids = set()
    for campaign in active_campaigns:
        for ca in campaign.dm_campaign_accounts.all():
            account_ids.add(ca.account_id)
    
    logger.info(f"Starting DM reply listeners for {len(account_ids)} accounts")
    
    # Start listener for each account
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    tasks = []
    for account_id in account_ids:
        task = loop.create_task(listen_account_replies(account_id))
        tasks.append(task)
    
    # Run all listeners
    try:
        loop.run_until_complete(asyncio.gather(*tasks))
    except Exception as e:
        logger.error(f"Error in DM reply listeners: {str(e)}")
    finally:
        loop.close()


async def listen_account_replies(account_id):
    """Listen to incoming messages for one account"""
    
    logger.info(f"Starting reply listener for account {account_id}")
    
    try:
        # Get Telethon client
        client = get_telethon_client(account_id)
        
        if not client.is_connected():
            await client.connect()
        
        # Define message handler
        @client.on(events.NewMessage(incoming=True))
        async def handle_incoming_message(event):
            """Handle incoming DM"""
            try:
                sender = await event.get_sender()
                
                if not sender:
                    return
                
                # Check if sender is in our DM targets
                username = sender.username
                if not username:
                    # Try to find by user_id
                    logger.debug(f"Incoming message from user without username: {sender.id}")
                    return
                
                # Find target by username (could be from any active campaign)
                target = DMTarget.query.filter_by(
                    username=username,
                    sent_by_account_id=account_id,
                    status='sent'
                ).first()
                
                if not target:
                    # Not our target, ignore
                    logger.debug(f"Incoming message from non-target user: @{username}")
                    return
                
                # Save reply
                message_text = event.message.text or '[Media message]'
                
                # Update target replied_at
                if not target.replied_at:
                    from datetime import datetime
                    target.replied_at = datetime.utcnow()
                
                # Save message to history
                dm_message = DMMessage(
                    campaign_id=target.campaign_id,
                    target_id=target.id,
                    account_id=account_id,
                    direction='incoming',
                    message_text=message_text,
                    has_media=bool(event.message.media),
                    media_type=type(event.message.media).__name__ if event.message.media else None,
                    telegram_message_id=event.message.id
                )
                
                db.session.add(dm_message)
                db.session.commit()
                
                logger.info(f"Saved reply from @{username} in campaign {target.campaign_id}")
                
                # Send notification
                notify_dm_reply(target.campaign_id, username)
                
                # Check for stop keywords (blacklist)
                stop_keywords = ['stop', 'unsubscribe', 'spam', 'отпишись', 'стоп']
                if any(keyword in message_text.lower() for keyword in stop_keywords):
                    # Add to blacklist
                    from models.blacklist import GlobalBlacklist
                    
                    existing = GlobalBlacklist.query.filter_by(username=username).first()
                    if not existing:
                        blacklist_entry = GlobalBlacklist(
                            user_id=sender.id,
                            username=username,
                            reason='stop_keyword',
                            added_by_campaign_id=target.campaign_id,
                            notes=f'User replied with stop keyword: {message_text[:50]}'
                        )
                        db.session.add(blacklist_entry)
                        db.session.commit()
                        
                        logger.info(f"Added @{username} to blacklist (stop keyword)")
                
            except Exception as e:
                logger.error(f"Error handling incoming message: {str(e)}")
        
        logger.info(f"Reply listener active for account {account_id}")
        
        # Keep client running
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"Error in reply listener for account {account_id}: {str(e)}")
    finally:
        logger.info(f"Reply listener stopped for account {account_id}")


@celery.task
def check_and_restart_listeners():
    """
    Check if listeners are running and restart if needed
    This task should run periodically (e.g., every hour)
    """
    
    active_campaigns = DMCampaign.query.filter_by(status='active').count()
    
    if active_campaigns > 0:
        logger.info(f"Found {active_campaigns} active DM campaigns, ensuring listeners are running")
        start_dm_reply_listeners.delay()
    else:
        logger.info("No active DM campaigns")


@celery.task
def process_missed_replies(account_id):
    """
    Process any replies that might have been missed while listener was down
    Checks recent messages and updates database
    """
    
    logger.info(f"Processing missed replies for account {account_id}")
    
    try:
        from datetime import datetime, timedelta
        from telethon.tl.functions.messages import GetDialogsRequest
        from telethon.tl.types import InputPeerEmpty
        
        client = get_telethon_client(account_id)
        
        async def check_missed():
            if not client.is_connected():
                await client.connect()
            
            # Get recent dialogs (conversations)
            dialogs = await client.get_dialogs(limit=50)
            
            processed = 0
            
            for dialog in dialogs:
                if not dialog.is_user:
                    continue
                
                user = dialog.entity
                if not user.username:
                    continue
                
                # Check if this user is in our targets
                target = DMTarget.query.filter_by(
                    username=user.username,
                    sent_by_account_id=account_id,
                    status='sent'
                ).first()
                
                if not target:
                    continue
                
                # Get messages from this dialog
                messages = await client.get_messages(dialog, limit=10)
                
                for msg in messages:
                    if msg.out:
                        # Outgoing message, skip
                        continue
                    
                    # Check if we already have this message
                    existing = DMMessage.query.filter_by(
                        telegram_message_id=msg.id,
                        account_id=account_id
                    ).first()
                    
                    if existing:
                        continue
                    
                    # New incoming message, save it
                    message_text = msg.text or '[Media message]'
                    
                    if not target.replied_at:
                        target.replied_at = msg.date
                    
                    dm_message = DMMessage(
                        campaign_id=target.campaign_id,
                        target_id=target.id,
                        account_id=account_id,
                        direction='incoming',
                        message_text=message_text,
                        has_media=bool(msg.media),
                        telegram_message_id=msg.id,
                        timestamp=msg.date
                    )
                    
                    db.session.add(dm_message)
                    processed += 1
            
            db.session.commit()
            logger.info(f"Processed {processed} missed replies for account {account_id}")
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(check_missed())
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error processing missed replies for account {account_id}: {str(e)}")
