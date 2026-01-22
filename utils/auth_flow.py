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
    session_data: Dict
) -> bool:
    """
    Perform TDesktop-compatible handshake sequence
    
    This function emulates the exact sequence of requests that official
    Telegram Desktop client makes on startup to avoid anti-bot detection.
    
    Args:
        client: Connected Telethon client
        session_data: Dict with device parameters (device_model, app_version, etc.)
    
    Returns:
        bool: True if handshake successful
        
    Raises:
        Exception: If handshake fails
    """
    try:
        logger.info("🔄 Starting TDesktop handshake sequence...")
        
        # Extract device parameters
        device_model = session_data.get('device_model', 'Desktop')
        system_version = session_data.get('system_version', 'Windows 10')
        app_version = session_data.get('app_version', '5.6.3 x64')
        lang_code = session_data.get('lang_code', 'en')
        system_lang_code = session_data.get('system_lang_code', 'en-US')
        api_id = session_data.get('api_id', client.api_id)
        
        # ==================== STEP 1: Connect ====================
        if not client.is_connected():
            logger.info("📡 Connecting to Telegram...")
            await client.connect()
        
        # ==================== STEP 2: Initial Pause ====================
        # Emulate network delay and socket initialization
        initial_delay = random.uniform(0.5, 1.5)
        logger.info(f"⏱️  Initial delay: {initial_delay:.2f}s")
        await asyncio.sleep(initial_delay)
        
        # ==================== STEP 3: InitConnection + GetConfig ====================
        logger.info(f"🤝 Sending InitConnection (Layer {LAYER})...")
        
        # CRITICAL: We MUST use InvokeWithLayerRequest to override lang_pack='tdesktop'
        # The TelegramClient constructor in v1.33 doesn't accept lang_pack
        await client(InvokeWithLayerRequest(
            layer=LAYER,
            query=InitConnectionRequest(
                api_id=api_id,
                device_model=device_model,
                system_version=system_version,
                app_version=app_version,
                system_lang_code=system_lang_code,
                lang_pack='tdesktop',  # <--- THIS IS THE KEY!
                lang_code=lang_code,
                proxy=None, # Telethon handles socket proxy
                params=None,
                query=GetConfigRequest()
            )
        ))
        logger.info("✅ InitConnection successful")

        
        fake_token = generate_wns_token()
        await client(RegisterDeviceRequest(
            token_type=8,  # 8 = WNS (Windows), 1 = APNS (iOS), 2 = FCM (Android)
            token=fake_token,
            app_sandbox=False,
            secret=b'',
            other_uids=[]
        ))
        logger.info("✅ Device registered")
        
        # ==================== STEP 5: GetState ====================
        # Check for updates (standard behavior)
        logger.info("🔄 Checking updates state...")
        await client(GetStateRequest())
        logger.info("✅ Updates checked")
        
        # ==================== STEP 6: GetStrings (LangPack) ====================
        # Download language pack for UI rendering
        logger.info(f"🌐 Fetching language pack ({lang_code})...")
        await client(GetStringsRequest(
            lang_pack='tdesktop',
            lang_code=lang_code,
            keys=[]  # Empty = get all string hashes
        ))
        logger.info("✅ Language pack fetched")
        
        # ==================== STEP 7: Main Pause (UI Rendering) ====================
        # Emulate time spent rendering interface and loading cache
        main_delay = random.uniform(2.0, 5.0)
        logger.info(f"⏱️  UI rendering delay: {main_delay:.2f}s")
        await asyncio.sleep(main_delay)
        
        logger.info("✅ TDesktop handshake complete - ready for GetMe")
        return True
        
    except Exception as e:
        logger.error(f"❌ Handshake failed: {e}", exc_info=True)
        raise Exception(f"Desktop handshake failed: {str(e)}")


async def verify_session_light(client: TelegramClient) -> bool:
    """
    Light verification for subsequent checks
    Only checks if session is still alive without GetMe
    
    Args:
        client: Connected Telethon client
        
    Returns:
        bool: True if session is alive
        
    Raises:
        Exception: If session is dead/banned
    """
    from telethon.errors import (
        UserDeactivatedError,
        UserDeactivatedBanError,
        AuthKeyUnregisteredError
    )
    
    try:
        logger.info("🔍 Light verification: Checking session status...")
        
        if not client.is_connected():
            await client.connect()
        
        # Lightest possible request to check if session is valid
        await client(GetStateRequest())
        
        logger.info("✅ Light check passed - session is alive")
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
