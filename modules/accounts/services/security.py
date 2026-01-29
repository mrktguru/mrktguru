"""
Security Service - 2FA and session management

Handles 2FA password operations and session termination.
"""
import asyncio
import random
import string
from dataclasses import dataclass
from typing import Optional

from database import db
from models.account import Account
from modules.accounts.exceptions import (
    AccountNotFoundError,
    TwoFANotSetError,
    TwoFASetError
)


@dataclass
class TwoFAResult:
    """Result of 2FA operation"""
    success: bool
    password: Optional[str] = None
    message: str = ""
    error: Optional[str] = None


@dataclass
class SessionsResult:
    """Result of sessions operation"""
    success: bool
    sessions: Optional[list] = None
    error: Optional[str] = None


class SecurityService:
    """Service for security operations (2FA, sessions)"""
    
    @staticmethod
    def _get_account_or_raise(account_id: int) -> Account:
        """Get account or raise AccountNotFoundError"""
        account = Account.query.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return account
    
    @staticmethod
    def _run_async(coro):
        """Helper to run async coroutine in sync context using asyncio.run()"""
        try:
            return asyncio.run(coro)
        except RuntimeError as e:
            # Handle case where loop is already running
            if "already running" in str(e):
                import asyncio
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(coro)
            raise e
    
    @staticmethod
    def generate_password(length: int = 10) -> str:
        """Generate random alphanumeric password"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    @staticmethod
    def set_2fa(account_id: int) -> TwoFAResult:
        """
        Set 2FA password on account.
        
        Args:
            account_id: Account ID
            
        Returns:
            TwoFAResult with generated password
            
        Raises:
            AccountNotFoundError: If account doesn't exist
        """
        from utils.telethon_helper import set_2fa_password
        
        account = SecurityService._get_account_or_raise(account_id)
        password = SecurityService.generate_password()
        
        try:
            result = SecurityService._run_async(set_2fa_password(account_id, password))
            
            if result.get('success'):
                # Re-fetch account after async operation
                account_ref = Account.query.get(account_id)
                if account_ref:
                    account_ref.two_fa_password = password
                    db.session.commit()
                
                return TwoFAResult(
                    success=True,
                    password=password,
                    message=f'2FA Password Set Successfully: {password}'
                )
            else:
                return TwoFAResult(
                    success=False,
                    error=result.get('error', 'Unknown error')
                )
        
        except Exception as e:
            return TwoFAResult(success=False, error=str(e))
    
    @staticmethod
    def remove_2fa(account_id: int) -> TwoFAResult:
        """
        Remove 2FA password from account.
        
        Args:
            account_id: Account ID
            
        Returns:
            TwoFAResult
            
        Raises:
            AccountNotFoundError: If account doesn't exist
            TwoFANotSetError: If no local 2FA password stored
        """
        from utils.telethon_helper import remove_2fa_password
        
        account = SecurityService._get_account_or_raise(account_id)
        
        current_password = account.two_fa_password
        if not current_password:
            raise TwoFANotSetError(account_id)
        
        try:
            result = SecurityService._run_async(
                remove_2fa_password(account_id, current_password)
            )
            
            if result.get('success'):
                # Re-fetch account after async operation
                account_ref = Account.query.get(account_id)
                if account_ref:
                    account_ref.two_fa_password = None
                    db.session.commit()
                
                return TwoFAResult(
                    success=True,
                    message='2FA Password Removed Successfully'
                )
            else:
                return TwoFAResult(
                    success=False,
                    error=result.get('error', 'Unknown error')
                )
        
        except Exception as e:
            return TwoFAResult(success=False, error=str(e))
    
    @staticmethod
    def get_active_sessions(account_id: int) -> SessionsResult:
        """
        Get active Telegram sessions.
        
        Args:
            account_id: Account ID
            
        Returns:
            SessionsResult with session list
            
        Raises:
            AccountNotFoundError: If account doesn't exist
        """
        from utils.telethon_helper import get_active_sessions
        
        _ = SecurityService._get_account_or_raise(account_id)
        
        try:
            result = SecurityService._run_async(get_active_sessions(account_id))
            return SessionsResult(
                success=result.get('success', False),
                sessions=result.get('sessions'),
                error=result.get('error')
            )
        except Exception as e:
            return SessionsResult(success=False, error=str(e))
    
    @staticmethod
    def terminate_session(account_id: int, session_hash: str) -> TwoFAResult:
        """
        Terminate a specific Telegram session.
        
        Args:
            account_id: Account ID
            session_hash: Session hash to terminate
            
        Returns:
            TwoFAResult
            
        Raises:
            AccountNotFoundError: If account doesn't exist
        """
        from utils.telethon_helper import terminate_session
        
        _ = SecurityService._get_account_or_raise(account_id)
        
        try:
            result = SecurityService._run_async(terminate_session(account_id, session_hash))
            return TwoFAResult(
                success=result.get('success', False),
                message='Session terminated' if result.get('success') else '',
                error=result.get('error')
            )
        except Exception as e:
            return TwoFAResult(success=False, error=str(e))
    
    @staticmethod
    def terminate_all_sessions(account_id: int) -> TwoFAResult:
        """
        Terminate all Telegram sessions except current.
        
        Args:
            account_id: Account ID
            
        Returns:
            TwoFAResult
            
        Raises:
            AccountNotFoundError: If account doesn't exist
        """
        from utils.telethon_helper import terminate_all_sessions
        
        _ = SecurityService._get_account_or_raise(account_id)
        
        try:
            result = SecurityService._run_async(terminate_all_sessions(account_id))
            return TwoFAResult(
                success=result.get('success', False),
                message='All sessions terminated' if result.get('success') else '',
                error=result.get('error')
            )
        except Exception as e:
            return TwoFAResult(success=False, error=str(e))
