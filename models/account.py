from datetime import datetime
from database import db


class Account(db.Model):
    """Telegram accounts table"""
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    session_file_path = db.Column(db.String(500), nullable=False)
    session_string = db.Column(db.Text)  # Telethon StringSession for PostgreSQL
    proxy_id = db.Column(db.Integer, db.ForeignKey('proxies.id'))
    status = db.Column(db.String(20), default='active', index=True)  # active/warming_up/cooldown/banned
    health_score = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime)
    warm_up_days_completed = db.Column(db.Integer, default=0)
    warmup_enabled = db.Column(db.Boolean, default=False)  # Manual control for warmup activation
    messages_sent_today = db.Column(db.Integer, default=0)
    invites_sent_today = db.Column(db.Integer, default=0)
    cooldown_until = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    # Telegram user info
    telegram_id = db.Column(db.Integer)
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    username = db.Column(db.String(255))
    bio = db.Column(db.Text)
    photo_url = db.Column(db.String(500))
    last_sync_at = db.Column(db.DateTime)  # Last time synced from Telegram
    
    # Verification & Metadata
    session_metadata = db.Column(db.JSON)
    last_verification_attempt = db.Column(db.DateTime)
    verified = db.Column(db.Boolean, default=False)
    
    # Safe Verification Tracking
    last_verification_method = db.Column(db.String(50))  # 'self_check', 'get_me', 'public_channel'
    last_verification_time = db.Column(db.DateTime)  # For cooldown enforcement
    verification_count = db.Column(db.Integer, default=0)  # Total verifications
    
    # Anti-Ban Authentication Flow
    first_verified_at = db.Column(db.DateTime)  # First successful full verification
    last_check_status = db.Column(db.String(50), default='pending')  # pending/active/banned/error
    
    # FLOOD_WAIT Management
    flood_wait_until = db.Column(db.DateTime)  # When flood wait expires
    flood_wait_action = db.Column(db.String(50))  # Action that triggered flood: 'smart_subscribe', 'send_message', etc.
    last_flood_wait = db.Column(db.DateTime)  # Last time flood wait occurred (for analytics)
    
    # API Credentials (for TData import)
    api_credential_id = db.Column(db.Integer, db.ForeignKey('api_credentials.id'))
    
    # TData Import & Phone Login
    source_type = db.Column(db.String(20), default='session')  # 'session' or 'tdata'
    tdata_archive_path = db.Column(db.String(500))  # Path to original .zip
    phone_code_hash = db.Column(db.String(255))  # For interactive phone login
    two_fa_password = db.Column(db.String(255))  # Local record of 2FA password
    
    # Relationships
    proxy = db.relationship('Proxy', backref=db.backref('accounts', lazy='dynamic'))
    device_profile = db.relationship('DeviceProfile', backref='account', uselist=False, cascade='all, delete-orphan')
    subscriptions = db.relationship('AccountSubscription', backref='account', lazy='dynamic', cascade='all, delete-orphan')
    api_credential = db.relationship('ApiCredential', backref='accounts')
    tdata_metadata = db.relationship('TDataMetadata', backref='account', uselist=False, cascade='all, delete-orphan')
    
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
    client_type = db.Column(db.String(20), default='desktop')  # desktop/ios/android
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
    status = db.Column(db.String(20), default="pending")  # pending/active/failed
    notes = db.Column(db.Text)
    
    def __repr__(self):
        return f'<AccountSubscription {self.channel_username}>'
