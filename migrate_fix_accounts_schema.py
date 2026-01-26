import os
# Determine DB path dynamically if not set
if not os.environ.get('DATABASE_URL'):
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, 'instance', 'mrktguru.db')
    os.environ['DATABASE_URL'] = f"sqlite:///{db_path}"

from app import create_app
from database import db
from sqlalchemy import text

app = create_app()

def run_fix():
    with app.app_context():
        print("Checking accounts table columns...")
        try:
            res = db.session.execute(text("PRAGMA table_info(accounts)")).fetchall()
            existing_cols =set([r[1] for r in res])
            
            # map column name -> type definition
            required_cols = {
                'session_string': 'TEXT',
                'proxy_network_id': 'INTEGER REFERENCES proxy_networks(id)',
                'assigned_port': 'INTEGER',
                'last_verification_method': 'VARCHAR(50)',
                'last_verification_time': 'DATETIME',
                'verification_count': 'INTEGER DEFAULT 0',
                'first_verified_at': 'DATETIME',
                'last_check_status': 'VARCHAR(50) DEFAULT "pending"',
                'flood_wait_until': 'DATETIME',
                'flood_wait_action': 'VARCHAR(50)',
                'last_flood_wait': 'DATETIME',
                'api_credential_id': 'INTEGER',
                'source_type': 'VARCHAR(20) DEFAULT "session"',
                'tdata_archive_path': 'VARCHAR(500)',
                'phone_code_hash': 'VARCHAR(255)',
                'two_fa_password': 'VARCHAR(255)',
                'last_sync_at': 'DATETIME',
                'session_metadata': 'JSON',
                'last_verification_attempt': 'DATETIME',
                'verified': 'BOOLEAN DEFAULT 0',
                'warmup_enabled': 'BOOLEAN DEFAULT 0'
            }
            
            for col, type_def in required_cols.items():
                if col not in existing_cols:
                    print(f"Adding missing column: {col}...")
                    try:
                        db.session.execute(text(f"ALTER TABLE accounts ADD COLUMN {col} {type_def}"))
                        print(f"✅ Added {col}")
                    except Exception as e:
                         print(f"⚠️ Failed to add {col}: {e}")
                else:
                    print(f"✓ {col} exists")
            
            db.session.commit()
            print("Schema update complete.")
                 
        except Exception as e:
            print(f"❌ Error checking/modifying accounts: {e}")
            db.session.rollback()
            
if __name__ == '__main__':
    run_fix()
