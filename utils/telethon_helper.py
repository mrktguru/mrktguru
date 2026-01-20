import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import Config
from telethon.tl.functions.messages import AddChatUserRequest

# DO NOT store active clients - always create fresh ones
_active_clients = {}

# Official App APIs (to avoid "Automated" flags)
# Using these makes the client look like the official app
OFFICIAL_APIS = {
    'ios': {
        'api_id': 6,
        'api_hash': "eb06d4abfb49dc3eeb1aeb98ae0f581e"
    },
    'android': {
        'api_id': 4,
        'api_hash': "014b35b6184100b085b0d0572f9b5103"
    },
    'desktop': {
        'api_id': 2040,
        'api_hash': "b18441a1ff607e10a989891a54616e98"
    }
}


def get_telethon_client(account_id, proxy=None):
    """
    Get or create Telethon client for account
    Always creates a NEW client to avoid event loop conflicts
    Uses TData metadata and selected API credentials if available
    """
    from models.account import Account
    from models.api_credential import ApiCredential
    from database import db
    from utils.encryption import decrypt_api_hash
    
    account = Account.query.get(account_id)
    if not account:
        raise ValueError(f"Account {account_id} not found")
    
    
    # ==================== API CREDENTIALS SELECTION ====================
    # Priority: Selected API Credential > Original from TData > Config fallback
    
    if account.api_credential_id:
        # Use selected API credential from manager
        api_cred = ApiCredential.query.get(account.api_credential_id)
        if api_cred:
            api_id = api_cred.api_id
            api_hash = decrypt_api_hash(api_cred.api_hash)
            print(f"✅ Using selected API credential: {api_cred.name} (ID: {api_id})")
        else:
            # Fallback to config
            api_id = Config.TG_API_ID
            api_hash = Config.TG_API_HASH
            print(f"⚠️ API credential not found, using config")
    
    elif account.tdata_metadata and account.tdata_metadata.original_api_id:
        # Use original API from TData
        tdata = account.tdata_metadata
        api_id = tdata.original_api_id
        api_hash = decrypt_api_hash(tdata.original_api_hash) if tdata.original_api_hash else Config.TG_API_HASH
        print(f"✅ Using original API from TData (ID: {api_id})")
    
    else:
        # Fallback to config
        api_id = Config.TG_API_ID
        api_hash = Config.TG_API_HASH
        print(f"ℹ️ Using API from config (ID: {api_id})")
    
    # ==================== DEVICE FINGERPRINT ====================
    # Priority: TData exact fingerprint > DeviceProfile > Defaults
    
    if account.tdata_metadata:
        # Use EXACT device info from TData
        tdata = account.tdata_metadata
        device_model = tdata.device_model or "Desktop"
        system_version = tdata.system_version or "Windows 10"
        app_version = tdata.app_version or "1.0"
        lang_code = tdata.lang_code or "en"
        system_lang_code = tdata.system_lang_code or "en-US"
        print(f"✅ Using exact device fingerprint from TData: {device_model}")
    
    elif account.device_profile:
        # Use device profile (for .session uploads)
        device = account.device_profile
        device_model = device.device_model
        system_version = device.system_version
        app_version = device.app_version
        lang_code = device.lang_code
        system_lang_code = device.system_lang_code
        print(f"ℹ️ Using device profile: {device_model}")
    
    else:
        # Fallback defaults
        device_model = "Desktop"
        system_version = "Windows 10"
        app_version = "1.0"
        lang_code = "en"
        system_lang_code = "en-US"
        print(f"⚠️ Using default device fingerprint")
    
    # ==================== PROXY CONFIGURATION ====================
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
        
        # CRITICAL: Import socks module FIRST
        # Telethon requires actual socks.SOCKS5/HTTP objects, NOT integers!
        if account.proxy.type == "socks5":
            proxy_type_obj = socks.SOCKS5
        else:
            proxy_type_obj = socks.HTTP
        
        # Format: (proxy_type, addr, port, rdns, username, password)
        proxy_dict = (
            proxy_type_obj,  # Use actual socks.SOCKS5 object, not integer!
            account.proxy.host,
            account.proxy.port,
            True,  # rdns - resolve DNS through proxy
            account.proxy.username,
            account.proxy.password
        )
        print(f"✅ Using proxy for account {account_id}: {account.proxy.host}:{account.proxy.port} (type: {account.proxy.type})")
        
        # CRITICAL DEBUG: Log exact proxy tuple
        with open('/tmp/proxy_debug.log', 'a') as f:
            f.write(f"PROXY TUPLE PASSED TO TELETHON: {proxy_dict}\n")
            f.write(f"PROXY TYPE OBJECT: {proxy_type_obj} (type: {type(proxy_type_obj)})\n")
    
    # ==================== SESSION CONFIGURATION ====================
    # Support both StringSession (DB storage) and SQLite file (TData import)
    session = None
    
    if account.session_string:
        # Preferred: StringSession stored in DB
        session = StringSession(account.session_string)
        print(f"DEBUG: Using StringSession for account {account_id}")
    elif account.session_file_path:
        # Legacy/TData: SQLite file path
        # Ensure path is absolute
        if os.path.isabs(account.session_file_path):
            session_path = account.session_file_path
        else:
            # Assuming relative to app root or check existence
            session_path = os.path.abspath(account.session_file_path)
            
        print(f"DEBUG: Checking session file: {session_path}")
        
        if os.path.exists(session_path):
            session = session_path  # Telethon accepts str path for SQLiteSession
            print(f"DEBUG: Using SQLite session file for account {account_id}")
        else:
            print(f"WARNING: Session file not found at {session_path}")
            # If we create a new session here, it will be empty.
            # But maybe we want that for initial login?
            # For TData import, the file MUST exist.
            if account.source_type == 'tdata':
                 # Try to find it relative to cwd if absolute check failed
                 if os.path.exists(account.session_file_path):
                      session = account.session_file_path
                 else:
                      raise ValueError(f"Session file missing for TData account: {account.session_file_path}")
            else:
                 session = StringSession('')
    else:
        # Default empty session
        session = StringSession('')

    # Create client
    client = TelegramClient(
        session,
        api_id,
        api_hash,
        device_model=device_model,
        system_version=system_version,
        app_version=app_version,
        lang_code=lang_code,
        system_lang_code=system_lang_code,
        proxy=proxy_dict,
        # Enhanced timeouts for stability
        connection_retries=3,
        flood_sleep_threshold=60,  # Auto-sleep on floods up to 60s
        request_retries=3,
        base_logger=None, # Disable internal logs as suggested
        catch_up=False    # Don't sync history as suggested
    )
    
    # Save session back to DB on disconnect (if modified)
    # Save session back to DB on disconnect (if modified)
    original_disconnect = client.disconnect
    
    # Store initial state for comparison
    using_string_session = isinstance(session, StringSession)
    initial_session_string = account.session_string or ''

    async def disconnect_and_save():
        # Save session string before disconnecting IF using StringSession
        if using_string_session and client.session and client.is_connected():
            # For StringSession, save() returns the string
            new_session_string = client.session.save()
            if new_session_string and new_session_string != initial_session_string:
                try:
                    account.session_string = new_session_string
                    db.session.commit()
                except Exception as e:
                    print(f"Error saving session string: {e}")
                    db.session.rollback()
        await original_disconnect()
    
    client.disconnect = disconnect_and_save
    
    return client


async def connect_client(account_id):
    """Connect Telethon client"""
    client = get_telethon_client(account_id)
    if not client.is_connected():
        await client.connect()
    return client


async def verify_session(account_id):
    """
    Verify that session is valid using safe strategy
    
    Returns:
        dict: {"success": bool, "user": dict, "error": str, "wait": int}
    """
    from telethon.errors import (
        FloodWaitError, 
        UserDeactivatedError, 
        UserDeactivatedBanError,
        AuthKeyError
    )
    from models.account import Account
    from database import db
    import asyncio
    import random
    import os
    
    client = None
    try:
        print(f"DEBUG: verify_session started for account {account_id}")
        
        # CRITICAL: Write to file for debugging
        with open('/tmp/proxy_debug.log', 'a') as f:
            f.write(f"\n=== VERIFY SESSION {account_id} ===\n")
        
        client = get_telethon_client(account_id)
        
        # CRITICAL: Log proxy configuration
        from models.account import Account
        from database import db
        account = db.session.query(Account).get(account_id)
        
        proxy_status = "NO PROXY - SERVER IP EXPOSED!"
        if account and account.proxy:
            proxy_status = f"PROXY: {account.proxy.host}:{account.proxy.port} ({account.proxy.country})"
            print(f"🔒 PROXY ACTIVE for verification: {account.proxy.host}:{account.proxy.port} ({account.proxy.country})")
        else:
            print(f"⚠️ WARNING: NO PROXY for account {account_id} - SERVER IP WILL BE EXPOSED!")
        
        # Write to file
        with open('/tmp/proxy_debug.log', 'a') as f:
            f.write(f"{proxy_status}\n")
        
        await client.connect()
        
        if not client.is_connected():
             raise Exception("Client failed to connect")

        # Step 1: minimal verification
        print("DEBUG: Calling get_me()...")
        me = await client.get_me()
        print(f"DEBUG: get_me() returned: {me}")
        
        if me is None:
            print("DEBUG: me is None!")
            return {
                "success": False,
                "user": None,
                "error": "Session valid but not logged in (get_me returned None) - PLEASE RELOGIN",
                "error_type": "not_logged_in"
            }
            
        if not hasattr(me, 'id'):
             print(f"DEBUG: me has no id! Type: {type(me)}")
             return {
                "success": False,
                "user": None,
                "error": f"Invalid user object returned: {type(me)}",
                "error_type": "invalid_response"
             }
        
        user_data = {
            "id": me.id,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "username": me.username,
            "photo": False
        }
        
        # Basic photo check
        if hasattr(me, "photo") and me.photo:
            user_data["photo"] = True
            
        # Random delay for safety
        await asyncio.sleep(random.uniform(2, 5))
        
        return {
            "success": True,
            "user": user_data,
            "error": None
        }
        
    except FloodWaitError as e:
        return {
            "success": False,
            "user": None,
            "error": f"FloodWait: {e.seconds}s",
            "wait": e.seconds,
            "error_type": "flood_wait"
        }
    except (UserDeactivatedError, UserDeactivatedBanError) as e:
        return {
            "success": False,
            "user": None,
            "error": "Account is banned/deactivated by Telegram",
            "error_type": "banned"
        }
    except AuthKeyError as e:
        return {
            "success": False,
            "user": None,
            "error": "Session is invalid (AuthKeyError) - session file mismatch",
            "error_type": "invalid_session"
        }
    except Exception as e:
        error_msg = str(e)
        if "api_id_invalid" in error_msg.lower() or "api_hash_invalid" in error_msg.lower():
             return {
                "success": False,
                "user": None,
                "error": "The API ID/Hash is invalid or revoked by Telegram",
                "error_type": "invalid_api_key"
            }
            
        return {
            "success": False,
            "user": None,
            "error": error_msg,
            "error_type": "generic_error"
        }
        return {
            "success": False,
            "user": None,
            "error": str(e),
            "error_type": "generic_error"
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


async def update_telegram_profile(account_id, username=None, bio=None, first_name=None, last_name=None):
    """
    Update Telegram profile information
    
    Args:
        account_id: Account ID
        username: New username (without @)
        bio: New bio/about text
        first_name: New first name
        last_name: New last name
    
    Returns:
        dict: {success, updated_fields, error}
    """
    from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
    
    import random
    import asyncio
    
    client = None
    updated_fields = []
    
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        # Human-like thinking pause (simulate navigating to settings)
        thinking_time = random.uniform(2.0, 5.0)
        print(f"🤔 Thinking for {thinking_time:.1f}s before updating profile...")
        await asyncio.sleep(thinking_time)
        
        # Update username (separate request)
        if username is not None:
            # Simulate typing username
            typing_speed = random.uniform(0.1, 0.3)
            typing_time = len(username) * typing_speed
            print(f"⌨️  Simulating typing username... ({typing_time:.1f}s)")
            await asyncio.sleep(typing_time)
            
            try:
                await client(UpdateUsernameRequest(username=username))
                updated_fields.append('username')
                
                # Pause after success
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
            except Exception as e:
                error_msg = str(e)
                if "USERNAME_OCCUPIED" in error_msg:
                    return {"success": False, "updated_fields": [], "error": "Username already taken"}
                elif "USERNAME_INVALID" in error_msg:
                    return {"success": False, "updated_fields": [], "error": "Invalid username format"}
                raise
        
        # Update profile (first_name, last_name, bio)
        profile_updates = {}
        if first_name is not None:
            profile_updates['first_name'] = first_name
        if last_name is not None:
            profile_updates['last_name'] = last_name
        if bio is not None:
            profile_updates['about'] = bio
        
        if profile_updates:
            # Simulate switching fields and typing
            if updated_fields: # If we just updated username
                await asyncio.sleep(random.uniform(1.0, 3.0))
                
            total_chars = sum(len(str(v)) for v in profile_updates.values() if v)
            if total_chars > 0:
                typing_time = total_chars * random.uniform(0.1, 0.25)
                print(f"⌨️  Simulating typing bio/name... ({typing_time:.1f}s)")
                await asyncio.sleep(typing_time)
            
            await client(UpdateProfileRequest(**profile_updates))
            updated_fields.extend(profile_updates.keys())
        
        return {"success": True, "updated_fields": updated_fields, "error": None}
        
    except Exception as e:
        return {"success": False, "updated_fields": updated_fields, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def update_telegram_photo(account_id, photo_path):
    """
    Update Telegram profile photo
    
    Args:
        account_id: Account ID
        photo_path: Path to photo file
    
    Returns:
        dict: {success, error}
    """
    from telethon.tl.functions.photos import UploadProfilePhotoRequest
    
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        # Human-like thinking (simulate browsing for photo)
        thinking_time = random.uniform(2.0, 4.0)
        print(f"🤔 Thinking for {thinking_time:.1f}s before uploading photo...")
        await asyncio.sleep(thinking_time)
        
        # Upload photo
        file = await client.upload_file(photo_path)
        
        # Confirm pause
        await asyncio.sleep(random.uniform(1.0, 2.0))
        
        await client(UploadProfilePhotoRequest(file=file))
        
        return {"success": True, "error": None}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def search_public_channels(account_id, query, limit=20):
    """
    Search for public channels/groups
    
    Args:
        account_id: Account ID
        query: Search query
        limit: Max results
    
    Returns:
        dict: {success, results, error}
    """
    from telethon.tl.functions.contacts import SearchRequest
    from telethon.tl.types import Channel
    
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        # Human-like delay before search
        await asyncio.sleep(random.uniform(1.0, 2.5))
        
        # Perform search
        result = await client(SearchRequest(
            q=query,
            limit=limit
        ))
        
        channels = []
        for chat in result.chats:
            if isinstance(chat, Channel):
                # Filter for channels/groups, skip if no username
                if chat.username:
                    channels.append({
                        "id": chat.id,
                        "title": chat.title,
                        "username": chat.username,
                        "participants_count": getattr(chat, "participants_count", 0),
                        "type": "megagroup" if chat.megagroup else "channel"
                    })
        
        return {"success": True, "results": channels, "error": None}
        
    except Exception as e:
        return {"success": False, "results": [], "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def sync_official_profile(account_id):
    """
    Fetch full profile info from Telegram with human delays
    
    Args:
        account_id: Account ID
    
    Returns:
        dict: {success, data, error}
    """
    from telethon.tl.functions.users import GetFullUserRequest
    
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        # Simulate opening settings/profile
        print("🤔 Opening profile for sync...")
        await asyncio.sleep(random.uniform(1.5, 3.0))
        
        # Get basic info
        me = await client.get_me()
        
        # Simulate scrolling/viewing
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # Get full info (needed for Bio/About)
        full = await client(GetFullUserRequest(me))
        
        # Handle full user result which might vary by Telethon version
        bio = None
        if hasattr(full, 'full_user') and full.full_user:
             bio = full.full_user.about
        
        # Simulate finishing reading
        await asyncio.sleep(random.uniform(0.5, 1.0))
        
        return {
            "success": True,
            "data": {
                "id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "phone": getattr(me, 'phone', None),
                "bio": bio
            },
            "error": None
        }
        
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def set_2fa_password(account_id, password):
    """
    Set 2FA password with human behavior emulation
    """
    from telethon.tl.functions.account import UpdatePasswordSettingsRequest
    from telethon.tl.types import InputCheckPasswordEmpty
    from telethon.errors import PasswordHashInvalidError
    from utils.human_behavior import random_sleep, simulate_typing, simulate_scrolling
    
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        if not await client.is_user_authorized():
            return {"success": False, "error": "User not authorized"}
            
        # Human behavior: Pause before action
        await random_sleep(2, 4, "opening settings")
        
        # Human behavior: Simulate scrolling/exploring
        await simulate_scrolling((2, 4))
        
        # Human behavior: "Typing" the password
        await simulate_typing(len(password))
        
        try:
            # Using Telethon's helper which is much easier than raw requests
            await client.edit_2fa(new_password=password)
            
            await random_sleep(1, 2, "saving settings")
            return {"success": True}
            
        except Exception as e:
            # If it requires current password, this will fail
            return {"success": False, "error": str(e)}
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def get_active_sessions(account_id):
    """
    Get active sessions for account
    """
    from telethon.tl.functions.account import GetAuthorizationsRequest
    from utils.human_behavior import random_sleep

    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        if not await client.is_user_authorized():
            return {"success": False, "error": "User not authorized"}
        
        # Human behavior: Opening devices list
        await random_sleep(1, 2, "loading sessions")

        # Get sessions
        result = await client(GetAuthorizationsRequest())
        
        sessions = []
        for auth in result.authorizations:
            sessions.append({
                "hash": auth.hash,
                "device_model": auth.device_model,
                "platform": auth.platform,
                "system_version": auth.system_version,
                "api_id": auth.api_id,
                "app_name": auth.app_name,
                "app_version": auth.app_version,
                "date_created": auth.date_created.isoformat(),
                "date_active": auth.date_active.isoformat(),
                "ip": auth.ip,
                "country": auth.country,
                "region": auth.region,
                "current": auth.current
            })
            
        return {"success": True, "sessions": sessions}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def terminate_session(account_id, session_hash):
    """
    Terminate a specific session with human emulation
    """
    from telethon.tl.functions.account import ResetAuthorizationRequest
    from utils.human_behavior import random_sleep, simulate_mouse_move
    
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        if not await client.is_user_authorized():
            return {"success": False, "error": "User not authorized"}
            
        # Emulation
        await random_sleep(1, 3, "selecting session")
        await simulate_mouse_move()
        
        # Terminate
        await client(ResetAuthorizationRequest(hash=int(session_hash)))
        
        await random_sleep(0.5, 1.5, "confirming termination")
        
        return {"success": True}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()


async def terminate_all_sessions(account_id):
    """
    Terminate all OTHER sessions with human emulation
    """
    from telethon.tl.functions.auth import ResetAuthorizationsRequest
    from utils.human_behavior import random_sleep, simulate_scrolling
    
    client = None
    try:
        client = get_telethon_client(account_id)
        await client.connect()
        
        if not await client.is_user_authorized():
            return {"success": False, "error": "User not authorized"}
            
        # Emulation
        await random_sleep(1, 3, "reviewing sessions")
        await simulate_scrolling((1, 3))
        
        # Terminate others
        await client(ResetAuthorizationsRequest())
        
        await random_sleep(1, 2, "cleanup")
        
        return {"success": True}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()
