from datetime import datetime
from database import db


class ApiCredential(db.Model):
    """API Credentials for Telegram connections (public + personal)"""
    __tablename__ = 'api_credentials'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # "My Personal API", "iOS Official"
    api_id = db.Column(db.Integer, nullable=False)
    api_hash = db.Column(db.String(255), nullable=False)  # Encrypted
    client_type = db.Column(db.String(20))  # ios/android/desktop/custom
    is_official = db.Column(db.Boolean, default=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    
    def __repr__(self):
        return f'<ApiCredential {self.name} (ID: {self.api_id})>'
