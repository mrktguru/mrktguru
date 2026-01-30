from datetime import datetime
from database import db


class Proxy(db.Model):
    """Proxies table"""
    __tablename__ = 'proxies'
    
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)  # socks5/http/mobile
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(255))
    password = db.Column(db.String(255))
    rotation_url = db.Column(db.Text)
    rotation_type = db.Column(db.String(20), default="api")  # auto/api
    rotation_interval = db.Column(db.Integer, default=1200)  # seconds
    current_ip = db.Column(db.String(50))
    last_rotation = db.Column(db.DateTime)
    is_mobile = db.Column(db.Boolean, default=False)
    country = db.Column(db.String(10))  # Extracted from username (e.g., __cr.us -> US)
    status = db.Column(db.String(20), default='active')  # active/inactive/error
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    
    def __repr__(self):
        return f'<Proxy {self.type}://{self.host}:{self.port}>'
    
    def to_dict(self):
        """Convert to dictionary for Telethon"""
        return {
            'proxy_type': self.type,
            'addr': self.host,
            'port': self.port,
            'username': self.username,
            'password': self.password,
        }
    
    @property
    def flag(self):
        """Get emoji flag for country"""
        if not self.country or len(self.country) != 2:
            return ""
        try:
            base = 127397
            first = ord(self.country[0].upper()) + base
            second = ord(self.country[1].upper()) + base
            return chr(first) + chr(second)
        except:
            return ""
