"""
Profile Service - Telegram profile updates

Handles profile updates (bio, username, photo) via SessionOrchestrator.
"""
import os
import asyncio
from dataclasses import dataclass
from typing import Optional, List
from werkzeug.utils import secure_filename

from database import db
from models.account import Account
from utils.activity_logger import ActivityLogger
from modules.accounts.exceptions import AccountNotFoundError


@dataclass
class ProfileUpdateResult:
    """Result of profile update operation"""
    success: bool
    updated_fields: List[str] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.updated_fields is None:
            self.updated_fields = []
        if self.errors is None:
            self.errors = []


class ProfileService:
    """Service for Telegram profile updates"""
    
    @staticmethod
    def _get_account_or_raise(account_id: int) -> Account:
        """Get account or raise AccountNotFoundError"""
        account = Account.query.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return account
    
    @staticmethod
    def _run_async(coro):
        """Helper to run async coroutine in sync context"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    @staticmethod
    def update_telegram_profile(
        account_id: int,
        username: str = None,
        bio: str = None,
        photo_file = None  # Werkzeug FileStorage or path string
    ) -> ProfileUpdateResult:
        """
        Update Telegram profile via SessionOrchestrator.
        
        Args:
            account_id: Account ID
            username: New username (without @)
            bio: New bio/about text
            photo_file: Photo file (FileStorage or path)
            
        Returns:
            ProfileUpdateResult with updated fields and any errors
        """
        from modules.telethon import SessionOrchestrator
        from tasks.profile import task_update_profile, task_update_photo, task_update_username
        
        account = ProfileService._get_account_or_raise(account_id)
        logger = ActivityLogger(account_id)
        
        result = ProfileUpdateResult(success=True)
        
        # Handle photo upload if file object
        photo_path = None
        if photo_file:
            if hasattr(photo_file, 'save'):  # FileStorage object
                filename = secure_filename(f"{account.phone}_{photo_file.filename}")
                photo_path = os.path.join("uploads/photos", filename)
                os.makedirs("uploads/photos", exist_ok=True)
                photo_file.save(photo_path)
            elif isinstance(photo_file, str) and os.path.exists(photo_file):
                photo_path = photo_file
        
        # Close session for async operations
        db.session.close()
        
        async def _execute():
            bot = SessionOrchestrator(account_id)
            try:
                updates = []
                errors = []
                
                # Update bio
                if bio is not None:
                    res = await bot.execute(task_update_profile, about=bio)
                    if res.get('success'):
                        updates.append('bio')
                    else:
                        errors.append(f"Bio: {res.get('error', 'Unknown error')}")
                
                # Update username
                if username is not None:
                    res = await bot.execute(task_update_username, username=username)
                    if res.get('success'):
                        updates.append('username')
                    else:
                        errors.append(f"Username: {res.get('error', 'Unknown error')}")
                
                # Update photo
                if photo_path:
                    res = await bot.execute(task_update_photo, photo_path=photo_path)
                    if res.get('success'):
                        updates.append('photo')
                    else:
                        errors.append(f"Photo: {res.get('error', 'Unknown error')}")
                
                return updates, errors
            finally:
                await bot.stop()
        
        try:
            updates, errors = ProfileService._run_async(_execute())
            
            result.updated_fields = updates
            result.errors = errors
            result.success = len(errors) == 0
            
            # Update local DB
            if updates:
                account_ref = Account.query.get(account_id)
                if account_ref:
                    if 'bio' in updates and bio is not None:
                        account_ref.bio = bio
                    if 'username' in updates and username is not None:
                        account_ref.username = username
                    if 'photo' in updates and photo_path:
                        account_ref.photo_url = photo_path
                    db.session.commit()
                    
                    logger.log(
                        action_type='profile_update',
                        status='success',
                        description=f"Updated: {', '.join(updates)}",
                        category='manual'
                    )
            
            if errors:
                logger.log(
                    action_type='profile_update',
                    status='partial' if updates else 'failed',
                    description=f"Errors: {'; '.join(errors)}",
                    category='manual'
                )
            
            return result
            
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            return result
    
    @staticmethod
    def update_local_metadata(
        account_id: int,
        source: str = None,
        tags: List[str] = None
    ) -> Account:
        """
        Update local account metadata (no Telegram API calls).
        
        Args:
            account_id: Account ID
            source: Source string
            tags: List of tags
            
        Returns:
            Updated Account object
        """
        account = ProfileService._get_account_or_raise(account_id)
        
        if source is not None:
            account.source = source
        if tags is not None:
            account.tags = tags
            
        db.session.commit()
        return account
