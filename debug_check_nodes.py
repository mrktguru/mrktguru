import sys
import os
sys.path.append(os.getcwd())

from app import app
from models.warmup_schedule import WarmupSchedule
from models.warmup_schedule_node import WarmupScheduleNode
from datetime import datetime
import pytz
from config import Config

with app.app_context():
    print("=== DEBUG SCHEDULER STATE ===")
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)
    print(f"Current Server Time: {now}")
    print(f"Server Date: {now.date()}")
    
    schedules = WarmupSchedule.query.filter_by(status='active').all()
    print(f"Active Schedules: {len(schedules)}")
    
    for s in schedules:
        print(f"\nSchedule {s.id} (Account {s.account_id}):")
        print(f"  Start Date: {s.start_date}")
        
        days_elapsed = (now.date() - s.start_date).days
        day_number = days_elapsed + 1
        print(f"  Calculated Day Number: {day_number}")
        
        # Check nodes for this day
        nodes_today = WarmupScheduleNode.query.filter_by(schedule_id=s.id, day_number=day_number).all()
        print(f"  Nodes for Day {day_number}: {len(nodes_today)}")
        for n in nodes_today:
            exec_date = getattr(n, 'execution_date', 'N/A')
            print(f"    - Node {n.id} ({n.node_type}): Time={n.execution_time}, Date={exec_date}, Status={n.status}")
            
        # Check nodes for ALL days (pending)
        all_pending = WarmupScheduleNode.query.filter_by(schedule_id=s.id, status='pending').all()
        print(f"  All Pending Nodes (Any Day): {len(all_pending)}")
        for n in all_pending:
            exec_date = getattr(n, 'execution_date', 'N/A')
            print(f"    - Node {n.id} ({n.node_type}) Day {n.day_number} ({exec_date})")
