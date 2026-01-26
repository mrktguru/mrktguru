import os
import asyncio
import logging
import random
import string
import inspect

# ---------------------------------------------------------------------------
# 🔥 ГЛАВНОЕ ИЗМЕНЕНИЕ:
# Импортируем TelegramClient из opentele, а не из telethon.
try:
    from opentele.tl.telethon import TelegramClient as OpenteleClient
    OPENTELE_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).critical("❌ Opentele library not found! Run: pip install opentele")
    from telethon import TelegramClient as OpenteleClient
    OPENTELE_AVAILABLE = False
# ---------------------------------------------------------------------------


class ExtendedTelegramClient(OpenteleClient):
    """
    💉 Extended Telegram Client with lang_pack support
    
    Решает проблему: opentele 1.15.1 не поддерживает lang_pack в конструкторе.
    
    Паттерн "Наследование + Инъекция":
    1. Перехватываем lang_pack в __init__ (не передаём parent)
    2. Инициализируем родителя без lang_pack
    3. Внедряем lang_pack во внутреннюю структуру _init_request
    """
    
    def __init__(self, *args, lang_pack: str = None, **kwargs):
        # Перехватываем lang_pack — родитель его не принимает
        self._custom_lang_pack = lang_pack
        
        # Вызываем конструктор родителя БЕЗ lang_pack
        super().__init__(*args, **kwargs)
        
        # Инъекция lang_pack во внутреннюю структуру
        if lang_pack:
            self._inject_lang_pack(lang_pack)
    
    def _inject_lang_pack(self, lang_pack: str):
        """
        Внедряет lang_pack в структуру InitConnectionRequest
        Telethon хранит её в self._init_request (InitConnectionRequest)
        """
        try:
            # Telethon 1.x хранит init request здесь
            if hasattr(self, '_init_request') and self._init_request:
                self._init_request.lang_pack = lang_pack
                logging.info(f"✅ lang_pack='{lang_pack}' injected into _init_request")
            else:
                # Fallback: попробуем после первого connect()
                self._pending_lang_pack = lang_pack
                logging.debug(f"⏳ lang_pack='{lang_pack}' queued for injection after connect")
        except Exception as e:
            logging.warning(f"⚠️ Failed to inject lang_pack: {e}")
    
    async def connect(self):
        """Override connect to inject lang_pack if pending"""
        result = await super().connect()
        
        # Попытка инъекции после connect если ещё не сделано
        if hasattr(self, '_pending_lang_pack') and self._pending_lang_pack:
            if hasattr(self, '_init_request') and self._init_request:
                self._init_request.lang_pack = self._pending_lang_pack
                logging.info(f"✅ lang_pack='{self._pending_lang_pack}' injected after connect")
                del self._pending_lang_pack
        
        return result


# Алиас для совместимости
TelegramClient = ExtendedTelegramClient

from telethon.sessions import StringSession
from config import Config
from telethon.tl.functions.messages import AddChatUserRequest

logger = logging.getLogger(__name__)

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
    from models.proxy_network import ProxyNetwork
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
            print(f"✅ [{account_id}] Using selected API credential: {api_cred.name} (ID: {api_id})")
        else:
            # Fallback to config
            api_id = Config.TG_API_ID
            api_hash = Config.TG_API_HASH
            print(f"⚠️ [{account_id}] API credential not found, using config")
    
    elif account.tdata_metadata and account.tdata_metadata.original_api_id:
        # Use original API from TData
        tdata = account.tdata_metadata
        api_id = tdata.original_api_id
        api_hash = decrypt_api_hash(tdata.original_api_hash) if tdata.original_api_hash else Config.TG_API_HASH
        print(f"✅ [{account_id}] Using original API from TData (ID: {api_id})")
    
    else:
        # Fallback to config
        api_id = Config.TG_API_ID
        api_hash = Config.TG_API_HASH
        print(f"ℹ️ [{account_id}] Using API from config (ID: {api_id})")
    
    # ==================== DEVICE FINGERPRINT ====================
    # Priority: JSON (if selected) > TData binary > DeviceProfile > Defaults
    
    # Generate human-like fingerprint components
    import string
    
    # Current TDesktop versions (as of late 2024/early 2025)
    tdesktop_versions = ["5.6.3", "5.7.1", "5.8.0", "5.9.0"]
    base_version = random.choice(tdesktop_versions)
    
    # FIX: Only 30% of real users have beta/dev suffix
    if random.random() < 0.3:
        app_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        app_version = f"{base_version} x64 {app_suffix}"
    else:
        app_version = f"{base_version} x64"
    
    # Random Windows build numbers (realistic ranges)
    win10_builds = [19041, 19042, 19043, 19044, 19045]  # Windows 10 updates
    win11_builds = [22000, 22621, 22631, 22635]  # Windows 11 versions
    
    # 60% Windows 10, 40% Windows 11 (updated market share)
    if random.random() < 0.6:
        build = random.choice(win10_builds)
        system_ver = f"Windows 10 (Build {build})"
    else:
        build = random.choice(win11_builds)
        system_ver = f"Windows 11 (Build {build})"
    
    # 1. Base values (Fallbacks) - with realistic randomization
    device_params = {
        'device_model': "Desktop",
        'system_version': system_ver,
        'app_version': app_version,
        'lang_code': "en",
        'system_lang_code': "en-US"
    }
    
    if account.tdata_metadata:
        tdata = account.tdata_metadata
        
        # LOGIC: Choose between JSON and TData binary
        # If user selected JSON and data exists - use it
        if getattr(tdata, 'device_source', None) == 'json' and tdata.json_device_model:
            print(f"✅ [{account_id}] Using JSON fingerprint")
            device_params.update({
                'device_model': tdata.json_device_model,
                'system_version': tdata.json_system_version or tdata.system_version,
                'app_version': tdata.json_app_version or tdata.app_version,
                'lang_code': tdata.json_lang_code or tdata.lang_code,
                'system_lang_code': tdata.json_system_lang_code or tdata.system_lang_code
            })
        else:
            # Otherwise use TData binary data
            print(f"✅ [{account_id}] Using TData binary fingerprint")
            device_params.update({
                'device_model': tdata.device_model or "Desktop",
                'system_version': tdata.system_version or "Windows 10",
                'app_version': tdata.app_version or "5.6.3 x64",
                'lang_code': tdata.lang_code or "en",
                'system_lang_code': tdata.system_lang_code or "en-US"
            })
            
    elif account.device_profile:
        # Use device profile (for .session uploads)
        device = account.device_profile
        print(f"ℹ️  [{account_id}] Using device profile: {device.device_model}")
        device_params.update({
            'device_model': device.device_model,
            'system_version': device.system_version,
            'app_version': device.app_version,
            'lang_code': device.lang_code,
            'system_lang_code': device.system_lang_code
        })
    else:
        print(f"⚠️  [{account_id}] Using default device fingerprint")
    
    # ==================== FIX #3: API/DEVICE CONSISTENCY CHECK ====================
    # If api_id is TDesktop (2040) but device_model looks like mobile, override to Desktop
    # This prevents fingerprint mismatch bans
    TDESKTOP_API_ID = 2040
    ANDROID_API_ID = 4
    IOS_API_ID = 6
    
    device_model = device_params.get('device_model', '')
    
    # Detect mobile device patterns
    mobile_patterns = [
        'samsung', 'xiaomi', 'huawei', 'realme', 'oppo', 'vivo', 'oneplus',
        'pixel', 'galaxy', 'redmi', 'poco', 'iphone', 'ipad', 'sm-', 'lg-',
        'nokia', 'motorola', 'sony', 'zte', 'meizu', 'asus', 'lenovo'
    ]
    is_mobile_device = any(pattern in device_model.lower() for pattern in mobile_patterns)
    
    if api_id == TDESKTOP_API_ID and is_mobile_device:
        print(f"⚠️  [{account_id}] FIX #3: Mobile device '{device_model}' with TDesktop API - overriding to Desktop")
        device_params.update({
            'device_model': "Desktop",
            'system_version': "Windows 10",
            'app_version': "5.6.3 x64"
        })
    elif api_id == ANDROID_API_ID and not is_mobile_device and 'android' not in device_model.lower():
        # Android API with desktop device - could be suspicious
        print(f"⚠️  Warning: Desktop device '{device_model}' with Android API - consider changing API type")
    elif api_id == IOS_API_ID and 'iphone' not in device_model.lower() and 'ipad' not in device_model.lower():
        # iOS API with non-Apple device
        print(f"⚠️  Warning: Non-iOS device '{device_model}' with iOS API - consider changing API type")
    
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
    elif account.proxy_network_id and account.assigned_port:
        # ==========================================================
        # 📡 DYNAMIC PROXY NETWORK
        # ==========================================================
        network = ProxyNetwork.query.get(account.proxy_network_id)
        if network:
            from utils.validators import validate_proxy
            # Construct connection string and parse it
            conn_str = f"{network.base_url}:{account.assigned_port}"
            is_valid, res = validate_proxy(conn_str)
            
            if is_valid:
                proxy_type_str = 'socks5' if res['type'] == 'socks5' else 'http'
                proxy_dict = (
                    proxy_type_str,
                    res['host'],
                    res['port'],
                    True, # rdns
                    res.get('username'),
                    res.get('password')
                )
                print(f"✅ [{account_id}] Using Dynamic Proxy Network: '{network.name}' via {res['host']}:{res['port']}")
            else:
                print(f"❌ [{account_id}] Invalid Proxy Network Config ('{network.name}'): {res}")
        else:
            print(f"❌ [{account_id}] Proxy Network {account.proxy_network_id} not found in DB")

    elif account.proxy:
        # ==========================================================
        # 🔒 STATIC INDIVIDUAL PROXY
        # ==========================================================
        if account.proxy.type == "socks5":
            proxy_type_str = 'socks5'
        elif account.proxy.type == "http":
            proxy_type_str = 'http'
        else:
            proxy_type_str = 'socks5'
        
        proxy_dict = (
            proxy_type_str,
            account.proxy.host,
            account.proxy.port,
            True,
            account.proxy.username,
            account.proxy.password
        )
        print(f"✅ [{account_id}] Using Static Proxy: {account.proxy.host}:{account.proxy.port} (type: {proxy_type_str})")
        
        # CRITICAL DEBUG: Log exact proxy tuple
        with open('/tmp/proxy_debug.log', 'a') as f:
            f.write(f"PROXY TUPLE PASSED TO TELETHON: {proxy_dict}\n")
            f.write(f"PROXY TYPE STRING: '{proxy_type_str}' (type: {type(proxy_type_str)})\n")
            
        # ===================================================================
        # 🌍 REAL IP VERIFICATION (Requested by User)
        # ===================================================================
        try:
            import requests
            # Construct requests proxy dict
            auth = f"{account.proxy.username}:{account.proxy.password}@" if account.proxy.username else ""
            requests_proxy = {
                "http": f"{account.proxy.type}://{auth}{account.proxy.host}:{account.proxy.port}",
                "https": f"{account.proxy.type}://{auth}{account.proxy.host}:{account.proxy.port}"
            }
            
            # Short timeout to avoid blocking
            ip_response = requests.get(
                "http://checkip.amazonaws.com", 
                proxies=requests_proxy, 
                timeout=3
            )
            
            if ip_response.status_code == 200:
                real_ip = ip_response.text.strip()
                print(f"🌍 [{account_id}] Proxy Exit IP: {real_ip}")
            else:
                print(f"🌍 [{account_id}] Proxy Exit IP: [Check Failed - Status {ip_response.status_code}]")
                
        except Exception as e:
            # Don't fail the client creation if IP check fails
            print(f"🌍 [{account_id}] Proxy Exit IP: [Check Failed - {str(e)}]")
        # ===================================================================
    
    # ==================== SESSION CONFIGURATION ====================
    # Support both StringSession (DB storage) and SQLite file (TData import)
    session = None
    
    if account.session_string:
        # Preferred: StringSession stored in DB
        session = StringSession(account.session_string)
        print(f"DEBUG: [{account_id}] Using StringSession")
    elif account.session_file_path:
        # Legacy/TData: SQLite file path
        # Ensure path is absolute and clean
        clean_path = account.session_file_path.strip()
        
        if os.path.isabs(clean_path):
            session_path = clean_path
        else:
            # Try 1: Relative to CWD (app root)
            path_1 = os.path.abspath(clean_path)
            # Try 2: Relative to SESSIONS_FOLDER
            path_2 = os.path.join(Config.SESSIONS_FOLDER, clean_path)
            # Try 3: Relative to uploads
            path_3 = os.path.join(Config.UPLOAD_FOLDER, clean_path)
            
            if os.path.exists(path_1):
                session_path = path_1
            elif os.path.exists(path_2):
                session_path = path_2
            elif os.path.exists(path_3):
                session_path = path_3
            else:
                session_path = path_1 # Default to abspath
            
        print(f"DEBUG: [{account_id}] Checking session file: {session_path}")
        
        if os.path.exists(session_path):
            session = session_path  # Telethon accepts str path for SQLiteSession
        print(f"DEBUG: [{account_id}] Using SQLite session file")
        else:
            print(f"WARNING: Session file not found at {session_path}")
            # If we create a new session here, it will be empty.
            if account.source_type == 'tdata':
                 # Try to find it relative to cwd if absolute check failed
                 if os.path.exists(account.session_file_path):
                      session = account.session_file_path
                 else:
                      # CRITICAL: Don't just reset to empty string, raise error to prevent data loss
                      # raise ValueError(f"Session file missing for TData account: {account.session_file_path}")
                      print(f"CRITICAL: TData Session file missing! Account might appear logged out.")
                      session = StringSession('')
            else:
                 session = StringSession('')
    else:
        # Default empty session
        session = StringSession('')

    # Create client using ExtendedTelegramClient (safe lang_pack injection)
    client = TelegramClient(
        session,
        api_id,
        api_hash,
        
        # Device parameters
        device_model=device_params['device_model'],
        system_version=device_params['system_version'],
        app_version=device_params['app_version'],
        lang_code=device_params['lang_code'],
        system_lang_code=device_params['system_lang_code'],
        
        # CRITICAL: lang_pack='tdesktop'
        # Now safely handled by ExtendedTelegramClient via injection
        lang_pack='tdesktop',
        
        proxy=proxy_dict,
        connection_retries=3,
        flood_sleep_threshold=60,
        request_retries=3,
        base_logger=None,
        catch_up=False
    )
    
    logging.info(f"✅ [{account_id}] Client created via ExtendedTelegramClient (lang_pack='tdesktop')")
    
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
    
    # NOTE: lang_pack='tdesktop' is now passed natively via opentele
    # No monkey-patching needed!
    
    return client


async def connect_client(account_id):
    """Connect Telethon client"""
    client = get_telethon_client(account_id)
    if not client.is_connected():
        await client.connect()
    return client


async def verify_session(account_id, force_full=False, disable_anchor=False, client=None):
    """
    Hybrid Session Verification
    - Full Verify: First-time verification with complete handshake + GetMe
    - Light Verify: Subsequent checks using only GetState
    
    Args:
        account_id: Account ID to verify
        force_full: Force full verification even if already verified
        disable_anchor: Skip anchor logic
        client: Optional existing client (for Orchestrator)
    
    Returns:
        dict: {
            "success": bool,
            "user": dict (only for full verify),
            "error": str,
            "wait": int,
            "verification_type": "full" | "light"
        }
    """
    from telethon.errors import (
        FloodWaitError, 
        UserDeactivatedError, 
        UserDeactivatedBanError,
        AuthKeyError,
        AuthKeyUnregisteredError
    )
    from models.account import Account
    from database import db
    from utils.auth_flow import perform_desktop_handshake, verify_session_light
    from datetime import datetime
    import asyncio
    import random
    import os
    
    verification_type = "light"
    # Track if we created the client locally (to close it later)
    created_locally = False
    
    try:
        logger.info(f"🔍 Starting verification for account {account_id}...")
        
        # Load account from DB
        account = db.session.query(Account).get(account_id)
        if not account:
            return {
                "success": False,
                "error": "Account not found",
                "error_type": "not_found"
            }
        
        # Write proxy status to debug log
        try:
            with open('/tmp/proxy_debug.log', 'a') as f:
                f.write(f"\n=== VERIFY SESSION {account_id} ===\n")
                if account.proxy:
                    f.write(f"🔒 PROXY: {account.proxy.host}:{account.proxy.port} ({account.proxy.country})\n")
                else:
                    f.write("⚠️  NO PROXY - SERVER IP EXPOSED!\n")
        except:
             pass

        
        # Determine verification type
        if not account.first_verified_at or not account.telegram_id or force_full:
            verification_type = "full"
            logger.info(f"📋 Verification type: FULL (first-time or forced)")
        else:
            logger.info(f"📋 Verification type: LIGHT (already verified)")
        
        # Use existing client or create new one
        if not client:
            client = get_telethon_client(account_id)
            await client.connect()
            created_locally = True
        
        if not client.is_connected():
            if created_locally:
                await client.connect()
            else:
                 raise Exception("Provided client is not connected")
        
        if not client.is_connected():
            raise Exception("Client failed to connect")
        
        # ==================== FULL VERIFICATION ====================
        if verification_type == "full":
            logger.info("🚀 Starting FULL verification with anti-ban handshake...")
            
            # Prepare session data for handshake
            # We must pass device_params explicitly because we need to construct proper InitConnection
            device_params_for_handshake = {
                'api_id': client.api_id,
                # Re-use the SAME logic as get_telethon_client to ensure consistency
            }
            
            # Re-extract device params from account metadata/profile to be 100% sure
            # (We could also try to extract from client.session but it's safer to have source of truth)
            if account.tdata_metadata:
                tdata = account.tdata_metadata
                if getattr(tdata, 'device_source', None) == 'json' and tdata.json_device_model:
                     device_params_for_handshake.update({
                        'device_model': tdata.json_device_model,
                        'system_version': tdata.json_system_version or tdata.system_version,
                        'app_version': tdata.json_app_version or tdata.app_version,
                        'lang_code': tdata.json_lang_code or tdata.lang_code,
                        'system_lang_code': tdata.json_system_lang_code or tdata.system_lang_code
                     })
                else:
                     device_params_for_handshake.update({
                        'device_model': tdata.device_model or "Desktop",
                        'system_version': tdata.system_version or "Windows 10",
                        'app_version': tdata.app_version or "5.6.3 x64",
                        'lang_code': tdata.lang_code or "en",
                        'system_lang_code': tdata.system_lang_code or "en-US"
                     })
            elif account.device_profile:
                device = account.device_profile
                device_params_for_handshake.update({
                    'device_model': device.device_model,
                    'system_version': device.system_version,
                    'app_version': device.app_version,
                    'lang_code': device.lang_code,
                    'system_lang_code': device.system_lang_code
                })
            else:
                device_params_for_handshake.update({
                    'device_model': "Desktop",
                    'system_version': "Windows 10",
                    'app_version': "5.6.3 x64",
                    'lang_code': "en",
                    'system_lang_code': "en-US"
                })

            # 1. PERFORM SAFE HANDSHAKE
            try:
                await perform_desktop_handshake(client, device_params_for_handshake)
            except Exception as handshake_error:
                logger.error(f"❌ Handshake failed: {handshake_error}")
                return {
                    "success": False,
                    "error": f"Handshake failed: {str(handshake_error)}",
                    "error_type": "handshake_failed",
                    "verification_type": "full"
                }
            
            # 2. NOW SAFELY CALL GetMe
            logger.info("👤 Fetching user info (GetMe)...")
            me = await client.get_me()
            
            if me is None:
                return {
                    "success": False,
                    "user": None,
                    "error": "Session valid but not logged in (get_me returned None)",
                    "error_type": "not_logged_in",
                    "verification_type": "full"
                }
            
            if not hasattr(me, 'id'):
                return {
                    "success": False,
                    "user": None,
                    "error": f"Invalid user object returned: {type(me)}",
                    "error_type": "invalid_response",
                    "verification_type": "full"
                }

            # 🔥 CRITICAL FLAG CHECK (Fixes "Account deleted but check validated" issue)
            if getattr(me, 'deleted', False):
                logger.error(f"❌ Full verification FAILED: Account {me.id} is DELETED")
                return {
                    "success": False,
                    "user": None,
                    "error": "Account is marked as DELETED (Deleted Account)",
                    "error_type": "banned",
                    "verification_type": "full"
                }
            
            if getattr(me, 'restricted', False):
                reason = getattr(me, 'restriction_reason', [])
                reason_str = str(reason) if reason else "Unknown"
                logger.warning(f"⚠️ Account {me.id} is RESTRICTED: {reason_str}")
            
            # Extract user data
            user_data = {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "photo": False
            }
            
            if hasattr(me, "photo") and me.photo:
                try:
                    # Download profile photo
                    from config import Config
                    upload_folder = os.path.join(os.getcwd(), 'uploads', 'photos')
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = f"{me.id}_{int(datetime.utcnow().timestamp())}.jpg"
                    filepath = os.path.join(upload_folder, filename)
                    
                    logger.info(f"📸 Downloading profile photo to {filepath}...")
                    await client.download_profile_photo(me, file=filepath)
                    
                    if os.path.exists(filepath):
                        user_data["photo_path"] = f"uploads/photos/{filename}"
                        user_data["photo"] = True
                        logger.info(f"✅ Photo downloaded: {user_data['photo_path']}")
                    else:
                        logger.warning("⚠️ Photo download appeared successful but file is missing")
                        user_data["photo"] = False
                except Exception as e:
                    logger.error(f"❌ Failed to download photo: {e}")
                    user_data["photo"] = False
            
            # Mark as first verified
            if not account.first_verified_at:
                account.first_verified_at = datetime.utcnow()
                logger.info("✅ First verification completed - timestamp saved")
            
            # TRIGGER DIGITAL ANCHOR (Background Task)
            # TRIGGER DIGITAL ANCHOR (Background Task)
            # Only run if disable_anchor is False (checkbox was checked)
            if not disable_anchor:
                try:
                    from utils.digital_anchor import run_digital_anchor_background
                    run_digital_anchor_background(account_id)
                    logger.info("⚓ Digital Anchor initiated")
                except Exception as anchor_err:
                    logger.warning(f"Failed to start Digital Anchor: {anchor_err}")
            else:
                logger.info("⏭️ Digital Anchor skipped (disabled by user)")
            
            return {
                "success": True,
                "user": user_data,
                "error": None,
                "verification_type": "full"
            }
        
        # ==================== LIGHT VERIFICATION ====================
        else:
            logger.info("⚡ Starting LIGHT verification (GetState only)...")
            
            try:
                # Use light verification from auth_flow
                is_alive = await verify_session_light(client)
                
                if is_alive:
                    logger.info("✅ Light verification passed - session is alive")
                    return {
                        "success": True,
                        "user": None,  # Use existing DB data
                        "error": None,
                        "verification_type": "light"
                    }
                    
            except Exception as light_error:
                # Light verification failed - propagate error
                raise light_error
        
    except FloodWaitError as e:
        logger.error(f"⏱️  FloodWait: {e.seconds}s")
        return {
            "success": False,
            "user": None,
            "error": f"FloodWait: {e.seconds}s",
            "wait": e.seconds,
            "error_type": "flood_wait",
            "verification_type": verification_type
        }
        
    except (UserDeactivatedError, UserDeactivatedBanError) as e:
        logger.error(f"🚫 Account BANNED: {e}")
        return {
            "success": False,
            "user": None,
            "error": "Account is banned/deactivated by Telegram",
            "error_type": "banned",
            "verification_type": verification_type
        }
        
    except (AuthKeyError, AuthKeyUnregisteredError) as e:
        logger.error(f"🔑 Session INVALID: {e}")
        return {
            "success": False,
            "user": None,
            "error": "Session is invalid (AuthKeyError) - session file mismatch",
            "error_type": "invalid_session",
            "verification_type": verification_type
        }
        
    except Exception as e:
        error_msg = str(e)
        
        # Check for specific errors
        if "ACCOUNT_BANNED" in error_msg:
            return {
                "success": False,
                "user": None,
                "error": "Account is banned by Telegram",
                "error_type": "banned",
                "verification_type": verification_type
            }
        elif "SESSION_REVOKED" in error_msg:
            return {
                "success": False,
                "user": None,
                "error": "Session has been revoked",
                "error_type": "invalid_session",
                "verification_type": verification_type
            }
        elif "api_id_invalid" in error_msg.lower() or "api_hash_invalid" in error_msg.lower():
            return {
                "success": False,
                "user": None,
                "error": "The API ID/Hash is invalid or revoked by Telegram",
                "error_type": "invalid_api_key",
                "verification_type": verification_type
            }
        
        logger.error(f"❌ Verification error: {error_msg}", exc_info=True)
        return {
            "success": False,
            "user": None,
            "error": error_msg,
            "error_type": "generic_error",
            "verification_type": verification_type
        }
        
    finally:
        if created_locally and client and client.is_connected():
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
    Get active sessions for account and persist them to DB
    """
    from telethon.tl.functions.account import GetAuthorizationsRequest
    from utils.human_behavior import random_sleep
    from models.account_session import AccountSession
    from database import db
    from datetime import datetime

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
        
        sessions_data = []
        
        # CLEAR existing sessions for this account (full refresh)
        try:
            AccountSession.query.filter_by(account_id=account_id).delete()
            db.session.commit()
        except Exception as db_err:
            db.session.rollback()
            print(f"Error clearing sessions: {db_err}")

        for auth in result.authorizations:
            # Create DB Record
            session_rec = AccountSession(
                account_id=account_id,
                session_hash=str(auth.hash),
                device_model=auth.device_model,
                platform=auth.platform,
                system_version=auth.system_version,
                api_id=auth.api_id,
                app_name=auth.app_name,
                app_version=auth.app_version,
                date_created=auth.date_created,
                date_active=auth.date_active,
                ip=auth.ip,
                country=auth.country,
                region=auth.region,
                is_current=auth.current
            )
            db.session.add(session_rec)
            
            # Add to return list
            sessions_data.append({
                "hash": str(auth.hash),
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
            
        try:
            db.session.commit()
            print(f"✅ Persisted {len(sessions_data)} sessions for account {account_id}")
            
            # Double check count
            saved_count = AccountSession.query.filter_by(account_id=account_id).count()
            
            from utils.debug_logger import debug_log
            debug_log(f"Persistence: Account {account_id} - Saved {len(sessions_data)} sessions. Verified in DB: {saved_count}")
            
        except Exception as commit_err:
            db.session.rollback()
            from utils.debug_logger import debug_log
            debug_log(f"Persistence Error: {commit_err}")
            print(f"❌ Failed to persist sessions: {commit_err}")
            # We still return success because the API call worked
            # But the user needs to know persistence failed if they look at logs
            
        return {"success": True, "sessions": sessions_data}
        
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
        result = await client(ResetAuthorizationRequest(hash=int(session_hash)))
        
        await random_sleep(0.5, 1.5, "confirming termination")
        
        if result:
            logger.info(f"✅ Session {session_hash} terminated successfully")
            return {"success": True}
        else:
            logger.warning(f"❌ Failed to terminate session {session_hash} (API returned False)")
            return {"success": False, "error": "API returned False (session might need password or hash invalid)"}
        
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
