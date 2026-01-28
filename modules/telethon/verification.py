import logging
import asyncio
import os
from datetime import datetime
from telethon.errors import (
    FloodWaitError,
    UserDeactivatedError,
    UserDeactivatedBanError,
    AuthKeyError,
    AuthKeyUnregisteredError
)

from modules.telethon.client import ClientFactory
from utils.auth_flow import perform_desktop_handshake, verify_session_light

logger = logging.getLogger(__name__)

async def verify_session(account_id, force_full=False, disable_anchor=False, client=None):
    from models.account import Account
    from database import db
    
    verification_type = "light"
    created_locally = False
    
    try:
        logger.info(f"🔍 Starting verification for account {account_id}...")
        
        account = db.session.query(Account).get(account_id)
        if not account:
            return {"success": False, "error": "Account not found", "error_type": "not_found"}

        if not account.first_verified_at or not account.telegram_id or force_full:
            verification_type = "full"
        else:
            verification_type = "light"
            
        if not client:
            client = ClientFactory.create_client(account_id)
            await client.connect()
            created_locally = True
            
        if not client.is_connected():
            if created_locally:
                await client.connect()
            else:
                 raise Exception("Provided client is not connected")

        # FULL VERIFICATION
        if verification_type == "full":
            logger.info("🚀 Starting FULL verification...")
            
            # Construct handshake params from client attributes or account metadata
            # We assume client is configured correctly by ClientFactory
            device_params = {
                'api_id': client.api_id,
                # In a real refactor, we would pass these explicitly or extract from client/account again
                # For now using defaults/logic similar to factory
                 'device_model': 'Desktop', # fallback
                 'system_version': 'Windows 10',
                 'app_version': '5.6.3 x64',
                 'lang_code': 'en',
                 'system_lang_code': 'en-US'
            }
            # Attempt to enrich from account if possible
            if account.device_profile:
                d = account.device_profile
                device_params.update({
                    'device_model': d.device_model,
                    'system_version': d.system_version,
                    'app_version': d.app_version,
                    'lang_code': d.lang_code,
                    'system_lang_code': d.system_lang_code
                })

            try:
                await perform_desktop_handshake(client, device_params)
            except Exception as e:
                logger.error(f"❌ Handshake failed: {e}")
                return {"success": False, "error": f"Handshake failed: {str(e)}", "error_type": "handshake_failed"}

            me = await client.get_me()
            if not me:
                return {"success": False, "error": "Session valid but not logged in", "error_type": "not_logged_in"}
            
            if getattr(me, 'deleted', False):
                 return {"success": False, "error": "Account is marked as DELETED", "error_type": "banned"}

            # Update User Data
            user_data = {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "photo": False
            }
            
            # Download Photo
            if getattr(me, "photo", None):
                 try:
                     upload_folder = os.path.join(os.getcwd(), 'uploads', 'photos')
                     os.makedirs(upload_folder, exist_ok=True)
                     filename = f"{me.id}_{int(datetime.utcnow().timestamp())}.jpg"
                     filepath = os.path.join(upload_folder, filename)
                     await client.download_profile_photo(me, file=filepath)
                     if os.path.exists(filepath):
                         user_data["photo_path"] = f"uploads/photos/{filename}"
                         user_data["photo"] = True
                 except Exception as e:
                     logger.error(f"Failed to download photo: {e}")

            if not account.first_verified_at:
                account.first_verified_at = datetime.utcnow()
                db.session.commit()

            # Digital Anchor
            if not disable_anchor:
                try:
                    from utils.digital_anchor import run_digital_anchor_background
                    run_digital_anchor_background(account_id)
                except Exception as e:
                    logger.warning(f"Failed to start Digital Anchor: {e}")
            
            return {"success": True, "user": user_data, "error": None, "verification_type": "full"}

        # LIGHT VERIFICATION
        else:
            logger.info("⚡ Starting LIGHT verification...")
            if await verify_session_light(client):
                return {"success": True, "user": None, "error": None, "verification_type": "light"}
            else:
                 raise Exception("Light verification failed (GetState returned None)")

    except FloodWaitError as e:
        return {"success": False, "error": f"FloodWait: {e.seconds}s", "wait": e.seconds, "error_type": "flood_wait"}
    except (UserDeactivatedError, UserDeactivatedBanError):
        return {"success": False, "error": "Account is banned", "error_type": "banned"}
    except (AuthKeyError, AuthKeyUnregisteredError):
        return {"success": False, "error": "Session invalid (AuthKeyError)", "error_type": "invalid_session"}
    except Exception as e:
        logger.error(f"Verification error: {e}")
        return {"success": False, "error": str(e), "error_type": "unknown"}
    finally:
        if created_locally and client:
            await client.disconnect()

