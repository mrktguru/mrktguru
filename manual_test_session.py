import asyncio
import logging
from app import create_app
from models.account import Account
from utils.telethon_helper import get_telethon_client
from telethon import TelegramClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_account_manually():
    app = create_app()
    with app.app_context():
        # Get the failing account
        account = Account.query.order_by(Account.created_at.desc()).first()
        if not account:
            print("No account found")
            return

        print(f"Testing account {account.id} ({account.phone})")
        print(f"Session path: {account.session_file_path}")
        
        try:
            client = get_telethon_client(account.id)
            print("Connecting...")
            await client.connect()
            
            if not await client.is_user_authorized():
                print("❌ Client reports NOT AUTHORIZED (is_user_authorized() = False)")
            else:
                print("✅ Client reports AUTHORIZED")

            print("Calling get_me()...")
            me = await client.get_me()
            
            if me:
                print(f"✅ SUCCESS! User: {me.first_name} (ID: {me.id})")
                print(f"Status: {me.status}")
            else:
                print("❌ get_me() returned None")
                
                # Try getting dialogs to see if it triggers anything
                try:
                    print("Trying to fetch dialogs...")
                    dialogs = await client.get_dialogs(limit=1)
                    print(f"Dialogs count: {len(dialogs)}")
                except Exception as e:
                    print(f"Error fetching dialogs: {e}")

            await client.disconnect()
            
        except Exception as e:
            print(f"CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_account_manually())
