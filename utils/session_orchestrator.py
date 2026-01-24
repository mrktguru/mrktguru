import asyncio
import logging
import random
from datetime import datetime
from typing import Callable, Any

# Telethon Imports
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.help import GetConfigRequest
from telethon.tl.functions.updates import GetStateRequest, GetDifferenceRequest
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty

# Custom Client Import
from utils.telethon_helper import get_telethon_client

logger = logging.getLogger(__name__)

class SessionOrchestrator:
    """
    Manages the lifecycle of a Telegram session using a State Machine approach.
    States:
    - OFFLINE: Disconnected. Requires Cold Start.
    - IDLE: Connected but inactive (background). Requires Hot Start to become ACTIVE.
    - ACTIVE: Connected and actively performing tasks.
    """
    
    def __init__(self, account_id: int):
        self.account_id = account_id
        self.client = None
        
        # States: 'OFFLINE', 'ACTIVE', 'IDLE'
        self.state = "OFFLINE" 
        
        self.last_activity = datetime.now()
        self._monitor_task = None
        self._stop_event = asyncio.Event()

    async def start_monitoring(self):
        """Starts a background monitor to handle Auto-Idle state transitions."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._lifecycle_monitor())
            logger.info(f"[{self.account_id}] 📡 Lifecycle monitor started")

    async def execute(self, task_func: Callable, *args, **kwargs) -> Any:
        """
        ⚡ MAIN ENTRY POINT.
        Checks the current state, performs necessary transitions (Cold/Hot start),
        and executes the provided task function.
        """
        try:
            # 1. STATE CHECK & PREPARATION
            await self._ensure_ready_state()

            # 2. TASK EXECUTION
            task_name = task_func.__name__
            logger.info(f"[{self.account_id}] ▶️ Executing: {task_name}")
            
            # Inject client as the first argument to the task
            result = await task_func(self.client, *args, **kwargs)
            
            # 3. UPDATE ACTIVITY
            self.last_activity = datetime.now()
            return result

        except Exception as e:
            logger.error(f"[{self.account_id}] ❌ Execution failed: {e}")
            # If network/auth failure, reset to OFFLINE
            if "Connection" in str(e) or "Disconnect" in str(e) or "AuthKey" in str(e):
                logger.warning(f"[{self.account_id}] 🔌 Connection/Auth lost. Resetting to OFFLINE.")
                self.state = "OFFLINE"
            raise e

    async def stop(self):
        """Graceful shutdown of the session and monitor."""
        self._stop_event.set()
        if self._monitor_task:
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        if self.client and self.client.is_connected():
            logger.info(f"[{self.account_id}] 🚪 Shutting down...")
            try:
                # Set offline status before disconnecting
                await self.client(UpdateStatusRequest(offline=True))
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"[{self.account_id}] Error setting offline status: {e}")
            
            await self.client.disconnect()
            
        self.state = "OFFLINE"
        self.client = None

    # --- INTERNAL LOGIC (PRIVATE) ---

    async def _ensure_ready_state(self):
        """Handles state transitions to ensure the bot is ready for ACTIVE work."""
        
        # Scenario 1: BOT IS DISCONNECTED (Cold Start)
        if self.state == "OFFLINE" or not self.client or not self.client.is_connected():
            await self._perform_cold_start()

        # Scenario 2: BOT IS SLEEPING IN TRAY (Hot Start)
        elif self.state == "IDLE":
            await self._perform_hot_start()

        # Scenario 3: BOT IS ACTIVE -> Just update timer
        else:
            self.last_activity = datetime.now()

    async def _perform_cold_start(self):
        """🧊 COLD START: Full application launch simulation."""
        logger.info(f"[{self.account_id}] 🧊 Starting Telegram Desktop (Cold Boot)...")
        
        if not self.client:
            self.client = get_telethon_client(self.account_id)
        
        if not self.client.is_connected():
            await self.client.connect()
        
        if not await self.client.is_user_authorized():
            # If not authorized, we cannot proceed with tasks.
            # Depending on logic, might raise or return. Raising is safer to stop flow.
            # Ensure we close connection if auth fails to avoid zombie connections
            await self.client.disconnect()
            self.state = "OFFLINE"
            raise Exception("Session Unauthorized/Banned during Cold Start")

        # Emulate TDesktop startup sequences
        try:
            await self.client(GetConfigRequest())
            state = await self.client(GetStateRequest())
            # Sync difference (updates while offline)
            await self.client(GetDifferenceRequest(
                pts=state.pts, date=state.date, qts=state.qts, pts_total_limit=100
            ))
            # Load dialog list (Tray load)
            await self.client(GetDialogsRequest(
                offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(),
                limit=40, hash=0
            ))
            
            # Set Status Online
            await self.client(UpdateStatusRequest(offline=False))
            
            self.state = "ACTIVE"
            self.last_activity = datetime.now()
            logger.info(f"[{self.account_id}] ✅ Cold Start Complete. System Online.")
            
        except Exception as e:
            logger.error(f"[{self.account_id}] ❌ Cold Start Failed: {e}")
            await self.client.disconnect()
            self.state = "OFFLINE"
            raise e

    async def _perform_hot_start(self):
        """🔥 HOT START: Waking up from IDLE (Tray restore)."""
        logger.info(f"[{self.account_id}] 🔥 Waking up from Idle (Hot Start)...")
        
        # Human reaction delay
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        try:
            # Set Online
            await self.client(UpdateStatusRequest(offline=False))
            
            # Light sync check
            await self.client(GetStateRequest())
            
            self.state = "ACTIVE"
            self.last_activity = datetime.now()
        except Exception as e:
             logger.warning(f"[{self.account_id}] ⚠️ Hot start verification failed ({e}). Fallback to Cold Start.")
             # If hot start fails (e.g. connection dropped in background), try cold start
             self.state = "OFFLINE"
             await self._perform_cold_start()

    async def _lifecycle_monitor(self):
        """Background loop to auto-switch to IDLE after inactivity."""
        logger.debug(f"[{self.account_id}] Lifecycle monitor running...")
        
        while not self._stop_event.is_set():
            try:
                now = datetime.now()
                idle_seconds = (now - self.last_activity).total_seconds()

                # If ACTIVE and inactive for > 180s (3 mins) -> Go IDLE
                # (User minimizes window / stops interacting)
                if self.state == "ACTIVE" and idle_seconds > 180:
                    logger.info(f"[{self.account_id}] 💤 Auto-Idle triggered (>3 min inactivity)")
                    try:
                        if self.client and self.client.is_connected():
                            await self.client(UpdateStatusRequest(offline=True))
                        self.state = "IDLE"
                    except Exception as e:
                        logger.warning(f"[{self.account_id}] Auto-Idle status update failed: {e}")
                        self.state = "OFFLINE"

                # If connected but physically disconnected -> Mark OFFLINE
                if self.client and not self.client.is_connected() and self.state != "OFFLINE":
                    logger.warning(f"[{self.account_id}] 🔌 Socket disconnected in background.")
                    self.state = "OFFLINE"

                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.account_id}] Monitor error: {e}")
                await asyncio.sleep(10)
