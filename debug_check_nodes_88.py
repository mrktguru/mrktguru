from app import app
from models.warmup_schedule_node import WarmupScheduleNode

with app.app_context():
    node_175 = WarmupScheduleNode.query.get(175)
    print(f"Node 175: Type={node_175.node_type}, Status={node_175.status}, ExecutedAt={node_175.executed_at}, Error={node_175.error_message}")
    
    # Check other recent nodes for Account 88
    # Assuming we can find them by schedule_id if we knew it, or just filter by ID range if close
    # Or finding schedule for account 88 first
    from models.warmup_schedule import WarmupSchedule
    schedule = WarmupSchedule.query.filter_by(account_id=88).first()
    if schedule:
        print(f"Schedule ID: {schedule.id}")
        nodes = WarmupScheduleNode.query.filter_by(schedule_id=schedule.id).order_by(WarmupScheduleNode.id.desc()).limit(5).all()
        for n in nodes:
             print(f"Node {n.id}: Type={n.node_type}, Status={n.status}, Started={n.execution_started_at}, Executed={n.executed_at}, Error={n.error_message}")
    else:
        print("No schedule found for Account 88")
