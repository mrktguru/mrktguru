"""
Metadata Service - Tags and Source management

Simple operations that don't require Telethon.
"""
from typing import Optional
from database import db
from models.account import Account
from modules.accounts.exceptions import AccountNotFoundError


class MetadataService:
    """Service for account metadata operations (tags, source)"""
    
    @staticmethod
    def get_account_or_raise(account_id: int) -> Account:
        """Get account by ID or raise AccountNotFoundError"""
        account = Account.query.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return account
    
    @staticmethod
    def add_tag(account_id: int, tag: str) -> bool:
        """
        Add a tag to account.
        
        Args:
            account_id: Account ID
            tag: Tag string to add
            
        Returns:
            True if tag was added, False if it already existed
            
        Raises:
            AccountNotFoundError: If account doesn't exist
        """
        account = MetadataService.get_account_or_raise(account_id)
        tag = tag.strip()
        
        if not tag:
            return False
        
        # Initialize list if None
        if account.tags is None:
            account.tags = []
        
        # Create a copy to ensure SQLAlchemy detects change (JSON mutable tracking)
        current_tags = list(account.tags)
        
        if tag in current_tags:
            return False
        
        current_tags.append(tag)
        account.tags = current_tags
        db.session.commit()
        return True
    
    @staticmethod
    def remove_tag(account_id: int, tag: str) -> bool:
        """
        Remove a tag from account.
        
        Args:
            account_id: Account ID
            tag: Tag string to remove
            
        Returns:
            True if tag was removed, False if it didn't exist
            
        Raises:
            AccountNotFoundError: If account doesn't exist
        """
        account = MetadataService.get_account_or_raise(account_id)
        
        if not tag or not account.tags:
            return False
        
        current_tags = list(account.tags)
        
        if tag not in current_tags:
            return False
        
        current_tags.remove(tag)
        account.tags = current_tags
        db.session.commit()
        return True
    
    @staticmethod
    def update_source(account_id: int, source: str) -> bool:
        """
        Update account source field.
        
        Args:
            account_id: Account ID
            source: New source value
            
        Returns:
            True if source was changed, False if same value
            
        Raises:
            AccountNotFoundError: If account doesn't exist
        """
        account = MetadataService.get_account_or_raise(account_id)
        new_source = (source or '').strip()
        
        if new_source == (account.source or ''):
            return False
        
        account.source = new_source
        db.session.commit()
        return True
    
    @staticmethod
    def get_tags(account_id: int) -> list[str]:
        """
        Get all tags for account.
        
        Args:
            account_id: Account ID
            
        Returns:
            List of tags (empty list if none)
            
        Raises:
            AccountNotFoundError: If account doesn't exist
        """
        account = MetadataService.get_account_or_raise(account_id)
        return list(account.tags) if account.tags else []
