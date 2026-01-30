
import sys
import os
sys.path.append(os.getcwd())

# Patch gevent
try:
    from gevent import monkey
    monkey.patch_all()
except ImportError:
    pass

from app import create_app
from database import db
from models.proxy import Proxy
from utils.validators import validate_proxy
from utils.proxy_helper import extract_country_from_username, test_proxy_connection

def debug_update():
    app = create_app()
    with app.app_context():
        print("--- DEBUGGING PROXY UPDATE ---")
        
        # Create a dummy proxy logic
        proxy_string = "http://user:pass@127.0.0.1:8080"
        print(f"Validating: {proxy_string}")
        
        is_valid, result = validate_proxy(proxy_string)
        if not is_valid:
            print("Validation failed")
            return
            
        print(f"Validation result: {result}")
        
        # Simulate Update
        print("Simulating update...")
        try:
            # We won't save to DB to avoid clutter, just simulate object manipulation
            p = Proxy()
            p.type = result['type']
            p.host = result['host']
            p.port = result['port']
            p.username = result['username']
            p.password = result['password']
            
            p.country = extract_country_from_username(p.username)
            print(f"Country extracted: {p.country}")
            
            print("Testing connection (Dry Run)...")
            # We mock requests to avoid actual network call issues distracting us
            # But wait, recursion might be IN requests patching if gevent is messing up?
            # Let's try real call check first.
            
            res = test_proxy_connection(p)
            print(f"Connection Test Result: {res}")
            
            print("Accessing properties...")
            print(f"Flag: {p.flag}")
            print(f"Repr: {repr(p)}")
            
        except RecursionError:
            print("!!! RECURSION ERROR DETECTED !!!")
            import traceback
            traceback.print_exc()
        except Exception as e:
            print(f"Other error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_update()
