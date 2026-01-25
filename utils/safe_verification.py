"""
Safe Account Verification Methods
Provides three verification methods with different safety levels
"""
import asyncio
import random
from datetime import datetime, timedelta
from telethon.errors import FloodWaitError, UserDeactivatedError, UserDeactivatedBanError, AuthKeyError
from telethon.tl.types import InputPeerSelf
import logging

logger = logging.getLogger(__name__)


async def safe_self_check(client):
    """
    🛡️ PASSIVE Self-Check via GetDialogs (SMART VERSION)
    Checks for 'deleted' and 'restricted' flags in the response.
    """
    from telethon.tl.functions.messages import GetDialogsRequest
    from telethon.tl.types import InputPeerEmpty
    
    try:
        logger.info("🛡️ Starting PASSIVE self-check (GetDialogs)...")
        
        if not client.is_connected():
            await client.connect()
            
        if not await client.is_user_authorized():
            return {'success': False, 'method': 'self_check', 'error': 'Session invalid (Unauthorized)'}

        # 1. Делаем запрос (как и раньше)
        dialogs = await client(GetDialogsRequest(
            offset_date=None, 
            offset_id=0, 
            offset_peer=InputPeerEmpty(), 
            limit=40,   # <-- TDesktop default pagination (limit=40)
            hash=0
        ))
        
        # 2. 🔥 ГЛАВНОЕ ИЗМЕНЕНИЕ: Анализ пользователя
        me = None
        # Ищем себя в списке пользователей, который вернул сервер
        if hasattr(dialogs, 'users'):
            for user in dialogs.users:
                if getattr(user, 'is_self', False):
                    me = user
                    break
        
        # 3. Validation
        if not me:
            logger.error("❌ Self-check failed: User entity not found in GetDialogs/GetMe")
            return {
                'success': False, 
                'method': 'self_check', 
                'error': 'SELF_USER_NOT_FOUND',
                'error_type': 'protocol_error'
            }

        debug_info = f"v3 CHECK: Type={type(me).__name__} ID={getattr(me, 'id', '?')} Deleted={getattr(me, 'deleted', '?')} Name='{getattr(me, 'first_name', 'None')}'"
        logger.info(f"🕵️ {debug_info}")
        
        from telethon.tl.types import UserEmpty


        if isinstance(me, UserEmpty):
             logger.error(f"❌ Account is UserEmpty (Deleted)")
             return {
                 'success': False, 
                 'method': 'self_check', 
                 'error': 'ACCOUNT_IS_EMPTY', 
                 'error_type': 'banned',
                 'debug_info': debug_info
             }

        if getattr(me, 'deleted', False):
            logger.error(f"❌ Account {me.id} detected as DELETED (User.deleted=True)")
            return {
                'success': False, 
                'method': 'self_check', 
                'error': 'ACCOUNT_DELETED', 
                'error_type': 'banned',
                'debug_info': debug_info
            }
            
        # Heuristic: Valid accounts MUST have a first_name
        first_name = getattr(me, 'first_name', None)
        if not first_name or str(first_name).strip() == "" or str(first_name) == "None":
             logger.error(f"❌ Account {me.id} has NO NAME (Deleted/Ghost)")
             return {
                'success': False, 
                'method': 'self_check', 
                'error': 'ACCOUNT_nameless_ghost', 
                'error_type': 'banned',
                'debug_info': debug_info
            }
            
        if getattr(me, 'restricted', False):
            # ... (rest of logic same)
            reason = getattr(me, 'restriction_reason', [])
            reason_str = str(reason) if reason else "Unknown"
            logger.warning(f"⚠️ Account {me.id} is RESTRICTED: {reason_str}")
                
            return {
                'success': False, 
                'method': 'self_check', 
                'error': f'ACCOUNT_RESTRICTED: {reason_str}',
                'error_type': 'restricted',
                'debug_info': debug_info
            }

        logger.info("✅ Passive Check: OK (v3-validated)")
        return {
            'success': True,
            'method': 'self_check',
            'user_id': me.id,
            'username': getattr(me, 'username', None),
            'first_name': getattr(me, 'first_name', None),
            'last_name': getattr(me, 'last_name', None),
            'check_time': datetime.now().isoformat(),
            'debug_info': debug_info
        }

    except Exception as e:
        logger.error(f"❌ Self-check error: {e}")
        return {'success': False, 'method': 'self_check', 'error': str(e)}


async def safe_get_me(client, last_check_time=None):
    """
    Get Me with Delays - MODERATE SAFETY
    
    Executes get_me() with random delays before and after.
    Should only be used max 1 time per 2-3 hours.
    
    Risk Level: ⭐⭐ Moderate
    Speed: ~10-25 seconds
    Recommended: For established accounts
    
    Args:
        client: Telethon client
        last_check_time: DateTime of last check (for cooldown enforcement)
    
    Returns:
        dict: Verification result
    """
    try:
        # Enforce cooldown (2 hours minimum)
        if last_check_time:
            time_since_last = datetime.now() - last_check_time
            cooldown_hours = 2
            if time_since_last < timedelta(hours=cooldown_hours):
                remaining = timedelta(hours=cooldown_hours) - time_since_last
                remaining_minutes = int(remaining.total_seconds() / 60)
                
                logger.warning(f"Cooldown active: {remaining_minutes} minutes remaining")
                return {
                    'success': False,
                    'method': 'get_me',
                    'error': f'Cooldown active. Wait {remaining_minutes} more minutes.',
                    'error_type': 'cooldown',
                    'remaining_minutes': remaining_minutes
                }
        
        logger.info("Starting safe get_me verification")
        
        # Connect client first
        if not client.is_connected():
            await client.connect()

        # Random delay BEFORE request (5-15 seconds)
        delay_before = random.uniform(5, 15)
        logger.info(f"Waiting {delay_before:.1f}s before get_me...")
        await asyncio.sleep(delay_before)
        
        # Execute get_me
        me = await client.get_me()
        
        # Get Full User Info (Bio/About) - optional but requested
        bio = None
        try:
            from telethon.tl.functions.users import GetFullUserRequest
            full_user = await client(GetFullUserRequest(me))
            bio = getattr(full_user.full_user, 'about', None)
        except Exception as bio_err:
            logger.warning(f"Failed to fetch bio: {bio_err}")
            
        # Download Photo
        photo_path = None
        if getattr(me, 'photo', None):
            try:
                import os
                upload_folder = os.path.join(os.getcwd(), 'uploads', 'photos')
                os.makedirs(upload_folder, exist_ok=True)
                
                filename = f"{me.id}_{int(datetime.utcnow().timestamp())}.jpg"
                filepath = os.path.join(upload_folder, filename)
                
                await client.download_profile_photo(me, file=filepath)
                if os.path.exists(filepath):
                    photo_path = f"uploads/photos/{filename}"
            except Exception as photo_err:
                logger.warning(f"Failed to download photo: {photo_err}")
        
        # Random delay AFTER request (3-8 seconds)
        delay_after = random.uniform(3, 8)
        logger.info(f"Waiting {delay_after:.1f}s after get_me...")
        await asyncio.sleep(delay_after)
        
        logger.info("Get_me verification successful")
        
        return {
            'success': True,
            'method': 'get_me',
            'user_id': me.id,
            'username': me.username,
            'first_name': me.first_name,
            'last_name': me.last_name,
            'phone': me.phone,
            'bio': bio,
            'photo_url': photo_path,
            'check_time': datetime.now().isoformat(),
            'duration': '~10-25s',
            'next_check_allowed': (datetime.now() + timedelta(hours=2)).isoformat()
        }
        
    except FloodWaitError as e:
        logger.error(f"FloodWait during get_me: {e.seconds}s")
        return {
            'success': False,
            'method': 'get_me',
            'error': f'FloodWait: {e.seconds}s',
            'error_type': 'flood_wait',
            'wait': e.seconds
        }
    except (UserDeactivatedError, UserDeactivatedBanError):
        logger.error("Account is banned/deactivated")
        return {
            'success': False,
            'method': 'get_me',
            'error': 'Account is banned/deactivated by Telegram',
            'error_type': 'banned'
        }
    except AuthKeyError:
        logger.error("Invalid session (AuthKeyError)")
        return {
            'success': False,
            'method': 'get_me',
            'error': 'Session is invalid (AuthKeyError)',
            'error_type': 'invalid_session'
        }
    except Exception as e:
        logger.error(f"Get_me error: {e}", exc_info=True)
        return {
            'success': False,
            'method': 'get_me',
            'error': str(e),
            'error_type': 'generic_error'
        }


async def check_via_public_channel(client, channel_username='telegram'):
    """
    Public Channel Check - SAFE METHOD
    
    Reads a public channel without joining to verify account is alive.
    Very safe as it's a normal user activity.
    
    Risk Level: ⭐ Low
    Speed: ~3-5 seconds
    Recommended: For daily checks
    
    Args:
        client: Telethon client
        channel_username: Public channel to check (default: @telegram)
    
    Returns:
        dict: Verification result
    """
    try:
        logger.info(f"Starting public channel check: @{channel_username}")
        
        # Random delay before request
        await asyncio.sleep(random.uniform(1, 3))
        
        # Connect client first
        if not client.is_connected():
            await client.connect()
        
        # Get channel entity (no join required for public channels)
        channel = await client.get_entity(channel_username)
        
        # Get last message (just reading, very safe)
        messages = await client.get_messages(channel, limit=1)
        
        # Get user info
        me = await client.get_me()
        
        # Random delay after
        await asyncio.sleep(random.uniform(2, 4))
        
        logger.info(f"Public channel check successful: @{channel_username}")
        
        return {
            'success': True,
            'method': 'public_channel',
            'user_id': me.id,
            'username': me.username,
            'first_name': me.first_name,
            'channel_checked': channel_username,
            'last_post_date': messages[0].date.isoformat() if messages else None,
            'check_time': datetime.now().isoformat(),
            'duration': '~3-5s'
        }
        
    except FloodWaitError as e:
        logger.error(f"FloodWait during channel check: {e.seconds}s")
        return {
            'success': False,
            'method': 'public_channel',
            'error': f'FloodWait: {e.seconds}s',
            'error_type': 'flood_wait',
            'wait': e.seconds
        }
    except (UserDeactivatedError, UserDeactivatedBanError):
        logger.error("Account is banned/deactivated")
        return {
            'success': False,
            'method': 'public_channel',
            'error': 'Account is banned/deactivated by Telegram',
            'error_type': 'banned'
        }
    except AuthKeyError:
        logger.error("Invalid session (AuthKeyError)")
        return {
            'success': False,
            'method': 'public_channel',
            'error': 'Session is invalid (AuthKeyError)',
            'error_type': 'invalid_session'
        }
    except Exception as e:
        logger.error(f"Public channel check error: {e}", exc_info=True)
        return {
            'success': False,
            'method': 'public_channel',
            'error': str(e),
            'error_type': 'generic_error'
        }
