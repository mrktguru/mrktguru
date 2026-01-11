#!/usr/bin/env python3
"""
Universal migration script to add last_sync_at column to accounts table
Supports both SQLite and PostgreSQL
Run this on the server: python3 migrate_universal.py
"""

import os
import sys

def load_env():
    """Load .env file if it exists"""
    env_path = '.env'
    if os.path.exists(env_path):
        print(f"📄 Loading environment from {env_path}")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip().strip('"').strip("'")
                    os.environ[key.strip()] = value
        return True
    return False

def migrate_sqlite(db_path):
    """Migrate SQLite database"""
    import sqlite3
    
    print(f"📁 Using SQLite database: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return False
    
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
        print(f"📋 Current columns in accounts table ({len(columns)} total):")
        print(f"   {', '.join(columns)}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def migrate_postgres(db_url):
    """Migrate PostgreSQL database"""
    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 not installed. Installing...")
        os.system("pip3 install psycopg2-binary")
        import psycopg2
    
    print(f"📁 Using PostgreSQL database")
    
    try:
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

def migrate():
    """Add last_sync_at column to accounts table"""
    
    # Try to load .env file
    load_env()
    
    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL', os.getenv('SQLALCHEMY_DATABASE_URI', ''))
    
    if not db_url:
        print("❌ DATABASE_URL environment variable not set")
        print("\nPlease either:")
        print("  1. Create a .env file with DATABASE_URL")
        print("  2. Export DATABASE_URL in your shell")
        print("\nExample formats:")
        print("  SQLite:     sqlite:///path/to/database.db")
        print("  PostgreSQL: postgresql://user:password@localhost:5432/database_name")
        return False
    
    # Detect database type
    if db_url.startswith('sqlite:'):
        # Extract path from SQLite URL
        db_path = db_url.replace('sqlite:///', '').replace('sqlite://', '')
        # Handle relative paths
        if not db_path.startswith('/'):
            db_path = os.path.join(os.getcwd(), db_path)
        return migrate_sqlite(db_path)
    
    elif db_url.startswith('postgresql:') or db_url.startswith('postgres:'):
        return migrate_postgres(db_url)
    
    else:
        print(f"❌ Unsupported database type in URL: {db_url}")
        print("Supported types: sqlite://, postgresql://")
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
