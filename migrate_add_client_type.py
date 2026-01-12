
import os
import sys
from flask import Flask
from database import db
from sqlalchemy import text
from config import Config
from models.account import DeviceProfile, Account
from models.proxy import Proxy # Import Proxy model too

def migrate():
    # Initialize Flask app
    app = Flask(__name__)
    
    # 🔧 Force SQLite for local migration if Postgres fails
    # This ensures we work with the local mrktguru.db file
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///mrktguru.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)

    with app.app_context():
        print("🔄 Starting migration: Add client_type to device_profiles table...")
        print(f"📁 Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        try:
            # 1. Ensure tables exist
            db.create_all()
            print("✅ Verified tables exist (created if missing).")
            
            # Check database type
            db_url = app.config['SQLALCHEMY_DATABASE_URI']
            is_sqlite = db_url.startswith('sqlite')
            
            with db.engine.connect() as conn:
                # Add client_type column
                try:
                    conn.execute(text("SELECT client_type FROM device_profiles LIMIT 1"))
                    print("✅ Column 'client_type' already exists.")
                except Exception:
                    print("➕ Adding 'client_type' column...")
                    col_type = "VARCHAR(20)" if not is_sqlite else "TEXT"
                    default_val = "'desktop'"
                    conn.execute(text(f"ALTER TABLE device_profiles ADD COLUMN client_type {col_type} DEFAULT {default_val}"))
                
                conn.commit()
                print("✅ Migration completed successfully!")
                
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    migrate()
