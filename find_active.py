from app import app; from models.account import Account; from models.warmup_schedule import WarmupSchedule;
with app.app_context():
    accounts = Account.query.filter_by(status='active').all()
    for a in accounts:
        sched = WarmupSchedule.query.filter_by(account_id=a.id).first()
        print(f'Account {a.id}: {a.username}, schedule={sched.id if sched else None}')
