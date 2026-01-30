
import sys
import os
from app import create_app
from database import db
from utils.telethon_helper import get_telethon_client
from models.account import Account
import traceback

app = create_app()

with app.app_context():
    try:
        print("Attempting to load account 40...")
        account = Account.query.get(40)
        if not account:
            print("Account 40 not found!")
            sys.exit(1)
            
        print(f"Account 40 found: {account.phone}")
        print(f"Proxy ID: {account.proxy_id}")
        if account.proxy:
             print(f"Proxy: {account.proxy.host}:{account.proxy.port} ({account.proxy.type})")
        else:
             print("No proxy object found via relationship")
        
        print("Attempting to get_telethon_client(40)...")
        client = get_telethon_client(40)
        print("Success! Client initialized.")
        
    except Exception as e:
        print("\n!!! ERROR CAUGHT !!!")
        traceback.print_exc()
