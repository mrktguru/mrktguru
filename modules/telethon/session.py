import asyncio
import logging
import random
import json
from datetime import datetime
from typing import Callable, Any

from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.help import GetConfigRequest
from telethon.tl.functions.contacts import GetTopPeersRequest
from telethon.tl.types import InputPeerEmpty

from modules.telethon.client import ClientFactory
from modules.telethon.verification import verify_session
from models.warmup_log import WarmupLog
from utils.redis_logger import redis_client
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
    def __init__(self, account_id: int, node_id: int = None):
        self.account_id = account_id
        self.node_id = node_id
        self.client = None
        self.state = 'OFFLINE'
        self.last_activity = None
        
        self.monitoring_task = None
        self._shutdown_event = None
        self._execution_lock = None
        
        # State config
        self.IDLE_TIMEOUT = 180  # 3 minutes
        self.MAX_LIFESPAN = 900  # 15 minutes

    def _log(self, level: str, message: str, action: str = None):
        """
        Unified logging: Console + DB + Redis (for Live UI)
        """
        # 1. Console log
        log_msg = f"[{self.account_id}] {message}"
        if level in ['error', 'critical']:
            logger.error(log_msg)
        elif level == 'warning':
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
        
        # 2. DB log
        try:
            from flask import has_app_context
            from app import app
            
            def do_log():
                WarmupLog.log(
                    self.account_id, 
                    level.upper(), 
                    message, 
                    action=action or f'orch_{level}',
                    node_id=self.node_id
                )
            
            if has_app_context():
                do_log()
            else:
                with app.app_context():
                    do_log()
        except Exception as e:
            logger.debug(f"[{self.account_id}] DB log failed: {e}")
        
        # 3. Redis publish (Live UI)
        try:
            if redis_client:
                channel = f"logs:account:{self.account_id}"
                payload = json.dumps({
                    'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
                    'level': level.upper(),
                    'message': message,
                    'clean_message': message
                })
                redis_client.publish(channel, payload)
                redis_client.rpush(f"history:{channel}", payload)
                redis_client.ltrim(f"history:{channel}", -50, -1)
        except Exception:
            pass

    @property
    def shutdown_event(self) -> asyncio.Event:
        if self._shutdown_event is None:
            self._shutdown_event = asyncio.Event()
        return self._shutdown_event

    @property
    def execution_lock(self) -> asyncio.Lock:
        if self._execution_lock is None:
            self._execution_lock = asyncio.Lock()
        return self._execution_lock

    async def start_monitoring(self):
        if not self.monitoring_task or self.monitoring_task.done():
            self.shutdown_event.clear()
            self.monitoring_task = asyncio.create_task(self._lifecycle_monitor())
            self._log('info', '🟢 Session Monitor started', action='orch_monitor_start')


    async def execute(self, task_func: Callable, *args, **kwargs) -> Any:
        async with self.execution_lock:
            try:
                await self._ensure_ready_state()
                self.last_activity = datetime.now()
                return await task_func(self.client, *args, **kwargs)
                
            except SessionDeathError:
                await self._handle_ban_logic()
                raise
            except Exception as e:
                self._log('error', f"Execution error: {e}", action='orch_exec_error')
                raise

    async def _handle_ban_logic(self):
        self._log('critical', '☠️ Handling Session Death...', action='orch_session_death')
        await self.stop()

    async def stop(self):
        # 1. Signal shutdown safely
        try:
            self.shutdown_event.set()
        except RuntimeError:
            # Loop mismatch on event is rare but possible if created in different loop
            pass

        # 2. Handle monitoring task safely
        if self.monitoring_task:
            try:
                # Loop safety check
                # If we are in the same loop, we can await. If not, we just cancel.
                current_loop = asyncio.get_running_loop()
                task_loop = getattr(self.monitoring_task, 'get_loop', lambda: getattr(self.monitoring_task, '_loop', None))()
                
                if task_loop is current_loop:
                    if not self.monitoring_task.done():
                        self.monitoring_task.cancel()
                        try:
                            # Wait briefly to let it clean up
                            await asyncio.wait_for(self.monitoring_task, timeout=0.1)
                        except (asyncio.TimeoutError, asyncio.CancelledError):
                            pass
                else:
                    # Different loop! Just cancel and move on.
                    # Awaiting here causes "Future attached to a different loop"
                    if not self.monitoring_task.done():
                        # We can call cancel() from another loop?
                        # It's thread-safe in recent Python updates, but loop-safe?
                        # Usually call_soon_threadsafe is better
                        task_loop.call_soon_threadsafe(self.monitoring_task.cancel)
            except Exception as e:
                logger.warning(f"[{self.account_id}] Monitoring stop warning: {e}")
            finally:
                self.monitoring_task = None
        
        if self.client:
            if self.client.is_connected():
                try:
                    self._log('info', '🔌 Disconnecting from Telegram...', action='orch_disconnect')
                    await self.client.disconnect()
                except Exception as e:
                     logger.warning(f"[{self.account_id}] Disconnect warning: {e}")
            self.client = None
            
        self.state = 'OFFLINE'
        self._log('info', '🔴 Session Stopped', action='orch_stopped')

    async def _ensure_ready_state(self):
        if self.state == 'OFFLINE' or not self.client or not self.client.is_connected():
            await self._perform_cold_start()
        elif self.state == 'IDLE':
            await self._perform_hot_start()
            
        if not await self.client.is_user_authorized():
            raise SessionDeathError("User not authorized", reason='auth_lost')

    async def _perform_cold_start(self):
        self._log('info', '🧊 COLD START initiated...', action='orch_cold_start')
        
        # Get proxy info for logging
        from flask import has_app_context
        from app import app
        proxy_info = "No proxy"
        try:
            def get_proxy_info():
                from models.account import Account
                from models.proxy_network import ProxyNetwork
                from urllib.parse import urlparse
                
                account = Account.query.get(self.account_id)
                if account and account.proxy_network_id:
                    pn = ProxyNetwork.query.get(account.proxy_network_id)
                    if pn:
                        port = account.assigned_port or pn.start_port
                        # Parse host from base_url (format: socks5://user:pass@host)
                        try:
                            parsed = urlparse(pn.base_url)
                            host = parsed.hostname or parsed.netloc.split('@')[-1]
                        except:
                            host = "proxy"
                        return f"{host}:{port} ({pn.name})"
                return "No proxy"
            
            if has_app_context():
                proxy_info = get_proxy_info()
            else:
                with app.app_context():
                    proxy_info = get_proxy_info()
        except Exception:
            pass
        
        self._log('info', f'🔌 Connecting via proxy: {proxy_info}', action='orch_proxy_connect')
        
        loop = asyncio.get_running_loop()
        self.client = ClientFactory.create_client(self.account_id, loop=loop)
        
        self._log('info', '📡 Establishing connection to Telegram...', action='orch_connecting')
        await self.client.connect()
        self._log('success', '✅ Connected to Telegram', action='orch_connected')
        
        if not await self.client.is_user_authorized():
             self._log('warning', 'Not authorized on cold start', action='orch_auth_fail')
             await self.client.disconnect()
             raise SessionDeathError("Not authorized", reason='auth_fail')
        
        self._log('info', '🔐 Verifying session...', action='orch_verify_start')
        res = await verify_session(self.account_id, client=self.client)
        if not res['success']:
             self._log('error', f"Verification failed: {res.get('error')}", action='orch_verify_fail')
             await self.client.disconnect()
             raise SessionDeathError(f"Verification failed: {res.get('error')}", reason='verify_fail')
        self._log('success', '✅ Session verified', action='orch_verified')
             
        # Simulate App Launch
        self._log('info', '📱 Simulating app launch (GetConfig)...', action='orch_app_init')
        
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
        self._log('success', '✅ COLD START complete. Session ACTIVE', action='orch_ready')

    async def _perform_hot_start(self):
        self._log('info', '🔥 HOT START - Reusing cached session', action='orch_hot_start')
        await self.client(UpdateStatusRequest(offline=False))
        self.state = 'ACTIVE'
        self.last_activity = datetime.now()
        self._log('success', '✅ Session resumed', action='orch_resumed')

    async def _lifecycle_monitor(self):
        logger.debug(f"[{self.account_id}] Monitor looper started")
        while not self.shutdown_event.is_set():
            try:
                if self.state == 'ACTIVE':
                    # Safety: If a task is currently executing, do NOT go IDLE
                    if self.execution_lock.locked():
                        self.last_activity = datetime.now() # Heartbeat
                        await asyncio.sleep(10)
                        continue


                    idle_sec = (datetime.now() - self.last_activity).total_seconds()
                    
                    if idle_sec > self.IDLE_TIMEOUT:
                        self._log('info', f'💤 Auto-switching to IDLE (idle {int(idle_sec)}s)', action='orch_idle')
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
