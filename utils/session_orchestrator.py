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
from telethon.tl.functions.contacts import GetTopPeersRequest # 🔥 NEW
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
        
        # 🔒 LOCK: Предотвращает гонку потоков при одновременном запуске задач
        self._lock = asyncio.Lock()

    async def start_monitoring(self):
        """Starts a background monitor to handle Auto-Idle state transitions."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._lifecycle_monitor())
            logger.info(f"[{self.account_id}] 📡 Lifecycle monitor started")

    async def execute(self, task_func: Callable, *args, **kwargs) -> Any:
        """
        ⚡ MAIN ENTRY POINT.
        Thread-safe execution wrapper.
        """
        # 🔒 Используем лок, чтобы не запустить Cold Start дважды
        async with self._lock:
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
                logger.error(f"[{self.account_id}] ❌ Execution failed in {task_func.__name__}: {e}")
                
                # Critical Error Handling
                err_str = str(e)
                if any(x in err_str for x in ["Connection", "Disconnect", "AuthKey", "Timeout"]):
                    logger.warning(f"[{self.account_id}] 🔌 Network/Auth critical error. Resetting to OFFLINE.")
                    self.state = "OFFLINE"
                    if self.client:
                        try:
                            await self.client.disconnect()
                        except:
                            pass
                raise e

    async def stop(self):
        """Graceful shutdown of the session and monitor."""
        self._stop_event.set()
        
        # Cancel monitor
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        async with self._lock: # 🔒 Ждем завершения текущих задач перед отключением
            if self.client and self.client.is_connected():
                logger.info(f"[{self.account_id}] 🚪 Shutting down...")
                try:
                    # Set offline status before disconnecting
                    await self.client(UpdateStatusRequest(offline=True))
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.debug(f"[{self.account_id}] Offline status set failed: {e}")
                
                await self.client.disconnect()
                
            self.state = "OFFLINE"
            # Не обнуляем self.client полностью, чтобы переиспользовать настройки, 
            # но можно и обнулить, если get_telethon_client создает новый инстанс.
            # self.client = None 

    # --- INTERNAL LOGIC (PRIVATE) ---

    async def _ensure_ready_state(self):
        """Handles state transitions."""
        
        # Scenario 1: COLD START
        if self.state == "OFFLINE" or not self.client or not self.client.is_connected():
            await self._perform_cold_start()

        # Scenario 2: HOT START (Wake up)
        elif self.state == "IDLE":
            await self._perform_hot_start()

        # Scenario 3: ACTIVE (Just touch)
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
            await self.client.disconnect()
            self.state = "OFFLINE"
            raise Exception("Session Unauthorized/Banned during Cold Start")

        # Emulate TDesktop startup sequences
        try:
            # 1. Config & State
            await self.client(GetConfigRequest())
            state = await self.client(GetStateRequest())
            
            # 2. Sync (Difference)
            await self.client(GetDifferenceRequest(
                pts=state.pts, date=state.date, qts=state.qts, pts_total_limit=100
            ))
            
            # 3. Dialogs (Tray load)
            await self.client(GetDialogsRequest(
                offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(),
                limit=40, hash=0
            ))
            
            # 4. 🔥 NEW: Top Peers (Search Hints) - Важно для мимикрии!
            try:
                await self.client(GetTopPeersRequest(
                    correspondents=True, bots_pm=True, bots_inline=True,
                    phone_calls=True, forward_users=True, forward_chats=True,
                    groups=True, channels=True,
                    offset=0, limit=20, hash=0
                ))
            except Exception:
                pass # Не критично, если пусто

            # 5. Set Online
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
        """🔥 HOT START: Waking up from IDLE."""
        logger.info(f"[{self.account_id}] 🔥 Waking up from Idle...")
        
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        try:
            await self.client(UpdateStatusRequest(offline=False))
            await self.client(GetStateRequest()) # Light sync check
            
            self.state = "ACTIVE"
            self.last_activity = datetime.now()
        except Exception as e:
             logger.warning(f"[{self.account_id}] ⚠️ Hot start failed. Fallback to Cold Start.")
             self.state = "OFFLINE"
             await self._perform_cold_start()

    async def _lifecycle_monitor(self):
        """Background loop to auto-switch to IDLE."""
        while not self._stop_event.is_set():
            try:
                now = datetime.now()
                idle_seconds = (now - self.last_activity).total_seconds()

                # Rule: ACTIVE -> IDLE after 180s silence
                if self.state == "ACTIVE" and idle_seconds > 180:
                    # 🔒 Lock check to ensure we don't switch while task is running
                    if not self._lock.locked(): 
                        logger.info(f"[{self.account_id}] 💤 Auto-Idle (>3 min inactivity)")
                        try:
                            if self.client and self.client.is_connected():
                                await self.client(UpdateStatusRequest(offline=True))
                            self.state = "IDLE"
                        except:
                            self.state = "OFFLINE"

                # Connection Watchdog
                if self.client and not self.client.is_connected() and self.state != "OFFLINE":
                    self.state = "OFFLINE"

                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.account_id}] Monitor error: {e}")
                await asyncio.sleep(10)
