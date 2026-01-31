import logging
import json
from datetime import datetime
from modules.nodes.registry import NODE_EXECUTORS
from models.warmup_log import WarmupLog
from utils.redis_logger import redis_client

logger = logging.getLogger(__name__)


def _log_execution_error(account_id, node_id, node_type, error):
    """Log node execution error to DB and Redis"""
    message = f"Node execution failed ({node_type}): {error}"
    
    # DB log
    try:
        WarmupLog.log(account_id, 'ERROR', message, action=f'{node_type}_exec_error', node_id=node_id)
    except Exception:
        pass
    
    # Redis log
    try:
        if redis_client:
            channel = f"logs:account:{account_id}"
            payload = json.dumps({
                'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
                'level': 'ERROR',
                'message': message,
                'clean_message': message
            })
            redis_client.publish(channel, payload)
            redis_client.rpush(f"history:{channel}", payload)
            redis_client.ltrim(f"history:{channel}", -50, -1)
    except Exception:
        pass


async def execute_node(client, node_type, account_id, config, node_id=None):
    """
    Execute a warmup node by type using the modular executor system.
    
    Args:
        client: Telethon client
        node_type: str, type of node (e.g. 'bio', 'subscribe')
        account_id: int
        config: dict, node configuration
        node_id: int, optional node ID for logging
        
    Returns:
        dict: {'success': bool, 'message': str, 'error': str}
    """
    executor_cls = NODE_EXECUTORS.get(node_type)
    
    if not executor_cls:
        return {'success': False, 'error': f'Unknown node type: {node_type}'}
    
    try:
        executor = executor_cls(client, account_id, config, node_id=node_id)
        return await executor.execute()
    except Exception as e:
        _log_execution_error(account_id, node_id, node_type, str(e))
        return {'success': False, 'error': str(e)}
