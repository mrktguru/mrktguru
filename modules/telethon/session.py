import asyncio
import logging
import random
from datetime import datetime
from typing import Callable, Any

from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.help import GetConfigRequest
from telethon.tl.functions.contacts import GetTopPeersRequest
from telethon.tl.types import InputPeerEmpty

from modules.telethon.client import ClientFactory
from modules.telethon.verification import verify_session
# Note: verify_session here is the NEW one.

logger = logging.getLogger(__name__)

class SessionDeathError(Exception):
    """Critical session error: Ban or Authorization lost."""
    def __init__(self, message, reason='unknown'):
        super().__init__(message)
        self.reason = reason

class SessionOrchestrator:
    """
    Manages the lifecycle of a Telegram session using a State Machine approach.
    """
    def __init__(self, account_id: int):
        self.account_id = account_id
        self.client = None
        self.state = 'OFFLINE'
        self.last_activity = None
        
        self.monitoring_task = None
        self.shutdown_event = asyncio.Event()
        self._execution_lock = asyncio.Lock()
        
        # State config
        self.IDLE_TIMEOUT = 180  # 3 minutes
        self.MAX_LIFESPAN = 900  # 15 minutes

    async def start_monitoring(self):
        if not self.monitoring_task or self.monitoring_task.done():
            self.shutdown_event.clear()
            self.monitoring_task = asyncio.create_task(self._lifecycle_monitor())
            logger.info(f"[{self.account_id}] 🟢 Session Monitor started")

    async def execute(self, task_func: Callable, *args, **kwargs) -> Any:
        async with self._execution_lock:
            try:
                await self._ensure_ready_state()
                self.last_activity = datetime.now()
                return await task_func(self.client, *args, **kwargs)
                
            except SessionDeathError:
                await self._handle_ban_logic()
                raise
            except Exception as e:
                logger.error(f"[{self.account_id}] Execution error: {e}")
                raise

    async def _handle_ban_logic(self):
        logger.critical(f"[{self.account_id}] ☠️ Handling Session Death...")
        await self.stop()

    async def stop(self):
        self.shutdown_event.set()
        if self.monitoring_task:
            try:
                await asyncio.wait_for(self.monitoring_task, timeout=2.0)
            except asyncio.TimeoutError:
                pass
        
        if self.client:
            if self.client.is_connected():
                await self.client.disconnect()
            self.client = None
            
        self.state = 'OFFLINE'
        logger.info(f"[{self.account_id}] 🔴 Session Stopped")

    async def _ensure_ready_state(self):
        if self.state == 'OFFLINE' or not self.client or not self.client.is_connected():
            await self._perform_cold_start()
        elif self.state == 'IDLE':
            await self._perform_hot_start()
            
        if not await self.client.is_user_authorized():
            raise SessionDeathError("User not authorized", reason='auth_lost')

    async def _perform_cold_start(self):
        logger.info(f"[{self.account_id}] 🧊 COLD START initiated...")
        
        self.client = ClientFactory.create_client(self.account_id)
        await self.client.connect()
        
        if not await self.client.is_user_authorized():
             logger.warning(f"[{self.account_id}] Not authorized on cold start")
             # Try clean disconnect
             await self.client.disconnect()
             raise SessionDeathError("Not authorized", reason='auth_fail')
        
        # Verify Session
        res = await verify_session(self.account_id, client=self.client)
        if not res['success']:
             await self.client.disconnect()
             raise SessionDeathError(f"Verification failed: {res.get('error')}", reason='verify_fail')
             
        # Simulate App Launch
        
        # 1. GetConfig
        await self.client(GetConfigRequest())
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # 2. GetTopPeers (Cache warming)
        try:
            await self.client(GetTopPeersRequest(
                correspondents=True, bots_pm=True, bots_inline=True,
                phone_calls=True, forward_users=True, forward_chats=True,
                groups=True, channels=True, offset=0, limit=20, hash=0
            ))
        except: pass
        
        self.state = 'ACTIVE'
        self.last_activity = datetime.now()
        logger.info(f"[{self.account_id}] ✅ COLD START complete. State: ACTIVE")

    async def _perform_hot_start(self):
        logger.info(f"[{self.account_id}] 🔥 HOT START initiated...")
        await self.client(UpdateStatusRequest(offline=False))
        self.state = 'ACTIVE'
        self.last_activity = datetime.now()

    async def _lifecycle_monitor(self):
        logger.debug(f"[{self.account_id}] Monitor looper started")
        while not self.shutdown_event.is_set():
            try:
                if self.state == 'ACTIVE':
                    idle_sec = (datetime.now() - self.last_activity).total_seconds()
                    
                    if idle_sec > self.IDLE_TIMEOUT:
                        logger.info(f"[{self.account_id}] 💤 Auto-switching to IDLE (Activity: {int(idle_sec)}s ago)")
                        self.state = 'IDLE'
                        # Maybe set offline?
                        if self.client and self.client.is_connected():
                             await self.client(UpdateStatusRequest(offline=True))

                elif self.state == 'IDLE':
                    # Check max lifespan
                    pass
                
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"[{self.account_id}] Monitor Error: {e}")
                await asyncio.sleep(10)
