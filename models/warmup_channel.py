"""
Warmup Channel Model
Represents channels/groups for warmup subscriptions
"""
from database import db
from datetime import datetime


class WarmupChannel(db.Model):
    __tablename__ = 'warmup_channels'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    
    # Channel info
    channel_id = db.Column(db.BigInteger, nullable=False)  # Telegram channel ID
    username = db.Column(db.String(100), nullable=True)  # @channel_username
    title = db.Column(db.String(200), nullable=True)  # Channel title
    
    # Search info
    search_query = db.Column(db.String(200), nullable=True)  # What was searched to find this
    
    # Action config
    action = db.Column(db.String(20), nullable=False)  # 'subscribe' or 'view_only'
    read_count = db.Column(db.Integer, default=5)  # Number of posts to read
    
    # Status
    status = db.Column(db.String(20), default='pending')  # 'pending', 'in_progress', 'completed', 'failed'
    
    # Result
    posts_read = db.Column(db.Integer, default=0)
    subscribed = db.Column(db.Boolean, default=False)
    error = db.Column(db.Text, nullable=True)
    
    # Timestamps
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    account = db.relationship('Account', backref=db.backref('warmup_channels', lazy='dynamic'))
    
    def __repr__(self):
        return f'<WarmupChannel {self.username or self.channel_id} for Account {self.account_id}>'
    
    def mark_in_progress(self):
        """Mark channel processing as in progress"""
        self.status = 'in_progress'
        db.session.commit()
    
    def mark_completed(self, posts_read, subscribed=False):
        """Mark channel processing as completed"""
        self.status = 'completed'
        self.posts_read = posts_read
        self.subscribed = subscribed
        self.executed_at = datetime.utcnow()
        db.session.commit()
    
    def mark_failed(self, error_message):
        """Mark channel processing as failed"""
        self.status = 'failed'
        self.error = error_message
        self.executed_at = datetime.utcnow()
        db.session.commit()
