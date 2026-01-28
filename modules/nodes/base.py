import logging
from models.warmup_log import WarmupLog

logger = logging.getLogger(__name__)

class BaseNodeExecutor:
    """
    Base class for all node executors.
    Provides infrastructure for logging and config access.
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
        """Wrapper for WarmupLog"""
        # Echo to standard python logger for visibility in celery/terminal
        log_msg = f"[{self.account_id}] {message}"
        if level == 'error' or level == 'critical':
            logger.error(log_msg)
        elif level == 'warning':
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
            
        WarmupLog.log(self.account_id, level, message, action=action)
        
    def get_config(self, key, default=None):
        """Helper to get config value"""
        return self.config.get(key, default)
