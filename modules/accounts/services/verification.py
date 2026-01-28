"""
Verification Service - Telethon-based account verification

Handles async verification operations with SessionOrchestrator.
"""
import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Literal

from database import db
from models.account import Account
from utils.activity_logger import ActivityLogger
from modules.accounts.exceptions import (
    AccountNotFoundError,
    SessionNotConfiguredError,
    TelegramFloodWaitError,
    TelegramBannedError,
    TelegramSessionInvalidError,
    TelegramHandshakeError,
    CooldownError
)


@dataclass
class VerificationResult:
    """Result of verification operation"""
    success: bool
    verification_type: Literal['full', 'light', 'safe', 'unknown'] = 'unknown'
    message: str = ""
    user_data: Optional[dict] = None
    error_type: Optional[str] = None
    wait_seconds: int = 0


@dataclass
class SyncResult:
    """Result of sync operation"""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


class VerificationService:
    """Service for account verification and sync operations"""
    
    @staticmethod
    def _get_account_or_raise(account_id: int) -> Account:
        """Get account or raise AccountNotFoundError"""
        account = Account.query.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return account
    
    @staticmethod
    def _check_session_configured(account: Account) -> None:
        """Check if session is configured, raise if not"""
        has_session_string = bool(account.session_string)
        has_session_file = account.session_file_path and os.path.exists(account.session_file_path)
        
        if not has_session_string and not has_session_file:
            raise SessionNotConfiguredError(account.id)
    
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
    def verify_account(account_id: int, enable_anchor: bool = False) -> VerificationResult:
        """
        Verify account using SessionOrchestrator.
        
        Args:
            account_id: Account ID
            enable_anchor: Whether to enable anti-ban anchor
            
        Returns:
            VerificationResult with success status and user data
            
        Raises:
            AccountNotFoundError: If account doesn't exist
            SessionNotConfiguredError: If session not configured
        """
        from utils.session_orchestrator import SessionOrchestrator
        from utils.telethon_helper import verify_session
        
        account = VerificationService._get_account_or_raise(account_id)
        VerificationService._check_session_configured(account)
        
        logger = ActivityLogger(account_id)
        
        # Log start
        logger.log(
            action_type='verification_start',
            status='pending',
            description='Starting risk-based verification',
            category='system'
        )
        
        # Update attempt time
        try:
            if hasattr(Account, 'last_verification_attempt'):
                account.last_verification_attempt = datetime.now()
                db.session.commit()
        except Exception:
            db.session.rollback()
        
        # Close session for long async operation
        db.session.close()
        
        async def _execute():
            bot = SessionOrchestrator(account_id)
            try:
                async def task_full_verify(client):
                    return await verify_session(
                        account_id, 
                        force_full=True, 
                        disable_anchor=not enable_anchor, 
                        client=client
                    )
                
                result = await bot.execute(task_full_verify)
                return result
            finally:
                await bot.stop()
        
        try:
            result = VerificationService._run_async(_execute())
            
            # Re-fetch account after async operation
            account_ref = Account.query.get(account_id)
            if not account_ref:
                return VerificationResult(success=False, message="Account not found after verification")
            
            if result.get('success'):
                verification_type = result.get('verification_type', 'unknown')
                
                # FULL VERIFICATION - Update all user data
                if verification_type == 'full' and result.get('user'):
                    user = result['user']
                    
                    account_ref.telegram_id = user.get('id')
                    if user.get('last_name') and user['last_name'].strip():
                        account_ref.last_name = user['last_name']
                    if user.get('first_name'):
                        account_ref.first_name = user['first_name']
                    elif not account_ref.first_name:
                        account_ref.first_name = user.get('first_name')
                    if user.get('username'):
                        account_ref.username = user['username']
                    
                    account_ref.status = 'active'
                    account_ref.last_check_status = 'active'
                    
                    if user.get('photo_path'):
                        account_ref.photo_url = user['photo_path']
                    elif user.get('photo'):
                        account_ref.photo_url = "photo_available"
                    
                    if hasattr(Account, 'verified'):
                        try:
                            account_ref.verified = True
                        except Exception:
                            pass
                    
                    db.session.commit()
                    logger.log(
                        action_type='verification_success', 
                        status='success', 
                        description='Full verification with handshake'
                    )
                    
                    return VerificationResult(
                        success=True,
                        verification_type='full',
                        message='Account verified (Full verification with anti-ban handshake)',
                        user_data=user
                    )
                
                # LIGHT VERIFICATION - Only update status
                elif verification_type == 'light':
                    account_ref.status = 'active'
                    account_ref.last_check_status = 'active'
                    db.session.commit()
                    
                    logger.log(
                        action_type='verification_success', 
                        status='success', 
                        description='Light verification passed'
                    )
                    
                    return VerificationResult(
                        success=True,
                        verification_type='light',
                        message='Account check passed (Light verification)'
                    )
                
                else:
                    return VerificationResult(
                        success=True,
                        verification_type='unknown',
                        message='Verification successful'
                    )
            
            else:
                # Handle failure
                error_type = result.get('error_type', 'generic_error')
                error_msg = result.get('error', 'Unknown error')
                
                if error_type == 'flood_wait':
                    wait_time = result.get('wait', 0)
                    account_ref.status = 'flood_wait'
                    account_ref.last_check_status = 'flood_wait'
                    db.session.commit()
                    logger.log(
                        action_type='verification_failed', 
                        status='error', 
                        description=f"FloodWait: {wait_time}s",
                        category='system'
                    )
                    return VerificationResult(
                        success=False,
                        error_type='flood_wait',
                        message=f'FloodWait: {wait_time}s',
                        wait_seconds=wait_time
                    )
                
                elif error_type == 'banned':
                    account_ref.status = 'banned'
                    account_ref.last_check_status = 'banned'
                    account_ref.health_score = 0
                    db.session.commit()
                    logger.log(
                        action_type='verification_failed', 
                        status='error', 
                        description=f"BANNED: {error_msg}",
                        category='system'
                    )
                    return VerificationResult(
                        success=False,
                        error_type='banned',
                        message=f'Account BANNED: {error_msg}'
                    )
                
                elif error_type == 'invalid_session':
                    account_ref.status = 'error'
                    account_ref.last_check_status = 'session_invalid'
                    db.session.commit()
                    logger.log(
                        action_type='verification_failed', 
                        status='error', 
                        description=f"Invalid: {error_msg}",
                        category='system'
                    )
                    return VerificationResult(
                        success=False,
                        error_type='invalid_session',
                        message=f'Session Invalid: {error_msg}'
                    )
                
                elif error_type == 'handshake_failed':
                    account_ref.status = 'error'
                    account_ref.last_check_status = 'handshake_failed'
                    db.session.commit()
                    logger.log(
                        action_type='verification_failed', 
                        status='error', 
                        description=f"Handshake: {error_msg}",
                        category='system'
                    )
                    return VerificationResult(
                        success=False,
                        error_type='handshake_failed',
                        message=f'Handshake failed: {error_msg}'
                    )
                
                else:
                    account_ref.status = 'error'
                    account_ref.last_check_status = 'error'
                    db.session.commit()
                    logger.log(
                        action_type='verification_failed', 
                        status='error', 
                        description=f"Error: {error_msg}",
                        category='system'
                    )
                    return VerificationResult(
                        success=False,
                        error_type='generic_error',
                        message=f'Failed: {error_msg}'
                    )
        
        except Exception as e:
            logger.log(
                action_type='verification_error', 
                status='error', 
                description=f"System Error: {str(e)}",
                category='system'
            )
            return VerificationResult(
                success=False,
                error_type='system_error',
                message=f'System Error: {str(e)}'
            )
    
    @staticmethod
    def sync_profile(account_id: int) -> SyncResult:
        """
        Sync profile info from Telegram.
        
        Args:
            account_id: Account ID
            
        Returns:
            SyncResult with synced data
            
        Raises:
            AccountNotFoundError: If account doesn't exist
            CooldownError: If sync is on cooldown
        """
        from utils.session_orchestrator import SessionOrchestrator
        from utils.telethon_helper import verify_session
        
        account = VerificationService._get_account_or_raise(account_id)
        
        # Check cooldown (5 minutes)
        COOLDOWN_MINUTES = 5
        if account.last_sync_at:
            time_since_sync = datetime.utcnow() - account.last_sync_at
            if time_since_sync < timedelta(minutes=COOLDOWN_MINUTES):
                remaining = COOLDOWN_MINUTES - int(time_since_sync.total_seconds() / 60)
                raise CooldownError("Sync", remaining)
        
        # Close session for long async operation
        db.session.close()
        
        async def _execute():
            bot = SessionOrchestrator(account_id)
            try:
                async def task_sync(client):
                    return await verify_session(account_id, force_full=True, client=client)
                
                result = await bot.execute(task_sync)
                return result
            finally:
                await bot.stop()
        
        try:
            result = VerificationService._run_async(_execute())
            
            # Re-fetch account
            account_ref = Account.query.get(account_id)
            if not account_ref:
                return SyncResult(success=False, error="Account not found")
            
            if result.get('success'):
                user = result.get('user', {})
                
                if user.get('id'):
                    account_ref.telegram_id = user['id']
                if user.get('first_name'):
                    account_ref.first_name = user['first_name']
                if user.get('last_name'):
                    account_ref.last_name = user['last_name']
                if user.get('username'):
                    account_ref.username = user['username']
                if user.get('photo_path'):
                    account_ref.photo_url = user['photo_path']
                elif user.get('photo'):
                    account_ref.photo_url = "photo_available"
                
                account_ref.last_sync_at = datetime.utcnow()
                
                logger = ActivityLogger(account_id)
                logger.log(
                    action_type='sync_success',
                    status='success',
                    description='Profile synced from Telegram',
                    category='system'
                )
                
                db.session.commit()
                return SyncResult(success=True, data=user)
            else:
                return SyncResult(success=False, error=result.get('error'))
        
        except Exception as e:
            return SyncResult(success=False, error=str(e))
    
    @staticmethod
    def human_check(account_id: int) -> VerificationResult:
        """
        Run human-like spam block check.
        
        Args:
            account_id: Account ID
            
        Returns:
            VerificationResult with clean/restricted status
            
        Raises:
            AccountNotFoundError: If account doesn't exist
        """
        from utils.session_orchestrator import SessionOrchestrator
        from tasks.basic import task_check_spamblock
        
        _ = VerificationService._get_account_or_raise(account_id)
        
        # Close session for long async operation
        db.session.close()
        
        async def _execute():
            bot = SessionOrchestrator(account_id)
            try:
                result = await bot.execute(task_check_spamblock)
                return result
            finally:
                await bot.stop()
        
        try:
            result = VerificationService._run_async(_execute())
            
            # Re-fetch account
            account_ref = Account.query.get(account_id)
            if not account_ref:
                return VerificationResult(success=False, message="Account not found")
            
            status = result.get('status', 'unknown')
            logger = ActivityLogger(account_id)
            
            if status == 'clean':
                if account_ref.status != 'active':
                    account_ref.status = 'active'
                db.session.commit()
                
                logger.log(
                    action_type='human_check_success',
                    status='success',
                    description='Human Check: 🟢 CLEAN. Status -> Active',
                    category='system'
                )
                return VerificationResult(
                    success=True,
                    message='Human Check: CLEAN',
                    verification_type='safe'
                )
            
            elif status == 'restricted':
                reason = result.get('reason', 'Unknown restriction')
                account_ref.status = 'banned'
                account_ref.health_score = 0
                db.session.commit()
                
                logger.log(
                    action_type='human_check_failed',
                    status='failed',
                    description=f'Human Check: 🔴 RESTRICTED. Reason: {reason}',
                    category='security'
                )
                return VerificationResult(
                    success=False,
                    error_type='restricted',
                    message=f'RESTRICTED: {reason}'
                )
            
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.log(
                    action_type='human_check_error',
                    status='error',
                    description=f'Human Check Error: {error_msg}',
                    category='system'
                )
                return VerificationResult(
                    success=False,
                    error_type='error',
                    message=error_msg
                )
        
        except Exception as e:
            return VerificationResult(
                success=False,
                error_type='system_error',
                message=str(e)
            )
