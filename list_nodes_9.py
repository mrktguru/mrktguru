from app import app; from models.warmup_schedule_node import WarmupScheduleNode;
with app.app_context():
    nodes = WarmupScheduleNode.query.filter_by(schedule_id=9).all()
    for n in nodes:
        print(f'Node {n.id}: {n.node_type}, status={n.status}')
