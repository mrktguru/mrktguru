import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import Config

# Store active clients to reuse them
_active_clients = {}


def get_telethon_client(account_id, proxy=None):
    """
    Get or create Telethon client for account
    
    Args:
        account_id: Account ID
        proxy: Proxy dict (optional)
    
    Returns:
        TelegramClient instance
    """
    from models.account import Account
    
    # Return cached client if exists
    if account_id in _active_clients:
        return _active_clients[account_id]
    
    account = Account.query.get(account_id)
    if not account:
        raise ValueError(f"Account {account_id} not found")
    
    # Get device profile
    device = account.device_profile
    
    # Build proxy dict for Telethon
    proxy_dict = None
    if proxy:
        import socks
        proxy_type = socks.SOCKS5 if proxy['type'] == 'socks5' else socks.HTTP
        proxy_dict = {
            'proxy_type': proxy_type,
            'addr': proxy['host'],
            'port': proxy['port'],
            'username': proxy.get('username'),
            'password': proxy.get('password'),
        }
    elif account.proxy:
        import socks
        proxy_type = socks.SOCKS5 if account.proxy.type == 'socks5' else socks.HTTP
        proxy_dict = {
            'proxy_type': proxy_type,
            'addr': account.proxy.host,
            'port': account.proxy.port,
            'username': account.proxy.username,
            'password': account.proxy.password,
        }
    
    # Create client
    client = TelegramClient(
        account.session_file_path,
        Config.TG_API_ID,
        Config.TG_API_HASH,
        proxy=proxy_dict,
        device_model=device.device_model if device else 'Desktop',
        system_version=device.system_version if device else 'Windows 10',
        app_version=device.app_version if device else '4.0.0',
        lang_code=device.lang_code if device else 'en',
        system_lang_code=device.system_lang_code if device else 'en-US',
    )
    
    # Cache client
    _active_clients[account_id] = client
    
    return client


async def connect_client(account_id):
    """Connect client if not connected"""
    client = get_telethon_client(account_id)
    if not client.is_connected():
        await client.connect()
    return client


async def disconnect_client(account_id):
    """Disconnect and remove client from cache"""
    if account_id in _active_clients:
        client = _active_clients[account_id]
        await client.disconnect()
        del _active_clients[account_id]


async def verify_session(account_id):
    """
    Verify session is valid by calling get_me()
    
    Returns:
        dict: {success: bool, user: dict or None, error: str or None}
    """
    try:
        client = await connect_client(account_id)
        me = await client.get_me()
        
        return {
            'success': True,
            'user': {
                'id': me.id,
                'username': me.username,
                'first_name': me.first_name,
                'last_name': me.last_name,
                'phone': me.phone,
            },
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'user': None,
            'error': str(e)
        }


async def get_channel_info(account_id, channel_username):
    """
    Get channel/group information
    
    Returns:
        dict: {success: bool, channel: dict, error: str}
    """
    try:
        client = await connect_client(account_id)
        entity = await client.get_entity(channel_username)
        
        # Check if we're admin
        is_admin = False
        admin_rights = None
        
        try:
            permissions = await client.get_permissions(entity)
            is_admin = permissions.is_admin
            if is_admin:
                admin_rights = {
                    'change_info': permissions.change_info,
                    'post_messages': permissions.post_messages,
                    'edit_messages': permissions.edit_messages,
                    'delete_messages': permissions.delete_messages,
                    'ban_users': permissions.ban_users,
                    'invite_users': permissions.invite_users,
                    'pin_messages': permissions.pin_messages,
                    'add_admins': permissions.add_admins,
                }
        except:
            pass
        
        return {
            'success': True,
            'channel': {
                'id': entity.id,
                'username': getattr(entity, 'username', None),
                'title': entity.title,
                'type': 'channel' if hasattr(entity, 'broadcast') and entity.broadcast else 'group',
                'participants_count': getattr(entity, 'participants_count', None),
                'is_admin': is_admin,
                'admin_rights': admin_rights,
            },
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'channel': None,
            'error': str(e)
        }


async def send_invite(account_id, channel_id, user_id):
    """
    Invite user to channel
    
    Returns:
        dict: {success: bool, error: str, error_type: str}
    """
    from telethon.errors import (
        FloodWaitError, UserPrivacyRestrictedError, 
        PeerFloodError, UserNotMutualContactError,
        UserChannelsTooMuchError
    )
    from telethon.tl.functions.channels import InviteToChannelRequest
    
    try:
        client = await connect_client(account_id)
        
        # Get entities
        user = await client.get_entity(user_id)
        channel = await client.get_entity(channel_id)
        
        # Send invite
        await client(InviteToChannelRequest(
            channel=channel,
            users=[user]
        ))
        
        return {
            'success': True,
            'error': None,
            'error_type': None
        }
        
    except FloodWaitError as e:
        return {
            'success': False,
            'error': f'FloodWait: {e.seconds}s',
            'error_type': 'flood_wait',
            'seconds': e.seconds
        }
    except UserPrivacyRestrictedError:
        return {
            'success': False,
            'error': 'User privacy settings restrict invites',
            'error_type': 'user_privacy'
        }
    except PeerFloodError:
        return {
            'success': False,
            'error': 'Too many requests, account limited',
            'error_type': 'peer_flood'
        }
    except UserNotMutualContactError:
        return {
            'success': False,
            'error': 'Not mutual contact',
            'error_type': 'not_mutual'
        }
    except UserChannelsTooMuchError:
        return {
            'success': False,
            'error': 'User is in too many channels',
            'error_type': 'user_channels_too_much'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'error_type': 'unknown'
        }


async def send_message(account_id, entity, message, media_path=None):
    """
    Send message to user or channel
    
    Returns:
        dict: {success: bool, message_id: int, error: str}
    """
    from telethon.errors import FloodWaitError, UserPrivacyRestrictedError
    
    try:
        client = await connect_client(account_id)
        
        # Send message
        message_obj = await client.send_message(
            entity=entity,
            message=message,
            file=media_path if media_path else None
        )
        
        return {
            'success': True,
            'message_id': message_obj.id,
            'error': None
        }
        
    except FloodWaitError as e:
        return {
            'success': False,
            'message_id': None,
            'error': f'FloodWait: {e.seconds}s',
            'error_type': 'flood_wait'
        }
    except UserPrivacyRestrictedError:
        return {
            'success': False,
            'message_id': None,
            'error': 'User privacy restricted',
            'error_type': 'user_privacy'
        }
    except Exception as e:
        return {
            'success': False,
            'message_id': None,
            'error': str(e),
            'error_type': 'unknown'
        }


async def parse_channel_members(account_id, channel_username, limit=None):
    """
    Parse members from channel
    
    Returns:
        list of dicts: [{user_id, username, first_name, last_name, ...}]
    """
    try:
        client = await connect_client(account_id)
        entity = await client.get_entity(channel_username)
        
        participants = await client.get_participants(entity, limit=limit)
        
        users = []
        for user in participants:
            users.append({
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': getattr(user, 'phone', None),
                'is_bot': user.bot,
                'is_premium': getattr(user, 'premium', False),
                'has_photo': user.photo is not None,
            })
        
        return {'success': True, 'users': users, 'error': None}
        
    except Exception as e:
        return {'success': False, 'users': [], 'error': str(e)}


def run_async(coroutine):
    """Helper to run async functions synchronously"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()
