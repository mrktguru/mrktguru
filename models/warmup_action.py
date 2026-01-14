"""
Warmup Action Model
Represents individual actions within a warmup stage
"""
from database import db
from datetime import datetime


class WarmupAction(db.Model):
    __tablename__ = 'warmup_actions'
    
    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey('warmup_stages.id'), nullable=False)
    
    # Action info
    action_type = db.Column(db.String(50), nullable=False)  # 'set_name', 'add_channels', 'search_channel', etc.
    action_category = db.Column(db.String(20), nullable=False)  # 'manual', 'automatic'
    
    # Status
    is_required = db.Column(db.Boolean, default=False)
    is_completed = db.Column(db.Boolean, default=False)
    
    # Data (JSON)
    action_data = db.Column(db.JSON, nullable=True)  # Input data for action
    result = db.Column(db.JSON, nullable=True)  # Result after execution
    error = db.Column(db.Text, nullable=True)  # Error message if failed
    
    # Dependencies
    depends_on_action = db.Column(db.Integer, nullable=True)  # Action ID that must complete first
    blocks_actions = db.Column(db.JSON, nullable=True)  # List of action IDs that are blocked
    
    # Timestamps
    executed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<WarmupAction {self.action_type} (Stage {self.stage_id})>'
    
    def can_execute(self):
        """Check if action can be executed"""
        # Check if required dependency is completed
        if self.depends_on_action:
            dep_action = WarmupAction.query.get(self.depends_on_action)
            if not dep_action or not dep_action.is_completed:
                return False
        
        return True
    
    def mark_completed(self, result_data=None):
        """Mark action as completed"""
        self.is_completed = True
        self.executed_at = datetime.utcnow()
        if result_data:
            self.result = result_data
        db.session.commit()
    
    def mark_failed(self, error_message):
        """Mark action as failed"""
        self.is_completed = False
        self.error = error_message
        self.executed_at = datetime.utcnow()
        db.session.commit()
