
import asyncio
import threading
import logging

logger = logging.getLogger(__name__)

class BackgroundLoop:
    """
    Manages a global background asyncio loop for the worker process.
    Ensures that persistent Telethon clients stay connected to the same loop
    across different Celery task executions.
    """
    _loop = None
    _thread = None
    _lock = threading.Lock()

    @classmethod
    def get_loop(cls):
        """Get or create the background loop"""
        with cls._lock:
            if cls._loop is None:
                cls._start_loop()
            return cls._loop

    @classmethod
    def _start_loop(cls):
        if cls._loop is not None:
            return
            
        logger.info("⚡ Starting Background AsyncIO Loop...")
        
        loop = asyncio.new_event_loop()
        # NOTE: We do NOT set global event loop here to avoid blocking main thread logic?
        # Actually it's fine for the background thread.
        
        cls._loop = loop
        
        def run_forever(l):
            asyncio.set_event_loop(l)
            try:
                l.run_forever()
            except Exception as e:
                logger.critical(f"Background Loop Crashed: {e}")
            
        cls._thread = threading.Thread(target=run_forever, args=(loop,), daemon=True)
        cls._thread.start()

    @classmethod
    def submit(cls, coro):
        """
        Submit a coroutine to the background loop and wait for result (blocking).
        Returns the return value of coroutine or raises exception.
        """
        loop = cls.get_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
