import logging
import asyncio
import random
import os
from datetime import datetime
from typing import Optional, Union, List, Dict

from telethon.errors import (
    UserPrivacyRestrictedError, UserNotMutualContactError, UserChannelsTooMuchError,
    UserAlreadyParticipantError, UserIdInvalidError, PeerFloodError, FloodWaitError,
    ChatAdminRequiredError, ChatWriteForbiddenError, ChannelPrivateError,
    UserBannedInChannelError, PasswordHashInvalidError
)
from telethon.tl.functions.channels import InviteToChannelRequest, JoinChannelRequest
from telethon.tl.functions.messages import SendReactionRequest, AddChatUserRequest
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest, UpdatePasswordSettingsRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.types import ReactionEmoji, Channel, Chat, InputCheckPasswordEmpty

from modules.telethon.client import ClientFactory
from utils.human_behavior import random_sleep, simulate_typing, simulate_scrolling

logger = logging.getLogger(__name__)

async def ensure_connected(client):
    if not client.is_connected():
        await client.connect()

async def send_invite(account_id: int, channel_username: str, target_user_id=None, target_username=None, client=None):
    """Send invite to user with detailed error handling"""
    own_client = False
    try:
        if not client:
            client = ClientFactory.create_client(account_id)
            own_client = True
        await ensure_connected(client)
        
        channel = await client.get_entity(channel_username)
        
        user = None
        if target_user_id:
            try:
                user = await client.get_entity(int(target_user_id))
            except:
                if target_username:
                     user = await client.get_entity(target_username)
        elif target_username:
             user = await client.get_entity(target_username)
        
        if not user:
             return {"status": "error", "error": "User not found", "error_type": "user_not_found"}

        await client(InviteToChannelRequest(channel=channel, users=[user]))
        return {"status": "success", "error": None, "error_type": None}

    except UserAlreadyParticipantError:
        return {"status": "already_member", "error": "User already in group", "error_type": "already_member"}
    except UserPrivacyRestrictedError:
        return {"status": "privacy_restricted", "error": "Privacy settings prevent invites", "error_type": "privacy_restricted"}
    except FloodWaitError as e:
        return {"status": "flood_wait", "error": f"Flood wait {e.seconds}s", "error_type": "flood_wait", "wait_seconds": e.seconds}
    except Exception as e:
        return {"status": "failed", "error": str(e), "error_type": "unknown"}
    finally:
        if own_client and client and client.is_connected():
            await client.disconnect()

async def send_dm(account_id: int, username: str, text: str, media_path: str = None, client=None):
    own_client = False
    try:
        if not client:
             client = ClientFactory.create_client(account_id)
             own_client = True
        await ensure_connected(client)
        
        user = await client.get_entity(username)
        if media_path:
             await client.send_file(user, media_path, caption=text)
        else:
             await client.send_message(user, text)
        return {"success": True, "message_id": None, "error": None}
    except Exception as e:
        return {"success": False, "message_id": None, "error": str(e)}
    finally:
         if own_client and client and client.is_connected():
              await client.disconnect()

async def update_telegram_profile(account_id: int, username=None, bio=None, first_name=None, last_name=None, client=None):
    own_client = False
    updated_fields = []
    try:
        if not client:
             client = ClientFactory.create_client(account_id)
             own_client = True
        await ensure_connected(client)
        
        await random_sleep(2.0, 5.0, "thinking before update")
        
        if username is not None:
             await simulate_typing(len(username))
             try:
                 await client(UpdateUsernameRequest(username=username))
                 updated_fields.append('username')
                 await random_sleep(1.0, 2.0)
             except Exception as e:
                 if "USERNAME_OCCUPIED" in str(e):
                      return {"success": False, "updated_fields": [], "error": "Username taken"}
                 raise e

        profile_updates = {}
        if first_name: profile_updates['first_name'] = first_name
        if last_name: profile_updates['last_name'] = last_name
        if bio: profile_updates['about'] = bio
        
        if profile_updates:
             await simulate_typing(sum(len(str(v)) for v in profile_updates.values()))
             await client(UpdateProfileRequest(**profile_updates))
             updated_fields.extend(profile_updates.keys())
             
        return {"success": True, "updated_fields": updated_fields, "error": None}
    except Exception as e:
        return {"success": False, "updated_fields": updated_fields, "error": str(e)}
    finally:
        if own_client and client and client.is_connected():
             await client.disconnect()

async def update_telegram_photo(account_id: int, photo_path: str, client=None):
    own_client = False
    try:
        if not client:
             client = ClientFactory.create_client(account_id)
             own_client = True
        await ensure_connected(client)
        
        await random_sleep(2.0, 4.0, "browsing photo")
        file = await client.upload_file(photo_path)
        await random_sleep(1.0, 2.0)
        await client(UploadProfilePhotoRequest(file=file))
        
        return {"success": True, "error": None}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if own_client and client and client.is_connected():
             await client.disconnect()

async def get_channel_info(account_id: int, channel_username: str, client=None):
    own_client = False
    try:
        if not client:
             client = ClientFactory.create_client(account_id)
             own_client = True
        await ensure_connected(client)
        
        entity = None
        for fmt in [f"@{channel_username}", channel_username, f"https://t.me/{channel_username}"]:
            try:
                entity = await client.get_entity(fmt)
                break
            except: continue
        
        if not entity: return {"success": False, "error": f"Channel not found: {channel_username}"}

        channel_type = "channel"
        if isinstance(entity, Channel):
             channel_type = "megagroup" if entity.megagroup else "channel"
        elif isinstance(entity, Chat):
             channel_type = "group"
             
        is_admin = False
        try:
             full = await client.get_entity(entity) 
             is_admin = getattr(entity, 'admin_rights', None) is not None
        except: pass
        
        return {
            "success": True,
            "channel": {
                 "id": entity.id,
                 "title": getattr(entity, 'title', channel_username),
                 "username": getattr(entity, 'username', channel_username),
                 "type": channel_type,
                 "is_admin": is_admin,
                 "participants_count": getattr(entity, 'participants_count', 0)
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
         if own_client and client and client.is_connected():
              await client.disconnect()

async def join_channel(account_id: int, channel_username: str, client=None):
    own_client = False
    try:
        if not client:
            client = ClientFactory.create_client(account_id)
            own_client = True
        await ensure_connected(client)
        
        channel = await client.get_entity(channel_username)
        await client(JoinChannelRequest(channel))
        return {"success": True, "already_member": False, "error": None}
    except UserAlreadyParticipantError:
        return {"success": True, "already_member": True, "error": None}
    except FloodWaitError as e:
        return {"success": False, "error": f"FloodWait: {e.seconds}s", "wait_seconds": e.seconds}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if own_client and client and client.is_connected():
            await client.disconnect()

async def read_channel_posts(account_id: int, channel_username: str, count=10, delay_between=5, client=None):
    own_client = False
    try:
        if not client:
            client = ClientFactory.create_client(account_id)
            own_client = True
        await ensure_connected(client)
        
        channel = await client.get_entity(channel_username)
        messages = []
        async for msg in client.iter_messages(channel, limit=count):
             messages.append(msg)
             
        if not messages: return {"success": True, "posts_read": 0, "error": None}
        
        cnt = 0
        for msg in messages:
             try:
                 await client.send_read_acknowledge(channel, msg)
                 cnt += 1
                 if delay_between > 0 and cnt < len(messages):
                      await asyncio.sleep(random.uniform(delay_between * 0.5, delay_between * 1.5))
             except: continue
        return {"success": True, "posts_read": cnt, "error": None}
    except Exception as e:
        return {"success": False, "posts_read": 0, "error": str(e)}
    finally:
        if own_client and client and client.is_connected():
             await client.disconnect()

async def react_to_post(account_id: int, channel_username: str, message_id=None, reaction="👍", client=None):
    own_client = False
    try:
        if not client:
             client = ClientFactory.create_client(account_id)
             own_client = True
        await ensure_connected(client)
        
        channel = await client.get_entity(channel_username)
        if message_id is None:
             async for msg in client.iter_messages(channel, limit=1):
                 message_id = msg.id
                 break
        if not message_id: return {"success": False, "error": "No messages"}
        
        await client(SendReactionRequest(peer=channel, msg_id=message_id, reaction=[ReactionEmoji(emoticon=reaction)]))
        return {"success": True, "error": None}
    except Exception as e:
        if "REACTION_INVALID" in str(e): return {"success": False, "error": "Reactions disabled"}
        return {"success": False, "error": str(e)}
    finally:
         if own_client and client and client.is_connected():
              await client.disconnect()

async def parse_channel_members(account_id: int, channel_username: str, filters=None, client=None):
    own_client = False
    try:
        if not client:
             client = ClientFactory.create_client(account_id)
             own_client = True
        await ensure_connected(client)
        
        channel = await client.get_entity(channel_username)
        members = []
        
        async for user in client.iter_participants(channel, limit=None):
            if filters:
                 if filters.get("skip_bots") and user.bot: continue
                 if filters.get("only_with_username") and not user.username: continue
            
            members.append({
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": getattr(user, 'phone', None),
                "is_bot": user.bot
            })
        return {"success": True, "members": members, "error": None}
    except Exception as e:
        return {"success": False, "members": [], "error": str(e)}
    finally:
         if own_client and client and client.is_connected():
              await client.disconnect()

async def get_channel_messages(account_id: int, channel_username: str, limit=100, client=None):
    own_client = False
    try:
        if not client:
             client = ClientFactory.create_client(account_id)
             own_client = True
        await ensure_connected(client)
        
        channel = await client.get_entity(channel_username)
        msgs = []
        async for m in client.iter_messages(channel, limit=limit):
             msgs.append({"message_id": m.id, "text": m.text, "date": m.date, "views": getattr(m, 'views', 0)})
        return {"success": True, "messages": msgs, "error": None}
    except Exception as e:
        return {"success": False, "messages": [], "error": str(e)}
    finally:
         if own_client and client and client.is_connected():
              await client.disconnect()

async def send_channel_message(account_id: int, channel_username: str, text: str, media_path=None, pin=False, client=None):
    own_client = False
    try:
        if not client:
             client = ClientFactory.create_client(account_id)
             own_client = True
        await ensure_connected(client)
        
        channel = await client.get_entity(channel_username)
        if media_path:
             msg = await client.send_file(channel, media_path, caption=text)
        else:
             msg = await client.send_message(channel, text)
             
        if pin: await client.pin_message(channel, msg)
        return {"success": True, "message_id": msg.id, "error": None}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
         if own_client and client and client.is_connected():
              await client.disconnect()

async def sync_official_profile(account_id: int, client=None):
    own_client = False
    try:
        if not client:
             client = ClientFactory.create_client(account_id)
             own_client = True
        await ensure_connected(client)
        
        me = await client.get_me()
        full = await client(GetFullUserRequest(me))
        bio = None
        if hasattr(full, 'full_user') and full.full_user:
             bio = full.full_user.about
             
        return {
            "success": True, 
            "data": {
                "id": me.id, "username": me.username, 
                "first_name": me.first_name, "last_name": me.last_name,
                "phone": getattr(me, 'phone', None), "bio": bio
            },
            "error": None
        }
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
    finally:
         if own_client and client and client.is_connected():
              await client.disconnect()

async def set_2fa_password(account_id: int, password: str, client=None):
    own_client = False
    try:
        if not client:
             client = ClientFactory.create_client(account_id)
             own_client = True
        await ensure_connected(client)
        
        await random_sleep(2.0, 4.0, "typing password")
        
        # New password logic
        # Typically involves checking if current password exists, but helper assumed setting new one
        # Telethon logic for setting 2fa is complex if already exists, but legacy helper used pure UpdatePasswordSettingsRequest?
        # Let's assume legacy behavior
        from telethon.tl.functions.account import GetPasswordRequest
        
        pwd_info = await client(GetPasswordRequest())
        if pwd_info.has_password:
             return {"success": False, "error": "Password already set"}
             
        # Set it
        # Note: Compute hash etc. Telethon client.edit_2fa?
        # Legacy helper used custom logic or client method?
        # I'll rely on Telethon's high level method if possible
        await client.edit_2fa(new_password=password)
        
        return {"success": True, "error": None}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
         if own_client and client and client.is_connected():
              await client.disconnect()

async def search_public_channels(account_id: int, query: str, limit=20, client=None):
    own_client = False
    try:
        if not client:
             client = ClientFactory.create_client(account_id)
             own_client = True
        await ensure_connected(client)
        
        res = await client(SearchRequest(q=query, limit=limit))
        channels = []
        for chat in res.chats:
             if isinstance(chat, Channel) and chat.username:
                 channels.append({
                     "id": chat.id,
                     "title": chat.title,
                     "username": chat.username,
                     "participants_count": getattr(chat, 'participants_count', 0),
                     "type": "megagroup" if chat.megagroup else "channel"
                 })
        return {"success": True, "results": channels, "error": None}
    except Exception as e:
        return {"success": False, "results": [], "error": str(e)}
    finally:
         if own_client and client and client.is_connected():
              await client.disconnect()

async def send_conversation_message(account_id, target_account_id, message_text, client=None):
    from models.account import Account
    own_client = False
    try:
        if not client:
             client = ClientFactory.create_client(account_id)
             own_client = True
        await ensure_connected(client)
        
        target = Account.query.get(target_account_id)
        if not target: return {"success": False, "error": "Target not found"}
        
        idf = target.telegram_id or target.username
        if not idf: return {"success": False, "error": "No ID/Username for target"}
        
        user = await client.get_entity(idf if isinstance(idf, str) else int(idf))
        msg = await client.send_message(user, message_text)
        return {"success": True, "message_id": msg.id, "error": None}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
         if own_client and client and client.is_connected():
              await client.disconnect()
