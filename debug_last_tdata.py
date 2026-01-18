from app import create_app
from models.tdata_metadata import TDataMetadata
from models.account import Account
import json
import sys

# Initialize Flask app context
app = create_app()

with app.app_context():
    # Get the most recent account
    account = Account.query.order_by(Account.created_at.desc()).first()
    
    if not account:
        print("❌ No accounts found in database.")
        sys.exit(1)
        
    print(f"\n=== DEBUGGING ACCOUNT #{account.id} ({account.phone}) ===")
    print(f"Source Type: {account.source_type}")
    print(f"Created At: {account.created_at}")
    
    if account.source_type != 'tdata':
        print("⚠️ This account is NOT from TData.")
    
    if not account.tdata_metadata:
        print("❌ CRITICAL: No TData metadata record found!")
        sys.exit(1)
        
    td = account.tdata_metadata
    print(f"\n--- Stored Metadata ---")
    print(f"DC ID (used for session): {td.dc_id}")
    print(f"Main DC ID (extracted):   {td.main_dc_id}")
    print(f"User ID (extracted):      {td.user_id}")
    print(f"Auth Key ID:              {td.auth_key_id}")
    
    print(f"\n--- Raw Metadata Dump ---")
    if td.raw_metadata:
        try:
            # Check deep inside raw metadata for clues
            auth = td.raw_metadata.get('auth_data', {})
            print(f"Raw Auth Data DC ID: {auth.get('dc_id')}")
            print(f"Raw Auth Data Main DC: {auth.get('main_dc_id')}")
            
            # Check if DC ID mismatch exists
            if td.dc_id != auth.get('dc_id') and auth.get('dc_id'):
                print(f"⚠️ MISMATCH DETECTED: Stored DC {td.dc_id} != Raw DC {auth.get('dc_id')}")
        except Exception as e:
            print(f"Error reading raw metadata: {e}")
    else:
        print("No raw_metadata json found.")
        
    print(f"\n==========================================")
    print("If 'DC ID' is 2 but 'Main DC ID' is different or None, that's the bug.")
