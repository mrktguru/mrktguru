import asyncio
import random
import os
import shutil
import logging
from datetime import datetime

from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.errors import PasswordHashInvalidError

from modules.nodes.base import BaseNodeExecutor
from models.account import Account
from utils.warmup_executor import emulate_typing
from database import db
from app import app

logger = logging.getLogger(__name__)

class BioExecutor(BaseNodeExecutor):
    async def execute(self):
        try:
            account = Account.query.get(self.account_id)
            if not account:
                return {'success': False, 'error': 'Account not found'}
            
            # First name
            first_name = self.get_config('first_name')
            if first_name and first_name != account.first_name:
                self.log('info', f"Setting first name: {first_name}", action='set_first_name')
                await emulate_typing(first_name, 'normal', self.account_id)
                await self.client(UpdateProfileRequest(first_name=first_name))
                account.first_name = first_name
                await asyncio.sleep(random.uniform(3, 8))
                self.log('success', f"First name set: {first_name}", action='set_first_name')
            
            # Last name
            last_name = self.get_config('last_name')
            if last_name is not None and last_name != account.last_name:
                await asyncio.sleep(random.uniform(10, 20))
                self.log('info', f"Setting last name: {last_name}", action='set_last_name')
                await emulate_typing(last_name, 'normal', self.account_id)
                await self.client(UpdateProfileRequest(last_name=last_name))
                account.last_name = last_name
                await asyncio.sleep(random.uniform(3, 8))
                self.log('success', f"Last name set: {last_name}", action='set_last_name')
            
            # Bio
            bio = self.get_config('bio')
            if bio is not None and bio != account.bio:
                await asyncio.sleep(random.uniform(10, 20))
                self.log('info', f"Setting bio", action='set_bio')
                await emulate_typing(bio, 'normal', self.account_id)
                await self.client(UpdateProfileRequest(about=bio))
                account.bio = bio
                await asyncio.sleep(random.uniform(2, 5))
                self.log('success', 'Bio updated', action='set_bio')
            
            # Sync back
            await asyncio.sleep(random.uniform(2, 4))
            me = await self.client.get_me()
            
            if me.first_name and me.first_name.strip():
                account.first_name = me.first_name
            if me.last_name and me.last_name.strip():
                account.last_name = me.last_name
            account.bio = getattr(me, 'about', account.bio)
            
            db.session.commit()
            
            return {'success': True, 'message': 'Bio node executed successfully'}
            
        except Exception as e:
            logger.error(f"Bio node failed: {e}")
            self.log('error', f"Bio update failed: {str(e)}", action='bio_error')
            return {'success': False, 'error': str(e)}


class UsernameExecutor(BaseNodeExecutor):
    async def execute(self):
        try:
            account = Account.query.get(self.account_id)
            if not account:
                return {'success': False, 'error': 'Account not found'}
                
            username = self.get_config('username', '').replace('@', '').strip()
            if not username:
                return {'success': False, 'error': 'Username is required'}
            
            if username == account.username:
                return {'success': True, 'message': 'Username already set'}
            
            self.log('info', f"Setting username: @{username}", action='set_username')
            await asyncio.sleep(random.uniform(10, 20))
            await emulate_typing(username, 'normal', self.account_id)
            await self.client(UpdateUsernameRequest(username=username))
            account.username = username
            await asyncio.sleep(random.uniform(3, 8))
            
            db.session.commit()
            self.log('success', f"Username set: @{username}", action='set_username')
            
            return {'success': True, 'message': f'Username set to @{username}'}
            
        except Exception as e:
            logger.error(f"Username node failed: {e}")
            self.log('error', f"Username update failed: {str(e)}", action='username_error')
            return {'success': False, 'error': str(e)}


class PhotoExecutor(BaseNodeExecutor):
    async def execute(self):
        try:
            account = Account.query.get(self.account_id)
            if not account:
                return {'success': False, 'error': 'Account not found'}
            
            source_path = self.get_config('photo_path')
            if not source_path:
                return {'success': False, 'error': 'Photo path is required'}
            
            if not os.path.exists(source_path):
                error_msg = f"Photo file not found: {source_path}"
                self.log('error', error_msg, action='photo_error')
                return {'success': False, 'error': error_msg}
            
            self.log('info', 'Preparing profile photo...', action='upload_photo_start')
            
            me = await self.client.get_me()
            if not me:
                raise Exception("Could not get_me()")

            target_dir = os.path.join(os.getcwd(), 'uploads', 'photos')
            os.makedirs(target_dir, exist_ok=True)
            
            stable_filename = f"{self.account_id}_{me.id}.jpg"
            stable_path = os.path.join(target_dir, stable_filename)
            
            try:
                shutil.copy2(source_path, stable_path)
            except Exception as copy_error:
                raise Exception(f"Failed to process image file: {copy_error}")

            await asyncio.sleep(random.uniform(5, 10))
            
            uploaded_file = await self.client.upload_file(stable_path)
            if not uploaded_file:
                raise Exception("File upload to Telegram failed")
            
            await self.client(UploadProfilePhotoRequest(file=uploaded_file))
            
            relative_path = f"uploads/photos/{stable_filename}"
            try:
                # Re-fetch account to ensure session is active
                current_account = Account.query.get(self.account_id)
                if current_account:
                    current_account.photo_url = relative_path
                    db.session.commit()
                    self.log('info', f"DB updated with stable photo: {relative_path}", action='db_photo_update')
            except Exception as db_e:
                db.session.rollback()
                logger.error(f"Failed to update DB photo_url: {db_e}")
            
            await asyncio.sleep(random.uniform(2, 5))
            self.log('success', 'Photo uploaded and set', action='set_photo')
            
            return {'success': True, 'message': 'Profile photo uploaded'}
            
        except Exception as e:
            logger.error(f"Photo node failed: {e}")
            self.log('error', f"Photo upload failed: {str(e)}", action='photo_error')
            return {'success': False, 'error': str(e)}


class SyncProfileExecutor(BaseNodeExecutor):
    async def execute(self):
        logger.info(f"[{self.account_id}] 🔄 Starting Profile Sync Node...")
        try:
            with app.app_context():
                 # Ensure context if needed for queries not handled by Base
                 # Base executor doesn't enforce context but user code does.
                 # Actually base log() uses WarmupLog which uses db.session.
                 pass

            me = await self.client.get_me()
            if not me:
                return {'success': False, 'error': 'Could not get_me()'}

            about_text = None
            try:
                full_user_data = await self.client(GetFullUserRequest(me))
                if hasattr(full_user_data, 'full_user') and hasattr(full_user_data.full_user, 'about'):
                    about_text = full_user_data.full_user.about
            except Exception as e:
                logger.warning(f"[{self.account_id}] Could not fetch Bio: {e}")

            photo_db_path = None
            if getattr(me, 'photo', None):
                try:
                    upload_folder = os.path.join(os.getcwd(), 'uploads', 'photos')
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    filename = f"{self.account_id}_{me.id}.jpg"
                    filepath = os.path.join(upload_folder, filename)
                    current_db_path = f"uploads/photos/{filename}"
                    
                    should_download = True
                    if os.path.exists(filepath):
                        with app.app_context():
                             acc = Account.query.get(self.account_id)
                             if acc and acc.photo_url == current_db_path:
                                 should_download = False
                    
                    if should_download:
                        await self.client.download_profile_photo(me, file=filepath)
                    
                    if os.path.exists(filepath):
                        photo_db_path = current_db_path
                        
                except Exception as e:
                    logger.error(f"[{self.account_id}] Photo download error: {e}")

            with app.app_context():
                try:
                    account = Account.query.get(self.account_id)
                    if not account:
                        return {'success': False, 'error': 'Account not found in DB'}

                    changed = []
                    if account.telegram_id != me.id:
                        account.telegram_id = me.id
                        changed.append('id')

                    tg_first = me.first_name or ""
                    tg_last = me.last_name or ""
                    tg_username = me.username or ""

                    if account.first_name != tg_first:
                         account.first_name = tg_first
                         changed.append('first_name')
                    if account.last_name != tg_last:
                         account.last_name = tg_last
                         changed.append('last_name')
                    if account.username != tg_username:
                         account.username = tg_username
                         changed.append('username')
                    if about_text is not None and account.bio != about_text:
                         account.bio = about_text
                         changed.append('bio')
                    if photo_db_path and account.photo_url != photo_db_path:
                         account.photo_url = photo_db_path
                         changed.append('photo')
                         
                    if hasattr(account, 'last_sync_at'):
                       account.last_sync_at = datetime.now()

                    db.session.commit()
                    msg = f"Sync complete. Updated: {', '.join(changed) if changed else 'No changes'}"
                    logger.info(f"[{self.account_id}] ✅ {msg}")
                    return {'success': True, 'message': msg}

                except Exception as db_err:
                    db.session.rollback()
                    logger.error(f"[{self.account_id}] DB Error: {db_err}")
                    return {'success': False, 'error': str(db_err)}

        except Exception as e:
            logger.error(f"[{self.account_id}] Sync failed: {e}")
            return {'success': False, 'error': str(e)}


class Set2FAExecutor(BaseNodeExecutor):
    async def execute(self):
        password = self.get_config('password')
        hint = self.get_config('hint', '')
        remove_password = self.get_config('remove_password', False)
        
        with app.app_context():
             # We need context for DB ops inside
             pass

        if remove_password:
            try:
                acc = Account.query.get(self.account_id)
                current_pwd = acc.two_fa_password if acc else None
                
                if not current_pwd:
                    return {'success': False, 'error': 'Cannot remove 2FA: No local password record found.'}

                await self.client.edit_2fa(current_password=current_pwd, new_password=None)
                
                acc = Account.query.get(self.account_id)
                if acc:
                    acc.two_fa_password = None
                    db.session.commit()
                
                msg = "2FA Password Removed Successfully"
                self.log('info', msg, action='remove_2fa')
                return {'success': True, 'message': msg}

            except PasswordHashInvalidError:
                 return {'success': False, 'error': 'Current password incorrect.'}
            except Exception as e:
                return {'success': False, 'error': f"Failed to remove 2FA: {e}"}

        if not password:
            return {'success': False, 'error': 'Password is required'}

        try:
            current_db_pass = None
            acc = Account.query.get(self.account_id)
            if acc:
                current_db_pass = acc.two_fa_password
            
            try:
                await self.client.edit_2fa(
                    current_password=current_db_pass,
                    new_password=password,
                    hint=hint
                )
            except PasswordHashInvalidError:
                 return {'success': False, 'error': 'Invalid current password.'}
            except Exception as e:
                 return {'success': False, 'error': str(e)}

            acc = Account.query.get(self.account_id)
            acc.two_fa_password = password
            db.session.commit()
            
            self.log('info', f"2FA Password updated", action='set_2fa_success')
            return {'success': True, 'message': '2FA Password set successfully'}

        except Exception as e:
            return {'success': False, 'error': str(e)}
