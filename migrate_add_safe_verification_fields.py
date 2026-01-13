"""
Migration: Add safe verification tracking fields to accounts table
"""
from database import db
from models.account import Account
from sqlalchemy import text

def migrate():
    """Add safe verification tracking fields"""
    
    with db.engine.connect() as conn:
        # Add last_verification_method
        try:
            conn.execute(text('''
                ALTER TABLE accounts 
                ADD COLUMN last_verification_method VARCHAR(50)
            '''))
            conn.commit()
            print("✅ Added last_verification_method column")
        except Exception as e:
            print(f"⚠️  last_verification_method column may already exist: {e}")
        
        # Add last_verification_time
        try:
            conn.execute(text('''
                ALTER TABLE accounts 
                ADD COLUMN last_verification_time TIMESTAMP
            '''))
            conn.commit()
            print("✅ Added last_verification_time column")
        except Exception as e:
            print(f"⚠️  last_verification_time column may already exist: {e}")
        
        # Add verification_count
        try:
            conn.execute(text('''
                ALTER TABLE accounts 
                ADD COLUMN verification_count INTEGER DEFAULT 0
            '''))
            conn.commit()
            print("✅ Added verification_count column")
        except Exception as e:
            print(f"⚠️  verification_count column may already exist: {e}")
    
    print("✅ Migration completed!")

if __name__ == '__main__':
    from app import app
    with app.app_context():
        migrate()
