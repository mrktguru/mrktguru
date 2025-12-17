from datetime import datetime, time
from app import db


class DMCampaign(db.Model):
    """Direct message campaigns table"""
    __tablename__ = 'dm_campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    message_text = db.Column(db.Text, nullable=False)
    media_type = db.Column(db.String(20), default='none')  # none/photo/video/audio/document
    media_file_path = db.Column(db.String(500))
    status = db.Column(db.String(20), default='draft', index=True)  # draft/active/paused/stopped/completed/limit_reached
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    paused_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    total_targets = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    
    # Settings
    messages_per_account_limit = db.Column(db.Integer, default=5)
    delay_min = db.Column(db.Integer, default=60)
    delay_max = db.Column(db.Integer, default=180)
    working_hours_start = db.Column(db.Time, default=time(9, 0))
    working_hours_end = db.Column(db.Time, default=time(22, 0))
    
    # Relationships
    dm_campaign_accounts = db.relationship('DMCampaignAccount', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')
    targets = db.relationship('DMTarget', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('DMMessage', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<DMCampaign {self.name}>'


class DMCampaignAccount(db.Model):
    """Many-to-many relationship between DM campaigns and accounts"""
    __tablename__ = 'dm_campaign_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('dm_campaigns.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    messages_sent = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='active')  # active/limit_reached/error
    
    # Relationships
    account = db.relationship('Account', backref=db.backref('dm_campaign_accounts', lazy='dynamic'))
    
    __table_args__ = (db.UniqueConstraint('campaign_id', 'account_id', name='_dm_campaign_account_uc'),)
    
    def __repr__(self):
        return f'<DMCampaignAccount campaign={self.campaign_id} account={self.account_id}>'


class DMTarget(db.Model):
    """DM targets table"""
    __tablename__ = 'dm_targets'
    
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('dm_campaigns.id'), nullable=False, index=True)
    username = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    custom_data = db.Column(db.JSON)  # additional fields from CSV
    source = db.Column(db.String(20), default='manual')  # manual/csv/xls
    status = db.Column(db.String(20), default='new', index=True)  # new/sent/error/deleted
    sent_at = db.Column(db.DateTime)
    sent_by_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    error_message = db.Column(db.Text)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    replied_at = db.Column(db.DateTime)
    
    # Relationships
    sent_by = db.relationship('Account', backref=db.backref('dm_targets', lazy='dynamic'))
    
    def __repr__(self):
        return f'<DMTarget {self.username}>'


class DMMessage(db.Model):
    """DM conversation history"""
    __tablename__ = 'dm_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('dm_campaigns.id'), nullable=False, index=True)
    target_id = db.Column(db.Integer, db.ForeignKey('dm_targets.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    direction = db.Column(db.String(10), nullable=False)  # outgoing/incoming
    message_text = db.Column(db.Text)
    has_media = db.Column(db.Boolean, default=False)
    media_type = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_read = db.Column(db.Boolean, default=False)
    telegram_message_id = db.Column(db.BigInteger)
    
    # Relationships
    target = db.relationship('DMTarget', backref=db.backref('messages', lazy='dynamic'))
    account = db.relationship('Account', backref=db.backref('dm_messages', lazy='dynamic'))
    
    def __repr__(self):
        return f'<DMMessage {self.id} {self.direction}>'
