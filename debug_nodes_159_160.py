from app import create_app
from database import db
from models.warmup_schedule_node import WarmupScheduleNode
from models.warmup_log import WarmupLog
from models.warmup_schedule import WarmupSchedule

app = create_app()

with app.app_context():
    for node_id in [159, 160]:
        node = WarmupScheduleNode.query.get(node_id)
        if not node:
            print(f"Node {node_id} not found")
            continue
            
        schedule = WarmupSchedule.query.get(node.schedule_id)
        account_id = schedule.account_id
        
        print(f"--- Node {node.id} ---")
        print(f"Account ID: {account_id}")
        print(f"Status: {node.status}")
        print(f"Type: {node.node_type}")
        print(f"Scheduled: {node.execution_time}")
        print(f"Started: {node.execution_started_at}")
        print(f"Completed: {node.executed_at}")
        print(f"Error: {node.error_message}")
        print("--------------------")

    print("\n--- Recent Logs (Account 88) ---")
    logs = WarmupLog.query.filter_by(account_id=88)\
        .order_by(WarmupLog.timestamp.desc())\
        .limit(5).all()
        
    for log in logs:
        print(f"[{log.timestamp}] {log.status}: {log.message}")
