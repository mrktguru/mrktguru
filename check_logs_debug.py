from app import app
from models.warmup_log import WarmupLog
from database import db

with app.app_context():
    logs = WarmupLog.query.filter_by(account_id=22).order_by(WarmupLog.timestamp.desc()).limit(20).all()
    print("Timestamp | Status | Stage | Action | Message")
    print("-" * 80)
    for l in logs:
        print(f"{l.timestamp} | {l.status} | {l.stage_number} | {l.action_type} | {l.message}")
