import os
import sys
import asyncio
import zipfile
import shutil
from telethon import TelegramClient
from telethon.sessions import StringSession
from app import create_app
from models.account import Account
from opentele.td import TDesktop
from opentele.api import API

async def test_conversion():
    app = create_app()
    with app.app_context():
        account = Account.query.filter(Account.source_type == 'tdata').order_by(Account.created_at.desc()).first()
        if not account:
            print("No TData account found")
            return

        print(f"Testing account {account.id} ({account.phone})")
        archive_path = account.tdata_archive_path
        if not archive_path or not os.path.exists(archive_path):
            print(f"Archive missing: {archive_path}")
            return

        # Extract to temp
        extract_dir = f"temp_debug_tdata_{account.id}"
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir)
        
        print(f"Extracting {archive_path} to {extract_dir}")
        with zipfile.ZipFile(archive_path, 'r') as z:
            z.extractall(extract_dir)
            
        # Find tdata folder
        tdata_path = None
        for root, dirs, files in os.walk(extract_dir):
            if 'tdata' in dirs:
                tdata_path = os.path.join(root, 'tdata')
                break
            if os.path.basename(root) == 'tdata':
                tdata_path = root
                break
        
        if not tdata_path:
            tdata_path = extract_dir # Assume root is tdata
            
        print(f"Loading TData from {tdata_path}")
        try:
            tdesk = TDesktop(tdata_path)
            
            # Use official API for conversion check
            api = API.TelegramDesktop
            
            # Convert to session
            print("Converting to Telethon session...")
            client = await tdesk.ToTelethon(session=StringSession(), flag=UseCurrentSession)
            
            session_str = client.session.save()
            print(f"✅ GENERATED STRING SESSION: {session_str[:20]}...")
            
            # Test connection
            print("Connecting with generated session...")
            await client.connect()
            
            me = await client.get_me()
            if me:
                print(f"✅ SUCCESS! Logged in as: {me.first_name} ({me.id})")
            else:
                print("❌ FAILED: get_me() returned None")
                
            await client.disconnect()
            
        except Exception as e:
            print(f"❌ CONVERSION ERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            shutil.rmtree(extract_dir)

# Need UseCurrentSession flag or similar?
# opentele ToTelethon signature: (session=None, flag=None, api=None)
# UseCurrentSession is a constant in opentele? checking...

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_conversion())
