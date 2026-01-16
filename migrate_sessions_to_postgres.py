#!/usr/bin/env python3
"""
Migrate existing Telethon .session files to PostgreSQL StringSession
"""
import os
from telethon.sessions import SQLiteSession, StringSession

def migrate_sessions():
    from app import app, db
    from models.account import Account
    
    print("Migrating Telethon sessions from SQLite files to PostgreSQL...")
    
    with app.app_context():
        accounts = Account.query.all()
        migrated = 0
        skipped = 0
        errors = 0
        
        for account in accounts:
            print(f"\nProcessing account {account.id} ({account.phone})...")
            
            # Skip if already has session_string
            if account.session_string:
                print(f"  ✓ Already has session_string, skipping")
                skipped += 1
                continue
            
            # Check if session file exists
            session_path = account.session_file_path
            if not os.path.exists(session_path):
                print(f"  ✗ Session file not found: {session_path}")
                errors += 1
                continue
            
            try:
                # Load SQLite session
                sqlite_session = SQLiteSession(session_path)
                
                # Convert to string
                session_string = StringSession.save(sqlite_session)
                
                # Save to database
                account.session_string = session_string
                db.session.commit()
                
                print(f"  ✓ Migrated successfully (session string length: {len(session_string)})")
                migrated += 1
                
            except Exception as e:
                print(f"  ✗ Error migrating: {e}")
                errors += 1
                db.session.rollback()
        
        print(f"\n{'='*60}")
        print(f"Migration Summary:")
        print(f"  Migrated: {migrated}")
        print(f"  Skipped (already migrated): {skipped}")
        print(f"  Errors: {errors}")
        print(f"  Total: {len(accounts)}")
        print(f"{'='*60}\n")

if __name__ == '__main__':
    migrate_sessions()
