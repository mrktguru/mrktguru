"""
Warmup Schedule Model
Stores automated warmup schedules for accounts
"""
from database import db
from datetime import datetime


class WarmupSchedule(db.Model):
    __tablename__ = 'warmup_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False, default='Warmup Schedule')
    status = db.Column(db.String(50), nullable=False, default='draft')  # draft, active, paused, completed, failed
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    account = db.relationship('Account', backref=db.backref('warmup_schedules', lazy='dynamic'))
    nodes = db.relationship('WarmupScheduleNode', backref='schedule', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<WarmupSchedule {self.id}: {self.name} ({self.status})>'
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'account_id': self.account_id,
            'name': self.name,
            'status': self.status,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'nodes_count': self.nodes.count()
        }
