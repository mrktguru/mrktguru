from datetime import datetime
from database import db

class AccountSession(db.Model):
    """
    Active Telegram sessions for an account.
    Persisted from Telethon's GetAuthorizationsRequest.
    """
    __tablename__ = 'account_sessions'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False, index=True)
    
    # Session Details
    session_hash = db.Column(db.String(255), nullable=False) # Unique ID for the session from Telegram
    device_model = db.Column(db.String(255))
    platform = db.Column(db.String(255))
    system_version = db.Column(db.String(255))
    api_id = db.Column(db.Integer)
    app_name = db.Column(db.String(255))
    app_version = db.Column(db.String(255))
    
    # Activity & Location
    date_created = db.Column(db.DateTime)
    date_active = db.Column(db.DateTime)
    ip = db.Column(db.String(100))
    country = db.Column(db.String(100))
    region = db.Column(db.String(100))
    
    # Status
    is_current = db.Column(db.Boolean, default=False)
    
    # Local metadata
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<AccountSession {self.device_model} ({self.ip})>'

    def to_dict(self):
        return {
            "hash": self.session_hash,
            "device_model": self.device_model,
            "platform": self.platform,
            "system_version": self.system_version,
            "api_id": self.api_id,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "date_created": self.date_created.isoformat() if self.date_created else None,
            "date_active": self.date_active.isoformat() if self.date_active else None,
            "ip": self.ip,
            "country": self.country,
            "region": self.region,
            "current": self.is_current,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }
