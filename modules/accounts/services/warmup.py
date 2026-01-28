"""
Warmup Service - Channel discovery and scheduling

Handles warmup channel candidates and schedule management.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from database import db
from models.account import Account
from modules.accounts.exceptions import AccountNotFoundError


@dataclass
class ChannelSearchResult:
    """Result of channel search"""
    success: bool
    results: List[dict]
    error: Optional[str] = None


@dataclass
class ScheduleChannelResult:
    """Result of scheduling a channel visit"""
    success: bool
    node_id: Optional[int] = None
    error: Optional[str] = None


class WarmupService:
    """Service for warmup operations - channel discovery and scheduling"""
    
    @staticmethod
    def _get_account_or_raise(account_id: int) -> Account:
        """Get account or raise AccountNotFoundError"""
        account = Account.query.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return account
    
    @staticmethod
    def search_candidates(account_id: int, query: str = "") -> ChannelSearchResult:
        """
        Search discovered channel candidates.
        
        Args:
            account_id: Account ID
            query: Optional search query (searches title and username)
            
        Returns:
            ChannelSearchResult with matching candidates
        """
        from models.channel_candidate import ChannelCandidate
        
        try:
            base_query = ChannelCandidate.query.filter(
                ChannelCandidate.account_id == account_id
            )
            
            if query:
                base_query = base_query.filter(
                    (ChannelCandidate.title.ilike(f"%{query}%")) |
                    (ChannelCandidate.username.ilike(f"%{query}%"))
                )
            
            candidates = base_query.order_by(
                ChannelCandidate.last_visit_ts.desc()
            ).limit(50).all()
            
            return ChannelSearchResult(
                success=True,
                results=[c.to_dict() for c in candidates]
            )
            
        except Exception as e:
            return ChannelSearchResult(
                success=False,
                results=[],
                error=str(e)
            )
    
    @staticmethod
    def schedule_channel_visit(
        account_id: int,
        channel_id: int,
        action: str = 'view_only',
        read_count: int = 5
    ) -> ScheduleChannelResult:
        """
        Schedule a channel visit in the warmup schedule.
        
        Args:
            account_id: Account ID
            channel_id: Channel candidate ID
            action: 'view_only' or 'subscribe'
            read_count: Number of messages to read
            
        Returns:
            ScheduleChannelResult with node_id on success
        """
        from models.warmup_schedule import WarmupSchedule
        from models.warmup_schedule_node import WarmupScheduleNode
        from models.channel_candidate import ChannelCandidate
        
        try:
            account = WarmupService._get_account_or_raise(account_id)
            
            # Verify candidate exists and belongs to account
            candidate = ChannelCandidate.query.get(channel_id)
            if not candidate or candidate.account_id != account_id:
                return ScheduleChannelResult(
                    success=False,
                    error='Channel candidate not found'
                )
            
            # Get or create active schedule
            schedule = WarmupSchedule.query.filter_by(account_id=account_id).first()
            if not schedule:
                schedule = WarmupSchedule(
                    account_id=account_id,
                    name="Default Schedule",
                    status='active',
                    start_date=datetime.now().date()
                )
                db.session.add(schedule)
                db.session.commit()
            
            # Calculate relative day since account creation
            days_active = (datetime.now().date() - account.created_at.date()).days + 1
            days_active = max(1, days_active)
            
            # Execution time: Now + 1 min
            exec_time = (datetime.now() + timedelta(minutes=1)).strftime("%H:%M")
            
            # Build target identifier
            target = f"@{candidate.username}" if candidate.username else f"https://t.me/c/{candidate.peer_id}"
            
            # Create node
            node = WarmupScheduleNode(
                schedule_id=schedule.id,
                day_number=days_active,
                execution_time=exec_time,
                node_type='subscribe' if action == 'subscribe' else 'visit',
                status='pending',
                config={
                    'target': target,
                    'username': candidate.username,
                    'peer_id': candidate.peer_id,
                    'access_hash': candidate.access_hash,
                    'read_count': read_count,
                    'origin': 'discovered_ui'
                }
            )
            
            db.session.add(node)
            db.session.commit()
            
            return ScheduleChannelResult(success=True, node_id=node.id)
            
        except AccountNotFoundError:
            return ScheduleChannelResult(success=False, error='Account not found')
        except Exception as e:
            db.session.rollback()
            return ScheduleChannelResult(success=False, error=str(e))
    
    @staticmethod  
    def delete_candidate(candidate_id: int) -> bool:
        """
        Delete a channel candidate.
        
        Args:
            candidate_id: Candidate ID
            
        Returns:
            True if deleted, False if not found
        """
        from models.channel_candidate import ChannelCandidate
        
        candidate = ChannelCandidate.query.get(candidate_id)
        if not candidate:
            return False
            
        db.session.delete(candidate)
        db.session.commit()
        return True
    
    @staticmethod
    def trigger_execution() -> bool:
        """
        Trigger immediate execution of pending warmup nodes.
        
        Returns:
            True if triggered successfully
        """
        from workers.scheduler_worker import check_warmup_schedules
        check_warmup_schedules.delay()
        return True
