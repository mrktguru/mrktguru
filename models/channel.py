from datetime import datetime
from app import db


class Channel(db.Model):
    """Target channels/groups table"""
    __tablename__ = 'channels'
    
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)  # channel/group/supergroup
    username = db.Column(db.String(255), unique=True, index=True)
    chat_id = db.Column(db.BigInteger, unique=True, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    is_admin = db.Column(db.Boolean, default=False)
    admin_rights = db.Column(db.JSON)
    status = db.Column(db.String(20), default='active')
    owner_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    owner_account = db.relationship('Account', backref=db.backref('owned_channels', lazy='dynamic'))
    posts = db.relationship('ChannelPost', backref='channel', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('ChannelMessage', backref='channel', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Channel {self.username or self.title}>'


class ChannelPost(db.Model):
    """Channel posts table"""
    __tablename__ = 'channel_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=False)
    message_id = db.Column(db.BigInteger, nullable=False)
    content_type = db.Column(db.String(20), nullable=False)  # text/photo/video/document/poll
    text_content = db.Column(db.Text)
    media_file_path = db.Column(db.String(500))
    is_pinned = db.Column(db.Boolean, default=False)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)
    posted_by_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    views_count = db.Column(db.Integer, default=0)
    reactions_count = db.Column(db.Integer, default=0)
    
    # Relationships
    posted_by = db.relationship('Account', backref=db.backref('posts', lazy='dynamic'))
    
    def __repr__(self):
        return f'<ChannelPost {self.id}>'


class ChannelMessage(db.Model):
    """Incoming messages from groups"""
    __tablename__ = 'channel_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=False)
    message_id = db.Column(db.BigInteger, nullable=False)
    from_user_id = db.Column(db.BigInteger)
    from_username = db.Column(db.String(255))
    from_first_name = db.Column(db.String(255))
    text = db.Column(db.Text)
    received_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_replied = db.Column(db.Boolean, default=False)
    reply_message_id = db.Column(db.BigInteger)
    reply_text = db.Column(db.Text)
    replied_at = db.Column(db.DateTime)
    replied_by_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    
    # Relationships
    replied_by = db.relationship('Account', backref=db.backref('message_replies', lazy='dynamic'))
    
    def __repr__(self):
        return f'<ChannelMessage {self.id}>'
