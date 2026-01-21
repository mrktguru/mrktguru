#!/usr/bin/env python3
"""
Migration script for Smart Subscriber Node
Adds tracking fields to channel_candidates and accounts tables
Supports both SQLite and PostgreSQL
"""

import os
import sys

def load_env():
    """Load database URL from .env file or config.py"""
    # Try .env file first
    env_path = '.env'
    if os.path.exists(env_path):
        print(f"📄 Loading environment from {env_path}")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip().strip('"').strip("'")
                    os.environ[key.strip()] = value
        return True
    
    # Try loading from config.py
    try:
        sys.path.insert(0, os.getcwd())
        from config import Config
        db_url = Config.SQLALCHEMY_DATABASE_URI
        if db_url:
            os.environ['DATABASE_URL'] = db_url
            print(f"📄 Loaded DATABASE_URL from config.py")
            return True
    except Exception as e:
        print(f"⚠️  Could not load from config.py: {e}")
    
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
        
        # Get existing columns for channel_candidates
        cursor.execute("PRAGMA table_info(channel_candidates)")
        channel_columns = [col[1] for col in cursor.fetchall()]
        
        # Get existing columns for accounts
        cursor.execute("PRAGMA table_info(accounts)")
        account_columns = [col[1] for col in cursor.fetchall()]
        
        print(f"\n📋 Adding Smart Subscriber fields...")
        
        # Add channel_candidates fields
        if 'pool_name' not in channel_columns:
            print("  ➕ Adding pool_name to channel_candidates")
            cursor.execute("ALTER TABLE channel_candidates ADD COLUMN pool_name VARCHAR(100)")
        else:
            print("  ✓ pool_name already exists")
            
        if 'subscribed_at' not in channel_columns:
            print("  ➕ Adding subscribed_at to channel_candidates")
            cursor.execute("ALTER TABLE channel_candidates ADD COLUMN subscribed_at TIMESTAMP")
        else:
            print("  ✓ subscribed_at already exists")
            
        if 'muted_at' not in channel_candidates:
            print("  ➕ Adding muted_at to channel_candidates")
            cursor.execute("ALTER TABLE channel_candidates ADD COLUMN muted_at TIMESTAMP")
        else:
            print("  ✓ muted_at already exists")
            
        if 'archived_at' not in channel_columns:
            print("  ➕ Adding archived_at to channel_candidates")
            cursor.execute("ALTER TABLE channel_candidates ADD COLUMN archived_at TIMESTAMP")
        else:
            print("  ✓ archived_at already exists")
        
        # Add accounts fields
        if 'flood_wait_until' not in account_columns:
            print("  ➕ Adding flood_wait_until to accounts")
            cursor.execute("ALTER TABLE accounts ADD COLUMN flood_wait_until TIMESTAMP")
        else:
            print("  ✓ flood_wait_until already exists")
            
        if 'flood_wait_action' not in account_columns:
            print("  ➕ Adding flood_wait_action to accounts")
            cursor.execute("ALTER TABLE accounts ADD COLUMN flood_wait_action VARCHAR(50)")
        else:
            print("  ✓ flood_wait_action already exists")
            
        if 'last_flood_wait' not in account_columns:
            print("  ➕ Adding last_flood_wait to accounts")
            cursor.execute("ALTER TABLE accounts ADD COLUMN last_flood_wait TIMESTAMP")
        else:
            print("  ✓ last_flood_wait already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
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
        
        # Check channel_candidates columns
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='channel_candidates'
        """)
        channel_columns = [row[0] for row in cursor.fetchall()]
        
        # Check accounts columns
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='accounts'
        """)
        account_columns = [row[0] for row in cursor.fetchall()]
        
        print(f"\n📋 Adding Smart Subscriber fields...")
        
        # Add channel_candidates fields
        if 'pool_name' not in channel_columns:
            print("  ➕ Adding pool_name to channel_candidates")
            cursor.execute("ALTER TABLE channel_candidates ADD COLUMN pool_name VARCHAR(100)")
        else:
            print("  ✓ pool_name already exists")
            
        if 'subscribed_at' not in channel_columns:
            print("  ➕ Adding subscribed_at to channel_candidates")
            cursor.execute("ALTER TABLE channel_candidates ADD COLUMN subscribed_at TIMESTAMP")
        else:
            print("  ✓ subscribed_at already exists")
            
        if 'muted_at' not in channel_columns:
            print("  ➕ Adding muted_at to channel_candidates")
            cursor.execute("ALTER TABLE channel_candidates ADD COLUMN muted_at TIMESTAMP")
        else:
            print("  ✓ muted_at already exists")
            
        if 'archived_at' not in channel_columns:
            print("  ➕ Adding archived_at to channel_candidates")
            cursor.execute("ALTER TABLE channel_candidates ADD COLUMN archived_at TIMESTAMP")
        else:
            print("  ✓ archived_at already exists")
        
        # Add accounts fields
        if 'flood_wait_until' not in account_columns:
            print("  ➕ Adding flood_wait_until to accounts")
            cursor.execute("ALTER TABLE accounts ADD COLUMN flood_wait_until TIMESTAMP")
        else:
            print("  ✓ flood_wait_until already exists")
            
        if 'flood_wait_action' not in account_columns:
            print("  ➕ Adding flood_wait_action to accounts")
            cursor.execute("ALTER TABLE accounts ADD COLUMN flood_wait_action VARCHAR(50)")
        else:
            print("  ✓ flood_wait_action already exists")
            
        if 'last_flood_wait' not in account_columns:
            print("  ➕ Adding last_flood_wait to accounts")
            cursor.execute("ALTER TABLE accounts ADD COLUMN last_flood_wait TIMESTAMP")
        else:
            print("  ✓ last_flood_wait already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def migrate():
    """Run migration for Smart Subscriber fields"""
    
    # Try to load .env file
    load_env()
    
    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL', os.getenv('SQLALCHEMY_DATABASE_URI', ''))
    
    if not db_url:
        print("❌ DATABASE_URL environment variable not set")
        print("\nPlease either:")
        print("  1. Create a .env file with DATABASE_URL")
        print("  2. Export DATABASE_URL in your shell")
        return False
    
    # Detect database type
    if db_url.startswith('sqlite:'):
        # Extract path from SQLite URL
        db_path = db_url.replace('sqlite:///', '').replace('sqlite://', '')
        if not db_path.startswith('/'):
            db_path = os.path.join(os.getcwd(), db_path)
        return migrate_sqlite(db_path)
    
    elif db_url.startswith('postgresql:') or db_url.startswith('postgres:'):
        return migrate_postgres(db_url)
    
    else:
        print(f"❌ Unsupported database type in URL: {db_url}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Smart Subscriber Migration")
    print("=" * 60)
    success = migrate()
    sys.exit(0 if success else 1)
