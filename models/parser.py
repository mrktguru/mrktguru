from database import db
from datetime import datetime


class ParseJob(db.Model):
    __tablename__ = "parse_jobs"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    job_type = db.Column(db.String(50), nullable=False)  # single/multi_channel/by_activity/by_keyword
    source_channels = db.Column(db.JSON)  # array of channel usernames
    filters = db.Column(db.JSON)  # parsing filters
    status = db.Column(db.String(20), default="pending")  # pending/running/completed/failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    total_parsed = db.Column(db.Integer, default=0)
    total_valid = db.Column(db.Integer, default=0)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    error_message = db.Column(db.Text)


class ParsedUserLibrary(db.Model):
    __tablename__ = "parsed_user_library"
    
    id = db.Column(db.Integer, primary_key=True)
    collection_name = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.BigInteger)
    username = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    source_channel = db.Column(db.String(255))
    has_profile_photo = db.Column(db.Boolean)
    is_premium = db.Column(db.Boolean)
    last_seen = db.Column(db.DateTime)
    parsed_at = db.Column(db.DateTime, default=datetime.utcnow)
    extra_data = db.Column(db.JSON)  # additional parsed data
