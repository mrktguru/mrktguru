"""
Warmup Activity Models - tracking warmup actions and conversation pairs
"""
from datetime import datetime
from database import db


class WarmupActivity(db.Model):
    """Log of warmup activities performed by accounts"""
    __tablename__ = 'warmup_activities'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False, index=True)
    day = db.Column(db.Integer, default=0)  # Day of warmup (0-indexed)
    action_type = db.Column(db.String(50), nullable=False)  # read_posts, join_channel, react, conversation
    target = db.Column(db.String(255))  # Channel username or conversation partner account_id
    status = db.Column(db.String(20), default='pending')  # pending, success, failed
    details = db.Column(db.Text)  # Additional info (error message, posts count, etc.)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    account = db.relationship('Account', backref=db.backref('warmup_activities', lazy='dynamic'))
    
    def __repr__(self):
        return f'<WarmupActivity {self.action_type} for account {self.account_id}>'


class ConversationPair(db.Model):
    """Pairs of accounts for warmup conversations"""
    __tablename__ = 'conversation_pairs'
    
    id = db.Column(db.Integer, primary_key=True)
    account_a_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False, index=True)
    account_b_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    last_conversation_at = db.Column(db.DateTime)
    conversation_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    account_a = db.relationship('Account', foreign_keys=[account_a_id], backref=db.backref('conversation_pairs_as_a', lazy='dynamic'))
    account_b = db.relationship('Account', foreign_keys=[account_b_id], backref=db.backref('conversation_pairs_as_b', lazy='dynamic'))
    
    # Unique constraint to prevent duplicate pairs
    __table_args__ = (
        db.UniqueConstraint('account_a_id', 'account_b_id', name='_conversation_pair_uc'),
    )
    
    def __repr__(self):
        return f'<ConversationPair {self.account_a_id} <-> {self.account_b_id}>'


class WarmupChannelTheme(db.Model):
    """Predefined channel themes for warmup subscriptions"""
    __tablename__ = 'warmup_channel_themes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # news, tech, crypto, etc.
    display_name = db.Column(db.String(100), nullable=False)  # Новости, Технологии, etc.
    channels = db.Column(db.Text)  # Comma-separated channel usernames
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_channels_list(self):
        """Return list of channel usernames"""
        if not self.channels:
            return []
        return [ch.strip() for ch in self.channels.split(',') if ch.strip()]
    
    def set_channels_list(self, channels_list):
        """Set channels from list"""
        self.channels = ','.join(channels_list)
    
    def __repr__(self):
        return f'<WarmupChannelTheme {self.name}>'


class AccountWarmupChannel(db.Model):
    """Channels assigned to account for warmup reading"""
    __tablename__ = 'account_warmup_channels'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False, index=True)
    channel_username = db.Column(db.String(255), nullable=False)
    source = db.Column(db.String(50), default='manual')  # manual, theme:news, theme:tech, etc.
    is_active = db.Column(db.Boolean, default=True)
    last_read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    account = db.relationship('Account', backref=db.backref('warmup_channels', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('account_id', 'channel_username', name='_account_warmup_channel_uc'),
    )
    
    def __repr__(self):
        return f'<AccountWarmupChannel {self.channel_username} for {self.account_id}>'
