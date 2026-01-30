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
        Convenience method to create a log entry with retry logic for SQLite locks
        """
        import time
        from sqlalchemy.exc import OperationalError
        
        max_retries = 5
        retry_delay = 0.1  # start with 100ms
        
        for attempt in range(max_retries):
            try:
                log = WarmupLog(
                    account_id=account_id,
                    stage_number=stage,
                    action_type=action,
                    status=status,
                    message=message,
                    details=details
                )
                
                
                # Database entry is enough here, console logging is handled by caller (e.g. BaseNodeExecutor)
                db.session.add(log)
                db.session.commit()
                return log
            except OperationalError as e:
                db.session.rollback()
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # exponential backoff
                    continue
                raise e
            except Exception as e:
                db.session.rollback()
                raise e
