"""
Warmup Schedule Node Model
Stores individual scheduled warmup actions (nodes)
"""
from database import db
from datetime import datetime


class WarmupScheduleNode(db.Model):
    __tablename__ = 'warmup_schedule_nodes'
    
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('warmup_schedules.id'), nullable=False)
    
    # Node configuration
    node_type = db.Column(db.String(50), nullable=False)  # bio, username, photo, contacts, subscribe, visit, idle
    day_number = db.Column(db.Integer, nullable=False)  # 1-14
    execution_date = db.Column(db.Date, nullable=True)  # Specific date: 2025-01-25
    execution_time = db.Column(db.String(20), nullable=True)  # "14:00" or "random:10:00-18:00"
    is_random_time = db.Column(db.Boolean, nullable=False, default=False)
    
    # Node-specific configuration stored as JSON
    config = db.Column(db.JSON, nullable=True)
    # Examples:
    # bio: {first_name: "John", last_name: "Doe", bio: "Marketing Guru"}
    # subscribe: {channels: ["@channel1", "@channel2"], read_count: 5, interaction_depth: {...}}
    # import_contacts: {count: 5}
    
    # Execution tracking
    status = db.Column(db.String(50), nullable=False, default='pending')  # pending, running, completed, failed, skipped
    executed_at = db.Column(db.DateTime, nullable=True)  # When execution finished
    execution_started_at = db.Column(db.DateTime, nullable=True)  # When execution actually started (status→running)
    error_message = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<WarmupScheduleNode {self.id}: {self.node_type} Day {self.day_number} ({self.status})>'
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'node_type': self.node_type,
            'day_number': self.day_number,
            'execution_time': self.execution_time,
            'is_random_time': self.is_random_time,
            'config': self.config,
            'status': self.status,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def get_execution_time_range(self):
        """Parse execution time string into start/end times"""
        if not self.execution_time:
            return None, None
        
        if self.is_random_time and ':' in self.execution_time:
            # Format: "random:10:00-18:00"
            if self.execution_time.startswith('random:'):
                time_range = self.execution_time.replace('random:', '')
                start, end = time_range.split('-')
                return start.strip(), end.strip()
        else:
            # Fixed time: "14:00"
            return self.execution_time, self.execution_time
        
        return None, None
