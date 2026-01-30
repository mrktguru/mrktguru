import sys
import os

# Add project root to path (parent directory of scripts/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.warmup_schedule import WarmupSchedule
from database import db

def list_active():
    with app.app_context():
        active = WarmupSchedule.query.filter_by(status='active').all()
        print(f"\n⚡ Active Warmup Schedules: {len(active)}")
        if not active:
            print("   No active schedules found.")
        for s in active:
            # Try to estimate current day
            print(f"   - [ID: {s.id}] Account: {s.account_id} | Start: {s.start_date} | Status: {s.status}")
        print("\n")
        return len(active)

def pause_all():
    with app.app_context():
        active = WarmupSchedule.query.filter_by(status='active').all()
        if not active:
            print("Nothing to pause.")
            return
        
        print(f"Pausing {len(active)} schedules...")
        for s in active:
            s.status = 'paused'
            print(f"   - Schedule {s.id} -> 'paused'")
        
        db.session.commit()
        print("✅ All active schedules have been paused.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--pause':
        pause_all()
    else:
        count = list_active()
        if count > 0:
            print("To PAUSE all active schedules, run:")
            print("python3 scripts/manage_warmup_schedules.py --pause")
