#!/usr/bin/env python3
"""
Migration script to add last_sync_at column to accounts table (PostgreSQL)
Run this on the server: python3 migrate_add_last_sync_at_postgres.py
"""

import os
import sys

def migrate():
    """Add last_sync_at column to accounts table in PostgreSQL"""
    
    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 not installed. Installing...")
        os.system("pip3 install psycopg2-binary")
        import psycopg2
    
    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("❌ DATABASE_URL environment variable not set")
        print("Please set it or provide connection details manually")
        return False
    
    print(f"📁 Connecting to database...")
    
    try:
        # Parse PostgreSQL URL
        # Format: postgresql://user:password@host:port/database
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='accounts' AND column_name='last_sync_at'
        """)
        
        if cursor.fetchone():
            print("✅ Column 'last_sync_at' already exists in accounts table")
            cursor.close()
            conn.close()
            return True
        
        # Add the column
        print("Adding 'last_sync_at' column to accounts table...")
        cursor.execute("ALTER TABLE accounts ADD COLUMN last_sync_at TIMESTAMP")
        conn.commit()
        
        print("✅ Migration completed successfully!")
        
        # Verify
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='accounts'
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in cursor.fetchall()]
        print(f"📋 Current columns in accounts table ({len(columns)} total):")
        print(f"   {', '.join(columns)}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
