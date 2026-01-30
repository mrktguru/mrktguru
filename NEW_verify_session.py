"""
Новая версия verify_session для telethon_helper.py
Вставить вместо старой функции verify_session (примерно строка 241)
"""

import logging
logger = logging.getLogger(__name__)


async def verify_session(account_id, force_full=False):
    """
    Hybrid Session Verification
    - Full Verify: First-time verification with complete handshake + GetMe
    - Light Verify: Subsequent checks using only GetState
    
    Args:
        account_id: Account ID to verify
        force_full: Force full verification even if already verified
    
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
    
    client = None
    verification_type = "light"
    
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
        with open('/tmp/proxy_debug.log', 'a') as f:
            f.write(f"\n=== VERIFY SESSION {account_id} ===\n")
            if account.proxy:
                f.write(f"🔒 PROXY: {account.proxy.host}:{account.proxy.port} ({account.proxy.country})\n")
            else:
                f.write("⚠️  NO PROXY - SERVER IP EXPOSED!\n")
        
        # Determine verification type
        if not account.first_verified_at or not account.telegram_id or force_full:
            verification_type = "full"
            logger.info(f"📋 Verification type: FULL (first-time or forced)")
        else:
            logger.info(f"📋 Verification type: LIGHT (already verified)")
        
        # Create client
        client = get_telethon_client(account_id)
        await client.connect()
        
        if not client.is_connected():
            raise Exception("Client failed to connect")
        
        # ==================== FULL VERIFICATION ====================
        if verification_type == "full":
            logger.info("🚀 Starting FULL verification with anti-ban handshake...")
            
            # Prepare session data for handshake
            session_data = {}
            
            # Get device parameters from TData or DeviceProfile
            if account.tdata_metadata:
                tdata = account.tdata_metadata
                
                # Use JSON data if selected
                if tdata.device_source == 'json' and tdata.json_device_model:
                    session_data = {
                        'device_model': tdata.json_device_model,
                        'system_version': tdata.json_system_version or tdata.system_version,
                        'app_version': tdata.json_app_version or tdata.app_version,
                        'lang_code': tdata.json_lang_code or tdata.lang_code,
                        'system_lang_code': tdata.json_system_lang_code or tdata.system_lang_code,
                        'api_id': tdata.original_api_id or client.api_id
                    }
                    logger.info("📱 Using JSON device parameters")
                else:
                    # Use TData device parameters
                    session_data = {
                        'device_model': tdata.device_model or "Desktop",
                        'system_version': tdata.system_version or "Windows 10",
                        'app_version': tdata.app_version or "5.6.3 x64",
                        'lang_code': tdata.lang_code or "en",
                        'system_lang_code': tdata.system_lang_code or "en-US",
                        'api_id': tdata.original_api_id or client.api_id
                    }
                    logger.info("📱 Using TData device parameters")
                    
            elif account.device_profile:
                device = account.device_profile
                session_data = {
                    'device_model': device.device_model,
                    'system_version': device.system_version,
                    'app_version': device.app_version,
                    'lang_code': device.lang_code,
                    'system_lang_code': device.system_lang_code,
                    'api_id': client.api_id
                }
                logger.info("📱 Using DeviceProfile parameters")
            else:
                # Fallback
                session_data = {
                    'device_model': "Desktop",
                    'system_version': "Windows 10",
                    'app_version': "5.6.3 x64",
                    'lang_code': "en",
                    'system_lang_code': "en-US",
                    'api_id': client.api_id
                }
                logger.warning("⚠️  Using fallback device parameters")
            
            # Perform anti-ban handshake
            try:
                await perform_desktop_handshake(client, session_data)
            except Exception as handshake_error:
                logger.error(f"❌ Handshake failed: {handshake_error}")
                return {
                    "success": False,
                    "error": f"Handshake failed: {str(handshake_error)}",
                    "error_type": "handshake_failed",
                    "verification_type": "full"
                }
            
            # Now safe to call GetMe
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
            
            # Extract user data
            user_data = {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "photo": False
            }
            
            if hasattr(me, "photo") and me.photo:
                user_data["photo"] = True
            
            # Mark as first verified
            if not account.first_verified_at:
                account.first_verified_at = datetime.utcnow()
                logger.info("✅ First verification completed - timestamp saved")
            
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
        if client and client.is_connected():
            await client.disconnect()
