from app import create_app
from database import db
from models.warmup_schedule_node import WarmupScheduleNode
from models.warmup_log import WarmupLog
from models.warmup_schedule import WarmupSchedule

app = create_app()

with app.app_context():
    node_id = 160
    node = WarmupScheduleNode.query.get(node_id)
    if not node:
        print(f"Node {node_id} not found")
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
    # Fetch logs around the time of execution or just recent ones
    title_logs = WarmupLog.query.filter_by(account_id=account_id)\
        .order_by(WarmupLog.timestamp.desc())\
        .limit(30).all()
        
    for log in title_logs:
        print(f"[{log.timestamp}] {log.status}: {log.message} (Action: {log.action_type})")
