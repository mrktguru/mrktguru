
import logging
import redis
import json
import re
import hashlib
from datetime import datetime

# Initialize Redis
# decode_responses=True is important to get strings back
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

class RedisPubSubHandler(logging.Handler):
    """
    Handler that intercepts logs, extracts [account_id], and publishes to Redis.
    """
    
    def __init__(self):
        super().__init__()
        # In-memory dedup cache: hash -> timestamp
        self._recent_messages = {}
        self._dedup_window_seconds = 2  # Skip duplicate messages within this window
    
    def _is_duplicate(self, account_id, msg):
        """Check if this message was recently published for this account"""
        # Create a hash of account_id + message content
        content_key = f"{account_id}:{msg}"
        msg_hash = hashlib.md5(content_key.encode()).hexdigest()
        
        now = datetime.now().timestamp()
        
        # Clean old entries (older than window)
        self._recent_messages = {
            k: v for k, v in self._recent_messages.items() 
            if now - v < self._dedup_window_seconds
        }
        
        # Check if this is a duplicate
        if msg_hash in self._recent_messages:
            return True
        
        # Record this message
        self._recent_messages[msg_hash] = now
        return False
    
    def emit(self, record):
        try:
            # DEBUG PRINT
            # print(f"RedisPubSubHandler: Processing record {record.msg}", flush=True)
            
            msg = self.format(record)
            
            # 1. Determine account_id
            # First check extra fields
            account_id = getattr(record, 'account_id', None)
            
            # Skip if explicitly marked to ignore (e.g. handled by BaseNodeExecutor)
            if getattr(record, 'no_redis', False):
                return

            # If not found, look for pattern "[123]" in the message
            if not account_id:
                match = re.search(r'\[(\d+)\]', msg)
                if match:
                    account_id = match.group(1)

            # If ID found, publish to Redis
            if account_id:
                # Check for duplicate message within short time window
                if self._is_duplicate(account_id, record.getMessage()):
                    return
                
                # print(f"RedisPubSubHandler: Found account_id {account_id}, publishing...", flush=True)
                channel = f"logs:account:{account_id}"
                
                # Format payload
                log_payload = json.dumps({
                    'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
                    'level': record.levelname,
                    'message': msg, # Full message (with asctime/level)
                    'raw_message': record.getMessage() # Just the message text
                })
                
                # Publish to channel (for live listeners)
                redis_client.publish(channel, log_payload)
                
                # Save history (for new connections)
                # Keep last 100 lines
                history_key = f"history:{channel}"
                pipe = redis_client.pipeline()
                pipe.rpush(history_key, log_payload)
                pipe.ltrim(history_key, -100, -1) 
                pipe.expire(history_key, 86400)   # Expire after 24 hours of inactivity
                pipe.execute()
                
        except Exception as e:
            # print(f"RedisPubSubHandler Error: {e}", flush=True)
            self.handleError(record)

# Global flag to ensure handler is attached only once per process
_redis_handler_attached = False

def setup_redis_logging(target_logger=None):
    """Attaches Redis handler to the target logger or root, ensuring no duplicates"""
    global _redis_handler_attached
    
    if target_logger is None:
        target_logger = logging.getLogger()
    
    # Check if we already have the handler attached in this process
    if _redis_handler_attached:
        return
        
    target_logger.setLevel(logging.INFO) # Force INFO level
    
    # Remove any existing RedisPubSubHandler to avoid duplicates across reloads/reconfigs
    for h in list(target_logger.handlers):
        if isinstance(h, RedisPubSubHandler):
            target_logger.removeHandler(h)

    redis_handler = RedisPubSubHandler()
    redis_handler.setLevel(logging.INFO) # Force INFO level
    # Removed explicit formatter to avoid double timestamping in frontend
    # formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    # redis_handler.setFormatter(formatter)
    
    target_logger.addHandler(redis_handler)
    _redis_handler_attached = True
    print(f"RedisPubSubHandler attached to logger: {target_logger.name}", flush=True)
