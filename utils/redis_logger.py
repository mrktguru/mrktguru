
import logging
import redis
import json
import re
from datetime import datetime

# Initialize Redis
# decode_responses=True is important to get strings back
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

class RedisPubSubHandler(logging.Handler):
    """
    Handler that intercepts logs, extracts [account_id], and publishes to Redis.
    """
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

def setup_redis_logging(target_logger=None):
    """Attaches Redis handler to the target logger or root, ensuring no duplicates"""
    if target_logger is None:
        target_logger = logging.getLogger()
        
    target_logger.setLevel(logging.INFO) # Force INFO level
    
    # Remove any existing RedisPubSubHandler to avoid duplicates across reloads/reconfigs
    for h in list(target_logger.handlers):
        if h.__class__.__name__ == 'RedisPubSubHandler':
            target_logger.removeHandler(h)

    redis_handler = RedisPubSubHandler()
    redis_handler.setLevel(logging.INFO) # Force INFO level
    # We use a formatter for the 'message' field, but 'raw_message' remains clean
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    redis_handler.setFormatter(formatter)
    
    target_logger.addHandler(redis_handler)
    print(f"RedisPubSubHandler (re)attached to logger: {target_logger.name}", flush=True)
