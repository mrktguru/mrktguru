"""
Node Executors for Warmup Scheduler
Individual, reusable functions for each warmup action type
"""
import asyncio
import random
import os
import logging
from datetime import datetime, timedelta
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest, UpdateNotifySettingsRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.folders import EditPeerFoldersRequest
from telethon.tl.types import InputPhoneContact, InputPeerNotifySettings, InputNotifyPeer, InputFolderPeer
from telethon.errors import FloodWaitError, ChannelPrivateError, UserBannedInChannelError
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
        
        # Sync from Telegram - PRESERVE existing values if Telegram returns None/empty
        await asyncio.sleep(random.uniform(2, 4))
        me = await client.get_me()
        
        # Only update if Telegram returned non-empty values
        if me.first_name and me.first_name.strip():
            account.first_name = me.first_name
        
        if me.last_name and me.last_name.strip():
            account.last_name = me.last_name
        # else: preserve existing last_name
        
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
        count = int(config.get('count', 5))
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
        count = int(config.get('count', 1))
        
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
        read_count = int(config.get('read_count', 5))
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
        read_count = int(config.get('read_count', 5))
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


async def execute_node_smart_subscribe(client, account_id, config):
    """
    Execute Smart Subscriber node - intelligent channel subscription with human-like behavior
    
    Config:
    {
        'target_entity': '@channel' or None,
        'random_count': 3,
        'pool_filter': 'Crypto_Base' or None,
        'posts_limit_min': 3,
        'posts_limit_max': 10,
        'read_speed_factor': 1.0,
        'comment_chance': 0.3,
        'view_media_chance': 0.5,
        'mute_target_chance': 0.5,
        'mute_random_chance': 1.0,
        'archive_random': True,
        'min_participants': 100,
        'exclude_dead_days': 7,
        'max_flood_wait_sec': 60
    }
    """
    from models.account import Account
    from models.channel_candidate import ChannelCandidate
    
    try:
        account = Account.query.get(account_id)
        if not account:
            return {'success': False, 'error': 'Account not found'}
        
        # Parse config with defaults
        target_entity = config.get('target_entity')
        random_count = int(config.get('random_count', 3))
        pool_filter = config.get('pool_filter')
        posts_min = int(config.get('posts_limit_min', 3))
        posts_max = int(config.get('posts_limit_max', 10))
        read_speed = float(config.get('read_speed_factor', 1.0))
        comment_chance = float(config.get('comment_chance', 0.3))
        view_media_chance = float(config.get('view_media_chance', 0.5))
        mute_target_chance = float(config.get('mute_target_chance', 0.5))
        mute_random_chance = float(config.get('mute_random_chance', 1.0))
        archive_random = config.get('archive_random', True)
        min_participants = int(config.get('min_participants', 100))
        exclude_dead_days = int(config.get('exclude_dead_days', 7))
        max_flood_wait = int(config.get('max_flood_wait_sec', 60))
        
        WarmupLog.log(account_id, 'info', f"Smart Subscriber starting: target={target_entity}, randoms={random_count}", action='smart_subscribe_start')
        
        # Build execution queue
        execution_queue = []
        
        # Add random channels from DB
        if random_count > 0:
            query = ChannelCandidate.query.filter_by(
                account_id=account_id,
                status='VISITED'
            ).filter(
                ChannelCandidate.type.in_(['CHANNEL', 'MEGAGROUP'])
            )
            
            # Apply pool filter
            if pool_filter:
                query = query.filter_by(pool_name=pool_filter)
            
            # Apply participant filter
            if min_participants:
                query = query.filter(ChannelCandidate.participants_count >= min_participants)
            
            # Apply dead channel filter
            if exclude_dead_days:
                threshold_date = datetime.utcnow() - timedelta(days=exclude_dead_days)
                query = query.filter(
                    db.or_(
                        ChannelCandidate.last_post_date >= threshold_date,
                        ChannelCandidate.last_post_date.is_(None)
                    )
                )
            
            # Apply "отлежались" filter (> 2 hours since last visit)
            two_hours_ago = datetime.utcnow() - timedelta(hours=2)
            query = query.filter(ChannelCandidate.last_visit_ts < two_hours_ago)
            
            # Order by creation date and limit
            random_channels = query.order_by(ChannelCandidate.created_at).limit(random_count).all()
            
            for ch in random_channels:
                execution_queue.append({
                    'entity': ch.username or f't.me/c/{ch.peer_id}',
                    'peer_id': ch.peer_id,
                    'access_hash': ch.access_hash,
                    'is_target': False,
                    'db_record': ch
                })
        
        # Add target entity if specified
        if target_entity:
            execution_queue.append({
                'entity': target_entity.replace('@', '').strip(),
                'is_target': True,
                'db_record': None
            })
        
        # Shuffle but ensure target is not first
        if len(execution_queue) > 1 and execution_queue[-1].get('is_target'):
            target_item = execution_queue.pop()
            random.shuffle(execution_queue)
            # Insert target at random position except first
            insert_pos = random.randint(1, len(execution_queue))
            execution_queue.insert(insert_pos, target_item)
        else:
            random.shuffle(execution_queue)
        
        if not execution_queue:
            return {'success': False, 'error': 'No channels to process (empty queue)'}
        
        WarmupLog.log(account_id, 'info', f"Execution queue: {len(execution_queue)} channels", action='queue_built')
        
        # Process each channel in queue
        for idx, item in enumerate(execution_queue):
            entity_str = item['entity']
            is_target = item.get('is_target', False)
            db_record = item.get('db_record')
            
            try:
                WarmupLog.log(account_id, 'info', f"[{idx+1}/{len(execution_queue)}] Processing: {entity_str}", action='channel_start')
                
                # Resolve entity
                # LOGIC: If we have access_hash, use Direct Access (mimic "Open from History")
                # Otherwise, resolve username (mimic "Search")
                try:
                    if item.get('peer_id') and item.get('access_hash'):
                        from telethon.tl.types import InputPeerChannel
                        entity = InputPeerChannel(int(item['peer_id']), int(item['access_hash']))
                        # Verify we can access it (and get updated info if needed) usually not needed for simple actions
                        # but get_messages accepts InputPeer
                    else:
                        entity = await client.get_entity(entity_str)
                except Exception as e:
                    WarmupLog.log(account_id, 'warning', f"Could not resolve {entity_str}: {e}", action='resolve_error')
                    continue
                
                # Pre-check: already subscribed?
                try:
                    full_channel = await client(GetFullChannelRequest(channel=entity))
                    if full_channel.full_chat.participant:
                        WarmupLog.log(account_id, 'info', f"Already subscribed to {entity_str}, skipping", action='already_subscribed')
                        if db_record:
                            db_record.status = 'SUBSCRIBED'
                            db.session.commit()
                        continue
                except:
                    pass  # Not subscribed, continue
                
                # Load history (last 20 messages)
                all_messages = await client.get_messages(entity, limit=20)
                if not all_messages:
                    WarmupLog.log(account_id, 'warning', f"No messages found in {entity_str}", action='no_messages')
                
                # Select N posts and reverse for chronological reading
                posts_count = random.randint(posts_min, min(posts_max, len(all_messages) if all_messages else posts_min))
                selected_messages = (all_messages[:posts_count] if all_messages else [])
                selected_messages.reverse()  # Oldest to newest
                
                WarmupLog.log(account_id, 'info', f"Reading {len(selected_messages)} posts from {entity_str}", action='reading_start')
                
                # Reading loop
                for msg in selected_messages:
                    # Calculate read time
                    text_length = len(msg.message) if msg.message else 50
                    base_read_time = (text_length / 20.0) * read_speed  # 20 chars/sec
                    
                    # Add media viewing time
                    if msg.media and random.random() < view_media_chance:
                        base_read_time += random.uniform(3, 6)
                    
                    # Read pause
                    await asyncio.sleep(base_read_time)
                    
                    # Explore comments (30% chance)
                    if msg.replies and msg.replies.replies > 0 and random.random() < comment_chance:
                        try:
                            WarmupLog.log(account_id, 'info', f"💬 Exploring comments ({msg.replies.replies} replies)", action='view_comments')
                            await asyncio.sleep(random.uniform(1, 2))  # Click pause
                            
                            comments = await client.get_messages(entity, reply_to=msg.id, limit=random.randint(5, 12))
                            await asyncio.sleep(random.uniform(5, 15))  # Read discussion
                            
                            # Occasionally view commenter profile
                            if comments and random.random() < 0.3:
                                comment = random.choice(comments)
                                if comment.sender_id:
                                    try:
                                        await asyncio.sleep(random.uniform(1, 2))
                                        await client.get_entity(comment.sender_id)
                                        await asyncio.sleep(random.uniform(4, 10))
                                    except:
                                        pass
                        except:
                            pass
                    
                    # Send read acknowledge (CRITICAL for Trust Score)
                    # 85% chance: mark latest, 15% chance: mark 2nd or 3rd from end (human pattern)
                    try:
                        if random.random() < 0.85:
                            await client.send_read_acknowledge(entity, message=msg)
                        else:
                            # Mark partial read (human left before finishing)
                            pass
                    except:
                        pass  # Non-critical
                
                # Decision pause before subscribing
                await asyncio.sleep(random.uniform(2, 5))
                
                # JOIN
                WarmupLog.log(account_id, 'info', f"Subscribing to {entity_str}...", action='subscribe_attempt')
                
                try:
                    await client(JoinChannelRequest(entity))
                    WarmupLog.log(account_id, 'success', f"✅ Subscribed to {entity_str}", action='subscribe_success')
                    
                except FloodWaitError as e:
                    # CRITICAL STOP - FLOOD_WAIT
                    wait_seconds = e.seconds
                    
                    if wait_seconds > max_flood_wait:
                        error_msg = f"FLOOD_WAIT {wait_seconds}s > max {max_flood_wait}s. Aborting."
                        WarmupLog.log(account_id, 'error', error_msg, action='flood_wait_abort')
                        
                        # Set account flood_wait status
                        account.status = 'flood_wait'
                        account.flood_wait_until = datetime.utcnow() + timedelta(seconds=wait_seconds)
                        account.flood_wait_action = 'smart_subscribe'
                        account.last_flood_wait = datetime.utcnow()
                        db.session.commit()
                        
                        return {
                            'success': False,
                            'error': error_msg,
                            'flood_wait': True,
                            'flood_wait_until': account.flood_wait_until
                        }
                    else:
                        # Wait and retry
                        WarmupLog.log(account_id, 'warning', f"FLOOD_WAIT {wait_seconds}s, waiting...", action='flood_wait')
                        await asyncio.sleep(wait_seconds + 1)
                        await client(JoinChannelRequest(entity))
                        WarmupLog.log(account_id, 'success', f"✅ Subscribed after flood wait", action='subscribe_success')
                
                except UserBannedInChannelError:
                    WarmupLog.log(account_id, 'warning', f"BANNED in {entity_str}, skipping", action='user_banned')
                    if db_record:
                        db_record.status = 'BANNED'
                        db_record.error_reason = 'USER_BANNED_IN_CHANNEL'
                        db.session.commit()
                    continue
                
                except Exception as join_error:
                    WarmupLog.log(account_id, 'error', f"Subscribe failed: {join_error}", action='subscribe_error')
                    continue
                
                # Post-processing: MUTE
                try:
                    should_mute = (not is_target and random.random() < mute_random_chance) or \
                                  (is_target and random.random() < mute_target_chance)
                    
                    if should_mute:
                        await asyncio.sleep(random.uniform(1, 2))
                        await client(UpdateNotifySettingsRequest(
                            peer=InputNotifyPeer(entity),
                            settings=InputPeerNotifySettings(mute_until=2147483647)  # Forever
                        ))
                        WarmupLog.log(account_id, 'info', f"🔕 Muted {entity_str}", action='mute')
                        
                        if db_record:
                            db_record.muted_at = datetime.utcnow()
                except Exception as e:
                    logger.warning(f"Mute failed for {entity_str}: {e}")
                
                # Post-processing: ARCHIVE
                try:
                    if archive_random and not is_target:
                        await asyncio.sleep(random.uniform(1, 2))
                        await client(EditPeerFoldersRequest([
                            InputFolderPeer(peer=entity, folder_id=1)  # folder_id=1 is Archive
                        ]))
                        WarmupLog.log(account_id, 'info', f"📁 Archived {entity_str}", action='archive')
                        
                        if db_record:
                            db_record.archived_at = datetime.utcnow()
                except Exception as e:
                    logger.warning(f"Archive failed for {entity_str}: {e}")
                
                # Update DB record
                if db_record:
                    db_record.status = 'SUBSCRIBED'
                    db_record.subscribed_at = datetime.utcnow()
                    db.session.commit()
                
                WarmupLog.log(account_id, 'success', f"Completed: {entity_str}", action='channel_complete')
                
                # Cooldown between channels (except last one)
                if idx < len(execution_queue) - 1:
                    cooldown_seconds = random.randint(120, 600)  # 2-10 min
                    WarmupLog.log(account_id, 'info', f"Cooldown: {cooldown_seconds//60} min", action='cooldown')
                    await asyncio.sleep(cooldown_seconds)
            
            except Exception as channel_error:
                logger.error(f"Error processing {entity_str}: {channel_error}")
                WarmupLog.log(account_id, 'error', f"Channel error: {str(channel_error)}", action='channel_error')
                continue
        
        WarmupLog.log(account_id, 'success', f"Smart Subscriber completed: {len(execution_queue)} channels processed", action='smart_subscribe_complete')
        return {'success': True, 'message': f'Processed {len(execution_queue)} channels'}
        
    except Exception as e:
        logger.error(f"Smart Subscriber failed: {e}")
        WarmupLog.log(account_id, 'error', f"Smart Subscriber failed: {str(e)}", action='smart_subscribe_error')
        return {'success': False, 'error': str(e)}



async def execute_node_passive_activity(client, account_id, config):
    """
    🧘 Node: Passive Activity (Universal).
    Combines "Tray Session" and "Passive Scroll".
    
    Logic:
    1. Bot goes Online.
    2. Stays online for duration_minutes.
    3. If enable_scroll is True — occasionally "wakes up", scrolls feed, then pauses.
    4. Otherwise — IDLE status (handled by SessionOrchestrator).
    
    Config JSON:
    {
        "duration_minutes": 60,       # Total duration
        "enable_scroll": true,        # Enable random scrolling?
        "scroll_count": 3,            # Number of scroll events (default: random 3-5)
        "scroll_duration_sec": 60     # Duration of each scroll (default: random 30-120)
    }
    """
    import asyncio
    import random
    import logging
    from datetime import datetime, timedelta
    from telethon.tl.functions.messages import GetDialogsRequest
    from telethon.tl.functions.account import UpdateStatusRequest
    from telethon.tl.types import InputPeerEmpty

    # --- 1. CONFIG PARSING ---
    duration_mins = int(config.get('duration_minutes', 30))
    total_seconds = duration_mins * 60
    
    enable_scroll = config.get('enable_scroll', False)
    
    # Generate scroll schedule
    scroll_events = []
    if enable_scroll:
        # Determine count (Range or fixed)
        count_min = int(config.get('scroll_count_min', 3))
        count_max = int(config.get('scroll_count_max', 6))
        count = random.randint(count_min, count_max)
        
        # Duration limits
        dur_min = int(config.get('scroll_duration_min', 30))
        dur_max = int(config.get('scroll_duration_max', 120))
        
        # Generate random start times
        # Buffer 2 mins at start/end
        if total_seconds > 300: # Only if session > 5 mins
            for _ in range(count):
                start_sec = random.randint(120, total_seconds - 120)
                duration = random.randint(dur_min, dur_max)
                scroll_events.append({
                    'start_at': start_sec,
                    'duration': duration,
                    'done': False
                })
            # Sort by time
            scroll_events.sort(key=lambda x: x['start_at'])

    logger.info(f"[{account_id}] 🧘 Starting Passive Activity for {duration_mins}m. "
                f"Scrolls scheduled: {len(scroll_events)}")
    
    # Log to DB
    WarmupLog.log(account_id, 'info', f"Starting Passive Activity ({duration_mins}m)", action='passive_start')

    start_time = datetime.now()

    try:
        # Initial Status Online
        await client(UpdateStatusRequest(offline=False))
        
        # === MAIN LOOP (SECONDLY) ===
        while True:
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # 1. Check total duration
            if elapsed >= total_seconds:
                break

            # 2. Check: time to scroll?
            current_scroll = None
            for event in scroll_events:
                # If time reached and not done
                if not event['done'] and elapsed >= event['start_at']:
                    current_scroll = event
                    break
            
            # === ACTIVE PHASE (SCROLLING) ===
            if current_scroll:
                logger.info(f"[{account_id}] 👀 Waking up to scroll feed for {current_scroll['duration']}s...")
                
                # 2.1. Explicitly set Online (in case we were Idle)
                await client(UpdateStatusRequest(offline=False))
                
                # 2.2. Scroll logic
                scroll_end_time = datetime.now() + timedelta(seconds=current_scroll['duration'])
                offset_id = 0
                offset_date = None
                
                while datetime.now() < scroll_end_time:
                    # Simulation of reading
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    
                    # Fetch dialogs
                    try:
                        await client(GetDialogsRequest(
                            offset_date=offset_date, offset_id=offset_id,
                            offset_peer=InputPeerEmpty(), limit=10, hash=0
                        ))
                    except Exception as e:
                        logger.debug(f"Scroll tick error: {e}")

                # 2.3. Finish scroll
                current_scroll['done'] = True
                logger.info(f"[{account_id}] 💤 Scroll finished. Going back to IDLE wait.")
                # We do NOT set offline=True manually.
                # Use natural timeout or Orchestrator IDLE logic.

            # === PASSIVE PHASE (IDLE WAIT) ===
            else:
                # Sleep short intervals to check timer
                await asyncio.sleep(5)
                
                # If > 3 mins inactivity, SessionOrchestrator handles IDLE state in background.

    except Exception as e:
        logger.error(f"[{account_id}] Passive Activity failed: {e}")
        return {'success': False, 'error': str(e)}

    logger.info(f"[{account_id}] 🧘 Activity finished. Shutting down.")
    return {'success': True, 'message': f'Completed {duration_mins}m session with {len(scroll_events)} scrolls'}


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
    'smart_subscribe': execute_node_smart_subscribe,
    'passive_activity': execute_node_passive_activity, # 🔥 United Passive Node
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
