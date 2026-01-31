from app import app
from models.warmup_schedule_node import WarmupScheduleNode

with app.app_context():
    node = WarmupScheduleNode.query.get(184)
    if node:
        print(f"Node 184: Type={node.node_type}, Status={node.status}")
        print(f"Error Message: {node.error_message}")
        print(f"Executed At: {node.executed_at}")
        
    # Also check if executor exists
    try:
        from modules.nodes.registry import NODE_EXECUTORS
        print(f"Executor for 'photo': {NODE_EXECUTORS.get('photo')}")
    except Exception as e:
        print(f"Registry check failed: {e}")

    # Dump logs
    from models.warmup_log import WarmupLog
    logs = WarmupLog.query.filter_by(account_id=87).order_by(WarmupLog.id.desc()).limit(10).all()
    print("\nRecent Logs:")
    for l in logs:
        print(f"[{l.timestamp}] {l.status}: {l.message} (Action: {l.action_type}) Details: {l.details}")
