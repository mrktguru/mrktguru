from app import create_app
from database import db
from models.warmup_schedule_node import WarmupScheduleNode
from models.warmup_log import WarmupLog
from models.warmup_schedule import WarmupSchedule

app = create_app()

with app.app_context():
    node = WarmupScheduleNode.query.get(158)
    if not node:
        print("Node 158 not found")
        exit()
        
    schedule = WarmupSchedule.query.get(node.schedule_id)
    account_id = schedule.account_id
    
    print(f"--- Node {node.id} ---")
    print(f"Account ID: {account_id}")
    print(f"Status: {node.status}")
    print(f"Type: {node.node_type}")
    print(f"Config: {node.config}")
    print(f"Scheduled: {node.execution_time}")
    print(f"Started: {node.execution_started_at}")
    print(f"Completed: {node.executed_at}")
    print(f"Error: {node.error_message}")
    
    print("\n--- Recent Logs (Account {}) ---".format(account_id))
    logs = WarmupLog.query.filter_by(account_id=account_id)\
        .order_by(WarmupLog.timestamp.desc())\
        .limit(20).all()
        
    for log in logs:
        print(f"[{log.timestamp}] {log.status}: {log.message} (Action: {log.action_type})")
