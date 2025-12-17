from datetime import datetime
from app import db


class Account(db.Model):
    """Telegram accounts table"""
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    session_file_path = db.Column(db.String(500), nullable=False)
    proxy_id = db.Column(db.Integer, db.ForeignKey('proxies.id'))
    status = db.Column(db.String(20), default='active', index=True)  # active/warming_up/cooldown/banned
    health_score = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime)
    warm_up_days_completed = db.Column(db.Integer, default=0)
    messages_sent_today = db.Column(db.Integer, default=0)
    invites_sent_today = db.Column(db.Integer, default=0)
    cooldown_until = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    # Relationships
    proxy = db.relationship('Proxy', backref=db.backref('accounts', lazy='dynamic'))
    device_profile = db.relationship('DeviceProfile', backref='account', uselist=False, cascade='all, delete-orphan')
    subscriptions = db.relationship('AccountSubscription', backref='account', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Account {self.phone}>'


class DeviceProfile(db.Model):
    """Device emulation profiles"""
    __tablename__ = 'device_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), unique=True, nullable=False)
    device_model = db.Column(db.String(100), nullable=False)
    system_version = db.Column(db.String(50), nullable=False)
    app_version = db.Column(db.String(50), nullable=False)
    lang_code = db.Column(db.String(10), default='ru')
    system_lang_code = db.Column(db.String(10), default='ru-RU')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<DeviceProfile {self.device_model}>'


class AccountSubscription(db.Model):
    """Channel subscriptions for warm-up"""
    __tablename__ = 'account_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    channel_username = db.Column(db.String(255), nullable=False)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    subscription_source = db.Column(db.String(20), default='manual')  # manual/auto/template
    notes = db.Column(db.Text)
    
    def __repr__(self):
        return f'<AccountSubscription {self.channel_username}>'
