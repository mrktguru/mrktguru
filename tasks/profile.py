import logging
import asyncio
import os
from datetime import datetime

logger = logging.getLogger(__name__)

async def task_sync_profile(client):
    """
    Task: Sync Profile from Telegram
    Fetches me, bio, photo and returns enriched data.
    """
    logger.info("⚡ [Task] Syncing profile from Telegram...")
    try:
        # Get user info
        me = await client.get_me()
        if not me:
            raise Exception("get_me returned None")

        data = {
            'telegram_id': me.id,
            'first_name': getattr(me, "first_name", None),
            'last_name': getattr(me, "last_name", None),
            'username': getattr(me, "username", None),
            'phone': getattr(me, "phone", None),
            'bio': None,
            'photo_path': None
        }
        
        # Get bio (about)
        try:
            full_user = await client.get_entity(me)
            if hasattr(full_user, 'about'):
                data['bio'] = full_user.about
        except Exception as e:
            logger.warning(f"Failed to fetch bio: {e}")
        
        # Try to download profile photo
        try:
            if hasattr(me, "photo") and me.photo:
                # We need the phone to name the file, but we might verify if me.phone exists
                # If not, use ID
                identifier = me.phone or me.id
                photo_path = f"uploads/photos/{identifier}_profile.jpg"
                os.makedirs("uploads/photos", exist_ok=True)
                
                await client.download_profile_photo(me, file=photo_path)
                data['photo_path'] = photo_path
            else:
                data['photo_path'] = None # No photo
        except Exception as photo_err:
             logger.warning(f"Failed to download photo: {photo_err}")
             if hasattr(me, "photo") and me.photo:
                 data['photo_path'] = "photo_available" # Fallback marker

        return {'success': True, 'data': data}

    except Exception as e:
        logger.error(f"❌ Profile sync failed: {e}")
        return {'success': False, 'error': str(e)}

async def task_update_profile(client, first_name=None, last_name=None, about=None):
    """
    Task: Update Profile Info (Name, Bio)
    Note: Updating username is more complex and might require different handling.
    """
    from telethon.tl.functions.account import UpdateProfileRequest
    
    logger.info("⚡ [Task] Updating Telegram profile...")
    try:
        # Prepare arguments - UpdateProfileRequest takes optional args
        # Only pass what is not None
        kwargs = {}
        if first_name is not None: kwargs['first_name'] = first_name
        if last_name is not None: kwargs['last_name'] = last_name
        if about is not None: kwargs['about'] = about
        
        if not kwargs:
            return {'success': True, 'message': 'Nothing to update'}

        await client(UpdateProfileRequest(**kwargs))
        return {'success': True}
        
    except Exception as e:
        logger.error(f"❌ Update profile failed: {e}")
        return {'success': False, 'error': str(e)}

async def task_update_username(client, username):
    """
    Task: Update Username
    """
    from telethon.tl.functions.account import UpdateUsernameRequest
    
    logger.info(f"⚡ [Task] Updating username to @{username}...")
    try:
        await client(UpdateUsernameRequest(username=username))
        return {'success': True}
    except Exception as e:
        logger.error(f"❌ Update username failed: {e}")
        return {'success': False, 'error': str(e)}

async def task_update_photo(client, photo_path):
    """
    Task: Update Profile Photo
    """
    from telethon.tl.functions.photos import UploadProfilePhotoRequest
    
    logger.info(f"⚡ [Task] Uploading profile photo: {photo_path}...")
    try:
        file = await client.upload_file(photo_path)
        await client(UploadProfilePhotoRequest(file=file))
        return {'success': True}
    except Exception as e:
        logger.error(f"❌ Upload photo failed: {e}")
        return {'success': False, 'error': str(e)}
