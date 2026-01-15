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

logger = logging.getLogger(__name__)

@celery.task(bind=True)
def execute_stage_1_task(self, account_id, data):
    """Execute Stage 1: Profile setup in background"""
    from app import app as flask_app
    
    with flask_app.app_context():
        account = Account.query.get(account_id)
        if not account:
            return {'success': False, 'error': 'Account not found'}
            
        async def run():
            client = get_telethon_client(account_id)
            try:
                async def profile_action(client, account_id):
                    # Smart Update logic
                    # First name
                    new_first_name = data.get('first_name')
                    if new_first_name and new_first_name != account.first_name:
                        await emulate_typing(new_first_name, 'slow', account_id)
                        await client(UpdateProfileRequest(first_name=new_first_name))
                        await asyncio.sleep(random.uniform(3, 8))
                        WarmupLog.log(account_id, 'success', f"First name set: {new_first_name}", stage=1, action='set_first_name')
                    
                    # Last name
                    new_last_name = data.get('last_name')
                    if new_last_name is not None and new_last_name != account.last_name:
                        await asyncio.sleep(random.uniform(60, 120))
                        await emulate_typing(new_last_name, 'slow', account_id)
                        await client(UpdateProfileRequest(last_name=new_last_name))
                        await asyncio.sleep(random.uniform(3, 8))
                        WarmupLog.log(account_id, 'success', f"Last name set: {new_last_name}", stage=1, action='set_last_name')
                    
                    # Username
                    new_username = data.get('username', '').replace('@', '').strip()
                    if new_username and new_username != account.username:
                        await asyncio.sleep(random.uniform(60, 120))
                        await emulate_typing(new_username, 'normal', account_id)
                        await client(UpdateUsernameRequest(username=new_username))
                        await asyncio.sleep(random.uniform(3, 8))
                        WarmupLog.log(account_id, 'success', f"Username set: @{new_username}", stage=1, action='set_username')

                    # Bio
                    new_bio = data.get('bio')
                    if new_bio is not None and new_bio != account.bio:
                        await asyncio.sleep(random.uniform(30, 60))
                        await emulate_typing(new_bio, 'normal', account_id)
                        await client(UpdateProfileRequest(about=new_bio))
                        await asyncio.sleep(random.uniform(2, 5))
                        WarmupLog.log(account_id, 'success', 'Bio updated', stage=1, action='set_bio')
                    
                    # Photo
                    if data.get('photo_path'):
                        await asyncio.sleep(random.uniform(10, 30))
                        photo = await client.upload_file(data['photo_path'])
                        await client(UploadProfilePhotoRequest(photo))
                        await asyncio.sleep(random.uniform(2, 5))
                        WarmupLog.log(account_id, 'success', 'Photo uploaded', stage=1, action='set_photo')
                    
                    return {'success': True}
                
                result = await execute_warmup_action(client, account_id, profile_action, estimated_duration=600)
                return result
            finally:
                if client.is_connected():
                    await client.disconnect()

        # Run async in celery thread
        return asyncio.run(run())

@celery.task(bind=True)
def execute_stage_2_task(self, account_id, phone_numbers):
    """Execute Stage 2: Contacts setup in background"""
    from app import app as flask_app
    
    with flask_app.app_context():
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
                                client_id=random.getrandbits(31), # Fixed range
                                phone=phone,
                                first_name=f"Contact {i+1}",
                                last_name=""
                            ))
                        
                        await client(ImportContactsRequest(contacts))
                        await asyncio.sleep(random.uniform(5, 10))
                        WarmupLog.log(account_id, 'success', f"Imported {len(phone_numbers)} contacts", stage=2, action='import_contacts_success')
                    
                    # 2. View Contact List
                    await asyncio.sleep(random.uniform(10, 20))
                    await client(GetContactsRequest(hash=0))
                    WarmupLog.log(account_id, 'success', "Viewed contact list", stage=2, action='view_contacts')
                    
                    # 3. Save to Saved Messages
                    await asyncio.sleep(random.uniform(15, 30))
                    greeting_texts = [
                        "Hello! This is my new account.",
                        "Starting fresh here.",
                        "Settings look good.",
                        "Testing saved messages feature.",
                        "Note to self: warmup in progress."
                    ]
                    text = random.choice(greeting_texts)
                    await emulate_typing(text, 'fast', account_id)
                    await client.send_message('me', text)
                    WarmupLog.log(account_id, 'success', "Sent message to Saved Messages", stage=2, action='send_saved_message')
                    
                    return {'success': True}
                
                result = await execute_warmup_action(client, account_id, contacts_action, estimated_duration=300)
                return result
            finally:
                if client.is_connected():
                    await client.disconnect()

        return asyncio.run(run())

@celery.task(bind=True)
def execute_stage_3_task(self, account_id):
    """Execute Stage 3: Channels activities in background"""
    from app import app as flask_app
    from models.warmup_channel import WarmupChannel
    
    with flask_app.app_context():
        async def run():
            client = get_telethon_client(account_id)
            try:
                # Get pending channels
                channels = WarmupChannel.query.filter_by(account_id=account_id, status='pending').all()
                if not channels:
                    return {'success': True, 'message': 'No pending channels'}

                async def channels_action(client, account_id):
                    for chan in channels:
                        WarmupLog.log(account_id, 'info', f"Processing channel: {chan.title or chan.username}", stage=3, action='process_channel_start')
                        
                        # Subscribe if requested
                        if chan.action == 'subscribe':
                            await asyncio.sleep(random.uniform(30, 60))
                            await client(JoinChannelRequest(chan.username))
                            WarmupLog.log(account_id, 'success', f"Subscribed to {chan.username}", stage=3, action='subscribe_success')
                        
                        # View/Read posts
                        read_count = chan.read_count or 5
                        await asyncio.sleep(random.uniform(10, 20))
                        
                        # Simple read emulation: fetch message history
                        history = await client.get_messages(chan.username, limit=read_count)
                        for i, msg in enumerate(history):
                            await asyncio.sleep(random.uniform(2, 5)) 
                            # No specific 'read' request needed in Telethon usually, 
                            # just fetching is enough for basic activity
                        
                        chan.status = 'completed'
                        db.session.commit()
                        WarmupLog.log(account_id, 'success', f"Read {read_count} posts in {chan.username}", stage=3, action='read_posts_success')
                    
                    return {'success': True}
                
                result = await execute_warmup_action(client, account_id, channels_action, estimated_duration=len(channels) * 120)
                return result
            finally:
                if client.is_connected():
                    await client.disconnect()

        return asyncio.run(run())
