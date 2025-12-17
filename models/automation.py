from datetime import datetime
from database import db


class ScheduledTask(db.Model):
    """Scheduled tasks table"""
    __tablename__ = 'scheduled_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    task_type = db.Column(db.String(50), nullable=False)  # subscribe_channel/post_message/rotate_proxy/etc
    entity_type = db.Column(db.String(50))  # account/campaign/channel
    entity_id = db.Column(db.Integer)
    scheduled_for = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(20), default='pending', index=True)  # pending/completed/failed
    payload = db.Column(db.JSON)  # task parameters
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    
    def __repr__(self):
        return f'<ScheduledTask {self.task_type}>'


class AutoAction(db.Model):
    """Auto-action rules table"""
    __tablename__ = 'auto_actions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    trigger_type = db.Column(db.String(50), nullable=False)  # campaign_progress/account_health/user_reply/time_based
    trigger_condition = db.Column(db.JSON, nullable=False)  # {type: "campaign_progress", value: 50, operator: ">="}
    action_type = db.Column(db.String(50), nullable=False)  # post_message/pause_account/send_notification/etc
    action_params = db.Column(db.JSON, nullable=False)
    is_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AutoAction {self.name}>'
