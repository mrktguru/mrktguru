"""
Digital Anchor (Цифровой Якорь)
Rule: After successful verification, keep session online for 2-5 minutes.
Periodically send GetStateRequest to keep socket alive and mimic user activity.
This builds "Trust Score" by showing stable connection/reading behavior.
"""
import asyncio
import random
import logging
import threading
from telethon import TelegramClient
from telethon.tl.functions.updates import GetStateRequest
from utils.telethon_helper import get_telethon_client

logger = logging.getLogger(__name__)

async def _run_anchor_logic(account_id):
    """
    Async logic for Digital Anchor
    """
    client = None
    try:
        # Random duration: 2 to 5 minutes (120 to 300 seconds)
        duration = random.randint(120, 300)
        logger.info(f"⚓ Digital Anchor started for Account {account_id}. Duration: {duration}s")
        
        # Create NEW client connection for the anchor
        # (We cannot reuse the previous one easily across threads/contexts in Flask)
        client = await get_telethon_client(account_id)
        
        if not client:
            logger.error(f"⚓ Anchor failed: Could not create client for Account {account_id}")
            return

        logger.info(f"⚓ Anchor connected for Account {account_id}")
        
        # Connect if not connected (get_telethon_client might return connected or not depending on impl)
        if not client.is_connected():
            await client.connect()

        # Main Loop
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < duration:
            # 1. Send GetState (Ping)
            try:
                await client(GetStateRequest())
                # logger.debug(f"⚓ Anchor Ping (GetState) for Account {account_id}")
            except Exception as e:
                logger.warning(f"⚓ Anchor Ping warning: {e}")
                # Don't break, try to stay online unless fatal
                if "AuthKey" in str(e) or "Deactivated" in str(e):
                    break

            # 2. Sleep for random interval (30-60 seconds)
            sleep_time = random.randint(30, 60)
            remaining = duration - (asyncio.get_event_loop().time() - start_time)
            
            if remaining <= 0:
                break
                
            sleep_time = min(sleep_time, remaining)
            await asyncio.sleep(sleep_time)

        logger.info(f"⚓ Digital Anchor finished for Account {account_id} (Success)")

    except Exception as e:
        logger.error(f"⚓ Digital Anchor error for Account {account_id}: {e}")
    finally:
        if client:
            await client.disconnect()
            logger.info(f"⚓ Anchor disconnected for Account {account_id}")

def run_digital_anchor_background(account_id):
    """
    Spawns a background thread to run the Digital Anchor logic.
    Call this AFTER successful verification.
    """
    def thread_target():
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run_anchor_logic(account_id))
        loop.close()

    thread = threading.Thread(target=thread_target, name=f"Anchor-{account_id}", daemon=True)
    thread.start()
    logger.info(f"⚓ Digital Anchor thread spawned for Account {account_id}")
