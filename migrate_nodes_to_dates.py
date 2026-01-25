
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
        # 1. Add column if not exists
        from sqlalchemy import text
        try:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE warmup_schedule_nodes ADD COLUMN IF NOT EXISTS execution_date DATE'))
                conn.commit()
                logger.info("Executed ALTER TABLE statement.")
        except Exception as e:
            logger.warning(f"Schema update note: {e}")

        # 2. Migrate Data
        nodes = WarmupScheduleNode.query.all()
        logger.info(f"Found {len(nodes)} nodes to check/update")
        
        updated_count = 0
        
        for node in nodes:
            if node.execution_date:
                continue # Already set
            
            schedule = WarmupSchedule.query.get(node.schedule_id)
            if not schedule or not schedule.start_date:
                logger.warning(f"Node {node.id} skipped: No schedule or start_date")
                continue
            
            # Calculate Date: Start + (Day - 1)
            # Day 1 = Start Date
            target_date = schedule.start_date + timedelta(days=node.day_number - 1)
            
            node.execution_date = target_date
            updated_count += 1
            
        db.session.commit()
        logger.info(f"Migration Complete. Updated {updated_count} nodes.")

if __name__ == "__main__":
    migrate_dates()
