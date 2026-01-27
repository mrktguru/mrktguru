from app import app; from database import db; from models.warmup_schedule_node import WarmupScheduleNode; from workers.scheduler_worker import execute_scheduled_node;
with app.app_context():
    node = WarmupScheduleNode.query.get(89)
    node.status = 'pending'
    db.session.commit()
    print('Triggering node 89...')
    execute_scheduled_node.apply_async(args=[89, True])
