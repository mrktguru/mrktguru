#!/usr/bin/env python3
"""
Migration: Add CASCADE DELETE to account_activity_logs foreign key

This fixes the error when deleting accounts with activity logs.
The foreign key needs to cascade delete to remove logs when account is deleted.
"""

import os
import sys

# Determine database type
DATABASE_URL = os.getenv('DATABASE_URL', '')

if 'postgresql' in DATABASE_URL:
    print("PostgreSQL database detected")
    import psycopg2
    
    # Parse connection string
    # Format: postgresql://user:pass@host:port/dbname
    url = DATABASE_URL.replace('postgresql://', '')
    if '@' in url:
        auth, location = url.split('@')
        user, password = auth.split(':')
        location_parts = location.split('/')
        host_port = location_parts[0]
        dbname = location_parts[1] if len(location_parts) > 1 else 'postgres'
        host, port = host_port.split(':') if ':' in host_port else (host_port, '5432')
    else:
        print("Error: Could not parse DATABASE_URL")
        sys.exit(1)
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname
        )
        cursor = conn.cursor()
        
        print("Updating foreign key constraint...")
        
        # Drop existing foreign key
        cursor.execute("""
            ALTER TABLE account_activity_logs 
            DROP CONSTRAINT IF EXISTS account_activity_logs_account_id_fkey;
        """)
        
        # Add new foreign key with CASCADE DELETE
        cursor.execute("""
            ALTER TABLE account_activity_logs 
            ADD CONSTRAINT account_activity_logs_account_id_fkey 
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE;
        """)
        
        conn.commit()
        print("✅ Foreign key updated successfully!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

else:
    print("SQLite database detected")
    import sqlite3
    
    # SQLite doesn't support ALTER CONSTRAINT, need to recreate table
    db_path = 'instance/telegram_system.db'
    
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("Recreating table with CASCADE DELETE...")
        
        # Create backup table
        cursor.execute("""
            CREATE TABLE account_activity_logs_backup AS 
            SELECT * FROM account_activity_logs;
        """)
        
        # Drop old table
        cursor.execute("DROP TABLE account_activity_logs;")
        
        # Create new table with CASCADE DELETE
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
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                duration_ms INTEGER,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            );
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX ix_account_activity_logs_account_id ON account_activity_logs(account_id);")
        cursor.execute("CREATE INDEX ix_account_activity_logs_action_type ON account_activity_logs(action_type);")
        cursor.execute("CREATE INDEX ix_account_activity_logs_timestamp ON account_activity_logs(timestamp);")
        
        # Restore data
        cursor.execute("""
            INSERT INTO account_activity_logs 
            SELECT * FROM account_activity_logs_backup;
        """)
        
        # Drop backup
        cursor.execute("DROP TABLE account_activity_logs_backup;")
        
        conn.commit()
        print("✅ Table recreated successfully with CASCADE DELETE!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        # Try to restore from backup
        try:
            cursor.execute("DROP TABLE IF EXISTS account_activity_logs;")
            cursor.execute("ALTER TABLE account_activity_logs_backup RENAME TO account_activity_logs;")
            conn.commit()
            print("Restored from backup")
        except:
            pass
        sys.exit(1)

print("\n✅ Migration completed successfully!")
print("You can now delete accounts without errors.")
