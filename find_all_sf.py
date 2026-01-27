from app import app; from models.warmup_schedule_node import WarmupScheduleNode;
with app.app_context():
    nodes = WarmupScheduleNode.query.filter_by(node_type='search_filter').all()
    for n in nodes:
        print(f'Node {n.id}: Schedule {n.schedule_id}, status={n.status}')
