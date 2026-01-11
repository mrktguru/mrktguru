#!/usr/bin/env python3
"""
Migration script to add last_sync_at column to accounts table
Run this on the server: python3 migrate_add_last_sync_at.py
"""

import sqlite3
import os

# Path to database
DB_PATH = 'mrktguru.db'

def migrate():
    """Add last_sync_at column to accounts table"""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(accounts)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'last_sync_at' in columns:
            print("✅ Column 'last_sync_at' already exists in accounts table")
            conn.close()
            return True
        
        # Add the column
        print("Adding 'last_sync_at' column to accounts table...")
        cursor.execute("ALTER TABLE accounts ADD COLUMN last_sync_at DATETIME")
        conn.commit()
        
        print("✅ Migration completed successfully!")
        
        # Verify
        cursor.execute("PRAGMA table_info(accounts)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"📋 Current columns in accounts table: {', '.join(columns)}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    migrate()
