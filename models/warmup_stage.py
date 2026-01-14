"""
Warmup Stage Model
Represents a stage in the account warmup process
"""
from database import db
from datetime import datetime


class WarmupStage(db.Model):
    __tablename__ = 'warmup_stages'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    
    # Stage info
    stage_number = db.Column(db.Integer, nullable=False)  # 1, 2, 3, 4
    stage_name = db.Column(db.String(50), nullable=False)  # 'profile', 'contacts', 'subscriptions', 'activity'
    
    # Status
    status = db.Column(db.String(20), default='pending')  # 'pending', 'in_progress', 'completed', 'blocked', 'failed'
    
    # Progress tracking
    total_actions = db.Column(db.Integer, default=0)
    completed_actions = db.Column(db.Integer, default=0)
    
    # Dependencies
    depends_on_stage = db.Column(db.Integer, nullable=True)  # Stage number that must be completed first
    blocking_action = db.Column(db.String(100), nullable=True)  # Action that's blocking progress
    
    # Timestamps
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    account = db.relationship('Account', backref=db.backref('warmup_stages', lazy='dynamic'))
    actions = db.relationship('WarmupAction', backref='stage', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<WarmupStage {self.stage_name} for Account {self.account_id}>'
    
    @property
    def progress_percentage(self):
        """Calculate completion percentage"""
        if self.total_actions == 0:
            return 0
        return int((self.completed_actions / self.total_actions) * 100)
    
    def can_start(self):
        """Check if stage can be started"""
        if self.depends_on_stage:
            # Check if dependency stage is completed
            dep_stage = WarmupStage.query.filter_by(
                account_id=self.account_id,
                stage_number=self.depends_on_stage
            ).first()
            
            if not dep_stage or dep_stage.status != 'completed':
                return False
        
        return True
    
    def mark_in_progress(self):
        """Mark stage as in progress"""
        self.status = 'in_progress'
        self.started_at = datetime.utcnow()
        db.session.commit()
    
    def mark_completed(self):
        """Mark stage as completed"""
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        db.session.commit()
    
    def mark_failed(self, reason):
        """Mark stage as failed"""
        self.status = 'failed'
        self.blocking_action = reason
        db.session.commit()
