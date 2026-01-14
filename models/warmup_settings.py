"""
Warmup Settings Model
Stores warmup configuration for each account
"""
from database import db
from datetime import datetime


class WarmupSettings(db.Model):
    __tablename__ = 'warmup_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False, unique=True)
    
    # Privacy settings (manual)
    privacy_phone = db.Column(db.String(20), default='nobody')  # 'nobody', 'contacts', 'everybody'
    privacy_photo = db.Column(db.String(20), default='contacts')  # 'nobody', 'contacts', 'everybody'
    privacy_status = db.Column(db.String(20), default='contacts')  # Who sees last seen
    
    # Language (manual)
    language = db.Column(db.String(10), default='en')  # 'en', 'ru', etc.
    
    # Timezone & active hours
    timezone = db.Column(db.String(50), nullable=True)  # e.g. 'Europe/Moscow'
    active_hours_start = db.Column(db.Integer, default=8)  # 8 AM
    active_hours_end = db.Column(db.Integer, default=23)  # 11 PM
    
    # Warmup control
    warmup_enabled = db.Column(db.Boolean, default=False)
    warmup_paused = db.Column(db.Boolean, default=False)
    current_stage = db.Column(db.Integer, default=1)  # Current stage number
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    account = db.relationship('Account', backref=db.backref('warmup_settings', uselist=False))
    
    def __repr__(self):
        return f'<WarmupSettings for Account {self.account_id}>'
    
    def is_active_time(self):
        """Check if current time is within active hours"""
        from datetime import datetime
        import pytz
        
        if not self.timezone:
            return True  # No timezone set, assume always active
        
        try:
            tz = pytz.timezone(self.timezone)
            now = datetime.now(tz)
            current_hour = now.hour
            
            return self.active_hours_start <= current_hour < self.active_hours_end
        except:
            return True  # Error, assume active
    
    def can_execute(self):
        """Check if warmup can be executed"""
        return (
            self.warmup_enabled and 
            not self.warmup_paused and 
            self.is_active_time()
        )
