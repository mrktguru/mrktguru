"""
Migration: Create API Credentials table and seed with official APIs
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from database import db
from models.api_credential import ApiCredential
from utils.encryption import encrypt_api_hash
from sqlalchemy import text

def run_migration():
    """Create api_credentials table and seed official APIs"""
    
    with app.app_context():
        print("🔄 Starting migration: Create API Credentials table...")
        
        # Get database connection
        conn = db.session.connection()
        
        # Check if table exists
        try:
            conn.execute(text("SELECT 1 FROM api_credentials LIMIT 1"))
            print("✅ Table 'api_credentials' already exists.")
        except Exception:
            print("➕ Creating 'api_credentials' table...")
            
            # Create table
            db.create_all()
            
            print("✅ Table created successfully.")
        
        # Seed official APIs
        print("🌱 Seeding official API credentials...")
        
        official_apis = [
            {
                'name': 'iOS Official (API ID 6)',
                'api_id': 6,
                'api_hash': 'eb06d4abfb49dc3eeb1aeb98ae0f581e',
                'client_type': 'ios',
                'is_official': True,
                'is_default': True,
                'notes': 'Official Telegram iOS client API'
            },
            {
                'name': 'Android Official (API ID 4)',
                'api_id': 4,
                'api_hash': '014b35b6184100b085b0d0572f9b5103',
                'client_type': 'android',
                'is_official': True,
                'is_default': False,
                'notes': 'Official Telegram Android client API'
            },
            {
                'name': 'Desktop Official (API ID 2040)',
                'api_id': 2040,
                'api_hash': 'b18441a1ff607e10a989891a54616e98',
                'client_type': 'desktop',
                'is_official': True,
                'is_default': False,
                'notes': 'Official Telegram Desktop client API'
            }
        ]
        
        for api_data in official_apis:
            # Check if already exists
            existing = ApiCredential.query.filter_by(api_id=api_data['api_id']).first()
            if existing:
                print(f"   ⚠️  API ID {api_data['api_id']} already exists, skipping.")
                continue
            
            # Encrypt API hash
            encrypted_hash = encrypt_api_hash(api_data['api_hash'])
            
            # Create credential
            credential = ApiCredential(
                name=api_data['name'],
                api_id=api_data['api_id'],
                api_hash=encrypted_hash,
                client_type=api_data['client_type'],
                is_official=api_data['is_official'],
                is_default=api_data['is_default'],
                notes=api_data['notes']
            )
            
            db.session.add(credential)
            print(f"   ✅ Added: {api_data['name']}")
        
        db.session.commit()
        
        print("\n✅ Migration completed successfully!")
        print(f"   Total API credentials: {ApiCredential.query.count()}")


if __name__ == '__main__':
    run_migration()
