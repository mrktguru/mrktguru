import logging
import json
import datetime
from models.warmup_log import WarmupLog
from utils.redis_logger import redis_client

logger = logging.getLogger(__name__)

class BaseNodeExecutor:
    """
    Base class for all node executors.
    Provides infrastructure for logging, config access, and real-time streaming.
    """
    def __init__(self, client, account_id, config):
        self.client = client
        self.account_id = account_id
        self.config = config or {}
        
    async def execute(self):
        """
        Execute the node logic.
        Must be implemented by subclasses.
        Returns:
            dict: {'success': bool, 'message': str, 'error': str (optional)}
        """
        raise NotImplementedError
        
    def log(self, level, message, action=None):
        """
        Centralized logging: Console + DB + Redis Stream
        """
        # 1. System log (Console/Celery)
        log_msg = f"[{self.account_id}] {message}"
        lvl = level.lower()
        
        if lvl in ['error', 'critical']:
            logger.error(log_msg)
        elif lvl == 'warning':
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
            
        # 2. Database log (Persistent History)
        try:
            WarmupLog.log(self.account_id, level.upper(), message, action=action)
        except Exception as e:
            logger.error(f"[{self.account_id}] Failed to write to DB log: {e}")

        # 3. Redis Publish (For Live Terminal in Frontend)
        try:
            if redis_client:
                channel = f"logs:account:{self.account_id}"
                payload = json.dumps({
                    'timestamp': datetime.datetime.now().strftime('%H:%M:%S'),
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
