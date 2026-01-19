
from app import app
from utils.telethon_helper import get_telethon_client
from models.account import Account
import traceback
import sys

# Configure logging to stdout
import logging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

print("--- START DEBUG BOOTSTRAPPED ---")
try:
    with app.app_context():
        print("Context loaded.")
        account = Account.query.get(40)
        if not account:
            print("Account 40 not found")
        else:
            print(f"Account: {account.phone}")
            print(f"Proxy ID: {account.proxy_id}")
            if account.proxy:
                print(f"Proxy: {account.proxy.host}")
                print(f"Proxy Type: {account.proxy.type}")
            else:
                 print("No proxy found")
            
            print("Calling get_telethon_client(40)...")
            client = get_telethon_client(40)
            print("Client created successfully")
            
except Exception:
    traceback.print_exc()
print("--- END DEBUG BOOTSTRAPPED ---")
