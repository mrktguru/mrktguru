"""
Proxy Service - Proxy assignment and management

Handles proxy operations for accounts.
"""
from dataclasses import dataclass
from typing import Optional, Literal

from database import db
from models.account import Account
from models.proxy import Proxy
from models.proxy_network import ProxyNetwork
from utils.proxy_manager import assign_dynamic_port, release_dynamic_port
from utils.activity_logger import ActivityLogger
from modules.accounts.exceptions import (
    AccountNotFoundError,
    ProxyNotFoundError,
    ProxyNetworkNotFoundError,
    ProxyAssignmentError
)


@dataclass
class ProxyAssignmentResult:
    """Result of proxy assignment operation"""
    success: bool
    proxy_type: Literal['individual', 'network', 'none']
    proxy_info: Optional[str] = None  # "host:port" or "network_name (port)"
    message: str = ""


class ProxyService:
    """Service for proxy management operations"""
    
    @staticmethod
    def get_account_or_raise(account_id: int) -> Account:
        """Get account by ID or raise AccountNotFoundError"""
        account = Account.query.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return account
    
    @staticmethod
    def clear_proxy(account_id: int) -> ProxyAssignmentResult:
        """
        Remove proxy from account.
        
        Args:
            account_id: Account ID
            
        Returns:
            ProxyAssignmentResult
            
        Raises:
            AccountNotFoundError: If account doesn't exist
        """
        account = ProxyService.get_account_or_raise(account_id)
        logger = ActivityLogger(account_id)
        
        # Clear individual proxy
        if account.proxy_id:
            account.proxy_id = None
        
        # Clear network proxy
        if account.proxy_network_id:
            release_dynamic_port(account, commit=False)
            account.proxy_network_id = None
            account.assigned_port = None
        
        db.session.commit()
        
        logger.log(
            action_type='remove_proxy',
            status='success',
            description='Proxy removed',
            category='system'
        )
        
        return ProxyAssignmentResult(
            success=True,
            proxy_type='none',
            message="Proxy removed"
        )
    
    @staticmethod
    def assign_individual_proxy(account_id: int, proxy_id: int) -> ProxyAssignmentResult:
        """
        Assign individual proxy to account.
        
        Args:
            account_id: Account ID
            proxy_id: Proxy ID
            
        Returns:
            ProxyAssignmentResult
            
        Raises:
            AccountNotFoundError: If account doesn't exist
            ProxyNotFoundError: If proxy doesn't exist
        """
        account = ProxyService.get_account_or_raise(account_id)
        logger = ActivityLogger(account_id)
        
        proxy = Proxy.query.get(proxy_id)
        if not proxy:
            raise ProxyNotFoundError(proxy_id)
        
        # Clear any existing assignment first
        if account.proxy_id:
            account.proxy_id = None
        if account.proxy_network_id:
            release_dynamic_port(account, commit=False)
            account.proxy_network_id = None
            account.assigned_port = None
        
        # Assign new proxy
        account.proxy_id = proxy.id
        db.session.commit()
        
        proxy_info = f"{proxy.host}:{proxy.port}"
        
        logger.log(
            action_type='assign_proxy',
            status='success',
            description=f"Assigned: {proxy.host}",
            category='system'
        )
        
        return ProxyAssignmentResult(
            success=True,
            proxy_type='individual',
            proxy_info=proxy_info,
            message=f"Assigned Individual Proxy: {proxy_info}"
        )
    
    @staticmethod
    def assign_network_proxy(account_id: int, network_id: int) -> ProxyAssignmentResult:
        """
        Assign proxy network to account.
        
        Args:
            account_id: Account ID
            network_id: Proxy Network ID
            
        Returns:
            ProxyAssignmentResult
            
        Raises:
            AccountNotFoundError: If account doesn't exist
            ProxyNetworkNotFoundError: If network doesn't exist
        """
        account = ProxyService.get_account_or_raise(account_id)
        logger = ActivityLogger(account_id)
        
        network = ProxyNetwork.query.get(network_id)
        if not network:
            raise ProxyNetworkNotFoundError(network_id)
        
        # Clear any existing assignment first
        if account.proxy_id:
            account.proxy_id = None
        if account.proxy_network_id:
            release_dynamic_port(account, commit=False)
            account.proxy_network_id = None
            account.assigned_port = None
        
        # Assign network with dynamic port
        port = assign_dynamic_port(account, network_id, commit=False)
        db.session.commit()
        
        proxy_info = f"{network.name} (Port {port})"
        
        logger.log(
            action_type='assign_proxy',
            status='success',
            description=f"Network: {network.name} Port {port}",
            category='system'
        )
        
        return ProxyAssignmentResult(
            success=True,
            proxy_type='network',
            proxy_info=proxy_info,
            message=f"Assigned Network: {proxy_info}"
        )
    
    @staticmethod
    def assign_proxy_from_selection(account_id: int, selection: str) -> ProxyAssignmentResult:
        """
        Assign proxy based on form selection string.
        
        Args:
            account_id: Account ID
            selection: Form value like "proxy_123", "network_456", or ""
            
        Returns:
            ProxyAssignmentResult
            
        Raises:
            AccountNotFoundError: If account doesn't exist
            ProxyNotFoundError: If proxy doesn't exist
            ProxyNetworkNotFoundError: If network doesn't exist
            ProxyAssignmentError: If selection format is invalid
        """
        if not selection:
            return ProxyService.clear_proxy(account_id)
        
        if selection.startswith("proxy_"):
            try:
                proxy_id = int(selection.replace("proxy_", ""))
                return ProxyService.assign_individual_proxy(account_id, proxy_id)
            except ValueError:
                raise ProxyAssignmentError(f"Invalid proxy selection: {selection}")
        
        elif selection.startswith("network_"):
            try:
                network_id = int(selection.replace("network_", ""))
                return ProxyService.assign_network_proxy(account_id, network_id)
            except ValueError:
                raise ProxyAssignmentError(f"Invalid network selection: {selection}")
        
        else:
            raise ProxyAssignmentError(f"Invalid selection format: {selection}")
