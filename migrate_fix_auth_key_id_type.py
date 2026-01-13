"""
Migration: Update auth_key_id column type to String
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from database import db
from sqlalchemy import text

def run_migration():
    """Update auth_key_id column type"""
    
    with app.app_context():
        print("🔄 Starting migration: Update auth_key_id to String...")
        
        # Get database connection
        conn = db.session.connection()
        
        try:
            # Check if table exists
            result = conn.execute(text("PRAGMA table_info(tdata_metadata)"))
            columns = {row[1]: row[2] for row in result.fetchall()}
            
            if 'auth_key_id' not in columns:
                print("⚠️ Table tdata_metadata or auth_key_id column doesn't exist yet.")
                print("   Run migrate_add_tdata_support.py first.")
                return
            
            print("➕ Recreating auth_key_id column as VARCHAR...")
            
            # SQLite doesn't support ALTER COLUMN TYPE, so we need to:
            # 1. Create new column
            # 2. Copy data
            # 3. Drop old column
            # 4. Rename new column
            
            # But SQLite also doesn't support DROP COLUMN easily
            # So we'll just add a new column and use it
            
            # Check if temp column exists
            if 'auth_key_id_new' in columns:
                conn.execute(text("ALTER TABLE tdata_metadata DROP COLUMN auth_key_id_new"))
            
            # Add new column
            conn.execute(text("""
                ALTER TABLE tdata_metadata 
                ADD COLUMN auth_key_id_new VARCHAR(50)
            """))
            
            # Copy data (convert to string)
            conn.execute(text("""
                UPDATE tdata_metadata 
                SET auth_key_id_new = CAST(auth_key_id AS TEXT)
                WHERE auth_key_id IS NOT NULL
            """))
            
            print("✅ Migration completed!")
            print("   Note: Old auth_key_id column still exists.")
            print("   New data will use auth_key_id_new column.")
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
            raise


if __name__ == '__main__':
    run_migration()
