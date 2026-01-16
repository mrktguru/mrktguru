"""
Warmup Routes
Backend routes for warmup system
"""
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, current_app
from werkzeug.utils import secure_filename
import os
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
from workers.warmup_worker import execute_stage_1_task, execute_stage_2_task, execute_stage_3_task
import asyncio
import random
import logging

# Logger will be used via current_app.logger in routes

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
    """Execute Stage 1: Profile setup via Celery (supports photo upload)"""
    import traceback
    try:
        current_app.logger.info(f"Received execute-profile request for account {account_id}")
        account = Account.query.get_or_404(account_id)
        
        # Handle both JSON and FormData
        if request.is_json:
            data = request.json
            current_app.logger.info("Parsing JSON data")
        else:
            data = request.form.to_dict()
            current_app.logger.info(f"Parsing FormData: {list(data.keys())}")
        
        # Validate required fields
        if not data.get('first_name'):
            current_app.logger.warning("First name missing in request")
            return jsonify({'success': False, 'error': 'First name is required'}), 400
        
        # Handle Photo upload
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo and photo.filename:
                filename = secure_filename(f"warmup_{account.id}_{photo.filename}")
                # Use absolute path for safety with Celery
                upload_dir = os.path.abspath(os.path.join(request.environ.get('PWD', os.getcwd()), 'uploads', 'photos'))
                os.makedirs(upload_dir, exist_ok=True)
                photo_path = os.path.join(upload_dir, filename)
                photo.save(photo_path)
                data['photo_path'] = photo_path
                current_app.logger.info(f"Photo saved for warmup at absolute path: {photo_path}")
            else:
                current_app.logger.info("Photo field present but no file selected or filename missing")
        
        # Trigger task
        execute_stage_1_task.apply_async((account_id, data))
        
        # Try to log but don't fail if DB is busy
        try:
            WarmupLog.log(account_id, 'info', 'Profile setup task queued', stage=1, action='queue_task')
        except Exception as log_err:
            current_app.logger.error(f"Failed to create WarmupLog: {log_err}")
        
        return jsonify({'success': True, 'message': 'Profile setup task started'})

    except Exception as e:
        error_trace = traceback.format_exc()
        current_app.logger.error(f"Error in execute_profile route: {error_trace}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== STAGE 2: CONTACTS ====================

@warmup_bp.route('/execute-contacts', methods=['POST'])
@login_required
def execute_contacts(account_id):
    """Execute Stage 2: Contacts setup via Celery"""
    data = request.json or {}
    phones = data.get('phones', [])
    
    # Trigger task
    execute_stage_2_task.apply_async((account_id, phones))
    
    WarmupLog.log(account_id, 'info', 'Contacts setup task queued', stage=2, action='queue_task')
    
    return jsonify({'success': True, 'message': 'Contacts setup task started'})


# ==================== STAGE 3: CHANNELS ====================

@warmup_bp.route('/search-channels', methods=['POST'])
@login_required
def search_channels(account_id):
    """Search for channels to join"""
    data = request.json
    query = data.get('query')
    
    if not query:
        return jsonify({'success': False, 'error': 'Query is required'}), 400
    
    # This one (search) should probably remain synchronous as it's quick
    # BUT we need to handle the loop correctly
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def search():
        client = get_telethon_client(account_id)
        try:
            async def search_action(client, account_id):
                result = await client(SearchRequest(q=query, limit=10))
                channels = []
                for chat in result.chats:
                    if hasattr(chat, 'username') and chat.username:
                        channels.append({
                            'id': chat.id,
                            'username': chat.username,
                            'title': chat.title,
                            'participants_count': getattr(chat, 'participants_count', 0)
                        })
                return {'success': True, 'results': channels}
            
            return await execute_warmup_action(client, account_id, search_action, estimated_duration=30)
        finally:
            if client.is_connected():
                await client.disconnect()

    try:
        result = loop.run_until_complete(search())
        return jsonify(result)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()


@warmup_bp.route('/add-channel', methods=['POST'])
@login_required
def add_channel(account_id):
    """Add a channel to warmup list"""
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
        action=data['action'],
        read_count=data['read_count']
    )
    
    db.session.add(channel)
    db.session.commit()
    
    WarmupLog.log(account_id, 'success', f'Channel added: @{data["username"]}', 
                stage=3, action='add_channel')
    
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
    """Execute Stage 3: Channels activities via Celery"""
    # Trigger task
    execute_stage_3_task.apply_async((account_id,))
    
    WarmupLog.log(account_id, 'info', 'Channels task queued', stage=3, action='queue_task')
    
    return jsonify({'success': True, 'message': 'Channels task started'})

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
            'id': f"act_{log.id}",
            'dt': log.timestamp,
            'ts': log.timestamp.timestamp(),
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
            'id': log.id,
            'dt': log.timestamp,
            'ts': log.timestamp.timestamp(),
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
