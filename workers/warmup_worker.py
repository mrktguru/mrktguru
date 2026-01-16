"""
Warmup Worker
Background tasks for account warmup activities
"""
from celery_app import celery
from database import db
from models.account import Account
from models.warmup_log import WarmupLog
from utils.telethon_helper import get_telethon_client
from utils.warmup_executor import execute_warmup_action, emulate_typing
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.contacts import ImportContactsRequest, GetContactsRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import SendMessageRequest
from telethon.tl.types import InputPhoneContact
import asyncio
import random
import logging
import os

logger = logging.getLogger(__name__)

@celery.task(bind=True)
def execute_stage_1_task(self, account_id, data):
    """Execute Stage 1: Profile setup in background"""
    from app import app as flask_app
    
    with flask_app.app_context():
        account = Account.query.get(account_id)
        if not account:
            return {'success': False, 'error': 'Account not found'}
            
        try:
            # Immediate feedback that worker started
            WarmupLog.log(account_id, 'info', 'Profile setup task started in background', stage=1, action='start_task')
            logger.info(f"Starting Stage 1 task for account {account_id}")

            async def run():
                client = get_telethon_client(account_id)
                if not client:
                    raise Exception("Failed to initialize Telethon client")
                
                try:
                    async def profile_action(client, account_id):
                        # Smart Update logic
                        # First name
                        new_first_name = data.get('first_name')
                        if new_first_name and new_first_name != account.first_name:
                            await emulate_typing(new_first_name, 'normal', account_id)
                            await client(UpdateProfileRequest(first_name=new_first_name))
                            account.first_name = new_first_name
                            logger.info(f"Updated account first_name={new_first_name} (pending commit)")
                            await asyncio.sleep(random.uniform(3, 8))
                            WarmupLog.log(account_id, 'success', f"First name set: {new_first_name}", stage=1, action='set_first_name')
                        
                        # Last name
                        new_last_name = data.get('last_name')
                        if new_last_name is not None and new_last_name != account.last_name:
                            await asyncio.sleep(random.uniform(10, 20)) # Reduced delay for debugging
                            await emulate_typing(new_last_name, 'normal', account_id)
                            await client(UpdateProfileRequest(last_name=new_last_name))
                            account.last_name = new_last_name
                            logger.info(f"Updated account last_name={new_last_name} (pending commit)")
                            await asyncio.sleep(random.uniform(3, 8))
                            WarmupLog.log(account_id, 'success', f"Last name set: {new_last_name}", stage=1, action='set_last_name')
                        
                        # Username
                        new_username = data.get('username', '').replace('@', '').strip()
                        if new_username and new_username != account.username:
                            await asyncio.sleep(random.uniform(10, 20)) # Reduced delay
                            await emulate_typing(new_username, 'normal', account_id)
                            await client(UpdateUsernameRequest(username=new_username))
                            account.username = new_username
                            logger.info(f"Updated account username=@{new_username} (pending commit)")
                            await asyncio.sleep(random.uniform(3, 8))
                            WarmupLog.log(account_id, 'success', f"Username set: @{new_username}", stage=1, action='set_username')

                        # Bio
                        new_bio = data.get('bio')
                        if new_bio is not None and new_bio != account.bio:
                            await asyncio.sleep(random.uniform(10, 20)) # Reduced delay
                            await emulate_typing(new_bio, 'normal', account_id)
                            await client(UpdateProfileRequest(about=new_bio))
                            account.bio = new_bio
                            logger.info(f"Updated account bio (pending commit)")
                            await asyncio.sleep(random.uniform(2, 5))
                            WarmupLog.log(account_id, 'success', 'Bio updated', stage=1, action='set_bio')
                        
                        # Photo
                        photo_path = data.get('photo_path')
                        if photo_path:
                            if not os.path.exists(photo_path):
                                WarmupLog.log(account_id, 'error', f"Photo file not found: {photo_path}", stage=1, action='set_photo_error')
                                logger.error(f"Photo file not found: {photo_path}")
                            else:
                                try:
                                    WarmupLog.log(account_id, 'info', 'Uploading profile photo...', stage=1, action='upload_photo_start')
                                    await asyncio.sleep(random.uniform(5, 10))
                                    
                                    # Upload to Telegram servers first
                                    uploaded_file = await client.upload_file(photo_path)
                                    if not uploaded_file:
                                        raise Exception("File upload to Telegram failed (returned None)")
                                    
                                    # Set as profile photo using explicit keyword argument
                                    await client(UploadProfilePhotoRequest(file=uploaded_file))
                                    
                                    # Update local DB with relative path for UI compatibility
                                    if 'uploads/' in photo_path:
                                        rel_path = photo_path.split('uploads/')[-1]
                                        account.photo_url = f"uploads/{rel_path}"
                                    else:
                                        account.photo_url = photo_path
                                    
                                    logger.info(f"Updated account photo_url={account.photo_url} (pending commit)")
                                    
                                    await asyncio.sleep(random.uniform(2, 5))
                                    WarmupLog.log(account_id, 'success', 'Photo uploaded and set', stage=1, action='set_photo')
                                    logger.info(f"Photo successfully set for account {account_id}")
                                except Exception as e:
                                    error_msg = f"Photo upload failed: {str(e)}"
                                    logger.error(error_msg, exc_info=True)
                                    WarmupLog.log(account_id, 'error', error_msg, stage=1, action='set_photo_error')
                                    # Don't fail the whole task if just photo fails, but log it
                        
                        # Final commit for all account changes
                        try:
                            # Use flask context from the outer block
                            db.session.commit()
                            logger.info(f"Final commit success for account {account_id}")
                        except Exception as commit_err:
                            logger.error(f"Final commit failed for account {account_id}: {commit_err}")
                            db.session.rollback()
                            raise 
                            
                        return {'success': True}
                    
                    result = await execute_warmup_action(client, account_id, profile_action, estimated_duration=600)
                    return result
                finally:
                    if client.is_connected():
                        await client.disconnect()

            # Run async in celery thread
            result = asyncio.run(run())
            
            # Log successful completion so UI knows task is done
            if result and result.get('success'):
                WarmupLog.log(account_id, 'success', 'Profile setup completed successfully', stage=1, action='complete')
            
            return result
        except Exception as e:
            error_msg = f"Stage 1 background error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            WarmupLog.log(account_id, 'error', error_msg, stage=1, action='task_failure')
            return {'success': False, 'error': str(e)}

@celery.task(bind=True)
def execute_stage_2_task(self, account_id, phone_numbers):
    """Execute Stage 2: Contacts setup in background"""
    from app import app as flask_app
    
    with flask_app.app_context():
        try:
            WarmupLog.log(account_id, 'info', 'Contacts task started in background', stage=2, action='start_task')
            
            async def run():
                client = get_telethon_client(account_id)
                try:
                    async def contacts_action(client, account_id):
                        # 1. Import Contacts
                        if phone_numbers:
                            WarmupLog.log(account_id, 'info', f"Starting import of {len(phone_numbers)} contacts", stage=2, action='import_contacts_start')
                            
                            contacts = []
                            for i, phone in enumerate(phone_numbers):
                                contacts.append(InputPhoneContact(
                                    client_id=random.getrandbits(31),
                                    phone=phone,
                                    first_name=f"Contact {i+1}",
                                    last_name=""
                                ))
                            
                            await client(ImportContactsRequest(contacts))
                            await asyncio.sleep(random.uniform(5, 10))
                            WarmupLog.log(account_id, 'success', f"Imported {len(phone_numbers)} contacts", stage=2, action='import_contacts_success')
                        
                        # 2. View Contact List
                        await asyncio.sleep(random.uniform(5, 10))
                        await client(GetContactsRequest(hash=0))
                        WarmupLog.log(account_id, 'success', "Viewed contact list", stage=2, action='view_contacts')
                        
                        # 3. Save to Saved Messages
                        await asyncio.sleep(random.uniform(10, 20))
                        greeting_texts = ["Hello!", "Fresh start.", "Testing.", "Warmup in progress."]
                        text = random.choice(greeting_texts)
                        await emulate_typing(text, 'normal', account_id)
                        await client.send_message('me', text)
                        WarmupLog.log(account_id, 'success', "Sent message to Saved Messages", stage=2, action='send_saved_message')
                        
                        return {'success': True}
                    
                    result = await execute_warmup_action(client, account_id, contacts_action, estimated_duration=300)
                    return result
                finally:
                    if client.is_connected():
                        await client.disconnect()

            return asyncio.run(run())
        except Exception as e:
            error_msg = f"Stage 2 background error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            WarmupLog.log(account_id, 'error', error_msg, stage=2, action='task_failure')
            return {'success': False, 'error': str(e)}

@celery.task(bind=True)
def execute_stage_3_task(self, account_id):
    """Execute Stage 3: Channels activities in background"""
    from app import app as flask_app
    from models.warmup_channel import WarmupChannel
    
    with flask_app.app_context():
        try:
            WarmupLog.log(account_id, 'info', 'Channels task started in background', stage=3, action='start_task')
            
            async def run():
                client = get_telethon_client(account_id)
                try:
                    channels = WarmupChannel.query.filter_by(account_id=account_id, status='pending').all()
                    if not channels:
                        WarmupLog.log(account_id, 'info', 'No pending channels to process', stage=3)
                        return {'success': True}

                    async def channels_action(client, account_id):
                        for chan in channels:
                            WarmupLog.log(account_id, 'info', f"Processing channel: {chan.title or chan.username}", stage=3, action='process_channel_start')
                            
                            if chan.action == 'subscribe':
                                # Subscribe logic
                                await asyncio.sleep(random.uniform(10, 20))
                                await client(JoinChannelRequest(chan.username))
                                WarmupLog.log(account_id, 'success', f"Subscribed to {chan.username}", stage=3, action='subscribe_success')
                                
                                # Basic reading for subscribed
                                read_count = chan.read_count or 5
                                await asyncio.sleep(random.uniform(5, 10))
                                await client.get_messages(chan.username, limit=read_count)
                                WarmupLog.log(account_id, 'success', f"Read {read_count} posts in {chan.username}", stage=3, action='read_posts_success')
                                
                            else:  # view_only / visit
                                WarmupLog.log(account_id, 'info', f"Visiting {chan.username}...", stage=3, action='visit_start')
                                await asyncio.sleep(random.uniform(2, 5))
                                
                                # 1. Read latest posts with micro-delays
                                limit = random.randint(3, 6)
                                msgs = await client.get_messages(chan.username, limit=limit)
                                
                                for msg in msgs:
                                    # Simulate reading post (micro-delay)
                                    read_time = random.uniform(2, 8)
                                    await asyncio.sleep(read_time)
                                    
                                    # 30% chance to open comments (if available)
                                    if msg.replies and msg.replies.replies > 0 and random.random() < 0.3:
                                        try:
                                            WarmupLog.log(account_id, 'info', "Opening comments...", stage=3, action='view_comments')
                                            # Transition delay
                                            await asyncio.sleep(random.uniform(1.5, 3.0))
                                            
                                            # Fetch comments (enter discussion)
                                            comments = await client.get_messages(chan.username, reply_to=msg.id, limit=random.randint(5, 12))
                                            
                                            # Scroll micro-delays in comments
                                            for _ in range(random.randint(2, 5)):
                                                await asyncio.sleep(random.uniform(1, 3))
                                                
                                            # 30% chance to view a commenter's profile
                                            if comments and random.random() < 0.3:
                                                comment = random.choice(comments)
                                                if comment.sender_id:
                                                    try:
                                                        WarmupLog.log(account_id, 'info', "Viewing commenter profile...", stage=3, action='view_profile')
                                                        # Click delay
                                                        await asyncio.sleep(random.uniform(1, 2))
                                                        # Fetch full entity (simulate studying profile)
                                                        await client.get_entity(comment.sender_id)
                                                        # Study delay
                                                        await asyncio.sleep(random.uniform(4, 10))
                                                        # Back to comments
                                                        await asyncio.sleep(random.uniform(1, 2))
                                                    except:
                                                        pass
                                            
                                            # Back to posts navigation
                                            await asyncio.sleep(random.uniform(1.5, 3.0))
                                            
                                        except Exception as c_err:
                                            pass
                                
                                # Final scroll simulation (Up/Down)
                                await asyncio.sleep(random.uniform(2, 4))
                                if msgs:
                                    last_id = msgs[-1].id
                                    # Scroll up (older)
                                    await client.get_messages(chan.username, limit=3, offset_id=last_id)
                                    await asyncio.sleep(random.uniform(3, 6))
                                
                                WarmupLog.log(account_id, 'success', f"Visited {chan.username} (deep interaction completed)", stage=3, action='visit_success')
                            
                            chan.status = 'completed'
                        
                        db.session.commit()
                        return {'success': True}
                    
                    result = await execute_warmup_action(client, account_id, channels_action, estimated_duration=600)
                    return result
                finally:
                    if client.is_connected():
                        await client.disconnect()

            return asyncio.run(run())
        except Exception as e:
            error_msg = f"Stage 3 background error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            WarmupLog.log(account_id, 'error', error_msg, stage=3, action='task_failure')
            return {'success': False, 'error': str(e)}
