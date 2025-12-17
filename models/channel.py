from database import db
from datetime import datetime


class Channel(db.Model):
    __tablename__ = "channels"
    
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)  # channel/group/supergroup
    username = db.Column(db.String(255), unique=True)
    chat_id = db.Column(db.BigInteger, unique=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    is_admin = db.Column(db.Boolean, default=False)
    admin_rights = db.Column(db.JSON)
    status = db.Column(db.String(20), default="active")
    owner_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    posts = db.relationship("ChannelPost", backref="channel", lazy="dynamic", cascade="all, delete-orphan")
    messages = db.relationship("ChannelMessage", backref="channel", lazy="dynamic", cascade="all, delete-orphan")


class ChannelPost(db.Model):
    __tablename__ = "channel_posts"
    
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("channels.id"), nullable=False)
    message_id = db.Column(db.BigInteger, nullable=False)
    content_type = db.Column(db.String(20), nullable=False)  # text/photo/video/document/poll
    text_content = db.Column(db.Text)
    media_file_path = db.Column(db.String(500))
    is_pinned = db.Column(db.Boolean, default=False)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)
    posted_by_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    views_count = db.Column(db.Integer, default=0)
    reactions_count = db.Column(db.Integer, default=0)


class ChannelMessage(db.Model):
    __tablename__ = "channel_messages"
    
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("channels.id"), nullable=False)
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
    replied_by_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
