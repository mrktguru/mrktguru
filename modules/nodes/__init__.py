import logging
from modules.nodes.registry import NODE_EXECUTORS

logger = logging.getLogger(__name__)

async def execute_node(client, node_type, account_id, config):
    """
    Execute a warmup node by type using the modular executor system.
    
    Args:
        client: Telethon client
        node_type: str, type of node (e.g. 'bio', 'subscribe')
        account_id: int
        config: dict, node configuration
        
    Returns:
        dict: {'success': bool, 'message': str, 'error': str}
    """
    executor_cls = NODE_EXECUTORS.get(node_type)
    
    if not executor_cls:
        return {'success': False, 'error': f'Unknown node type: {node_type}'}
    
    try:
        executor = executor_cls(client, account_id, config)
        return await executor.execute()
    except Exception as e:
        logger.error(f"Node execution failed ({node_type}): {e}")
        return {'success': False, 'error': str(e)}
