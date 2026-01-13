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
    Self-Check via Saved Messages - SAFEST METHOD
    
    Sends a message to "Saved Messages", waits, then deletes it.
    This is the safest verification as it only interacts with your own account.
    
    Risk Level: ⭐ Very Low
    Speed: ~5-10 seconds
    Recommended: For fresh/suspicious accounts
    
    Returns:
        dict: {
            'success': bool,
            'method': 'self_check',
            'user_id': int,
            'check_time': str,
            'error': str (if failed)
        }
    """
    try:
        logger.info("Starting safe self-check verification")
        
        # Connect client first
        if not client.is_connected():
            await client.connect()
        
        # Get user info first
        me = await client.get_me()
        
        # Random delay before sending
        await asyncio.sleep(random.uniform(1, 3))
        
        # Send message to Saved Messages using 'me' string directly
        check_time = datetime.now().strftime("%H:%M:%S")
        msg = await client.send_message(
            'me',  # Direct way - works correctly
            f'🔄 Check {check_time}'
        )
        
        logger.info(f"Self-check message sent: {msg.id}")
        
        # Wait 2-5 seconds (human-like)
        await asyncio.sleep(random.uniform(2, 5))
        
        # Delete message (cleanup)
        await asyncio.sleep(1)
        await msg.delete()
        
        logger.info("Self-check message deleted successfully")
        
        return {
            'success': True,
            'method': 'self_check',
            'user_id': me.id,
            'username': me.username,
            'first_name': me.first_name,
            'check_time': datetime.now().isoformat(),
            'duration': '~5-10s'
        }
        
    except FloodWaitError as e:
        logger.error(f"FloodWait during self-check: {e.seconds}s")
        return {
            'success': False,
            'method': 'self_check',
            'error': f'FloodWait: {e.seconds}s',
            'error_type': 'flood_wait',
            'wait': e.seconds
        }
    except (UserDeactivatedError, UserDeactivatedBanError):
        logger.error("Account is banned/deactivated")
        return {
            'success': False,
            'method': 'self_check',
            'error': 'Account is banned/deactivated by Telegram',
            'error_type': 'banned'
        }
    except AuthKeyError:
        logger.error("Invalid session (AuthKeyError)")
        return {
            'success': False,
            'method': 'self_check',
            'error': 'Session is invalid (AuthKeyError)',
            'error_type': 'invalid_session'
        }
    except Exception as e:
        logger.error(f"Self-check error: {e}", exc_info=True)
        return {
            'success': False,
            'method': 'self_check',
            'error': str(e),
            'error_type': 'generic_error'
        }


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
