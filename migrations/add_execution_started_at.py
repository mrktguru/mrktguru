"""
Add execution_started_at to warmup_schedule_nodes

This migration adds a new column to track when a node actually starts executing,
separate from updated_at which tracks configuration changes.
"""

import psycopg2
from datetime import datetime

# Database connection
conn = psycopg2.connect(
    host="127.0.0.1",
    port=5434,
    database="telegram_system",
    user="telegram_user",
    password="TelegramUser2024"
)
conn.autocommit = True
cursor = conn.cursor()

try:
    print(f"[{datetime.now()}] Adding execution_started_at column...")
    
    # Add the new column (nullable)
    cursor.execute("""
        ALTER TABLE warmup_schedule_nodes 
        ADD COLUMN IF NOT EXISTS execution_started_at TIMESTAMP;
    """)
    
    print(f"[{datetime.now()}] ✅ Column added successfully!")
    
    # Optional: Set execution_started_at = updated_at for nodes that are currently running
    # This provides a reasonable default for existing running nodes
    cursor.execute("""
        UPDATE warmup_schedule_nodes 
        SET execution_started_at = updated_at 
        WHERE status = 'running' AND execution_started_at IS NULL;
    """)
    
    rows_updated = cursor.rowcount
    print(f"[{datetime.now()}] ✅ Updated {rows_updated} existing running nodes")
    
    print(f"[{datetime.now()}] Migration completed successfully!")
    
except Exception as e:
    print(f"[{datetime.now()}] ❌ Migration failed: {e}")
    raise
finally:
    cursor.close()
    conn.close()
