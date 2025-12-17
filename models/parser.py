from datetime import datetime
from app import db


class ParsedUserLibrary(db.Model):
    """Parsed users library"""
    __tablename__ = 'parsed_user_library'
    
    id = db.Column(db.Integer, primary_key=True)
    collection_name = db.Column(db.String(255), nullable=False, index=True)
    user_id = db.Column(db.BigInteger)
    username = db.Column(db.String(255), index=True)
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    source_channel = db.Column(db.String(255))
    has_profile_photo = db.Column(db.Boolean)
    is_premium = db.Column(db.Boolean)
    last_seen = db.Column(db.DateTime)
    parsed_at = db.Column(db.DateTime, default=datetime.utcnow)
    metadata = db.Column(db.JSON)  # additional parsed data
    
    def __repr__(self):
        return f'<ParsedUserLibrary {self.username or self.user_id}>'


class ParseJob(db.Model):
    """Parse jobs table"""
    __tablename__ = 'parse_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    job_type = db.Column(db.String(50), nullable=False)  # single_channel/multi_channel/by_activity/by_keyword
    source_channels = db.Column(db.ARRAY(db.String))  # array of channel usernames
    filters = db.Column(db.JSON)  # parsing filters
    status = db.Column(db.String(20), default='pending', index=True)  # pending/running/completed/failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    total_parsed = db.Column(db.Integer, default=0)
    total_valid = db.Column(db.Integer, default=0)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    error_message = db.Column(db.Text)
    
    # Relationships
    account = db.relationship('Account', backref=db.backref('parse_jobs', lazy='dynamic'))
    
    def __repr__(self):
        return f'<ParseJob {self.name}>'
