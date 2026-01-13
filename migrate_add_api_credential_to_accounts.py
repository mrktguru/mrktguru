"""
Migration: Add api_credential_id to accounts table
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from database import db
from sqlalchemy import text

def run_migration():
    """Add api_credential_id column to accounts table"""
    
    with app.app_context():
        print("🔄 Starting migration: Add api_credential_id to accounts...")
        
        # Get database connection
        conn = db.session.connection()
        
        try:
            # Check if column already exists
            result = conn.execute(text("PRAGMA table_info(accounts)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'api_credential_id' in columns:
                print("✅ Column 'api_credential_id' already exists.")
                return
            
            print("➕ Adding 'api_credential_id' column...")
            
            # Add column
            conn.execute(text("""
                ALTER TABLE accounts 
                ADD COLUMN api_credential_id INTEGER
            """))
            
            # Add foreign key constraint (SQLite doesn't enforce FK in ALTER TABLE, but we document it)
            print("   Note: Foreign key to api_credentials.id (not enforced in SQLite ALTER)")
            
            db.session.commit()
            
            print("✅ Migration completed successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
            raise


if __name__ == '__main__':
    run_migration()
