"""
Device Profile Service - Device fingerprint management

Handles device profile CRUD operations without Telegram API.
"""
from dataclasses import dataclass
from typing import Optional

from database import db
from models.account import Account, DeviceProfile
from utils.activity_logger import ActivityLogger
from modules.accounts.exceptions import AccountNotFoundError


@dataclass 
class DeviceConfig:
    """Device profile configuration"""
    device_model: str
    system_version: str
    app_version: str
    lang_code: str = "en"
    system_lang_code: str = "en-US"
    client_type: str = "desktop"


@dataclass
class DeviceUpdateResult:
    """Result of device profile operation"""
    success: bool
    action: str  # 'created', 'updated', 'deleted', 'switched_json'
    message: str
    device: Optional[DeviceProfile] = None


class DeviceProfileService:
    """Service for device profile management"""
    
    @staticmethod
    def _get_account_or_raise(account_id: int) -> Account:
        """Get account or raise AccountNotFoundError"""
        account = Account.query.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return account
    
    @staticmethod
    def use_original_tdata(account_id: int) -> DeviceUpdateResult:
        """
        Switch to original TData device fingerprint.
        Deletes any custom device profile.
        
        Args:
            account_id: Account ID
            
        Returns:
            DeviceUpdateResult
        """
        account = DeviceProfileService._get_account_or_raise(account_id)
        logger = ActivityLogger(account_id)
        
        if account.device_profile:
            old_model = account.device_profile.device_model
            db.session.delete(account.device_profile)
            db.session.commit()
            
            logger.log(
                action_type='device_deleted',
                status='success',
                description=f"Switched to original TData device (was: {old_model})",
                details="Device profile deleted, using original TData fingerprint",
                category='system'
            )
            
            return DeviceUpdateResult(
                success=True,
                action='deleted',
                message='Switched to original TData device'
            )
        else:
            return DeviceUpdateResult(
                success=True,
                action='no_change',
                message='Already using original TData device'
            )
    
    @staticmethod
    def use_json_parameters(account_id: int) -> DeviceUpdateResult:
        """
        Switch to JSON device parameters from TData metadata.
        
        Args:
            account_id: Account ID
            
        Returns:
            DeviceUpdateResult
        """
        account = DeviceProfileService._get_account_or_raise(account_id)
        logger = ActivityLogger(account_id)
        
        if not account.tdata_metadata:
            return DeviceUpdateResult(
                success=False,
                action='error',
                message='No TData metadata or JSON data available'
            )
        
        # Delete device profile if exists
        if account.device_profile:
            db.session.delete(account.device_profile)
        
        # Set device_source to 'json'
        account.tdata_metadata.device_source = 'json'
        db.session.commit()
        
        logger.log(
            action_type='device_source_changed',
            status='success',
            description="Switched to JSON device parameters",
            details="Using JSON metadata for device fingerprint",
            category='system'
        )
        
        return DeviceUpdateResult(
            success=True,
            action='switched_json',
            message='Switched to JSON parameters'
        )
    
    @staticmethod
    def update_custom_device(account_id: int, config: DeviceConfig) -> DeviceUpdateResult:
        """
        Update or create custom device profile.
        
        Args:
            account_id: Account ID
            config: DeviceConfig with device parameters
            
        Returns:
            DeviceUpdateResult with updated device
        """
        account = DeviceProfileService._get_account_or_raise(account_id)
        logger = ActivityLogger(account_id)
        
        if account.device_profile:
            dp = account.device_profile
            old_model = dp.device_model
            
            dp.device_model = config.device_model
            dp.system_version = config.system_version
            dp.app_version = config.app_version
            dp.lang_code = config.lang_code
            dp.system_lang_code = config.system_lang_code
            dp.client_type = config.client_type
            
            action = 'updated'
            msg = f"Device updated: {old_model} → {config.device_model}"
        else:
            dp = DeviceProfile(
                account_id=account_id,
                device_model=config.device_model,
                system_version=config.system_version,
                app_version=config.app_version,
                lang_code=config.lang_code,
                system_lang_code=config.system_lang_code,
                client_type=config.client_type
            )
            db.session.add(dp)
            
            action = 'created'
            msg = f"Device created: {config.device_model}"
        
        db.session.commit()
        
        logger.log(
            action_type=f'device_{action}',
            status='success',
            description=msg,
            details=f"Model: {config.device_model}, System: {config.system_version}, App: {config.app_version}, Client: {config.client_type}",
            category='system'
        )
        
        return DeviceUpdateResult(
            success=True,
            action=action,
            message=msg,
            device=dp
        )
