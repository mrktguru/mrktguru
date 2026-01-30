"""
CRUD Service - Account listing, detail, deletion

Handles database operations for accounts without Telethon.
"""
import os
from typing import Optional, NamedTuple
from dataclasses import dataclass
from datetime import datetime

from database import db
from models.account import Account, DeviceProfile
from models.proxy import Proxy
from models.proxy_network import ProxyNetwork
from models.activity_log import AccountActivityLog
from modules.accounts.exceptions import AccountNotFoundError


@dataclass
class AccountListResult:
    """Result of list_accounts operation"""
    accounts: list
    proxies: list
    pagination: object


@dataclass
class AccountDetailResult:
    """Result of get_account_detail operation"""
    account: Account
    proxies: list
    proxy_networks: list
    json_device_params: Optional[dict]
    recent_logs: list


class CrudService:
    """Service for account CRUD operations"""
    
    @staticmethod
    def list_accounts(page: int = 1, per_page: int = 50) -> AccountListResult:
        """
        List accounts with pagination.
        
        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            
        Returns:
            AccountListResult with accounts, proxies, and pagination
        """
        pagination = Account.query.order_by(Account.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        proxies = Proxy.query.filter_by(status="active").all()
        
        return AccountListResult(
            accounts=pagination.items,
            proxies=proxies,
            pagination=pagination
        )
    
    @staticmethod
    def get_account_detail(account_id: int) -> AccountDetailResult:
        """
        Get account detail with related data.
        
        Args:
            account_id: Account ID
            
        Returns:
            AccountDetailResult with account and related data
            
        Raises:
            AccountNotFoundError: If account doesn't exist
        """
        account = Account.query.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        
        proxies = Proxy.query.filter_by(status="active").all()
        proxy_networks = ProxyNetwork.query.all()
        
        # Get recent activity logs
        recent_logs = AccountActivityLog.query.filter_by(
            account_id=account_id
        ).order_by(AccountActivityLog.timestamp.desc()).limit(20).all()
        
        # Get JSON device parameters if available
        json_device_params = None
        if account.tdata_metadata and account.tdata_metadata.json_raw_data:
            json_device_params = {
                'device_model': account.tdata_metadata.json_device_model or '',
                'system_version': account.tdata_metadata.json_system_version or '',
                'app_version': account.tdata_metadata.json_app_version or '',
                'lang_code': account.tdata_metadata.json_lang_code or '',
                'system_lang_code': account.tdata_metadata.json_system_lang_code or ''
            }
        
        return AccountDetailResult(
            account=account,
            proxies=proxies,
            proxy_networks=proxy_networks,
            json_device_params=json_device_params,
            recent_logs=recent_logs
        )
    
    @staticmethod
    def delete_account(account_id: int) -> None:
        """
        Delete account and all related records.
        
        Args:
            account_id: Account ID
            
        Raises:
            AccountNotFoundError: If account doesn't exist
            Exception: If deletion fails (rolls back transaction)
        """
        account = Account.query.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        
        try:
            # Delete related records first to avoid constraint errors
            from models.dm_campaign import DMCampaignAccount
            from models.campaign import CampaignAccount
            
            # Delete campaign associations
            DMCampaignAccount.query.filter_by(account_id=account_id).delete()
            CampaignAccount.query.filter_by(account_id=account_id).delete()
            
            # Delete logs and related data (using raw SQL for tables that may not have models)
            tables_to_clean = [
                "invite_logs",
                "dm_messages",
                "account_warmup_channels",
                "warmup_activities",
                "channel_candidates",
                "warmup_logs",
                "warmup_settings",
                "tdata_metadata",
                "warmup_channels",
                "warmup_stages",
                "warmup_schedules",
            ]
            
            for table in tables_to_clean:
                try:
                    if table == "conversation_pairs":
                        db.session.execute(
                            db.text("DELETE FROM conversation_pairs WHERE account_a_id = :aid OR account_b_id = :aid"),
                            {"aid": account_id}
                        )
                    else:
                        db.session.execute(
                            db.text(f"DELETE FROM {table} WHERE account_id = :aid"),
                            {"aid": account_id}
                        )
                except Exception:
                    # Ignore if table doesn't exist (legacy/migration issue)
                    pass
            
            # Also handle conversation_pairs separately
            try:
                db.session.execute(
                    db.text("DELETE FROM conversation_pairs WHERE account_a_id = :aid OR account_b_id = :aid"),
                    {"aid": account_id}
                )
            except Exception:
                pass
            
            # Delete session file and journal if exist
            if account.session_file_path and os.path.exists(account.session_file_path):
                os.remove(account.session_file_path)
                
                # Also delete .session-journal file
                journal_path = account.session_file_path + "-journal"
                if os.path.exists(journal_path):
                    os.remove(journal_path)
            
            # Delete profile photo if exists
            if account.photo_url:
                photo_path = account.photo_url.replace("/uploads/", "uploads/")
                if os.path.exists(photo_path):
                    os.remove(photo_path)
            
            # Delete from database (cascade will handle subscriptions and device_profile)
            db.session.delete(account)
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            raise
    
    @staticmethod
    def get_account(account_id: int) -> Account:
        """
        Get account by ID.
        
        Args:
            account_id: Account ID
            
        Returns:
            Account object
            
        Raises:
            AccountNotFoundError: If account doesn't exist
        """
        account = Account.query.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return account
