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
from utils.activity_logger import ActivityLogger  # Import ActivityLogger

logger = logging.getLogger(__name__)

async def _run_anchor_logic(account_id):
    """
    Async logic for Digital Anchor
    """
    client = None
    activity_logger = ActivityLogger(account_id) # Init logger
    
    try:
        # Random duration: 2 to 5 minutes (120 to 300 seconds)
        duration = random.randint(120, 300)
        
        # Log start to DB/UI
        activity_logger.log(
            action_type='anchor_start',
            status='info',
            description=f'⚓ Digital Anchor started (Keeping session alive for {duration}s)',
            category='system'
        )
        logger.info(f"⚓ Digital Anchor started for Account {account_id}. Duration: {duration}s")
        
        # Create NEW client connection for the anchor
        client = get_telethon_client(account_id)
        
        if not client:
            activity_logger.log(
                action_type='anchor_error',
                status='error',
                description='⚓ Anchor failed: Could not create client',
                category='system'
            )
            return

        # Connect if not connected
        if not client.is_connected():
            await client.connect()

        # Log connection success
        # activity_logger.log(
        #     action_type='anchor_connected',
        #     status='success',
        #     description='⚓ Anchor connected to Telegram socket',
        #     category='system'
        # )

        # Main Loop
        start_time = asyncio.get_event_loop().time()
        ping_count = 0
        
        while (asyncio.get_event_loop().time() - start_time) < duration:
            # 1. Send GetState (Ping)
            try:
                await client(GetStateRequest())
                ping_count += 1
                
                # Log detailed ping only periodically to avoid spamming logs (every ~3 pings)
                if ping_count == 1 or ping_count % 3 == 0:
                     activity_logger.log(
                        action_type='anchor_ping',
                        status='debug', # Debug shows in expanded logs
                        description=f'⚓ Anchor heartbeat (GetState) #{ping_count}',
                        category='system'
                    )
            except Exception as e:
                logger.warning(f"⚓ Anchor Ping warning: {e}")
                if "AuthKey" in str(e) or "Deactivated" in str(e):
                    activity_logger.log(
                        action_type='anchor_error',
                        status='error',
                        description=f'⚓ Anchor interrupted: {str(e)}',
                        category='system'
                    )
                    break

            # 2. Sleep for random interval (30-60 seconds)
            sleep_time = random.randint(30, 60)
            remaining = duration - (asyncio.get_event_loop().time() - start_time)
            
            if remaining <= 0:
                break
                
            sleep_time = min(sleep_time, remaining)
            await asyncio.sleep(sleep_time)

        # Finished
        activity_logger.log(
            action_type='anchor_finish',
            status='success',
            description=f'⚓ Digital Anchor finished successfully ({ping_count} heartbeats)',
            category='system'
        )
        logger.info(f"⚓ Digital Anchor finished for Account {account_id} (Success)")

    except Exception as e:
        logger.error(f"⚓ Digital Anchor error for Account {account_id}: {e}")
        activity_logger.log(
            action_type='anchor_error',
            status='error',
            description=f'⚓ Anchor crashed: {str(e)}',
            category='system'
        )
    finally:
        if client:
            await client.disconnect()

def run_digital_anchor_background(account_id):
    """
    Spawns a background thread to run the Digital Anchor logic.
    Call this AFTER successful verification.
    """
    def thread_target():
        # Import app here to avoid circular imports during startup
        from app import app
        
        # Create app context for DB access (ActivityLogger)
        with app.app_context():
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_run_anchor_logic(account_id))
            loop.close()

    thread = threading.Thread(target=thread_target, name=f"Anchor-{account_id}", daemon=True)
    thread.start()
    logger.info(f"⚓ Digital Anchor thread spawned for Account {account_id}")
