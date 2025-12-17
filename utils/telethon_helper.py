import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import Config

# DO NOT store active clients - always create fresh ones
_active_clients = {}


def get_telethon_client(account_id, proxy=None):
    """
    Get or create Telethon client for account
    Always creates a NEW client to avoid event loop conflicts
    """
    from models.account import Account
    from database import db
    
    account = Account.query.get(account_id)
    if not account:
        raise ValueError(f"Account {account_id} not found")
    
    # Get device profile
    device = account.device_profile
    
    # Build proxy dict for Telethon
    proxy_dict = None
    if proxy:
        import socks
        proxy_type = socks.SOCKS5 if proxy["type"] == "socks5" else socks.HTTP
        proxy_dict = {
            "proxy_type": proxy_type,
            "addr": proxy["host"],
            "port": proxy["port"],
            "username": proxy.get("username"),
            "password": proxy.get("password"),
        }
    elif account.proxy:
        import socks
        proxy_type = socks.SOCKS5 if account.proxy.type == "socks5" else socks.HTTP
        proxy_dict = {
            "proxy_type": proxy_type,
            "addr": account.proxy.host,
            "port": account.proxy.port,
            "username": account.proxy.username,
            "password": account.proxy.password,
        }
    
    # Create client
    client = TelegramClient(
        account.session_file_path,
        Config.TG_API_ID,
        Config.TG_API_HASH,
        device_model=device.device_model if device else "Desktop",
        system_version=device.system_version if device else "Windows 10",
        app_version=device.app_version if device else "1.0",
        lang_code=device.lang_code if device else "en",
        system_lang_code=device.system_lang_code if device else "en-US",
        proxy=proxy_dict
    )
    
    return client


async def connect_client(account_id):
    """Connect Telethon client"""
    client = get_telethon_client(account_id)
    if not client.is_connected():
        await client.connect()
    return client


async def verify_session(account_id):
    """
    Verify that session is valid
    
    Returns:
        dict: {"success": bool, "user": User object or None, "error": str}
    """
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        me = await client.get_me()
        return {
            "success": True,
            "user": me,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "user": None,
            "error": str(e)
        }
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def send_invite(account_id, channel_username, target_user_id):
    """Send invite to user"""
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        channel = await client.get_entity(channel_username)
        await client(AddChatUserRequest(
            chat_id=channel.id,
            user_id=target_user_id,
            fwd_limit=0
        ))
        
        return {"success": True, "error": None}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def send_dm(account_id, username, text, media_path=None):
    """Send DM to user"""
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        user = await client.get_entity(username)
        
        if media_path:
            await client.send_file(user, media_path, caption=text)
        else:
            await client.send_message(user, text)
        
        return {"success": True, "message_id": None, "error": None}
    except Exception as e:
        return {"success": False, "message_id": None, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def parse_channel_members(account_id, channel_username, filters=None):
    """Parse channel members"""
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        channel = await client.get_entity(channel_username)
        members = []
        
        async for user in client.iter_participants(channel, limit=None):
            if filters:
                if filters.get("skip_bots") and user.bot:
                    continue
                if filters.get("only_with_username") and not user.username:
                    continue
                if filters.get("only_with_photo") and not user.photo:
                    continue
            
            members.append({
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "is_bot": user.bot,
                "is_premium": getattr(user, "premium", False)
            })
        
        return {"success": True, "members": members, "error": None}
    except Exception as e:
        return {"success": False, "members": [], "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def get_channel_messages(account_id, channel_username, limit=100):
    """Get channel messages"""
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        channel = await client.get_entity(channel_username)
        messages = []
        
        async for message in client.iter_messages(channel, limit=limit):
            messages.append({
                "message_id": message.id,
                "text": message.text,
                "date": message.date,
                "views": message.views
            })
        
        return {"success": True, "messages": messages, "error": None}
    except Exception as e:
        return {"success": False, "messages": [], "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def send_channel_message(account_id, channel_username, text, media_path=None, pin=False):
    """Send message to channel"""
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        channel = await client.get_entity(channel_username)
        
        if media_path:
            message = await client.send_file(channel, media_path, caption=text)
        else:
            message = await client.send_message(channel, text)
        
        if pin:
            await client.pin_message(channel, message)
        
        return {"success": True, "message_id": message.id, "error": None}
    except Exception as e:
        return {"success": False, "message_id": None, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


def cleanup_clients():
    """Cleanup all active clients"""
    for client in _active_clients.values():
        if client.is_connected():
            client.disconnect()
    _active_clients.clear()
