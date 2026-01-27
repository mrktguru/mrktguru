
import os
import sys
import asyncio
from app import create_app
from database import db
from models.account import Account
from utils.telethon_helper import get_telethon_client
from datetime import datetime

# Initialize Flask App
app = create_app()

async def restore_photo(account_id):
    """Connect and re-download photo"""
    try:
        print(f"🔄 Processing Account {account_id}...")
        client = get_telethon_client(account_id)
        
        if not client.is_connected():
            await client.connect()
            
        if not await client.is_user_authorized():
            print(f"❌ Account {account_id} not authorized")
            await client.disconnect()
            return

        me = await client.get_me()
        if not me:
            print(f"❌ Account {account_id} GetMe failed")
            await client.disconnect()
            return
            
        if hasattr(me, "photo") and me.photo:
            # Download profile photo
            upload_folder = os.path.join(os.getcwd(), 'uploads', 'photos')
            os.makedirs(upload_folder, exist_ok=True)
            
            filename = f"{me.id}_{int(datetime.utcnow().timestamp())}.jpg"
            filepath = os.path.join(upload_folder, filename)
            
            print(f"📸 Downloading profile photo to {filepath}...")
            await client.download_profile_photo(me, file=filepath)
            
            if os.path.exists(filepath):
                # Update DB
                with app.app_context():
                    acc = Account.query.get(account_id)
                    acc.photo_url = f"uploads/photos/{filename}"
                    db.session.commit()
                print(f"✅ Account {account_id} photo restored.")
            else:
                print(f"⚠️ Download failed (file missing) for {account_id}")
        else:
            print(f"ℹ️ Account {account_id} has no photo on Telegram")
            
        await client.disconnect()
        
    except Exception as e:
        print(f"❌ Error for {account_id}: {e}")

async def main():
    with app.app_context():
        # Get active accounts
        accounts = Account.query.filter(Account.status != 'banned').all()
        ids = [a.id for a in accounts]
        print(f"Found {len(ids)} accounts to check.")
    
    for aid in ids:
        await restore_photo(aid)
        # Sleep to avoid flood limits? downloading photo is cheap
        await asyncio.sleep(1)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
