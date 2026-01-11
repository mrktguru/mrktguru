"""
Account Activity Log Model - comprehensive logging of all account actions
"""
from datetime import datetime
from database import db


class AccountActivityLog(db.Model):
    """Comprehensive log of all actions performed with/by an account"""
    __tablename__ = 'account_activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False, index=True)
    
    # Action details
    action_type = db.Column(db.String(50), nullable=False, index=True)
    # Types: verification, login, join_group, leave_group, send_message, 
    #        send_dm, invite_user, read_posts, react, update_profile, etc.
    
    action_category = db.Column(db.String(30), default='general')
    # Categories: system, warmup, campaign, manual, profile
    
    target = db.Column(db.String(500))  # Channel, user, or resource affected
    status = db.Column(db.String(20), default='success')  # success, failed, pending, skipped
    
    # Details
    description = db.Column(db.Text)  # Human-readable description
    details = db.Column(db.Text)  # JSON or detailed info
    error_message = db.Column(db.Text)  # Error details if failed
    
    # Metadata
    ip_address = db.Column(db.String(45))  # IPv4 or IPv6
    user_agent = db.Column(db.String(500))  # Browser/client info
    proxy_used = db.Column(db.String(100))  # Proxy info if used
    
    # Timing
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    duration_ms = db.Column(db.Integer)  # Action duration in milliseconds
    
    # Relationship
    account = db.relationship('Account', backref=db.backref('activity_logs', lazy='dynamic', order_by='AccountActivityLog.timestamp.desc()'))
    
    def __repr__(self):
        return f'<AccountActivityLog {self.action_type} for account {self.account_id} at {self.timestamp}>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'account_id': self.account_id,
            'action_type': self.action_type,
            'action_category': self.action_category,
            'target': self.target,
            'status': self.status,
            'description': self.description,
            'details': self.details,
            'error_message': self.error_message,
            'proxy_used': self.proxy_used,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'duration_ms': self.duration_ms
        }
