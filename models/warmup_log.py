"""
Warmup Log Model
Detailed activity logging for warmup actions
"""
from database import db
from datetime import datetime


class WarmupLog(db.Model):
    __tablename__ = 'warmup_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    
    # Context
    stage_number = db.Column(db.Integer, nullable=True)  # Which stage
    action_type = db.Column(db.String(50), nullable=True)  # Which action
    
    # Log info
    status = db.Column(db.String(20), nullable=False)  # 'info', 'success', 'warning', 'error'
    message = db.Column(db.Text, nullable=False)  # Human-readable message
    details = db.Column(db.JSON, nullable=True)  # Additional data
    
    # Timestamp
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    account = db.relationship('Account', backref=db.backref('warmup_logs', lazy='dynamic'))
    
    def __repr__(self):
        return f'<WarmupLog {self.status}: {self.message[:50]}>'
    
    @staticmethod
    def log(account_id, status, message, stage=None, action=None, details=None):
        """
        Convenience method to create a log entry
        
        Usage:
            WarmupLog.log(22, 'success', 'Profile updated', stage=1, action='set_name')
        """
        log = WarmupLog(
            account_id=account_id,
            stage_number=stage,
            action_type=action,
            status=status,
            message=message,
            details=details
        )
        db.session.add(log)
        db.session.commit()
        return log
