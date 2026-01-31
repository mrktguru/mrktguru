import logging
import json
import datetime
import hashlib
import threading
from models.warmup_log import WarmupLog
from utils.redis_logger import redis_client

logger = logging.getLogger(__name__)

# In-memory dedup cache for BaseNodeExecutor Redis publishing
_recent_log_messages = {}
_recent_log_messages_lock = threading.Lock()
_DEDUP_WINDOW_SECONDS = 2

class BaseNodeExecutor:
    """
    Base class for all node executors.
    Provides infrastructure for logging, config access, and real-time streaming.
    """
    def __init__(self, client, account_id, config, node_id=None):
        self.client = client
        self.account_id = account_id
        self.config = config or {}
        self.node_id = node_id
        
    async def execute(self):
        """
        Execute the node logic.
        Must be implemented by subclasses.
        Returns:
            dict: {'success': bool, 'message': str, 'error': str (optional)}
        """
        raise NotImplementedError
    
    def _is_duplicate_redis_message(self, message):
        """Check if this message was recently published for this account (thread-safe)"""
        global _recent_log_messages
        
        content_key = f"{self.account_id}:{message}"
        msg_hash = hashlib.md5(content_key.encode()).hexdigest()
        
        now = datetime.datetime.now().timestamp()
        
        with _recent_log_messages_lock:
            # Clean old entries (older than window)
            _recent_log_messages = {
                k: v for k, v in _recent_log_messages.items() 
                if now - v < _DEDUP_WINDOW_SECONDS
            }
            
            # Check if this is a duplicate
            if msg_hash in _recent_log_messages:
                return True
            
            # Record this message
            _recent_log_messages[msg_hash] = now
            return False
        
    def log(self, level, message, action=None):
        """
        Centralized logging: Console + DB + Redis Stream
        """
        # 1. System log (Console/Celery)
        log_msg = f"[{self.account_id}] {message}"
        lvl = level.lower()
        
        if lvl in ['error', 'critical']:
            logger.error(log_msg, extra={'no_redis': True})
        elif lvl == 'warning':
            logger.warning(log_msg, extra={'no_redis': True})
        else:
            logger.info(log_msg, extra={'no_redis': True})
            
        # 2. Database log (Persistent History) - always log to DB
        try:
            WarmupLog.log(self.account_id, level.upper(), message, action=action, node_id=self.node_id)
        except Exception as e:
            logger.error(f"[{self.account_id}] Failed to write to DB log: {e}")

        # 3. Redis Publish (For Live Terminal in Frontend)
        # Skip Redis publishing if this message was recently published (dedup)
        if self._is_duplicate_redis_message(message):
            return
            
        try:
            if redis_client:
                channel = f"logs:account:{self.account_id}"
                payload = json.dumps({
                    'timestamp': datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
                    'level': level.upper(),
                    'message': message,
                    'clean_message': message
                })
                # Publish to channel and save history (last 50 lines)
                redis_client.publish(channel, payload)
                redis_client.rpush(f"history:{channel}", payload)
                redis_client.ltrim(f"history:{channel}", -50, -1)
        except Exception as e:
            logger.error(f"[{self.account_id}] Failed to publish to Redis: {e}")
        
    def get_config(self, key, default=None):
        """Helper to get config value"""
        return self.config.get(key, default)
