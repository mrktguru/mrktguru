"""
Subscription Service - Channel subscription management

Handles joining/leaving channels via SessionOrchestrator.
"""
import asyncio
from dataclasses import dataclass
from typing import Optional

from database import db
from models.account import Account, AccountSubscription
from utils.activity_logger import ActivityLogger
from modules.accounts.exceptions import AccountNotFoundError


@dataclass
class JoinResult:
    """Result of channel join operation"""
    success: bool
    status: str  # 'active', 'pending', 'failed'
    message: str
    subscription_id: Optional[int] = None


class SubscriptionService:
    """Service for channel subscription operations"""
    
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
    def _normalize_channel_username(channel_input: str) -> str:
        """Extract clean username from various formats"""
        username = channel_input.strip().lstrip("@")
        if "t.me/" in username:
            username = username.split("t.me/")[-1].split("/")[0].split("?")[0]
        return username
    
    @staticmethod
    def join_channel(
        account_id: int, 
        channel_input: str,
        notes: str = "",
        source: str = "manual"
    ) -> JoinResult:
        """
        Join a Telegram channel/group.
        
        Args:
            account_id: Account ID
            channel_input: Channel username or t.me link
            notes: Optional notes
            source: Subscription source ('manual', 'warmup', etc.)
            
        Returns:
            JoinResult with status and subscription ID
        """
        from utils.session_orchestrator import SessionOrchestrator
        from tasks.warmup import task_join_channel
        
        account = SubscriptionService._get_account_or_raise(account_id)
        channel_username = SubscriptionService._normalize_channel_username(channel_input)
        logger = ActivityLogger(account_id)
        
        if not channel_username:
            return JoinResult(
                success=False, 
                status='failed', 
                message='Channel username is required'
            )
        
        # Check spam-block status
        if account.status == "spam-block":
            return JoinResult(
                success=False,
                status='failed',
                message='Account has spam-block and cannot join channels'
            )
        
        # Check for existing subscription
        existing = AccountSubscription.query.filter_by(
            account_id=account_id,
            channel_username=channel_username
        ).first()
        
        if existing:
            return JoinResult(
                success=False,
                status='exists',
                message=f'Already subscribed to @{channel_username}',
                subscription_id=existing.id
            )
        
        # Log attempt
        logger.log(
            action_type='join_group_attempt',
            status='pending',
            target=f"@{channel_username}",
            description=f"Attempting to join @{channel_username}",
            category='manual' if source == 'manual' else 'warmup'
        )
        
        # Close session for async operation
        db.session.close()
        
        async def _execute():
            bot = SessionOrchestrator(account_id)
            try:
                result = await bot.execute(task_join_channel, channel_username=channel_username)
                return result
            finally:
                await bot.stop()
        
        try:
            result = SubscriptionService._run_async(_execute())
            
            subscription_status = result.get('status', 'failed')
            message = result.get('message', 'Unknown result')
            
            # Log result
            logger = ActivityLogger(account_id)
            if subscription_status == "active":
                logger.log(
                    action_type='join_group',
                    status='success',
                    target=f"@{channel_username}",
                    description=message,
                    category='manual' if source == 'manual' else 'warmup'
                )
            else:
                logger.log(
                    action_type='join_group',
                    status='failed',
                    target=f"@{channel_username}",
                    description=f"Failed to join @{channel_username}",
                    error_message=message,
                    category='manual' if source == 'manual' else 'warmup'
                )
            
            # Save subscription
            subscription = AccountSubscription(
                account_id=account_id,
                channel_username=channel_username,
                subscription_source=source,
                status=subscription_status,
                notes=notes
            )
            db.session.add(subscription)
            db.session.commit()
            
            return JoinResult(
                success=(subscription_status == "active"),
                status=subscription_status,
                message=message,
                subscription_id=subscription.id
            )
            
        except Exception as e:
            # Log error
            logger.log(
                action_type='join_group',
                status='failed',
                target=f"@{channel_username}",
                description=f"Error joining @{channel_username}",
                error_message=str(e),
                category='manual' if source == 'manual' else 'warmup'
            )
            
            # Still save failed subscription for tracking
            subscription = AccountSubscription(
                account_id=account_id,
                channel_username=channel_username,
                subscription_source=source,
                status='failed',
                notes=notes
            )
            db.session.add(subscription)
            db.session.commit()
            
            return JoinResult(
                success=False,
                status='failed',
                message=str(e),
                subscription_id=subscription.id
            )
    
    @staticmethod
    def remove_subscription(account_id: int, subscription_id: int) -> bool:
        """
        Remove a subscription record.
        
        Note: This only removes the local record, doesn't leave the channel.
        
        Args:
            account_id: Account ID (for validation)
            subscription_id: Subscription ID
            
        Returns:
            True if removed, False if not found
        """
        subscription = AccountSubscription.query.filter_by(
            id=subscription_id,
            account_id=account_id
        ).first()
        
        if not subscription:
            return False
        
        db.session.delete(subscription)
        db.session.commit()
        return True
