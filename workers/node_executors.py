"""
Node Executors for Warmup Scheduler
Individual, reusable functions for each warmup action type
"""
import asyncio
import random
import os
import logging
from datetime import datetime
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import InputPhoneContact
from models.warmup_log import WarmupLog
from utils.warmup_executor import emulate_typing
from database import db

logger = logging.getLogger(__name__)


async def execute_node_bio(client, account_id, config):
    """
    Execute Bio node - update first name, last name, and bio
    
    Config:
    {
        'first_name': 'John',
        'last_name': 'Doe',
        'bio': 'Marketing Guru. DM for collaboration'
    }
    """
    from models.account import Account
    
    try:
        account = Account.query.get(account_id)
        if not account:
            return {'success': False, 'error': 'Account not found'}
        
        # First name
        first_name = config.get('first_name')
        if first_name and first_name != account.first_name:
            WarmupLog.log(account_id, 'info', f"Setting first name: {first_name}", action='set_first_name')
            await emulate_typing(first_name, 'normal', account_id)
            await client(UpdateProfileRequest(first_name=first_name))
            account.first_name = first_name
            await asyncio.sleep(random.uniform(3, 8))
            WarmupLog.log(account_id, 'success', f"First name set: {first_name}", action='set_first_name')
        
        # Last name
        last_name = config.get('last_name')
        if last_name is not None and last_name != account.last_name:
            await asyncio.sleep(random.uniform(10, 20))
            WarmupLog.log(account_id, 'info', f"Setting last name: {last_name}", action='set_last_name')
            await emulate_typing(last_name, 'normal', account_id)
            await client(UpdateProfileRequest(last_name=last_name))
            account.last_name = last_name
            await asyncio.sleep(random.uniform(3, 8))
            WarmupLog.log(account_id, 'success', f"Last name set: {last_name}", action='set_last_name')
        
        # Bio
        bio = config.get('bio')
        if bio is not None and bio != account.bio:
            await asyncio.sleep(random.uniform(10, 20))
            WarmupLog.log(account_id, 'info', f"Setting bio", action='set_bio')
            await emulate_typing(bio, 'normal', account_id)
            await client(UpdateProfileRequest(about=bio))
            account.bio = bio
            await asyncio.sleep(random.uniform(2, 5))
            WarmupLog.log(account_id, 'success', 'Bio updated', action='set_bio')
        
        # Sync from Telegram
        await asyncio.sleep(random.uniform(2, 4))
        me = await client.get_me()
        account.first_name = me.first_name or account.first_name
        account.last_name = me.last_name or account.last_name
        account.bio = getattr(me, 'about', account.bio)
        
        db.session.commit()
        
        return {'success': True, 'message': 'Bio node executed successfully'}
        
    except Exception as e:
        logger.error(f"Bio node failed: {e}")
        WarmupLog.log(account_id, 'error', f"Bio update failed: {str(e)}", action='bio_error')
        return {'success': False, 'error': str(e)}


async def execute_node_username(client, account_id, config):
    """
    Execute Username node - update Telegram username
    
    Config:
    {
        'username': 'johndoe123'
    }
    """
    from models.account import Account
    
    try:
        account = Account.query.get(account_id)
        if not account:
            return {'success': False, 'error': 'Account not found'}
        
        username = config.get('username', '').replace('@', '').strip()
        if not username:
            return {'success': False, 'error': 'Username is required'}
        
        if username == account.username:
            return {'success': True, 'message': 'Username already set'}
        
        WarmupLog.log(account_id, 'info', f"Setting username: @{username}", action='set_username')
        await asyncio.sleep(random.uniform(10, 20))
        await emulate_typing(username, 'normal', account_id)
        await client(UpdateUsernameRequest(username=username))
        account.username = username
        await asyncio.sleep(random.uniform(3, 8))
        
        db.session.commit()
        WarmupLog.log(account_id, 'success', f"Username set: @{username}", action='set_username')
        
        return {'success': True, 'message': f'Username set to @{username}'}
        
    except Exception as e:
        logger.error(f"Username node failed: {e}")
        WarmupLog.log(account_id, 'error', f"Username update failed: {str(e)}", action='username_error')
        return {'success': False, 'error': str(e)}


async def execute_node_photo(client, account_id, config):
    """
    Execute Photo node - upload profile photo
    
    Config:
    {
        'photo_path': '/absolute/path/to/photo.jpg'
    }
    """
    from models.account import Account
    
    try:
        account = Account.query.get(account_id)
        if not account:
            return {'success': False, 'error': 'Account not found'}
        
        photo_path = config.get('photo_path')
        if not photo_path:
            return {'success': False, 'error': 'Photo path is required'}
        
        if not os.path.exists(photo_path):
            error_msg = f"Photo file not found: {photo_path}"
            WarmupLog.log(account_id, 'error', error_msg, action='photo_error')
            return {'success': False, 'error': error_msg}
        
        WarmupLog.log(account_id, 'info', 'Uploading profile photo...', action='upload_photo_start')
        await asyncio.sleep(random.uniform(5, 10))
        
        # Upload to Telegram
        uploaded_file = await client.upload_file(photo_path)
        if not uploaded_file:
            raise Exception("File upload to Telegram failed")
        
        await client(UploadProfilePhotoRequest(file=uploaded_file))
        
        # Update local DB
        if 'uploads/' in photo_path:
            relative_path = photo_path.split('uploads/')[-1]
            account.photo = relative_path
        
        await asyncio.sleep(random.uniform(2, 5))
        db.session.commit()
        
        WarmupLog.log(account_id, 'success', 'Photo uploaded and set', action='set_photo')
        
        return {'success': True, 'message': 'Profile photo uploaded'}
        
    except Exception as e:
        logger.error(f"Photo node failed: {e}")
        WarmupLog.log(account_id, 'error', f"Photo upload failed: {str(e)}", action='photo_error')
        return {'success': False, 'error': str(e)}


async def execute_node_import_contacts(client, account_id, config):
    """
    Execute Import Contacts node
    
    Config:
    {
        'count': 5,
        'contacts': [
            {'phone': '+1234567890', 'first_name': 'John', 'last_name': 'Doe'},
            ...
        ]
    }
    """
    try:
        count = config.get('count', 5)
        contacts_data = config.get('contacts', [])
        
        if not contacts_data:
            return {'success': False, 'error': 'No contacts provided'}
        
        # Limit to requested count
        contacts_data = contacts_data[:count]
        
        WarmupLog.log(account_id, 'info', f"Importing {len(contacts_data)} contacts", action='import_start')
        await asyncio.sleep(random.uniform(5, 10))
        
        # Convert to Telethon format
        contacts = [
            InputPhoneContact(
                client_id=i,
                phone=c['phone'],
                first_name=c.get('first_name', 'Contact'),
                last_name=c.get('last_name', '')
            )
            for i, c in enumerate(contacts_data)
        ]
        
        # Import
        result = await client(ImportContactsRequest(contacts))
        
        await asyncio.sleep(random.uniform(3, 8))
        WarmupLog.log(account_id, 'success', f"Imported {len(contacts_data)} contacts", action='import_success')
        
        return {'success': True, 'message': f'Imported {len(contacts_data)} contacts'}
        
    except Exception as e:
        logger.error(f"Import contacts node failed: {e}")
        WarmupLog.log(account_id, 'error', f"Contact import failed: {str(e)}", action='import_error')
        return {'success': False, 'error': str(e)}


async def execute_node_send_message(client, account_id, config):
    """
    Execute Send Message node - send message to Saved Messages
    
    Config:
    {
        'message': 'Test message',
        'count': 1
    }
    """
    try:
        message = config.get('message', 'Test message')
        count = config.get('count', 1)
        
        WarmupLog.log(account_id, 'info', f"Sending {count} message(s) to Saved Messages", action='send_start')
        
        for i in range(count):
            await asyncio.sleep(random.uniform(5, 10))
            await client.send_message('me', message)
            WarmupLog.log(account_id, 'success', f"Message {i+1}/{count} sent", action='send_message')
        
        return {'success': True, 'message': f'Sent {count} message(s)'}
        
    except Exception as e:
        logger.error(f"Send message node failed: {e}")
        WarmupLog.log(account_id, 'error', f"Send message failed: {str(e)}", action='send_error')
        return {'success': False, 'error': str(e)}


async def execute_node_subscribe_channels(client, account_id, config):
    """
    Execute Subscribe Channels node
    
    Config:
    {
        'channels': ['@channel1', '@channel2'],
        'read_count': 5,
        'interaction_depth': {
            'comments': True,
            'profiles': True,
            'forward': True
        }
    }
    """
    try:
        channels = config.get('channels', [])
        read_count = config.get('read_count', 5)
        interaction = config.get('interaction_depth', {})
        
        if not channels:
            return {'success': False, 'error': 'No channels provided'}
        
        for channel_username in channels:
            channel_username = channel_username.replace('@', '').strip()
            
            # Subscribe
            WarmupLog.log(account_id, 'info', f"Subscribing to {channel_username}", action='subscribe_start')
            await asyncio.sleep(random.uniform(10, 20))
            await client(JoinChannelRequest(channel_username))
            WarmupLog.log(account_id, 'success', f"Subscribed to {channel_username}", action='subscribe_success')
            
            # Read posts with detailed logging
            await asyncio.sleep(random.uniform(5, 10))
            msgs = await client.get_messages(channel_username, limit=read_count)
            
            for msg in msgs:
                # Build post URL
                post_url = f"https://t.me/{channel_username}/{msg.id}"
                
                # Get text preview
                text_preview = ""
                if msg.message:
                    text_preview = msg.message[:80].replace('\n', ' ')
                    if len(msg.message) > 80:
                        text_preview += "..."
                elif msg.media:
                    text_preview = "[Media post]"
                else:
                    text_preview = "[Empty post]"
                
                WarmupLog.log(account_id, 'info', f"📖 Reading: {text_preview} | {post_url}", action='read_post')
                await asyncio.sleep(random.uniform(2, 8))
                
                # Comments interaction
                if interaction.get('comments') and msg.replies and msg.replies.replies > 0 and random.random() < 0.3:
                    try:
                        WarmupLog.log(account_id, 'info', f"💬 Opening comments ({msg.replies.replies} replies)", action='view_comments')
                        await asyncio.sleep(random.uniform(1.5, 3.0))
                        comments = await client.get_messages(channel_username, reply_to=msg.id, limit=random.randint(5, 12))
                        WarmupLog.log(account_id, 'info', f"📝 Read {len(comments)} comments", action='read_comments')
                        
                        for _ in range(random.randint(2, 5)):
                            await asyncio.sleep(random.uniform(1, 3))
                        
                        # Profile viewing
                        if interaction.get('profiles') and comments and random.random() < 0.3:
                            comment = random.choice(comments)
                            if comment.sender_id:
                                try:
                                    WarmupLog.log(account_id, 'info', f"👤 Viewing commenter profile", action='view_profile')
                                    await asyncio.sleep(random.uniform(1, 2))
                                    await client.get_entity(comment.sender_id)
                                    await asyncio.sleep(random.uniform(4, 10))
                                except:
                                    pass
                        
                        await asyncio.sleep(random.uniform(1.5, 3.0))
                    except:
                        pass
                
                # Forward to Saved
                if interaction.get('forward') and random.random() < 0.15:
                    try:
                        WarmupLog.log(account_id, 'info', f"✈️ Forwarding to Saved", action='forward_saved')
                        await asyncio.sleep(random.uniform(1, 2))
                        await client.forward_messages('me', msg)
                        await asyncio.sleep(random.uniform(1, 2))
                    except:
                        pass
            
            WarmupLog.log(account_id, 'success', f"Completed interaction with {channel_username}", action='subscribe_complete')
        
        return {'success': True, 'message': f'Subscribed to {len(channels)} channel(s)'}
        
    except Exception as e:
        logger.error(f"Subscribe channels node failed: {e}")
        WarmupLog.log(account_id, 'error', f"Subscribe failed: {str(e)}", action='subscribe_error')
        return {'success': False, 'error': str(e)}


async def execute_node_visit_channels(client, account_id, config):
    """
    Execute Visit Channels node (view only, no subscribe)
    
    Config: same as subscribe_channels
    """
    try:
        channels = config.get('channels', [])
        read_count = config.get('read_count', 5)
        interaction = config.get('interaction_depth', {})
        
        if not channels:
            return {'success': False, 'error': 'No channels provided'}
        
        for channel_username in channels:
            channel_username = channel_username.replace('@', '').strip()
            
            WarmupLog.log(account_id, 'info', f"Visiting {channel_username}", action='visit_start')
            await asyncio.sleep(random.uniform(2, 5))
            
            # Read posts (same logic as subscribe, but without joining)
            msgs = await client.get_messages(channel_username, limit=read_count)
            
            for msg in msgs:
                post_url = f"https://t.me/{channel_username}/{msg.id}"
                text_preview = ""
                if msg.message:
                    text_preview = msg.message[:80].replace('\n', ' ')
                    if len(msg.message) > 80:
                        text_preview += "..."
                elif msg.media:
                    text_preview = "[Media post]"
                else:
                    text_preview = "[Empty post]"
                
                WarmupLog.log(account_id, 'info', f"📖 Reading: {text_preview} | {post_url}", action='read_post')
                await asyncio.sleep(random.uniform(2, 8))
                
                # Same interaction logic as subscribe
                if interaction.get('comments') and msg.replies and msg.replies.replies > 0 and random.random() < 0.3:
                    try:
                        WarmupLog.log(account_id, 'info', f"💬 Opening comments", action='view_comments')
                        await asyncio.sleep(random.uniform(1.5, 3.0))
                        comments = await client.get_messages(channel_username, reply_to=msg.id, limit=random.randint(5, 12))
                        WarmupLog.log(account_id, 'info', f"📝 Read {len(comments)} comments", action='read_comments')
                        
                        for _ in range(random.randint(2, 5)):
                            await asyncio.sleep(random.uniform(1, 3))
                        
                        if interaction.get('profiles') and comments and random.random() < 0.3:
                            comment = random.choice(comments)
                            if comment.sender_id:
                                try:
                                    WarmupLog.log(account_id, 'info', f"👤 Viewing profile", action='view_profile')
                                    await asyncio.sleep(random.uniform(1, 2))
                                    await client.get_entity(comment.sender_id)
                                    await asyncio.sleep(random.uniform(4, 10))
                                except:
                                    pass
                        
                        await asyncio.sleep(random.uniform(1.5, 3.0))
                    except:
                        pass
                
                if interaction.get('forward') and random.random() < 0.15:
                    try:
                        WarmupLog.log(account_id, 'info', f"✈️ Forwarding to Saved", action='forward_saved')
                        await asyncio.sleep(random.uniform(1, 2))
                        await client.forward_messages('me', msg)
                        await asyncio.sleep(random.uniform(1, 2))
                    except:
                        pass
            
            WarmupLog.log(account_id, 'success', f"Visited {channel_username}", action='visit_success')
        
        return {'success': True, 'message': f'Visited {len(channels)} channel(s)'}
        
    except Exception as e:
        logger.error(f"Visit channels node failed: {e}")
        WarmupLog.log(account_id, 'error', f"Visit failed: {str(e)}", action='visit_error')
        return {'success': False, 'error': str(e)}


async def execute_node_idle(client, account_id, config):
    """
    Execute Idle node - do nothing (cooldown period)
    
    Config:
    {
        'duration_minutes': 60
    }
    """
    try:
        duration = config.get('duration_minutes', 60)
        
        WarmupLog.log(account_id, 'info', f"Idle period: {duration} minutes", action='idle_start')
        await asyncio.sleep(duration * 60)
        WarmupLog.log(account_id, 'success', f"Idle period completed", action='idle_complete')
        
        return {'success': True, 'message': f'Idle for {duration} minutes'}
        
    except Exception as e:
        logger.error(f"Idle node failed: {e}")
        return {'success': False, 'error': str(e)}


# Node executor registry
NODE_EXECUTORS = {
    'bio': execute_node_bio,
    'username': execute_node_username,
    'photo': execute_node_photo,
    'import_contacts': execute_node_import_contacts,
    'send_message': execute_node_send_message,
    'subscribe': execute_node_subscribe_channels,
    'visit': execute_node_visit_channels,
    'idle': execute_node_idle,
}


async def execute_node(node_type, client, account_id, config):
    """
    Execute a warmup node by type
    
    Args:
        node_type: Type of node ('bio', 'username', etc.)
        client: Telethon client
        account_id: Account ID
        config: Node configuration dict
    
    Returns:
        dict: {'success': bool, 'message': str, 'error': str}
    """
    executor = NODE_EXECUTORS.get(node_type)
    
    if not executor:
        return {'success': False, 'error': f'Unknown node type: {node_type}'}
    
    try:
        result = await executor(client, account_id, config)
        return result
    except Exception as e:
        logger.error(f"Node execution failed: {e}")
        return {'success': False, 'error': str(e)}
