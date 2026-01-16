#!/usr/bin/env python3
"""
Migration script: SQLite to PostgreSQL
Transfers all data from SQLite database to PostgreSQL
"""
import sqlite3
import os

# SQLite database path
SQLITE_PATH = '/root/mrktguru/instance/telegram_system.db'

def migrate():
    from app import app, db
    from models.account import Account
    from models.warmup_log import WarmupLog
    from models.api_credential import ApiCredential
    from models.proxy import Proxy
    from models.user import User
    
    if not os.path.exists(SQLITE_PATH):
        print(f"SQLite database not found at {SQLITE_PATH}")
        return
    
    # Connect to SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()
    
    with app.app_context():
        # Get list of tables from SQLite
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Found tables: {tables}")
        
        # Migrate Users
        if 'users' in tables:
            print("\n--- Migrating Users ---")
            cursor.execute("SELECT * FROM users")
            for row in cursor:
                row_dict = dict(row)
                try:
                    existing = User.query.get(row_dict['id'])
                    if not existing:
                        user = User(
                            id=row_dict['id'],
                            username=row_dict.get('username'),
                            password_hash=row_dict.get('password_hash'),
                            is_active=bool(row_dict.get('is_active', True))
                        )
                        db.session.add(user)
                        print(f"  Added user: {row_dict.get('username')}")
                except Exception as e:
                    print(f"  Error migrating user {row_dict.get('id')}: {e}")
            db.session.commit()
        
        # Migrate API Credentials
        if 'api_credentials' in tables:
            print("\n--- Migrating API Credentials ---")
            cursor.execute("SELECT * FROM api_credentials")
            for row in cursor:
                row_dict = dict(row)
                try:
                    existing = ApiCredential.query.get(row_dict['id'])
                    if not existing:
                        cred = ApiCredential(
                            id=row_dict['id'],
                            api_id=row_dict.get('api_id'),
                            api_hash=row_dict.get('api_hash'),
                            name=row_dict.get('name'),
                            client_type=row_dict.get('client_type'),
                            is_official=bool(row_dict.get('is_official', False)),
                            is_default=bool(row_dict.get('is_default', False)),
                            notes=row_dict.get('notes')
                        )
                        db.session.add(cred)
                        print(f"  Added API credential: {row_dict.get('name')}")
                except Exception as e:
                    print(f"  Error migrating API credential {row_dict.get('id')}: {e}")
            db.session.commit()
        
        # Migrate Proxies
        if 'proxies' in tables:
            print("\n--- Migrating Proxies ---")
            cursor.execute("SELECT * FROM proxies")
            for row in cursor:
                row_dict = dict(row)
                try:
                    existing = Proxy.query.get(row_dict['id'])
                    if not existing:
                        proxy = Proxy(
                            id=row_dict['id'],
                            host=row_dict.get('host'),
                            port=row_dict.get('port'),
                            username=row_dict.get('username'),
                            password=row_dict.get('password'),
                            type=row_dict.get('type', 'socks5'),
                            status=row_dict.get('status', 'active')
                        )
                        db.session.add(proxy)
                        print(f"  Added proxy: {row_dict.get('host')}")
                except Exception as e:
                    print(f"  Error migrating proxy {row_dict.get('id')}: {e}")
            db.session.commit()
        
        # Migrate Accounts
        if 'accounts' in tables:
            print("\n--- Migrating Accounts ---")
            cursor.execute("SELECT * FROM accounts")
            for row in cursor:
                row_dict = dict(row)
                try:
                    existing = Account.query.get(row_dict['id'])
                    if not existing:
                        acc = Account(
                            id=row_dict['id'],
                            phone=row_dict.get('phone'),
                            session_file_path=row_dict.get('session_file_path'),
                            proxy_id=row_dict.get('proxy_id'),
                            status=row_dict.get('status', 'unknown'),
                            health_score=row_dict.get('health_score', 100),
                            warm_up_days_completed=row_dict.get('warm_up_days_completed', 0),
                            warmup_enabled=bool(row_dict.get('warmup_enabled', False)),
                            messages_sent_today=row_dict.get('messages_sent_today', 0),
                            invites_sent_today=row_dict.get('invites_sent_today', 0),
                            notes=row_dict.get('notes'),
                            telegram_id=row_dict.get('telegram_id'),
                            first_name=row_dict.get('first_name'),
                            last_name=row_dict.get('last_name'),
                            username=row_dict.get('username'),
                            bio=row_dict.get('bio'),
                            photo_url=row_dict.get('photo_url'),
                            api_credential_id=row_dict.get('api_credential_id'),
                            source_type=row_dict.get('source_type'),
                            tdata_archive_path=row_dict.get('tdata_archive_path'),
                            verified=bool(row_dict.get('verified', False))
                        )
                        db.session.add(acc)
                        print(f"  Added account: {row_dict.get('phone')}")
                except Exception as e:
                    print(f"  Error migrating account {row_dict.get('id')}: {e}")
            db.session.commit()
        
        # Migrate Warmup Logs
        if 'warmup_logs' in tables:
            print("\n--- Migrating Warmup Logs ---")
            cursor.execute("SELECT * FROM warmup_logs")
            count = 0
            for row in cursor:
                row_dict = dict(row)
                try:
                    existing = WarmupLog.query.get(row_dict['id'])
                    if not existing:
                        log = WarmupLog(
                            id=row_dict['id'],
                            account_id=row_dict.get('account_id'),
                            stage_number=row_dict.get('stage_number'),
                            action_type=row_dict.get('action_type'),
                            status=row_dict.get('status'),
                            message=row_dict.get('message'),
                            details=row_dict.get('details')
                        )
                        db.session.add(log)
                        count += 1
                except Exception as e:
                    pass  # Silently skip log errors
            db.session.commit()
            print(f"  Added {count} warmup logs")
        
        # Reset sequences for PostgreSQL
        print("\n--- Resetting PostgreSQL sequences ---")
        try:
            db.session.execute(db.text("SELECT setval('accounts_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM accounts), false)"))
            db.session.execute(db.text("SELECT setval('api_credentials_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM api_credentials), false)"))
            db.session.execute(db.text("SELECT setval('warmup_logs_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM warmup_logs), false)"))
            db.session.execute(db.text("SELECT setval('users_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM users), false)"))
            db.session.execute(db.text("SELECT setval('proxies_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM proxies), false)"))
            db.session.commit()
            print("  Sequences reset successfully")
        except Exception as e:
            print(f"  Warning: Could not reset sequences: {e}")
    
    sqlite_conn.close()
    print("\n=== Migration Complete! ===")

if __name__ == '__main__':
    migrate()
