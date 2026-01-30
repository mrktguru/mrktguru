import asyncio
import random
import logging
from telethon.tl.functions.messages import ReadHistoryRequest

logger = logging.getLogger(__name__)

async def task_check_spamblock(client):
    """
    Task: Interactive Spamblock Check
    Simulates: Searching for SpamBot, opening chat, sending /start, reading reply.
    """
    # Import locally to avoid circular dependencies if any, 
    # though ideally the logic should be moved here fully.
    # For now, we will use the improved logic we just wrote in utils/human_spamblock.py
    # But since the orchestrator passes 'client', we need to adapt human_spamblock to accept an existing client.
    
    # OPTION 1: Refactor human_spamblock to accept client. 
    # OPTION 2: Re-implement logic here.
    
    # Let's re-implement the core "interaction" part here, as the Orchestrator handles the "login/sync" part.
    # We assume 'client' is already connected and synced (ACTIVE state).
    
    from telethon.tl.functions.contacts import ResolveUsernameRequest, UnblockRequest
    from telethon.tl.functions.messages import SetTypingRequest
    from telethon.tl.types import SendMessageTypingAction
    
    log_messages = []
    def log(msg, level='info'):
        log_messages.append(msg)
        if level == 'info': logger.info(msg)
        elif level == 'error': logger.error(msg)
        else: logger.warning(msg)

    try:
        # === 4. SEARCH (Assume we are already in Main View) ===
        log("🔍 [Task] Clicking Search bar...")
        await asyncio.sleep(abs(random.gauss(0.8, 0.3))) # Click delay

        # === 5. TYPE "SpamBot" ===
        target_username = "SpamBot"
        log(f"⌨️ [Task] Typing '@{target_username}'...")
        await asyncio.sleep(abs(random.gauss(1.5, 0.5))) # Type delay
        
        try:
            resolve_result = await client(ResolveUsernameRequest(target_username))
            spambot_peer = resolve_result.peer
            spambot_entity = resolve_result.users[0]
        except Exception as e:
            msg = f"❌ Could not resolve SpamBot: {e}"
            log(msg, 'error')
            return {'status': 'error', 'log': log_messages, 'error': msg}

        # === 6. OPEN CHAT ===
        log("🖱️ [Task] Found bot. Opening chat...")
        await asyncio.sleep(abs(random.gauss(0.8, 0.3)))
        
        try:
            await client(UnblockRequest(spambot_entity))
        except:
            pass

        # === 7. INTERACTION ===
        log("💬 [Task] Sending /start command...")
        
        try:
            await client(SetTypingRequest(spambot_peer, action=SendMessageTypingAction()))
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await client.send_message(spambot_entity, '/start')
        except Exception as e:
            if "FROZEN" in str(e) or "PEER_FLOOD" in str(e) or "USER_RESTRICTED" in str(e):
                log(f"❄️ ACCOUNT FROZEN on SendMessage: {e}", 'error')
                return {'status': 'restricted', 'reason': 'Hard Freeze (Send Failed)', 'is_frozen': True, 'log': log_messages}
            log(f"❌ Send failed: {e}", 'error')
            return {'status': 'error', 'log': log_messages, 'is_frozen': False, 'error': str(e)}

        # === WAIT FOR REPLY ===
        log("⏳ Waiting for bot reply...")
        response = None
        for _ in range(10): 
            await asyncio.sleep(1)
            history = await client.get_messages(spambot_entity, limit=1)
            if history and not history[0].out: 
                response = history[0]
                break
        
        if response:
            log(f"🤖 [Result] Bot Replied: {response.text[:50]}...")
            
            # Read Delay
            await asyncio.sleep(abs(random.gauss(3.0, 1.0)))
            
            try:
                await client(ReadHistoryRequest(peer=spambot_entity, max_id=response.id))
            except Exception as e:
                if "FROZEN" in str(e):
                    log("❄️ ACCOUNT FROZEN on ReadHistory", 'error')
                    return {'status': 'restricted', 'reason': 'Hard Freeze (Ack Failed)', 'is_frozen': True, 'log': log_messages}

            # Analysis
            clean_markers = ["Good news", "Ваш аккаунт свободен", "no limits", "нет ограничений", "хорошие новости"]
            if any(m in response.text for m in clean_markers):
                log("✅ ACCOUNT IS GREEN (CLEAN)")
                return {'status': 'clean', 'is_frozen': False, 'log': log_messages}
            else:
                log(f"⚠️ ACCOUNT IS RESTRICTED (Spamblock). Bot said: {response.text[:50]}", 'warning')
                return {'status': 'restricted', 'reason': response.text, 'is_frozen': True, 'log': log_messages}
        else:
            log("⚠️ Bot silent (Timeout).", 'warning')
            return {'status': 'unknown', 'log': log_messages}

    except Exception as e:
        log(f"❌ Task Error: {e}", 'error')
        raise e

async def task_passive_scroll(client):
    """
    Task: Passive Feed Scroll
    Simulates: User scrolling through their chat list or a channel.
    """
    logger.info("📜 [Task] Starting passive scroll...")
    # Simulate reading random chats from dialog list
    dialogs = await client.get_dialogs(limit=5)
    
    if not dialogs:
        logger.info("📜 No dialogs to scroll.")
        return

    # Pick a random chat to "view"
    target = random.choice(dialogs)
    logger.info(f"👀 Viewing chat: {target.name}")
    
    # Simulate reading time
    duration = random.uniform(5, 15)
    await asyncio.sleep(duration)
    
    logger.info("📜 Scroll task complete.")

async def task_read_news(client, channel_username: str):
    """
    Task: Read Specific Channel
    Simulates: Opening a channel and reading latest posts.
    """
    logger.info(f"📰 [Task] Reading news from {channel_username}...")
    try:
        entity = await client.get_entity(channel_username)
        messages = await client.get_messages(entity, limit=3)
        
        for msg in messages:
            # Simulate reading time per post
            await asyncio.sleep(random.uniform(2, 5))
            
            # Mark as read
            await client(ReadHistoryRequest(peer=entity, max_id=msg.id))
            
        logger.info(f"📰 Done reading {channel_username}.")
        
    except Exception as e:
        logger.error(f"❌ Failed to read news: {e}")
