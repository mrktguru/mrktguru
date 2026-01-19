"""
Migration: Add two_fa_password field to accounts table
"""
from database import db
from sqlalchemy import text

def migrate():
    """Add two_fa_password field"""
    
    with db.engine.connect() as conn:
        # Add two_fa_password
        try:
            conn.execute(text('''
                ALTER TABLE accounts 
                ADD COLUMN two_fa_password VARCHAR(255)
            '''))
            conn.commit()
            print("✅ Added two_fa_password column")
        except Exception as e:
            print(f"⚠️  two_fa_password column may already exist: {e}")
    
    print("✅ Migration completed!")

if __name__ == '__main__':
    from app import app
    with app.app_context():
        migrate()
