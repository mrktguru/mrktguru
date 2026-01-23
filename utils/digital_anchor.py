"""
Digital Anchor (Цифровой Якорь) v2.0
=====================================
Scenario: "User opens Telegram Desktop -> Idle -> PC goes to sleep"

This version emulates realistic idle behavior:
1. Connect to Telegram
2. Stay connected passively (Telethon handles MTProto keep-alive internally)
3. Optionally do ONE status check halfway through
4. Disconnect cleanly (simulating PC sleep mode)

NO GetState spam - real TDesktop doesn't ping every 30 seconds when idle.
"""
import asyncio
import random
import logging
import threading
from telethon.tl.functions.updates import GetStateRequest
from utils.telethon_helper import get_telethon_client
from utils.activity_logger import ActivityLogger

logger = logging.getLogger(__name__)


async def _run_anchor_logic(account_id):
    """
    ⚓ Idle -> Sleep Scenario
    
    1. Account connects (Telethon auto-sends InitConnection)
    2. Stays connected passively for 10-25 minutes
    3. Optional: Single GetState check at midpoint
    4. Disconnects (simulating PC going to sleep)
    """
    client = None
    activity_logger = ActivityLogger(account_id)
    
    try:
        # FIX: Use normal distribution instead of uniform
        # Real human behavior follows bell curve (most around 15min, some shorter/longer)
        # Mean = 900s (15min), StdDev = 300s (5min)
        import numpy as np
        sleep_timer = int(np.random.normal(900, 300))
        sleep_timer = max(300, min(sleep_timer, 2400))  # Clamp to 5-40 min
        
        activity_logger.log(
            action_type='anchor_start',
            status='info',
            description=f'⚓ Idle session started (PC sleep in {sleep_timer // 60} min)',
            category='system'
        )
        logger.info(f"⚓ Account {account_id}: Idle session started. Sleep timer: {sleep_timer}s")
        
        # Create client
        client = get_telethon_client(account_id)
        if not client:
            raise Exception("Failed to create client")
        
        # Connect
        if not client.is_connected():
            await client.connect()
        
        # Verify session is valid (this does one get_me internally)
        if not await client.is_user_authorized():
            raise Exception("Session invalid or unauthorized")
        
        logger.info(f"⚓ Account {account_id}: Connected, entering idle mode...")
        
        # === IDLE PHASE ===
        # We just wait. Telethon handles MTProto ping internally.
        # This is exactly what minimized TDesktop does.
        
        elapsed = 0
        check_interval = 10  # Check connection status every 10 sec
        midpoint = sleep_timer // 2
        midpoint_check_done = False
        
        while elapsed < sleep_timer:
            # Ensure connection is alive
            if not client.is_connected():
                logger.warning(f"⚓ Account {account_id}: Connection lost, reconnecting...")
                await client.connect()
            
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            # Optional: Single GetState at midpoint (mimics occasional tab switch)
            # This is realistic - user might glance at Telegram once during idle
            if not midpoint_check_done and elapsed >= midpoint:
                try:
                    await client(GetStateRequest())
                    midpoint_check_done = True
                    logger.debug(f"⚓ Account {account_id}: Midpoint check OK")
                except Exception as e:
                    logger.warning(f"⚓ Midpoint check failed: {e}")
                    if "AuthKey" in str(e) or "Deactivated" in str(e):
                        activity_logger.log(
                            action_type='anchor_error',
                            status='error',
                            description=f'Session error during idle: {str(e)}',
                            category='system'
                        )
                        break
            
            # Progress log every 5 minutes
            if elapsed % 300 == 0:
                logger.debug(f"⚓ Account {account_id}: Idle... {elapsed // 60}/{sleep_timer // 60} min")
        
        # === SLEEP PHASE ===
        # PC "went to sleep" - network interface disabled
        # We just disconnect cleanly
        
        activity_logger.log(
            action_type='anchor_finish',
            status='success',
            description=f'💤 PC went to sleep (idle {sleep_timer // 60} min)',
            category='system'
        )
        logger.info(f"💤 Account {account_id}: PC went to sleep after {sleep_timer // 60} min idle")
        
    except Exception as e:
        logger.error(f"⚓ Anchor error for Account {account_id}: {e}")
        activity_logger.log(
            action_type='anchor_error',
            status='error',
            description=f'Anchor error: {str(e)}',
            category='system'
        )
    finally:
        # Clean disconnect (simulates network interface shutdown)
        if client and client.is_connected():
            await client.disconnect()
            logger.debug(f"⚓ Account {account_id}: Disconnected")


def run_digital_anchor_background(account_id):
    """
    Spawns a background thread to run the Digital Anchor logic.
    Call this AFTER successful verification.
    """
    def thread_target():
        from app import app
        
        with app.app_context():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_run_anchor_logic(account_id))
            loop.close()
    
    thread = threading.Thread(target=thread_target, name=f"Anchor-{account_id}", daemon=True)
    thread.start()
    logger.info(f"⚓ Digital Anchor thread spawned for Account {account_id}")
