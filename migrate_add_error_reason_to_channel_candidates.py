"""
Migration: Add error_reason column to channel_candidates table
Created: 2026-01-18
"""
from database import db
from models.channel_candidate import ChannelCandidate

def migrate():
    """Add error_reason column to channel_candidates"""
    print("Adding error_reason column to channel_candidates...")
    
    try:
        # Check if column already exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('channel_candidates')]
        
        if 'error_reason' in columns:
            print("✓ Column error_reason already exists, skipping migration")
            return
        
        # Add column using raw SQL
        with db.engine.connect() as conn:
            conn.execute(db.text("ALTER TABLE channel_candidates ADD COLUMN error_reason TEXT"))
            conn.commit()
        
        print("✓ Successfully added error_reason column")
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        raise

if __name__ == '__main__':
    from app import app
    
    with app.app_context():
        migrate()
        print("\n✓ Migration completed successfully!")
