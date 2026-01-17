"""
Warmup Execution Utilities
Core functions for executing warmup actions with human-like behavior
"""
import asyncio
import random
import time
import logging
from telethon.tl.functions.account import UpdateStatusRequest
from models.warmup_log import WarmupLog

logger = logging.getLogger(__name__)


# ==================== PRESENCE EMULATION ====================

async def emulate_presence_start(client, account_id):
    """
    Set status to ONLINE before starting actions
    Simulates user opening the app
    """
    try:
        await client(UpdateStatusRequest(offline=False))
        logger.info(f"Account {account_id}: Status set to ONLINE")
        WarmupLog.log(account_id, 'info', 'Status set to ONLINE')
        return True
    except Exception as e:
        logger.error(f"Failed to set ONLINE status: {e}")
        return False


async def emulate_presence_end(client, account_id):
    """
    Set status to OFFLINE after completing actions
    Simulates user closing the app
    """
    try:
        await client(UpdateStatusRequest(offline=True))
        logger.info(f"Account {account_id}: Status set to OFFLINE")
        WarmupLog.log(account_id, 'info', 'Status set to OFFLINE')
        return True
    except Exception as e:
        logger.error(f"Failed to set OFFLINE status: {e}")
        return False


async def maintain_presence(client, account_id, duration_seconds):
    """
    Maintain ONLINE status during a session
    Periodically refreshes status every 2-3 minutes
    
    Args:
        client: Telethon client
        account_id: Account ID for logging
        duration_seconds: How long to maintain presence
    """
    start_time = time.time()
    
    try:
        while time.time() - start_time < duration_seconds:
            # Refresh ONLINE status
            await client(UpdateStatusRequest(offline=False))
            logger.debug(f"Account {account_id}: Refreshed ONLINE status")
            
            # Wait 2-3 minutes before next refresh
            await asyncio.sleep(random.uniform(120, 180))
    except asyncio.CancelledError:
        logger.info(f"Account {account_id}: Presence maintenance cancelled")
    except Exception as e:
        logger.error(f"Error maintaining presence: {e}")


# ==================== TYPING EMULATION ====================

async def emulate_typing(text, field_type='normal', account_id=None):
    """
    Emulate human typing with realistic delays and occasional typos
    
    Args:
        text: Text to type
        field_type: 'slow' (name/bio), 'normal' (search), 'fast' (messages)
        account_id: For logging
    
    Returns:
        str: The final typed text (may differ slightly due to typos)
    """
    # Typing speeds (milliseconds per character)
    speeds = {
        'slow': (150, 300),    # Thinking while typing (name, bio)
        'normal': (100, 200),  # Regular typing (search)
        'fast': (50, 100)      # Familiar typing (messages)
    }
    
    min_speed, max_speed = speeds.get(field_type, speeds['normal'])
    
    typed_text = ""
    typo_count = 0
    
    for i, char in enumerate(text):
        # 10% chance of typo (but not on first character)
        if i > 0 and random.random() < 0.1:
            # Type wrong character
            wrong_chars = 'qwertyuiopasdfghjklzxcvbnm'
            wrong_char = random.choice(wrong_chars)
            typed_text += wrong_char
            typo_count += 1
            
            # Delay for typing wrong char
            await asyncio.sleep(random.uniform(min_speed, max_speed) / 1000)
            
            # Pause - realize mistake
            await asyncio.sleep(random.uniform(200, 500) / 1000)
            
            # Backspace
            typed_text = typed_text[:-1]
            await asyncio.sleep(0.1)
        
        # Type correct character
        typed_text += char
        
        # Calculate delay
        delay = random.uniform(min_speed, max_speed) / 1000
        
        # Longer pause after spaces (thinking about next word)
        if char == ' ':
            delay *= random.uniform(1.5, 2.5)
        
        # Longer pause after punctuation
        if char in '.,!?':
            delay *= random.uniform(2.0, 3.0)
        
        await asyncio.sleep(delay)
    
    # Final pause before submission
    await asyncio.sleep(random.uniform(0.5, 1.5))
    
    if account_id and typo_count > 0:
        logger.debug(f"Account {account_id}: Typed '{text}' with {typo_count} typos")
    
    return typed_text


# ==================== ACTION EXECUTOR ====================

async def execute_warmup_action(client, account_id, action_func, estimated_duration=60, *args, **kwargs):
    """
    Execute a warmup action with full presence emulation
    
    Args:
        client: Telethon client
        account_id: Account ID
        action_func: Async function to execute
        estimated_duration: Estimated duration in seconds
        *args, **kwargs: Arguments for action_func
    
    Returns:
        Result from action_func
    """
    presence_task = None
    
    try:
        # 0. Ensure client is connected
        if not client.is_connected():
            logger.info(f"Account {account_id}: Connecting Telethon client...")
            await client.connect()
        
        # 1. Set status ONLINE
        await emulate_presence_start(client, account_id)
        
        # 2. Pause - "opening app"
        await asyncio.sleep(random.uniform(2, 5))
        
        # 3. Start background presence maintenance
        presence_task = asyncio.create_task(
            maintain_presence(client, account_id, estimated_duration)
        )
        
        # 4. Execute main action
        result = await action_func(client, account_id, *args, **kwargs)
        
        # 5. Stop presence maintenance
        if presence_task:
            presence_task.cancel()
            try:
                await presence_task
            except asyncio.CancelledError:
                pass
        
        # 6. Pause - "viewing result"
        await asyncio.sleep(random.uniform(3, 8))
        
        # 7. Scroll feed before going offline (realistic behavior)
        try:
            logger.info(f"Account {account_id}: Scrolling feed before going offline...")
            WarmupLog.log(account_id, 'info', 'Scrolling main feed', action='scroll_feed')
            
            # Get dialogs (chats list)
            dialogs = await client.get_dialogs(limit=random.randint(10, 20))
            await asyncio.sleep(random.uniform(1, 3))
            
            # Scroll through a few random chats
            for _ in range(random.randint(2, 4)):
                if dialogs:
                    random_dialog = random.choice(dialogs)
                    try:
                        # Fetch messages from random chat (simulate scrolling)
                        await client.get_messages(random_dialog, limit=random.randint(3, 10))
                        await asyncio.sleep(random.uniform(2, 5))
                    except:
                        pass  # Skip if error (e.g., restricted chat)
            
            logger.info(f"Account {account_id}: Feed scrolling completed")
            WarmupLog.log(account_id, 'info', 'Feed scrolling completed', action='scroll_complete')
        except Exception as scroll_err:
            logger.warning(f"Feed scrolling failed (non-critical): {scroll_err}")
        
        # 8. Random delay before going offline
        logger.info(f"Account {account_id}: Waiting before going offline...")
        await asyncio.sleep(random.uniform(5, 15))
        
        # 9. Set status OFFLINE
        logger.info(f"Account {account_id}: Setting status to OFFLINE...")
        await emulate_presence_end(client, account_id)
        
        logger.info(f"Account {account_id}: Warmup action completed successfully")
        return result
        
    except Exception as e:
        # Always set OFFLINE on error
        if presence_task:
            presence_task.cancel()
        
        await emulate_presence_end(client, account_id)
        
        logger.error(f"Error executing warmup action: {e}", exc_info=True)
        WarmupLog.log(account_id, 'error', f'Action failed: {str(e)}')
        
        raise


# ==================== TIMING UTILITIES ====================

def calculate_read_time(message):
    """
    Calculate realistic time to read a message
    
    Args:
        message: Telethon message object
    
    Returns:
        float: Seconds to read
    """
    if not message or not message.message:
        return random.uniform(1, 3)  # Empty message
    
    text_length = len(message.message)
    
    # Reading speed: ~20 characters per second
    read_time = text_length / 20
    
    # Minimum 2 seconds, maximum 15 seconds
    read_time = max(2, min(read_time, 15))
    
    # Add randomness ±20%
    read_time *= random.uniform(0.8, 1.2)
    
    return read_time


def random_pause(min_sec, max_sec):
    """
    Create a random pause within range
    
    Returns:
        Coroutine for asyncio.sleep()
    """
    return asyncio.sleep(random.uniform(min_sec, max_sec))

class WarmupExecutor:
    """
    Executor for warmup actions (Bio, Photo, Username, etc.)
    Handles Telethon connection and realistic behavior
    """
    
    def __init__(self):
        pass

    async def execute_immediate(self, account, node_type, config):
        """
        Execute a single node action immediately
        """
        from utils.telethon_helper import get_telethon_client
        
        client = None
        try:
            # Get Proxy
            from models.proxy import Proxy
            proxy = None
            if account.proxy_id:
                proxy_rec = Proxy.query.get(account.proxy_id)
                if proxy_rec:
                    proxy = proxy_rec.get_telethon_dict()
            
            # Create Client
            client = get_telethon_client(account.id, proxy)
            
            # Note: execute_warmup_action handles connection, but we need it here for dispatch
            # Actually, execute_warmup_action expects a connected client OR handles it?
            # Looking at execute_warmup_action: "if not client.is_connected(): await client.connect()"
            # So we can pass unconnected client.
            
            # Dispatch Action via execute_warmup_action for Safety
            if node_type == 'bio':
                return await execute_warmup_action(client, account.id, self._execute_bio, estimated_duration=30, config=config)
            elif node_type == 'username':
                return await execute_warmup_action(client, account.id, self._execute_username, estimated_duration=30, config=config)
            elif node_type == 'photo':
                return await execute_warmup_action(client, account.id, self._execute_photo, estimated_duration=45, config=config)
            elif node_type == 'send_message':
                return {'success': False, 'error': 'Message execution not yet implemented in immediate mode'}
            else:
                return {'success': False, 'error': f'Unknown node type: {node_type}'}
                
        except Exception as e:
            logger.error(f"Immediate execution failed: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            if client and client.is_connected():
                await client.disconnect()

    async def _execute_bio(self, client, account_id, config):
        from telethon.tl.functions.account import UpdateProfileRequest
        from models.account import Account
        from database import db

        new_bio = config.get('bio_text')
        if not new_bio:
            return {'success': False, 'error': 'No bio text provided'}
            
        # Emulate typing
        logger.info(f"Account {account_id}: Typing bio...")
        await emulate_typing(new_bio, field_type='slow', account_id=account_id)
            
        await client(UpdateProfileRequest(about=new_bio))
        
        # Update DB
        account = Account.query.get(account_id)
        if account:
            account.bio = new_bio
            db.session.commit()
        
        return {'success': True, 'message': 'Bio updated from node'}

    async def _execute_username(self, client, account_id, config):
        from telethon.tl.functions.account import UpdateUsernameRequest
        from models.account import Account
        from database import db
        
        username = config.get('username', '').replace('@', '')
        if not username:
            return {'success': False, 'error': 'No username provided'}
            
        # Emulate typing
        logger.info(f"Account {account_id}: Typing username...")
        await emulate_typing(username, field_type='normal', account_id=account_id)
            
        await client(UpdateUsernameRequest(username=username))
        
        # Update DB
        account = Account.query.get(account_id)
        if account:
            account.username = username
            db.session.commit()
        
        return {'success': True, 'message': 'Username updated'}

    async def _execute_photo(self, client, account_id, config):
        from telethon.tl.functions.photos import UploadProfilePhotoRequest
        from models.account import Account
        from database import db
        
        photo_path = config.get('photo_path')
        if not photo_path or not os.path.exists(photo_path):
            return {'success': False, 'error': 'Photo file not found'}
            
        # Emulate "selecting" photo delay
        await asyncio.sleep(random.uniform(2, 5))
            
        # Upload
        file = await client.upload_file(photo_path)
        await client(UploadProfilePhotoRequest(file=file))
        
        # Update DB
        account = Account.query.get(account_id)
        if account:
            account.photo_url = photo_path 
            db.session.commit()
        
        return {'success': True, 'message': 'Photo uploaded'}
