
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
            print(f"RedisPubSubHandler: Processing record {record.msg}", flush=True)
            
            msg = self.format(record)
            
            # 1. Determine account_id
            # First check extra fields
            account_id = getattr(record, 'account_id', None)
            
            # If not found, look for pattern "[123]" in the message
            if not account_id:
                match = re.search(r'\[(\d+)\]', msg)
                if match:
                    account_id = match.group(1)

            # If ID found, publish to Redis
            if account_id:
                print(f"RedisPubSubHandler: Found account_id {account_id}, publishing...", flush=True)
                channel = f"logs:account:{account_id}"
                
                # Format payload
                log_payload = json.dumps({
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'level': record.levelname,
                    'message': msg, # Full message
                    'clean_message': msg.replace(f"[{account_id}]", "").strip() # Message without ID prefix
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
            print(f"RedisPubSubHandler Error: {e}", flush=True)
            self.handleError(record)

def setup_redis_logging():
    """Attaches Redis handler to the root logger"""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO) # Force INFO level
    
    # Avoid adding duplicate handlers
    if any(isinstance(h, RedisPubSubHandler) for h in root_logger.handlers):
        return

    redis_handler = RedisPubSubHandler()
    redis_handler.setLevel(logging.INFO) # Force INFO level
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    redis_handler.setFormatter(formatter)
    
    root_logger.addHandler(redis_handler)
    print("RedisPubSubHandler attached to root logger", flush=True)
