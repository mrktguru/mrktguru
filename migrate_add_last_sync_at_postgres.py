#!/usr/bin/env python3
"""
Migration script to add last_sync_at column to accounts table (PostgreSQL)
Run this on the server: python3 migrate_add_last_sync_at_postgres.py
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

def migrate():
    """Add last_sync_at column to accounts table in PostgreSQL"""
    
    # Try to load .env file
    load_env()
    
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
        print("\nPlease either:")
        print("  1. Create a .env file with DATABASE_URL")
        print("  2. Export DATABASE_URL in your shell")
        print("  3. Use the SQL file directly: psql <connection> -f migrations/add_last_sync_at_postgres.sql")
        print("\nExample DATABASE_URL format:")
        print("  postgresql://user:password@localhost:5432/database_name")
        return False
    
    print(f"📁 Connecting to database...")
    print(f"   URL: {db_url.split('@')[0].split('://')[0]}://***@{db_url.split('@')[1] if '@' in db_url else '***'}")
    
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

