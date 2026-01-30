"""
Anti-Ban Authentication Flow
Implements TDesktop-compatible handshake sequence to avoid detection

Strategy:
Telethon 1.33 doesn't support lang_pack in constructor.
We must manually send InitConnection via InvokeWithLayer to force 'tdesktop'.
"""
import asyncio
import random
import secrets
import logging
from typing import Dict, Optional
from telethon import TelegramClient
from telethon.errors import AuthKeyUnregisteredError, UserDeactivatedError, UserDeactivatedBanError
from telethon.tl.functions import InvokeWithLayerRequest, InitConnectionRequest
from telethon.tl.functions.help import GetConfigRequest
from telethon.tl.functions.updates import GetStateRequest
from telethon.tl.functions.account import RegisterDeviceRequest
from telethon.tl.functions.langpack import GetStringsRequest
from telethon.tl.alltlobjects import LAYER

logger = logging.getLogger(__name__)




def generate_wns_token() -> str:
    """
    Generate fake WNS (Windows Notification Service) token
    Real WNS tokens are long hex strings
    """
    return secrets.token_hex(64)


def get_lang_code_by_proxy_country(proxy_country: Optional[str]) -> tuple:
    """
    Get appropriate language codes based on proxy country
    Returns: (lang_code, system_lang_code)
    """
    country_lang_map = {
        'US': ('en', 'en-US'),
        'GB': ('en', 'en-GB'),
        'RU': ('ru', 'ru-RU'),
        'ID': ('id', 'id-ID'),
        'UA': ('uk', 'uk-UA'),
        'DE': ('de', 'de-DE'),
        'FR': ('fr', 'fr-FR'),
        'ES': ('es', 'es-ES'),
        'BR': ('pt', 'pt-BR'),
        'TR': ('tr', 'tr-TR'),
        'IN': ('en', 'en-IN'),
        'PL': ('pl', 'pl-PL'),
    }
    
    if proxy_country and proxy_country.upper() in country_lang_map:
        return country_lang_map[proxy_country.upper()]
    
    # Default to English
    return ('en', 'en-US')


async def perform_desktop_handshake(
    client: TelegramClient,
    session_data: Dict,
    account_id: Optional[int] = None
) -> bool:
    """
    Perform TDesktop-compatible handshake sequence
    ...
    Args:
        client: Connected Telethon client
        session_data: Dict with device parameters
        account_id: Optional Account ID for Activity Logging
    """
    from utils.activity_logger import ActivityLogger
    
    # Initialize logger if account_id provided
    activity_logger = ActivityLogger(account_id) if account_id else None
    
    def log_activity(desc: str, status='info'):
        if activity_logger:
            activity_logger.log(
                action_type='handshake_step',
                status=status,
                description=desc,
                category='system',
                visible_on_ui=True
            )
        logger.info(desc)
    
    # Official TDesktop API ID
    OFFICIAL_TDESKTOP_API_ID = 2040
    
    def human_delay():
        """Generate human-like delay with non-uniform distribution"""
        r = random.random()
        if r < 0.6:
            return random.uniform(0.3, 1.0)   # Quick action
        elif r < 0.85:
            return random.uniform(1.0, 3.0)   # Normal pace
        else:
            return random.uniform(3.0, 7.0)   # Slow/distracted
    
    try:
        log_activity("🔄 Starting TDesktop handshake sequence...")
        
        # Extract device parameters
        lang_code = session_data.get('lang_code', 'en')
        api_id = session_data.get('api_id', client.api_id)
        
        # ==================== STEP 1: Connect ====================
        if not client.is_connected():
            log_activity("📡 Connecting to Telegram...")
            await client.connect()
        
        # ==================== STEP 2: Initial Pause ====================
        initial_delay = human_delay()
        logger.info(f"⏱️  Initial delay: {initial_delay:.2f}s")
        await asyncio.sleep(initial_delay)
        
        # ==================== STEP 3: GetConfig ====================
        log_activity("⚙️  Fetching server config...")
        try:
            await client(GetConfigRequest())
            logger.info("✅ Config received")
        except Exception as e:
            logger.warning(f"⚠️ GetConfig failed (non-fatal): {e}")
        
        await asyncio.sleep(human_delay())
        
        # ==================== STEP 4: GetState ====================
        log_activity("🔄 Checking updates state...")
        await client(GetStateRequest())
        logger.info("✅ Updates checked")
        
        # ==================== STEP 5: GetStrings (LangPack) ====================
        await asyncio.sleep(human_delay())
        log_activity(f"🌐 Fetching language pack ({lang_code})...")
        try:
            await client(GetStringsRequest(
                lang_pack='tdesktop',
                lang_code=lang_code,
                keys=[]  # Empty = get all string hashes
            ))
            logger.info("✅ Language pack fetched")
        except Exception as e:
            logger.warning(f"⚠️ GetStrings failed (non-fatal): {e}")
        
        # ==================== NOTE: WNS REMOVED ====================
        logger.debug("⏭️  WNS registration skipped (anti-detection)")
        
        # ==================== STEP 6: Main Pause (UI Rendering) ====================
        main_delay = random.uniform(2.0, 5.0)
        logger.info(f"⏱️  UI rendering delay: {main_delay:.2f}s")
        await asyncio.sleep(main_delay)
        
        log_activity("✅ Handshake complete - ready for GetMe", status='success')
        return True
        
    except AuthKeyUnregisteredError:
        logger.error("❌ Handshake failed: Session Revoked (AuthKeyUnregistered)")
        raise Exception("SESSION_REVOKED: The session key was revoked by Telegram. Please delete account and re-upload TData.")
        
    except (UserDeactivatedError, UserDeactivatedBanError):
        logger.error("❌ Handshake failed: Account Banned")
        raise Exception("ACCOUNT_BANNED: This account has been deactivated or banned by Telegram.")

    except Exception as e:
        logger.error(f"❌ Handshake failed: {e}", exc_info=True)
        raise Exception(f"Desktop handshake failed: {str(e)}")


async def verify_session_light(client: TelegramClient) -> bool:
    """
    Light verification (Strict TDesktop Mode).
    Checks if account is ALIVE by looking at User flags.
    GetStateRequest is NOT enough (it passes for deleted accounts).
    
    Args:
        client: Connected Telethon client
        
    Returns:
        bool: True if session is alive AND account is not deleted/banned
    """
    from telethon.tl.functions.users import GetUsersRequest
    from telethon.tl.types import InputPeerSelf
    
    try:
        logger.info("🔍 Light verification: Checking account status...")
        
        if not client.is_connected():
            await client.connect()

        # Вместо GetState используем GetUsers([InputPeerSelf])
        # Это дешевый запрос, который вернет актуальные флаги пользователя
        try:
            # Используем прямой запрос, чтобы обойти кэш Telethon
            result = await client(GetUsersRequest([InputPeerSelf()]))
            me = result[0]
        except Exception:
            # Fallback
            me = await client.get_me()

        if not me:
            logger.error("❌ Light check: Could not get user entity")
            return False

        # v3 STRICT CHECKS
        from telethon.tl.types import UserEmpty
        debug_info = f"Light v3: Type={type(me).__name__} ID={getattr(me, 'id', '?')} Deleted={getattr(me, 'deleted', '?')} Name='{getattr(me, 'first_name', 'None')}'"
        logger.info(f"🕵️ {debug_info}")

        if isinstance(me, UserEmpty):
             logger.error(f"❌ Light check FAILED: Account is UserEmpty (Deleted)")
             raise UserDeactivatedError("ACCOUNT_IS_USER_EMPTY")

        # 🔥 ПРОВЕРКА ФЛАГОВ
        if getattr(me, 'deleted', False):
            logger.error(f"❌ Light check FAILED: Account {me.id} is DELETED flag=True")
            raise UserDeactivatedError("ACCOUNT_DELETED")
            
        # Heuristic: Valid accounts MUST have a first_name
        first_name = getattr(me, 'first_name', None)
        if not first_name or str(first_name).strip() == "" or str(first_name) == "None":
             logger.error(f"❌ Light check FAILED: Account {me.id} has NO NAME (Deleted/Ghost)")
             raise UserDeactivatedError("ACCOUNT_nameless_ghost")
            
        if getattr(me, 'restricted', False):
            reason = getattr(me, 'restriction_reason', [])
            reason_str = str(reason) if reason else "Unknown"
            logger.warning(f"⚠️ Light check WARNING: Account {me.id} is RESTRICTED: {reason_str}")
            # raise Exception(f"ACCOUNT_RESTRICTED: {reason_str}")

        logger.info(f"✅ Light check passed: {me.first_name} (ID: {me.id}) [Alive]")
        return True
        
    except (UserDeactivatedError, UserDeactivatedBanError) as e:
        logger.error(f"❌ Account is BANNED: {e}")
        raise Exception("ACCOUNT_BANNED")
        
    except AuthKeyUnregisteredError as e:
        logger.error(f"❌ Session is INVALID: {e}")
        raise Exception("SESSION_REVOKED")
        
    except Exception as e:
        logger.error(f"❌ Light verification failed: {e}")
        raise


def validate_session_data(session_data: Dict) -> bool:
    """
    Validate that session_data has all required fields
    
    Args:
        session_data: Dict with device parameters
        
    Returns:
        bool: True if valid
    """
    required_fields = [
        'device_model',
        'system_version',
        'app_version',
        'lang_code',
        'system_lang_code'
    ]
    
    for field in required_fields:
        if field not in session_data or not session_data[field]:
            logger.warning(f"⚠️  Missing required field: {field}")
            return False
    
    return True
