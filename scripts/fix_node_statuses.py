from app import create_app
from database import db
from models.warmup_schedule_node import WarmupScheduleNode
import logging

def fix_statuses():
    app = create_app()
    with app.app_context():
        # Update failed, skipped, and draft nodes to pending
        count = WarmupScheduleNode.query.filter(
            WarmupScheduleNode.status.in_(['draft', 'failed', 'skipped'])
        ).update({WarmupScheduleNode.status: 'pending'}, synchronize_session=False)
        
        db.session.commit()
        print(f"Updated {count} nodes to 'pending' status.")

if __name__ == "__main__":
    fix_statuses()
