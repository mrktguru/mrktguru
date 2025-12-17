from datetime import datetime, time
from app import db


class InviteCampaign(db.Model):
    """Invite campaigns table"""
    __tablename__ = 'invite_campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'))
    status = db.Column(db.String(20), default='draft', index=True)  # draft/active/paused/stopped/completed
    strategy = db.Column(db.String(20), default='safe')  # safe/normal/aggressive/custom
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    paused_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    total_targets = db.Column(db.Integer, default=0)
    invited_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    
    # Settings
    delay_min = db.Column(db.Integer, default=45)
    delay_max = db.Column(db.Integer, default=90)
    invites_per_hour_min = db.Column(db.Integer, default=5)
    invites_per_hour_max = db.Column(db.Integer, default=10)
    burst_limit = db.Column(db.Integer, default=3)
    burst_pause_minutes = db.Column(db.Integer, default=15)
    working_hours_start = db.Column(db.Time, default=time(9, 0))
    working_hours_end = db.Column(db.Time, default=time(22, 0))
    human_like_behavior = db.Column(db.Boolean, default=True)
    auto_pause_on_errors = db.Column(db.Boolean, default=True)
    
    # Relationships
    channel = db.relationship('Channel', backref=db.backref('invite_campaigns', lazy='dynamic'))
    campaign_accounts = db.relationship('CampaignAccount', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')
    source_users = db.relationship('SourceUser', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')
    logs = db.relationship('InviteLog', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<InviteCampaign {self.name}>'


class CampaignAccount(db.Model):
    """Many-to-many relationship between campaigns and accounts"""
    __tablename__ = 'campaign_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('invite_campaigns.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    invites_sent = db.Column(db.Integer, default=0)
    last_invite_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active')  # active/limit_reached/cooldown/error
    
    # Relationships
    account = db.relationship('Account', backref=db.backref('campaign_accounts', lazy='dynamic'))
    
    __table_args__ = (db.UniqueConstraint('campaign_id', 'account_id', name='_campaign_account_uc'),)
    
    def __repr__(self):
        return f'<CampaignAccount campaign={self.campaign_id} account={self.account_id}>'


class SourceUser(db.Model):
    """Users to invite (targets)"""
    __tablename__ = 'source_users'
    
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('invite_campaigns.id'), nullable=False, index=True)
    user_id = db.Column(db.BigInteger)
    username = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    source = db.Column(db.String(255))  # channel username where parsed from
    status = db.Column(db.String(20), default='pending', index=True)  # pending/invited/failed/blacklisted
    invited_at = db.Column(db.DateTime)
    invited_by_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    error_message = db.Column(db.Text)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    priority_score = db.Column(db.Integer, default=50)  # 0-100
    
    # Relationships
    invited_by = db.relationship('Account', backref=db.backref('invited_users', lazy='dynamic'))
    
    def __repr__(self):
        return f'<SourceUser {self.username or self.user_id}>'


class InviteLog(db.Model):
    """Invite action logs"""
    __tablename__ = 'invite_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('invite_campaigns.id'), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    target_user_id = db.Column(db.BigInteger)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    status = db.Column(db.String(20), nullable=False, index=True)  # success/error/flood_wait/user_privacy/peer_flood
    details = db.Column(db.Text)
    
    # Relationships
    account = db.relationship('Account', backref=db.backref('invite_logs', lazy='dynamic'))
    
    def __repr__(self):
        return f'<InviteLog {self.id} {self.status}>'
