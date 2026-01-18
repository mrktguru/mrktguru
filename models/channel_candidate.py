"""
Channel Candidate Model
Stores discovered Telegram channels/groups pending subscription
"""
from datetime import datetime
from database import db


class ChannelCandidate(db.Model):
    """Discovered channels/groups from search and filter operations"""
    __tablename__ = 'channel_candidates'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    
    # Telegram identifiers
    peer_id = db.Column(db.BigInteger, nullable=False, index=True)
    access_hash = db.Column(db.BigInteger, nullable=False)
    username = db.Column(db.String(255), index=True)
    title = db.Column(db.String(255))
    
    # Classification
    type = db.Column(db.String(20))  # CHANNEL, MEGAGROUP
    language = db.Column(db.String(5))  # RU, EN
    origin = db.Column(db.String(20))  # SEARCH, LINK
    
    # Status tracking
    status = db.Column(db.String(20), default='VISITED')  # VISITED, JOINED, REJECTED
    last_visit_ts = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Validation data
    participants_count = db.Column(db.Integer)
    last_post_date = db.Column(db.DateTime)
    can_send_messages = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    account = db.relationship('Account', backref=db.backref('channel_candidates', lazy='dynamic'))
    
    # Unique constraint: one candidate per (account, peer_id)
    __table_args__ = (
        db.UniqueConstraint('account_id', 'peer_id', name='_account_peer_uc'),
    )
    
    def __repr__(self):
        return f'<ChannelCandidate {self.title or self.username} ({self.peer_id})>'
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'account_id': self.account_id,
            'peer_id': self.peer_id,
            'username': self.username,
            'title': self.title,
            'type': self.type,
            'language': self.language,
            'origin': self.origin,
            'status': self.status,
            'participants_count': self.participants_count,
            'last_post_date': self.last_post_date.isoformat() if self.last_post_date else None,
            'can_send_messages': self.can_send_messages,
            'last_visit_ts': self.last_visit_ts.isoformat() if self.last_visit_ts else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
