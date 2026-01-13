
from app import app
from models.campaign import InviteCampaign
from models.account import Account
from database import db

with app.app_context():
    print("--- 🔍 ACTIVE CAMPAIGNS CHECK ---")
    active_campaigns = InviteCampaign.query.filter_by(status='active').all()
    if active_campaigns:
        for c in active_campaigns:
            print(f"⚠️ FOUND ACTIVE CAMPAIGN: ID={c.id}, Name='{c.name}', Status='{c.status}'")
    else:
        print("✅ No active campaigns found.")

    print("\n--- 🌡️ ACTIVE WARMUP ACCOUNTS ---")
    warming_accounts = Account.query.filter_by(status='warming_up').all()
    print(f"Accounts in 'warming_up' status: {len(warming_accounts)}")
    
    active_accounts = Account.query.filter_by(status='active').all()
    warmup_enabled = [a for a in active_accounts if a.warmup_enabled]
    print(f"Active accounts with warmup_enabled=True: {len(warmup_enabled)}")
