"""
Migration: Add Anti-Ban Authentication Flow fields
Adds columns for hybrid verification and JSON metadata support
"""
from database import db
from models.account import Account
from models.tdata_metadata import TDataMetadata
from sqlalchemy import text

def migrate():
    """Add new columns for anti-ban authentication"""
    
    print("🔄 Starting anti-ban fields migration...")
    
    # ==================== ACCOUNT TABLE ====================
    print("\n1. Updating accounts table...")
    
    # Add first_verified_at
    try:
        db.session.execute(text("""
            ALTER TABLE accounts 
            ADD COLUMN IF NOT EXISTS first_verified_at TIMESTAMP
        """))
        print("   ✅ Added first_verified_at column")
    except Exception as e:
        print(f"   ⚠️  first_verified_at: {e}")
    
    # Add last_check_status
    try:
        db.session.execute(text("""
            ALTER TABLE accounts 
            ADD COLUMN IF NOT EXISTS last_check_status VARCHAR(50) DEFAULT 'pending'
        """))
        print("   ✅ Added last_check_status column")
    except Exception as e:
        print(f"   ⚠️  last_check_status: {e}")
    
    db.session.commit()
    
    # ==================== TDATA_METADATA TABLE ====================
    print("\n2. Updating tdata_metadata table...")
    
    # Add device_source
    try:
        db.session.execute(text("""
            ALTER TABLE tdata_metadata 
            ADD COLUMN IF NOT EXISTS device_source VARCHAR(20) DEFAULT 'tdata'
        """))
        print("   ✅ Added device_source column")
    except Exception as e:
        print(f"   ⚠️  device_source: {e}")
    
    # Add JSON metadata columns
    try:
        db.session.execute(text("""
            ALTER TABLE tdata_metadata 
            ADD COLUMN IF NOT EXISTS json_raw_data JSONB
        """))
        print("   ✅ Added json_raw_data column")
    except Exception as e:
        print(f"   ⚠️  json_raw_data: {e}")
    
    try:
        db.session.execute(text("""
            ALTER TABLE tdata_metadata 
            ADD COLUMN IF NOT EXISTS json_app_version VARCHAR(50)
        """))
        print("   ✅ Added json_app_version column")
    except Exception as e:
        print(f"   ⚠️  json_app_version: {e}")
    
    try:
        db.session.execute(text("""
            ALTER TABLE tdata_metadata 
            ADD COLUMN IF NOT EXISTS json_device_model VARCHAR(100)
        """))
        print("   ✅ Added json_device_model column")
    except Exception as e:
        print(f"   ⚠️  json_device_model: {e}")
    
    try:
        db.session.execute(text("""
            ALTER TABLE tdata_metadata 
            ADD COLUMN IF NOT EXISTS json_system_version VARCHAR(50)
        """))
        print("   ✅ Added json_system_version column")
    except Exception as e:
        print(f"   ⚠️  json_system_version: {e}")
    
    try:
        db.session.execute(text("""
            ALTER TABLE tdata_metadata 
            ADD COLUMN IF NOT EXISTS json_lang_code VARCHAR(10)
        """))
        print("   ✅ Added json_lang_code column")
    except Exception as e:
        print(f"   ⚠️  json_lang_code: {e}")
    
    try:
        db.session.execute(text("""
            ALTER TABLE tdata_metadata 
            ADD COLUMN IF NOT EXISTS json_system_lang_code VARCHAR(10)
        """))
        print("   ✅ Added json_system_lang_code column")
    except Exception as e:
        print(f"   ⚠️  json_system_lang_code: {e}")
    
    db.session.commit()
    
    print("\n✅ Migration completed successfully!")
    print("\nNew fields added:")
    print("  accounts.first_verified_at - Tracks first full verification")
    print("  accounts.last_check_status - Stores last verification status")
    print("  tdata_metadata.device_source - Source selection (tdata/json)")
    print("  tdata_metadata.json_* - JSON metadata storage")


if __name__ == '__main__':
    from app import app
    
    with app.app_context():
        migrate()
