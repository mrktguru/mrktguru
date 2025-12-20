import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import Config
from telethon.tl.functions.messages import AddChatUserRequest

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


async def send_invite(account_id, channel_username, target_user_id=None, target_username=None):
    """Send invite to user with detailed error handling"""
    from telethon.errors import (
        UserPrivacyRestrictedError,
        UserNotMutualContactError, 
        UserChannelsTooMuchError,
        UserAlreadyParticipantError,
        UserIdInvalidError,
        PeerFloodError,
        FloodWaitError,
        ChatAdminRequiredError,
        ChatWriteForbiddenError,
        ChannelPrivateError,
        UserBannedInChannelError
    )
    from telethon.tl.functions.channels import InviteToChannelRequest
    
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        # Get channel entity
        channel = await client.get_entity(channel_username)
        
        # Get user entity (try user_id first, fallback to username)
        if target_user_id:
            try:
                user = await client.get_entity(int(target_user_id))
            except Exception as e:
                print(f"Failed to get user by ID {target_user_id}: {e}, trying username")
                if target_username:
                    try:
                        user = await client.get_entity(target_username)
                    except Exception as e2:
                        return {"status": "error", "error": f"Failed to resolve user: {e2}", "error_type": "user_not_found"}
                else:
                    return {"status": "error", "error": f"Invalid user ID: {e}", "error_type": "user_not_found"}
        elif target_username:
            try:
                user = await client.get_entity(target_username)
            except Exception as e:
                print(f"Failed to get user by username {target_username}: {e}")
                return {"status": "error", "error": f"User not found: {e}", "error_type": "user_not_found"}
        else:
            return {"status": "error", "error": "No user_id or username provided", "error_type": "missing_user_info"}
        
        # Invite to channel (supergroup)
        await client(InviteToChannelRequest(
            channel=channel,
            users=[user]
        ))
        
        return {
            "status": "success", 
            "error": None,
            "error_type": None
        }
        
    except UserAlreadyParticipantError:
        return {
            "status": "already_member",
            "error": "User already in group",
            "error_type": "already_member"
        }
        
    except UserPrivacyRestrictedError:
        return {
            "status": "privacy_restricted",
            "error": "User privacy settings prevent invites",
            "error_type": "privacy_restricted"
        }
        
    except UserNotMutualContactError:
        return {
            "status": "not_mutual_contact",
            "error": "User requires mutual contact",
            "error_type": "not_mutual_contact"
        }
        
    except UserChannelsTooMuchError:
        return {
            "status": "too_many_channels",
            "error": "User joined too many channels",
            "error_type": "too_many_channels"
        }
        
    except UserIdInvalidError:
        return {
            "status": "invalid_user",
            "error": "Invalid user ID",
            "error_type": "invalid_user"
        }
        
    except PeerFloodError:
        return {
            "status": "flood_wait",
            "error": "Too many requests, account limited",
            "error_type": "peer_flood"
        }
        
    except FloodWaitError as e:
        return {
            "status": "flood_wait",
            "error": f"Flood wait {e.seconds} seconds",
            "error_type": "flood_wait",
            "wait_seconds": e.seconds
        }
        
    except UserBannedInChannelError:
        return {
            "status": "banned",
            "error": "User banned in channel",
            "error_type": "banned"
        }
        
    except ChatAdminRequiredError:
        return {
            "status": "no_permission",
            "error": "Account needs admin rights",
            "error_type": "no_admin"
        }
        
    except ChannelPrivateError:
        return {
            "status": "channel_private",
            "error": "Channel is private",
            "error_type": "channel_private"
        }
        
    except Exception as e:
        error_msg = str(e)
        
        # Detect "Could not find the input entity"
        if "Could not find the input entity" in error_msg:
            return {
                "status": "user_not_found",
                "error": "User not found or deleted",
                "error_type": "user_not_found"
            }
        
        return {
            "status": "failed",
            "error": error_msg,
            "error_type": "unknown"
        }
        
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


async def get_channel_info(account_id, channel_username):
    """
    Get channel/group information
    Returns dict with channel details or error
    """
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        # Try to get entity
        entity = None
        for fmt in [f"@{channel_username}", channel_username, f"https://t.me/{channel_username}"]:
            try:
                entity = await client.get_entity(fmt)
                break
            except:
                continue
        
        if not entity:
            return {"success": False, "error": f"Could not find channel: {channel_username}"}
        
        # Get channel details
        from telethon.tl.types import Channel, Chat
        
        channel_type = "channel"
        if isinstance(entity, Channel):
            if entity.megagroup:
                channel_type = "megagroup"
            elif entity.broadcast:
                channel_type = "channel"
            else:
                channel_type = "group"
        elif isinstance(entity, Chat):
            channel_type = "group"
        
        # Check admin rights
        is_admin = False
        admin_rights = None
        try:
            full_channel = await client.get_entity(entity)
            is_admin = getattr(full_channel, "admin_rights", None) is not None
            if is_admin:
                admin_rights = str(full_channel.admin_rights)
        except:
            pass
        
        return {
            "success": True,
            "channel": {
                "id": entity.id,
                "title": getattr(entity, "title", channel_username),
                "username": channel_username,
                "type": channel_type,
                "is_admin": is_admin,
                "admin_rights": admin_rights,
                "participants_count": getattr(entity, "participants_count", 0)
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


# ==================== WARMUP FUNCTIONS ====================

async def read_channel_posts(account_id, channel_username, count=10, delay_between=5):
    """
    Read posts from a channel (mark as read)
    
    Args:
        account_id: Account ID
        channel_username: Channel to read from
        count: Number of posts to read
        delay_between: Delay between reading posts (seconds)
    
    Returns:
        dict: {success, posts_read, error}
    """
    import random
    import asyncio
    
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        # Get channel entity
        channel = await client.get_entity(channel_username)
        
        # Get messages
        messages = []
        async for message in client.iter_messages(channel, limit=count):
            messages.append(message)
        
        if not messages:
            return {"success": True, "posts_read": 0, "error": None}
        
        # Mark messages as read with delays
        posts_read = 0
        for message in messages:
            try:
                await client.send_read_acknowledge(channel, message)
                posts_read += 1
                
                # Random delay to simulate human reading
                if delay_between > 0 and posts_read < len(messages):
                    await asyncio.sleep(random.uniform(delay_between * 0.5, delay_between * 1.5))
            except Exception as e:
                print(f"Error marking message as read: {e}")
                continue
        
        return {"success": True, "posts_read": posts_read, "error": None}
        
    except Exception as e:
        return {"success": False, "posts_read": 0, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def join_channel_for_warmup(account_id, channel_username):
    """
    Join a channel for warmup purposes
    
    Args:
        account_id: Account ID
        channel_username: Channel to join
    
    Returns:
        dict: {success, already_member, error}
    """
    from telethon.tl.functions.channels import JoinChannelRequest
    from telethon.errors import (
        ChannelPrivateError,
        UserAlreadyParticipantError,
        FloodWaitError
    )
    
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        # Get channel entity
        channel = await client.get_entity(channel_username)
        
        # Try to join
        try:
            await client(JoinChannelRequest(channel))
            return {"success": True, "already_member": False, "error": None}
        except UserAlreadyParticipantError:
            return {"success": True, "already_member": True, "error": None}
        except FloodWaitError as e:
            return {"success": False, "already_member": False, "error": f"FloodWait: {e.seconds}s", "wait_seconds": e.seconds}
        except ChannelPrivateError:
            return {"success": False, "already_member": False, "error": "Channel is private"}
            
    except Exception as e:
        return {"success": False, "already_member": False, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def react_to_post(account_id, channel_username, message_id=None, reaction="👍"):
    """
    React to a post in a channel
    
    Args:
        account_id: Account ID
        channel_username: Channel with the post
        message_id: Specific message ID (if None, react to latest post)
        reaction: Emoji reaction to send
    
    Returns:
        dict: {success, error}
    """
    from telethon.tl.functions.messages import SendReactionRequest
    from telethon.tl.types import ReactionEmoji
    
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        # Get channel entity
        channel = await client.get_entity(channel_username)
        
        # Get message to react to
        if message_id is None:
            # Get latest message
            async for message in client.iter_messages(channel, limit=1):
                message_id = message.id
                break
        
        if message_id is None:
            return {"success": False, "error": "No messages in channel"}
        
        # Send reaction
        await client(SendReactionRequest(
            peer=channel,
            msg_id=message_id,
            reaction=[ReactionEmoji(emoticon=reaction)]
        ))
        
        return {"success": True, "error": None}
        
    except Exception as e:
        error_msg = str(e)
        # Reactions might not be enabled on this channel
        if "REACTION_INVALID" in error_msg or "REACTIONS_TOO_MANY" in error_msg:
            return {"success": False, "error": "Reactions not allowed on this channel"}
        return {"success": False, "error": error_msg}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def send_conversation_message(account_id, target_account_id, message_text):
    """
    Send a message to another account (for warmup conversations)
    
    Args:
        account_id: Sender account ID
        target_account_id: Receiver account ID
        message_text: Message to send
    
    Returns:
        dict: {success, message_id, error}
    """
    from models.account import Account
    
    client = None
    try:
        # Get target account's Telegram ID or username
        target_account = Account.query.get(target_account_id)
        if not target_account:
            return {"success": False, "message_id": None, "error": "Target account not found"}
        
        # We need either telegram_id or username to send a message
        target_identifier = target_account.telegram_id or target_account.username
        if not target_identifier:
            return {"success": False, "message_id": None, "error": "Target account has no Telegram ID or username"}
        
        client = get_telethon_client(account_id)
        await client.connect()
        
        # Get target user entity
        if target_account.telegram_id:
            user = await client.get_entity(int(target_account.telegram_id))
        else:
            user = await client.get_entity(target_account.username)
        
        # Send message
        message = await client.send_message(user, message_text)
        
        return {"success": True, "message_id": message.id, "error": None}
        
    except Exception as e:
        return {"success": False, "message_id": None, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()

