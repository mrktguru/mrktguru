import logging
import asyncio
from telethon.tl.functions.channels import JoinChannelRequest

logger = logging.getLogger(__name__)

async def task_join_channel(client, channel_username, notes=None):
    """
    Task: Join a Channel/Group by username/link.
    """
    logger.info(f"⚡ [Task] Joining channel: {channel_username}...")
    
    try:
        # Get channel entity - try different formats
        try:
            # Try as @username
            entity = await client.get_entity(f"@{channel_username}")
        except:
            try:
                # Try without @
                entity = await client.get_entity(channel_username)
            except:
                # Try as t.me link
                entity = await client.get_entity(f"https://t.me/{channel_username}")
        
        # Try to join
        try:
            await client(JoinChannelRequest(entity))
            return {'success': True, 'status': 'active', 'message': f"Successfully joined @{channel_username}"}
        except Exception as join_err:
            # Check if already member
            try:
                me = await client.get_me()
                participants = await client.get_participants(entity, limit=100)
                if any(p.id == me.id for p in participants):
                    return {'success': True, 'status': 'active', 'message': f"Already a member of @{channel_username}"}
                else:
                    return {'success': False, 'status': 'failed', 'message': f"Could not join: {str(join_err)}"}
            except Exception as check_err:
                 return {'success': False, 'status': 'failed', 'message': f"Could not verify membership: {str(check_err)}"}
                
    except Exception as e:
        logger.error(f"❌ Join channel failed: {e}")
        return {'success': False, 'status': 'failed', 'message': str(e)}

async def task_search_channels(client, query):
    """
    Task: Search for channels by query.
    """
    from telethon.tl.functions.contacts import SearchRequest
    
    logger.info(f"⚡ [Task] Searching channels: {query}...")
    try:
        result = await client(SearchRequest(q=query, limit=10))
        channels = []
        for chat in result.chats:
            if hasattr(chat, 'username') and chat.username:
                channels.append({
                    'id': chat.id,
                    'username': chat.username,
                    'title': chat.title,
                    'participants_count': getattr(chat, 'participants_count', 0)
                })
        return {'success': True, 'results': channels}
    except Exception as e:
        logger.error(f"❌ Search channels failed: {e}")
        return {'success': False, 'error': str(e)}
