"""
Activity Logger - helper functions for logging account actions
"""
from models.activity_log import AccountActivityLog
from database import db
from datetime import datetime
import time


class ActivityLogger:
    """Helper class for logging account activities"""
    
    def __init__(self, account_id):
        self.account_id = account_id
        self.start_time = None
    
    def start_timer(self):
        """Start timing an action"""
        self.start_time = time.time()
    
    def get_duration_ms(self):
        """Get duration since start_timer was called"""
        if self.start_time:
            return int((time.time() - self.start_time) * 1000)
        return None
    
    def log(self, action_type, status='success', target=None, description=None, 
            details=None, error_message=None, category='general', proxy_used=None,
            duration_ms=None, commit=True, visible_on_ui=True):
        """
        Log an account activity
        
        Args:
            action_type: Type of action (verification, login, join_group, etc.)
            status: success, failed, pending, skipped
            target: Target of action (channel, user, etc.)
            description: Human-readable description
            details: Additional details (can be JSON string)
            error_message: Error message if failed
            category: system, warmup, campaign, manual, profile
            proxy_used: Proxy info if used
            duration_ms: Duration in milliseconds
            commit: Whether to commit immediately
        
        Returns:
            AccountActivityLog instance
        """
        # Auto-calculate duration if timer was started
        if duration_ms is None and self.start_time:
            duration_ms = self.get_duration_ms()
        
        log_entry = AccountActivityLog(
            account_id=self.account_id,
            action_type=action_type,
            action_category=category,
            target=target,
            status=status,
            description=description,
            details=details,
            error_message=error_message,
            proxy_used=proxy_used,
            duration_ms=duration_ms,
            timestamp=datetime.utcnow()
        )
        
        
        db.session.add(log_entry)
        
        # Update Account Last Activity Timestamp
        try:
            from models.account import Account
            # Use query.get matching the session context
            account = db.session.query(Account).get(self.account_id)
            if account:
                account.last_activity = datetime.utcnow()
                db.session.add(account)
        except Exception as e:
            print(f"Error updating last_activity: {e}")

        if commit:
            try:
                db.session.commit()
            except Exception as e:
                print(f"Error committing activity log: {e}")
                db.session.rollback()
        
        return log_entry
    
    # Convenience methods for common actions
    
    def log_verification(self, status='success', details=None, error=None, proxy=None):
        """Log account verification"""
        desc = "Account session verified" if status == 'success' else "Verification failed"
        return self.log(
            action_type='verification',
            status=status,
            description=desc,
            details=details,
            error_message=error,
            category='system',
            proxy_used=proxy
        )
    
    def log_login(self, status='success', proxy=None):
        """Log account login/connection"""
        return self.log(
            action_type='login',
            status=status,
            description='Connected to Telegram',
            category='system',
            proxy_used=proxy
        )
    
    def log_join_group(self, channel, status='success', error=None):
        """Log joining a group/channel"""
        desc = f"Joined {channel}" if status == 'success' else f"Failed to join {channel}"
        return self.log(
            action_type='join_group',
            status=status,
            target=channel,
            description=desc,
            error_message=error,
            category='warmup'
        )
    
    def log_leave_group(self, channel, status='success'):
        """Log leaving a group/channel"""
        return self.log(
            action_type='leave_group',
            status=status,
            target=channel,
            description=f"Left {channel}",
            category='manual'
        )
    
    def log_read_posts(self, channel, posts_count, status='success'):
        """Log reading posts from channel"""
        return self.log(
            action_type='read_posts',
            status=status,
            target=channel,
            description=f"Read {posts_count} posts from {channel}",
            details=f"Posts read: {posts_count}",
            category='warmup'
        )
    
    def log_react(self, channel, reaction, status='success', error=None):
        """Log reaction to post"""
        desc = f"Reacted {reaction} in {channel}" if status == 'success' else f"Failed to react in {channel}"
        return self.log(
            action_type='react',
            status=status,
            target=channel,
            description=desc,
            details=f"Reaction: {reaction}",
            error_message=error,
            category='warmup'
        )
    
    def log_send_message(self, target, status='success', error=None, category='warmup'):
        """Log sending a message"""
        desc = f"Sent message to {target}" if status == 'success' else f"Failed to send message to {target}"
        return self.log(
            action_type='send_message',
            status=status,
            target=target,
            description=desc,
            error_message=error,
            category=category
        )
    
    def log_send_dm(self, username, status='success', error=None):
        """Log sending a DM"""
        desc = f"Sent DM to @{username}" if status == 'success' else f"Failed to send DM to @{username}"
        return self.log(
            action_type='send_dm',
            status=status,
            target=f"@{username}",
            description=desc,
            error_message=error,
            category='campaign'
        )
    
    def log_invite_user(self, channel, username, status='success', error=None):
        """Log inviting user to channel"""
        desc = f"Invited @{username} to {channel}" if status == 'success' else f"Failed to invite @{username}"
        return self.log(
            action_type='invite_user',
            status=status,
            target=f"{channel} -> @{username}",
            description=desc,
            error_message=error,
            category='campaign'
        )
    
    def log_profile_update(self, field, status='success', error=None):
        """Log profile update"""
        desc = f"Updated {field}" if status == 'success' else f"Failed to update {field}"
        return self.log(
            action_type='update_profile',
            status=status,
            description=desc,
            details=f"Field: {field}",
            error_message=error,
            category='profile'
        )
    
    def log_sync(self, status='success', items_synced=0):
        """Log profile sync from Telegram"""
        return self.log(
            action_type='sync_profile',
            status=status,
            description=f"Synced profile from Telegram",
            details=f"Items synced: {items_synced}",
            category='system'
        )


# Standalone function for quick logging
def log_account_activity(account_id, action_type, status='success', **kwargs):
    """
    Quick function to log an activity without creating logger instance
    
    Usage:
        log_account_activity(123, 'verification', status='success', proxy='1.2.3.4:1080')
    """
    logger = ActivityLogger(account_id)
    return logger.log(action_type, status=status, **kwargs)
