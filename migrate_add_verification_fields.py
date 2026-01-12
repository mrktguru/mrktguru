
import os
import sys
from flask import Flask
from database import db
from sqlalchemy import text
from config import Config

def migrate():
    # Initialize Flask app
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        print("🔄 Starting migration: Add verification fields to accounts table...")
        
        # Check database type
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        is_sqlite = db_url.startswith('sqlite')
        
        try:
            with db.engine.connect() as conn:
                # Add metadata column
                try:
                    conn.execute(text("SELECT metadata FROM accounts LIMIT 1"))
                    print("✅ Column 'metadata' already exists.")
                except Exception:
                    print("➕ Adding 'metadata' column...")
                    col_type = "JSON" if not is_sqlite else "TEXT"
                    conn.execute(text(f"ALTER TABLE accounts ADD COLUMN metadata {col_type}"))
                
                # Add last_verification_attempt column
                try:
                    conn.execute(text("SELECT last_verification_attempt FROM accounts LIMIT 1"))
                    print("✅ Column 'last_verification_attempt' already exists.")
                except Exception:
                    print("➕ Adding 'last_verification_attempt' column...")
                    col_type = "TIMESTAMP" if not is_sqlite else "DATETIME"
                    conn.execute(text(f"ALTER TABLE accounts ADD COLUMN last_verification_attempt {col_type}"))
                
                # Add verified column
                try:
                    conn.execute(text("SELECT verified FROM accounts LIMIT 1"))
                    print("✅ Column 'verified' already exists.")
                except Exception:
                    print("➕ Adding 'verified' column...")
                    col_type = "BOOLEAN"
                    default_val = "FALSE" if not is_sqlite else "0"
                    conn.execute(text(f"ALTER TABLE accounts ADD COLUMN verified {col_type} DEFAULT {default_val}"))
                
                conn.commit()
                print("✅ Migration completed successfully!")
                
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    migrate()
