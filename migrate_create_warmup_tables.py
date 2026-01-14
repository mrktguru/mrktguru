"""
Migration script to create warmup system tables

Run with: python3 migrate_create_warmup_tables.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db
from models.warmup_stage import WarmupStage
from models.warmup_action import WarmupAction
from models.warmup_channel import WarmupChannel
from models.warmup_settings import WarmupSettings
from models.warmup_log import WarmupLog
from app import app


def create_warmup_tables():
    """Create all warmup-related tables"""
    
    with app.app_context():
        print("Creating warmup tables...")
        
        # Create tables
        db.create_all()
        
        print("✅ Tables created successfully:")
        print("  - warmup_stages")
        print("  - warmup_actions")
        print("  - warmup_channels")
        print("  - warmup_settings")
        print("  - warmup_logs")
        
        # Verify tables exist
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        warmup_tables = [
            'warmup_stages',
            'warmup_actions',
            'warmup_channels',
            'warmup_settings',
            'warmup_logs'
        ]
        
        for table in warmup_tables:
            if table in tables:
                print(f"✅ Verified: {table}")
            else:
                print(f"❌ Missing: {table}")
        
        print("\n✅ Migration completed!")


if __name__ == '__main__':
    create_warmup_tables()
