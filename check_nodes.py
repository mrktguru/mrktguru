from app import app; from models.warmup_schedule import WarmupSchedule; from models.warmup_schedule_node import WarmupScheduleNode;
with app.app_context():
    schedules = WarmupSchedule.query.filter_by(account_id=22).all()
    print(f'Total schedules for account 22: {len(schedules)}')
    for s in schedules:
        print(f'Schedule {s.id}: Status {s.status}')
        nodes = WarmupScheduleNode.query.filter_by(schedule_id=s.id).all()
        for n in nodes:
            print(f'  Node {n.id}: {n.node_type}, status={n.status}, time={n.execution_time}')
