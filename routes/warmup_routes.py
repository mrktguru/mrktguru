"""
Warmup Routes
Backend routes for warmup system
"""
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from utils.decorators import login_required
from database import db
from models.account import Account
from models.warmup_stage import WarmupStage
from models.warmup_action import WarmupAction
from models.warmup_channel import WarmupChannel
from models.warmup_settings import WarmupSettings
from models.warmup_log import WarmupLog
from utils.telethon_helper import get_telethon_client
from utils.warmup_executor import execute_warmup_action, emulate_typing
from telethon.tl.functions.contacts import SearchRequest, ImportContactsRequest, GetContactsRequest
from telethon.tl.functions.channels import GetFullChannelRequest, JoinChannelRequest
from telethon.tl.functions.account import UpdateProfileRequest, UpdateStatusRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.messages import SendMessageRequest
from telethon.tl.types import InputPhoneContact
import asyncio
import random
import logging

logger = logging.getLogger(__name__)

warmup_bp = Blueprint('warmup', __name__, url_prefix='/accounts/<int:account_id>/warmup')


# ==================== SETTINGS ====================

@warmup_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings(account_id):
    """Get or update warmup settings"""
    account = Account.query.get_or_404(account_id)
    
    if request.method == 'GET':
        # Get or create settings
        warmup_settings = WarmupSettings.query.filter_by(account_id=account_id).first()
        if not warmup_settings:
            warmup_settings = WarmupSettings(account_id=account_id)
            db.session.add(warmup_settings)
            db.session.commit()
        
        return jsonify({
            'privacy_phone': warmup_settings.privacy_phone,
            'privacy_photo': warmup_settings.privacy_photo,
            'language': warmup_settings.language,
            'warmup_enabled': warmup_settings.warmup_enabled,
            'current_stage': warmup_settings.current_stage
        })
    
    else:  # POST
        data = request.json
        
        warmup_settings = WarmupSettings.query.filter_by(account_id=account_id).first()
        if not warmup_settings:
            warmup_settings = WarmupSettings(account_id=account_id)
            db.session.add(warmup_settings)
        
        # Update settings
        if 'privacy_phone' in data:
            warmup_settings.privacy_phone = data['privacy_phone']
        if 'privacy_photo' in data:
            warmup_settings.privacy_photo = data['privacy_photo']
        if 'language' in data:
            warmup_settings.language = data['language']
        if 'warmup_enabled' in data:
            warmup_settings.warmup_enabled = data['warmup_enabled']
        
        db.session.commit()
        
        WarmupLog.log(account_id, 'success', 'Settings updated', stage=0, action='update_settings')
        
        return jsonify({'success': True})


# ==================== STAGE 1: PROFILE ====================

@warmup_bp.route('/execute-profile', methods=['POST'])
@login_required
def execute_profile(account_id):
    """Execute Stage 1: Profile setup"""
    account = Account.query.get_or_404(account_id)
    data = request.json
    
    # Validate required fields
    if not data.get('first_name'):
        return jsonify({'success': False, 'error': 'First name is required'}), 400
    
    db.session.close()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def setup_profile():
        client = get_telethon_client(account_id)
        
        try:
            async def profile_action(client, account_id):
                # Fetch account again within the action context if needed, 
                # but we can use the snapshot we take before session close
                
                # First name (required)
                new_first_name = data.get('first_name')
                if new_first_name and new_first_name != account.first_name:
                    await emulate_typing(new_first_name, 'slow', account_id)
                    await client(UpdateProfileRequest(first_name=new_first_name))
                    await asyncio.sleep(random.uniform(3, 8))
                    WarmupLog.log(account_id, 'success', f"First name set: {new_first_name}", stage=1, action='set_first_name')
                
                # Last name (optional)
                new_last_name = data.get('last_name')
                if new_last_name is not None and new_last_name != account.last_name:
                    await asyncio.sleep(random.uniform(60, 120))
                    await emulate_typing(new_last_name, 'slow', account_id)
                    await client(UpdateProfileRequest(last_name=new_last_name))
                    await asyncio.sleep(random.uniform(3, 8))
                    WarmupLog.log(account_id, 'success', f"Last name set: {new_last_name}", stage=1, action='set_last_name')
                
                # Username (optional)
                new_username = data.get('username', '').replace('@', '').strip()
                if new_username and new_username != account.username:
                    await asyncio.sleep(random.uniform(60, 120))
                    await emulate_typing(new_username, 'normal', account_id)
                    await client(UpdateUsernameRequest(username=new_username))
                    await asyncio.sleep(random.uniform(3, 8))
                    WarmupLog.log(account_id, 'success', f"Username set: @{new_username}", stage=1, action='set_username')

                # Bio (optional)
                new_bio = data.get('bio')
                if new_bio is not None and new_bio != account.bio:
                    await asyncio.sleep(random.uniform(30, 60))
                    await emulate_typing(new_bio, 'normal', account_id)
                    await client(UpdateProfileRequest(about=new_bio))
                    await asyncio.sleep(random.uniform(2, 5))
                    WarmupLog.log(account_id, 'success', 'Bio updated', stage=1, action='set_bio')
                
                # Photo (optional)
                if data.get('photo_path'):
                    await asyncio.sleep(random.uniform(10, 30))
                    photo = await client.upload_file(data['photo_path'])
                    await client(UploadProfilePhotoRequest(photo))
                    await asyncio.sleep(random.uniform(2, 5))
                    WarmupLog.log(account_id, 'success', 'Photo uploaded', stage=1, action='set_photo')
                
                return {'success': True}
            
            result = await execute_warmup_action(client, account_id, profile_action, estimated_duration=300)
            return result
            
        finally:
            if client.is_connected():
                await client.disconnect()
    
    try:
        result = loop.run_until_complete(setup_profile())
        
        # Mark stage as completed
        stage = WarmupStage.query.filter_by(account_id=account_id, stage_number=1).first()
        if stage:
            stage.mark_completed()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Profile setup failed: {e}", exc_info=True)
        WarmupLog.log(account_id, 'error', f'Profile setup failed: {str(e)}', stage=1)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()
# ==================== STAGE 2: CONTACTS ====================

@warmup_bp.route('/execute-contacts', methods=['POST'])
@login_required
def execute_contacts(account_id):
    """Execute Stage 2: Contacts import and activity"""
    account = Account.query.get_or_404(account_id)
    data = request.json or {}
    phone_numbers = data.get('phones', [])
    
    db.session.close()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def setup_contacts():
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
                    
                    # Import in small batches if many
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
                logger.info(f"Account {account_id}: Sending saved message: {text}")
                await emulate_typing(text, 'fast', account_id)
                await client.send_message('me', text)
                WarmupLog.log(account_id, 'success', "Sent message to Saved Messages", stage=2, action='send_saved_message')
                
                return {'success': True}
            
            result = await execute_warmup_action(client, account_id, contacts_action, estimated_duration=300)
            return result
            
        finally:
            if client.is_connected():
                await client.disconnect()
    
    try:
        result = loop.run_until_complete(setup_contacts())
        
        # Mark stage as completed
        stage = WarmupStage.query.filter_by(account_id=account_id, stage_number=2).first()
        if stage:
            stage.mark_completed()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Contacts warmup failed: {e}", exc_info=True)
        WarmupLog.log(account_id, 'error', f'Contacts warmup failed: {str(e)}', stage=2)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()


# ==================== STAGE 3: CHANNELS ====================

@warmup_bp.route('/search-channels', methods=['POST'])
@login_required
def search_channels(account_id):
    """Search for channels/groups"""
    account = Account.query.get_or_404(account_id)
    data = request.json
    query = data.get('query', '')
    
    if not query:
        return jsonify({'success': False, 'error': 'Query is required'}), 400
    
    db.session.close()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def search():
        client = get_telethon_client(account_id)
        
        try:
            async def search_action(client, account_id):
                # Emulate typing search query
                await emulate_typing(query, 'normal', account_id)
                
                # Search
                results = await client(SearchRequest(q=query, limit=20))
                
                channels = []
                for chat in results.chats:
                    if hasattr(chat, 'username'):
                        channels.append({
                            'id': chat.id,
                            'username': chat.username,
                            'title': chat.title,
                            'participants_count': getattr(chat, 'participants_count', 0)
                        })
                
                WarmupLog.log(account_id, 'success', f'Found {len(channels)} channels for "{query}"', 
                            stage=3, action='search_channels', details={'query': query, 'count': len(channels)})
                
                return {'success': True, 'results': channels}
            
            result = await execute_warmup_action(client, account_id, search_action, estimated_duration=30)
            return result
            
        finally:
            if client.is_connected():
                await client.disconnect()
    
    try:
        result = loop.run_until_complete(search())
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Channel search failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()


@warmup_bp.route('/add-channel', methods=['POST'])
@login_required
def add_channel(account_id):
    """Add a channel to warmup list"""
    account = Account.query.get_or_404(account_id)
    data = request.json
    
    # Validate
    required = ['channel_id', 'username', 'action', 'read_count']
    if not all(k in data for k in required):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    # Create channel record
    channel = WarmupChannel(
        account_id=account_id,
        channel_id=data['channel_id'],
        username=data['username'],
        title=data.get('title'),
        search_query=data.get('search_query'),
        action=data['action'],
        read_count=data['read_count']
    )
    
    db.session.add(channel)
    db.session.commit()
    
    WarmupLog.log(account_id, 'success', f'Channel added: @{data["username"]}', 
                stage=3, action='add_channel', details={'username': data['username']})
    
    return jsonify({'success': True, 'channel_id': channel.id})


@warmup_bp.route('/remove-channel/<int:channel_id>', methods=['POST'])
@login_required
def remove_channel(account_id, channel_id):
    """Remove a channel from warmup list"""
    channel = WarmupChannel.query.filter_by(id=channel_id, account_id=account_id).first_or_404()
    
    db.session.delete(channel)
    db.session.commit()
    
    WarmupLog.log(account_id, 'success', f'Channel removed: @{channel.username}', stage=3, action='remove_channel')
    
    return jsonify({'success': True})


@warmup_bp.route('/execute-channels', methods=['POST'])
@login_required
def execute_channels(account_id):
    """Execute Stage 3: Process all channels"""
    account = Account.query.get_or_404(account_id)
    
    # Get pending channels
    channels = WarmupChannel.query.filter_by(account_id=account_id, status='pending').all()
    
    if not channels:
        return jsonify({'success': False, 'error': 'No channels to process'}), 400
    
    db.session.close()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def process_channels():
        client = get_telethon_client(account_id)
        results = []
        
        try:
            for channel_config in channels:
                async def channel_action(client, account_id):
                    # Get channel entity
                    channel = await client.get_entity(channel_config.username)
                    
                    # Read posts
                    messages = await client.get_messages(channel, limit=channel_config.read_count)
                    
                    for i, msg in enumerate(messages):
                        from utils.warmup_executor import calculate_read_time
                        read_time = calculate_read_time(msg)
                        await asyncio.sleep(read_time)
                        
                        if i % 3 == 0:
                            from telethon.tl.functions.account import UpdateStatusRequest
                            await client(UpdateStatusRequest(offline=False))
                    
                    # Subscribe if needed
                    subscribed = False
                    if channel_config.action == 'subscribe':
                        await asyncio.sleep(random.uniform(2, 5))
                        await client(JoinChannelRequest(channel))
                        subscribed = True
                    
                    return {
                        'posts_read': len(messages),
                        'subscribed': subscribed
                    }
                
                try:
                    channel_config.mark_in_progress()
                    result = await execute_warmup_action(client, account_id, channel_action, estimated_duration=300)
                    channel_config.mark_completed(result['posts_read'], result['subscribed'])
                    results.append({'channel': channel_config.username, 'success': True})
                    
                except Exception as e:
                    channel_config.mark_failed(str(e))
                    results.append({'channel': channel_config.username, 'success': False, 'error': str(e)})
                
                # Pause between channels
                await asyncio.sleep(random.uniform(300, 600))
            
            return {'success': True, 'results': results}
            
        finally:
            if client.is_connected():
                await client.disconnect()
    
    try:
        result = loop.run_until_complete(process_channels())
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Channel processing failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()

# ==================== STAGE 4: ACTIVITY ====================

@warmup_bp.route('/execute-activity', methods=['POST'])
@login_required
def execute_activity(account_id):
    """Execute Stage 4: Random activity simulation"""
    return jsonify({
        'success': True, 
        'message': 'Activity simulation started (background)'
    })


@warmup_bp.route('/logs', methods=['GET'])
@login_required
def get_logs(account_id):
    """Get combined activity logs for warmup section"""
    from models.activity_log import AccountActivityLog
    
    # Get last 20 AccountActivityLog entries
    activity_logs = AccountActivityLog.query.filter_by(
        account_id=account_id
    ).order_by(AccountActivityLog.timestamp.desc()).limit(20).all()
    
    # Get last 20 WarmupLog entries
    warmup_logs = WarmupLog.query.filter_by(
        account_id=account_id
    ).order_by(WarmupLog.timestamp.desc()).limit(20).all()
    
    # Combine logs with original timestamps for sorting
    raw_logs = []
    
    # Add activity logs
    for log in activity_logs:
        raw_logs.append({
            'dt': log.timestamp,
            'timestamp': log.timestamp.strftime('%d.%m.%Y %H:%M:%S'),
            'action_type': log.action_type,
            'category': log.action_category or 'system',
            'status': log.status,
            'description': log.description or '',
            'source': 'activity'
        })
    
    # Add warmup logs
    for log in warmup_logs:
        raw_logs.append({
            'dt': log.timestamp,
            'timestamp': log.timestamp.strftime('%d.%m.%Y %H:%M:%S'),
            'action_type': log.action_type or 'warmup',
            'category': 'warmup',
            'status': log.status,
            'description': log.message,
            'source': 'warmup',
            'stage': log.stage_number
        })
    
    # Sort by datetime object (newest first)
    raw_logs.sort(key=lambda x: x['dt'], reverse=True)
    
    # Remove temporary 'dt' key and return last 20
    final_logs = []
    for log in raw_logs[:20]:
        del log['dt']
        final_logs.append(log)
        
    return jsonify({'logs': final_logs})
