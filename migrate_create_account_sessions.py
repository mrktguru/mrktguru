
from app import app, db
from models.account_session import AccountSession

def migrate():
    print("Starting migration...")
    with app.app_context():
        # Create tables
        db.create_all()
        print("✅ Database tables created (including account_sessions)")
        
if __name__ == "__main__":
    migrate()
