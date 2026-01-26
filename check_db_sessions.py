
from app import app
from models.account import Account
from models.account_session import AccountSession

def check():
    # Force SQLite Instance
    import os
    db_path = os.path.abspath("instance/mrktguru.db")
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
    print(f"Using DB: {app.config['SQLALCHEMY_DATABASE_URI']}")

    with app.app_context():
        # Get active account (or any account)
        account = Account.query.filter_by(status='active').first()
        if not account:
            account = Account.query.first()
        
        if not account:
            print("No accounts found in mrktguru.db")
            return

        print(f"Checking Account ID: {account.id} ({account.phone})")
        
        # 1. Direct active_sessions count
        count_direct = account.active_sessions.count()
        print(f"Via account.active_sessions.count(): {count_direct}")
        
        # 2. Query AccountSession table directly
        count_table = AccountSession.query.filter_by(account_id=account.id).count()
        print(f"Via AccountSession.query: {count_table}")
        
        # 3. List them
        sessions = AccountSession.query.filter_by(account_id=account.id).all()
        for s in sessions:
            print(f" - Session: {s.session_hash[:10]}... | Device: {s.device_model}")

if __name__ == "__main__":
    check()
