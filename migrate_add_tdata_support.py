"""
Migration: Add TData support to database
- Create tdata_metadata table
- Add source_type and tdata_archive_path to accounts
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from database import db
from sqlalchemy import text

def run_migration():
    """Add TData support to database"""
    
    with app.app_context():
        print("🔄 Starting migration: Add TData support...")
        
        # Get database connection
        conn = db.session.connection()
        
        # 1. Create tdata_metadata table
        try:
            conn.execute(text("SELECT 1 FROM tdata_metadata LIMIT 1"))
            print("✅ Table 'tdata_metadata' already exists.")
        except Exception:
            print("➕ Creating 'tdata_metadata' table...")
            
            # Create table using SQLAlchemy
            db.create_all()
            
            print("✅ Table 'tdata_metadata' created successfully.")
        
        # 2. Add source_type column to accounts
        try:
            result = conn.execute(text("PRAGMA table_info(accounts)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'source_type' not in columns:
                print("➕ Adding 'source_type' column to accounts...")
                conn.execute(text("""
                    ALTER TABLE accounts 
                    ADD COLUMN source_type VARCHAR(20) DEFAULT 'session'
                """))
                print("✅ Added 'source_type' column.")
            else:
                print("✅ Column 'source_type' already exists.")
            
            # 3. Add tdata_archive_path column
            if 'tdata_archive_path' not in columns:
                print("➕ Adding 'tdata_archive_path' column to accounts...")
                conn.execute(text("""
                    ALTER TABLE accounts 
                    ADD COLUMN tdata_archive_path VARCHAR(500)
                """))
                print("✅ Added 'tdata_archive_path' column.")
            else:
                print("✅ Column 'tdata_archive_path' already exists.")
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding columns: {e}")
            raise
        
        print("\n✅ Migration completed successfully!")
        print("   TData support is now enabled.")


if __name__ == '__main__':
    run_migration()
