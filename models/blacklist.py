from datetime import datetime
from app import db


class GlobalBlacklist(db.Model):
    """Global user blacklist"""
    __tablename__ = 'global_blacklist'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, index=True)
    username = db.Column(db.String(255), index=True)
    reason = db.Column(db.String(50), nullable=False)  # blocked_us/reported_spam/negative_reply/manual
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    added_by_campaign_id = db.Column(db.Integer)
    notes = db.Column(db.Text)
    
    def __repr__(self):
        return f'<GlobalBlacklist {self.username or self.user_id}>'


class GlobalWhitelist(db.Model):
    """Global user whitelist"""
    __tablename__ = 'global_whitelist'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, index=True)
    username = db.Column(db.String(255), index=True)
    category = db.Column(db.String(50))  # hot_lead/customer/partner/influencer
    priority_level = db.Column(db.Integer, default=1)  # 1-5
    notes = db.Column(db.Text)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<GlobalWhitelist {self.username or self.user_id}>'


class ChannelBlacklist(db.Model):
    """Blacklisted channels (avoid parsing from them)"""
    __tablename__ = 'channel_blacklist'
    
    id = db.Column(db.Integer, primary_key=True)
    channel_username = db.Column(db.String(255), unique=True, nullable=False, index=True)
    reason = db.Column(db.Text)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ChannelBlacklist {self.channel_username}>'
