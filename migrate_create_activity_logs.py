#!/usr/bin/env python3
"""
Universal migration script to create account_activity_logs table
Supports both SQLite and PostgreSQL
Run this on the server: python3 migrate_create_activity_logs.py
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
        
        # Check if table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='account_activity_logs'")
        if cursor.fetchone():
            print("✅ Table 'account_activity_logs' already exists")
            conn.close()
            return True
        
        # Create the table
        print("Creating 'account_activity_logs' table...")
        cursor.execute("""
            CREATE TABLE account_activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                action_type VARCHAR(50) NOT NULL,
                action_category VARCHAR(30) DEFAULT 'general',
                target VARCHAR(500),
                status VARCHAR(20) DEFAULT 'success',
                description TEXT,
                details TEXT,
                error_message TEXT,
                ip_address VARCHAR(45),
                user_agent VARCHAR(500),
                proxy_used VARCHAR(100),
                timestamp DATETIME NOT NULL,
                duration_ms INTEGER,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        
        # Create indexes
        print("Creating indexes...")
        cursor.execute("CREATE INDEX ix_account_activity_logs_account_id ON account_activity_logs(account_id)")
        cursor.execute("CREATE INDEX ix_account_activity_logs_action_type ON account_activity_logs(action_type)")
        cursor.execute("CREATE INDEX ix_account_activity_logs_timestamp ON account_activity_logs(timestamp)")
        
        conn.commit()
        
        print("✅ Migration completed successfully!")
        
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
        
        # Check if table already exists
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name='account_activity_logs'
        """)
        
        if cursor.fetchone():
            print("✅ Table 'account_activity_logs' already exists")
            cursor.close()
            conn.close()
            return True
        
        # Create the table
        print("Creating 'account_activity_logs' table...")
        cursor.execute("""
            CREATE TABLE account_activity_logs (
                id SERIAL PRIMARY KEY,
                account_id INTEGER NOT NULL REFERENCES accounts(id),
                action_type VARCHAR(50) NOT NULL,
                action_category VARCHAR(30) DEFAULT 'general',
                target VARCHAR(500),
                status VARCHAR(20) DEFAULT 'success',
                description TEXT,
                details TEXT,
                error_message TEXT,
                ip_address VARCHAR(45),
                user_agent VARCHAR(500),
                proxy_used VARCHAR(100),
                timestamp TIMESTAMP NOT NULL,
                duration_ms INTEGER
            )
        """)
        
        # Create indexes
        print("Creating indexes...")
        cursor.execute("CREATE INDEX ix_account_activity_logs_account_id ON account_activity_logs(account_id)")
        cursor.execute("CREATE INDEX ix_account_activity_logs_action_type ON account_activity_logs(action_type)")
        cursor.execute("CREATE INDEX ix_account_activity_logs_timestamp ON account_activity_logs(timestamp)")
        
        conn.commit()
        
        print("✅ Migration completed successfully!")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def migrate():
    """Create account_activity_logs table"""
    
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
    success = migrate()
    sys.exit(0 if success else 1)
