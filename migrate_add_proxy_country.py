"""
Migration: Add country field to proxies table
"""
import os
import sys
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from database import db
from sqlalchemy import text

def extract_country_from_username(username):
    """
    Extract country code from username
    Example: a5ff68df07c427bb72f5__cr.us -> US
    """
    if not username:
        return None
    
    # Pattern: __cr.{country_code}
    match = re.search(r'__cr\.([a-z]{2})', username.lower())
    if match:
        return match.group(1).upper()
    
    return None


def run_migration():
    """Add country column and populate from existing usernames"""
    
    with app.app_context():
        print("🔄 Starting migration: Add country to proxies...")
        
        # Get database connection
        conn = db.session.connection()
        
        try:
            # Check if column already exists
            result = conn.execute(text("PRAGMA table_info(proxies)"))
            columns = {row[1]: row[2] for row in result.fetchall()}
            
            if 'country' in columns:
                print("✅ Column 'country' already exists")
            else:
                print("➕ Adding 'country' column...")
                conn.execute(text("ALTER TABLE proxies ADD COLUMN country VARCHAR(10)"))
                db.session.commit()
                print("✅ Column added")
            
            # Populate country from existing usernames
            print("🔄 Extracting country codes from usernames...")
            
            from models.proxy import Proxy
            proxies = Proxy.query.all()
            
            updated = 0
            for proxy in proxies:
                if proxy.username:
                    country = extract_country_from_username(proxy.username)
                    if country:
                        proxy.country = country
                        updated += 1
                        print(f"   ✅ {proxy.host}:{proxy.port} -> {country}")
            
            db.session.commit()
            print(f"✅ Updated {updated} proxies with country codes")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
            raise


if __name__ == '__main__':
    run_migration()
