"""
Activity Service - Activity logs management

Handles activity log queries and pagination.
"""
from dataclasses import dataclass
from typing import List, Optional

from models.account import Account
from models.activity_log import AccountActivityLog
from modules.accounts.exceptions import AccountNotFoundError


@dataclass
class ActivityLogQuery:
    """Activity log query parameters"""
    account_id: int
    action_type: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    limit: int = 100


@dataclass
class ActivityLogResult:
    """Result of activity log query"""
    logs: List[AccountActivityLog]
    action_types: List[str]
    categories: List[str]
    total_count: int


class ActivityService:
    """Service for activity log operations"""
    
    @staticmethod
    def _get_account_or_raise(account_id: int) -> Account:
        """Get account or raise AccountNotFoundError"""
        account = Account.query.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return account
    
    @staticmethod
    def get_logs(query: ActivityLogQuery) -> ActivityLogResult:
        """
        Get activity logs with filtering.
        
        Args:
            query: ActivityLogQuery with filter parameters
            
        Returns:
            ActivityLogResult with logs and filter options
        """
        # Verify account exists
        ActivityService._get_account_or_raise(query.account_id)
        
        # Build query
        db_query = AccountActivityLog.query.filter_by(account_id=query.account_id)
        
        if query.action_type:
            db_query = db_query.filter_by(action_type=query.action_type)
        if query.category:
            db_query = db_query.filter_by(action_category=query.category)
        if query.status:
            db_query = db_query.filter_by(status=query.status)
        
        # Get total count before limit
        total_count = db_query.count()
        
        # Get logs with limit
        logs = db_query.order_by(
            AccountActivityLog.timestamp.desc()
        ).limit(query.limit).all()
        
        # Get unique filter options (from all logs for this account)
        all_logs = AccountActivityLog.query.filter_by(
            account_id=query.account_id
        ).all()
        
        action_types = sorted(set(
            log.action_type for log in all_logs if log.action_type
        ))
        categories = sorted(set(
            log.action_category for log in all_logs if log.action_category
        ))
        
        return ActivityLogResult(
            logs=logs,
            action_types=action_types,
            categories=categories,
            total_count=total_count
        )
