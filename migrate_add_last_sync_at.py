#!/usr/bin/env python3
"""
Migration script to add last_sync_at column to accounts table
Run this on the server: python3 migrate_add_last_sync_at.py
"""

import sqlite3
import os
import sys

def find_database():
    """Find the database file"""
    # Check environment variable
    db_url = os.getenv('DATABASE_URL', '')
    
    # If it's a SQLite URL, extract the path
    if db_url.startswith('sqlite:///'):
        db_path = db_url.replace('sqlite:///', '')
        if os.path.exists(db_path):
            return db_path
    
    # Common locations to check
    possible_paths = [
        'mrktguru.db',
        'instance/mrktguru.db',
        '../mrktguru.db',
        '/root/mrktguru.db',
        '/root/mrktguru/mrktguru.db',
        'database.db',
        'instance/database.db',
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Search in current directory and subdirectories
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.db'):
                return os.path.join(root, file)
    
    return None

def migrate():
    """Add last_sync_at column to accounts table"""
    
    db_path = find_database()
    
    if not db_path:
        print("❌ Database not found!")
        print("Please specify the database path manually:")
        print("  python3 migrate_add_last_sync_at.py /path/to/database.db")
        return False
    
    print(f"📁 Found database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
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
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Allow manual database path as argument
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        if not os.path.exists(db_path):
            print(f"❌ Database not found: {db_path}")
            sys.exit(1)
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("PRAGMA table_info(accounts)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'last_sync_at' in columns:
                print("✅ Column 'last_sync_at' already exists")
                sys.exit(0)
            
            cursor.execute("ALTER TABLE accounts ADD COLUMN last_sync_at DATETIME")
            conn.commit()
            conn.close()
            
            print("✅ Migration completed successfully!")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            sys.exit(1)
    else:
        success = migrate()
        sys.exit(0 if success else 1)

