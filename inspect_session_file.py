import sqlite3
import os
import sys
from app import create_app
from models.account import Account

app = create_app()

with app.app_context():
    account = Account.query.order_by(Account.created_at.desc()).first()
    if not account:
        print("No account found")
        sys.exit(1)
        
    path = account.session_file_path
    print(f"Inspecting session file: {path}")
    
    if not os.path.exists(path):
        print("File does not exist!")
        sys.exit(1)
        
    try:
        conn = sqlite3.connect(path)
        c = conn.cursor()
        
        print("\n--- SESSIONS TABLE ---")
        for row in c.execute("SELECT * FROM sessions"):
            print(f"DC ID: {row[0]}")
            print(f"Server: {row[1]}:{row[2]}")
            print(f"Auth Key Len: {len(row[3]) if row[3] else 0}")
            
        print("\n--- VERSION ---")
        for row in c.execute("SELECT * FROM version"):
            print(f"Version: {row[0]}")
            
        conn.close()
        
    except Exception as e:
        print(f"Error reading sqlite: {e}")
