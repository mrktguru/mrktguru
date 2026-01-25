
import sys
import os
sys.path.append(os.getcwd())

# 🔥 Monkey Patching for Gevent (Must be first)
try:
    from gevent import monkey
    monkey.patch_all()
except ImportError:
    pass

from app import create_app
from database import db
from models.warmup_schedule import WarmupSchedule
from models.warmup_schedule_node import WarmupScheduleNode
from datetime import timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_dates():
    app = create_app()
    with app.app_context():
        print("--- STARTING MIGRATION ---")
        
        # 1. Check if column exists using Inspector
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('warmup_schedule_nodes')]
        
        if 'execution_date' not in columns:
            print("Column 'execution_date' missing. Adding it...")
            try:
                # Use session for execution to ensure transaction handling
                db.session.execute(text('ALTER TABLE warmup_schedule_nodes ADD COLUMN execution_date DATE'))
                db.session.commit()
                print("Column added successfully.")
            except Exception as e:
                print(f"FAILED to add column: {e}")
                db.session.rollback()
                return
        else:
            print("Column 'execution_date' already exists.")

        # 2. Migrate Data
        print("Fetching nodes...")
        try:
            nodes = WarmupScheduleNode.query.all()
        except Exception as e:
             print(f"Failed to fetch nodes (Model mismatch?): {e}")
             return

        print(f"Found {len(nodes)} nodes to check/update")
        
        updated_count = 0
        
        for node in nodes:
            if node.execution_date:
                continue # Already set
            
            schedule = WarmupSchedule.query.get(node.schedule_id)
            if not schedule or not schedule.start_date:
                # print(f"Node {node.id} skipped: No schedule or start_date")
                continue
            
            # Calculate Date: Start + (Day - 1)
            target_date = schedule.start_date + timedelta(days=node.day_number - 1)
            
            node.execution_date = target_date
            updated_count += 1
            
        db.session.commit()
        print(f"Migration Complete. Updated {updated_count} nodes.")
        print("--- FINISHED ---")

if __name__ == "__main__":
    migrate_dates()
