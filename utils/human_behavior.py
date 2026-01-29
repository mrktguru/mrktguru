import asyncio
import random
import logging
from telethon import functions, errors

logger = logging.getLogger(__name__)

class HumanBehavior:
    """
    Simulates realistic human behavior for Telegram actions.
    Includes:
    - Smart link processing (Direct vs Search)
    - Typo simulation
    - "Paste vs Typing" logic
    - Scrolling and media viewing
    - Misclick simulation
    """

    def __init__(self, client, account_id=None):
        self.client = client
        self.account_id = account_id
        self.log_prefix = f"[{account_id}] " if account_id else ""

    async def process_mixed_links(self, config):
        """
        Main entry point. Processes a mixed list of links and usernames.
        """
        links_text = config.get('links', '')
        lines = [line.strip() for line in links_text.split('\n') if line.strip()]
        
        if not lines:
            logger.warning(f"{self.log_prefix}No links provided for processing")
            return

        # Shuffle execution order to avoid robotic patterns
        random.shuffle(lines)
        logger.info(f"{self.log_prefix}Processing {len(lines)} items with Smart Human Logic")

        for item in lines:
            try:
                # === SCENARIO 1: DIRECT LINK (BROWSER MODE) ===
                if 't.me/' in item or 'telegram.me/' in item:
                    await self._simulate_browser_click(item)

                # === SCENARIO 2: SEARCH (SEARCH & TYPING MODE) ===
                else:
                    await self._simulate_human_search(item)
                
                # Pause between channels (Human attention span)
                pause = random.uniform(5, 15)
                logger.info(f"{self.log_prefix}☕ Taking a break for {pause:.1f}s...")
                await asyncio.sleep(pause)

            except Exception as e:
                logger.error(f"{self.log_prefix}Error processing item '{item}': {e}")
                continue
        
        logger.info(f"{self.log_prefix}✅ All {len(lines)} items processed with Smart Human Logic")

    async def _simulate_browser_click(self, link):
        """
        Simulates clicking a link from an external source (Browser).
        Uses CheckChatInvite or ResolveUsername directly.
        """
        logger.info(f"{self.log_prefix}🔗 Simulating Browser Click: {link}")
        
        # 1. Invite Link (t.me/+AbCd...)
        if '+' in link or 'joinchat' in link:
            try:
                # Extract hash
                hash_arg = link.split('+')[-1] if '+' in link else link.split('joinchat/')[-1]
                hash_arg = hash_arg.replace('/', '').strip()
                
                # CheckChatInvite peeks at the chat without joining
                invite_info = await self.client(functions.messages.CheckChatInviteRequest(hash=hash_arg))
                
                logger.info(f"{self.log_prefix}   -> Viewed invite for: {getattr(invite_info, 'title', 'Unknown')}")
                await asyncio.sleep(random.uniform(2, 5)) # "Thinking" time
                return 

            except errors.InviteHashExpiredError:
                logger.warning(f"{self.log_prefix}   -> Link expired")
                return
            except Exception as e:
                logger.error(f"{self.log_prefix}   -> Failed to check invite: {e}")
                return

        # 2. Public Link (t.me/username)
        # Clean up link to get username
        username = link.split('t.me/')[-1].split('/')[0].split('?')[0]
        
        try:
            # ResolveUsername is a direct API call, analogous to opening a link
            entity = await self.client.get_entity(username)
            
            # Enter channel content view
            await self._view_channel_content(entity)
            
        except Exception as e:
            logger.error(f"{self.log_prefix}   -> Failed to resolve public link: {e}")

    async def _simulate_human_search(self, query):
        """
        Simulates manual typing in Global Search and clicking a result.
        """
        clean_query = query.replace('@', '') # Typing usually omits @ in search
        logger.info(f"{self.log_prefix}🔍 Simulating Search: '{clean_query}'")

        # 1. Focus Delay
        await asyncio.sleep(random.uniform(1.0, 3.0))

        # 2. Paste vs Typing Logic
        if len(clean_query) > 12:
            logger.info(f"{self.log_prefix}   -> Long query, simulating CTRL+V")
            await asyncio.sleep(random.uniform(0.5, 1.0)) # Ctrl+V pause
        else:
            await self._human_typing(clean_query)
        
        # 3. Final Search Request
        try:
            results = await self.client(functions.contacts.SearchRequest(
                q=clean_query,
                limit=5
            ))

            if not results.chats and not results.users:
                logger.info(f"{self.log_prefix}   -> Nothing found for '{clean_query}'")
                return

            # 4. Result Selection (with Misclick chance)
            # Combine chats and users, prioritizing chats usually
            all_results = results.chats + results.users
            if not all_results:
                return
            
            target_idx = 0 
            
            # MISCLICK SCENARIO (10% chance)
            if len(all_results) > 1 and random.random() < 0.1:
                wrong_target = all_results[1]
                logger.info(f"{self.log_prefix}   ⚠️ Misclick! Opened wrong channel: {getattr(wrong_target, 'title', 'Unknown')}")
                
                await self._view_channel_content(wrong_target, short_visit=True, origin='SEARCH')
                
                logger.info(f"{self.log_prefix}   🔙 Back to search results...")
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                target_idx = 0 # Correct target
            
            real_target = all_results[target_idx]
            title = getattr(real_target, 'title', getattr(real_target, 'username', 'Unknown'))
            logger.info(f"{self.log_prefix}   -> Clicked result: {title}")
            
            await self._view_channel_content(real_target, origin='SEARCH')

        except Exception as e:
            logger.error(f"{self.log_prefix}Search failed: {e}")

    async def _human_typing(self, text):
        """Simulates typing with realistic speed and occasional typos."""
        nearby_keys = {
            'a': 'qwsz', 'b': 'vghn', 'c': 'xdfv', 'd': 'serfc', 'e': 'rdsw',
            'f': 'drtgv', 'g': 'ftyhb', 'h': 'gyujn', 'i': 'ujko', 'j': 'hunik',
            'k': 'jilm', 'l': 'kop', 'm': 'njk', 'n': 'bhjm', 'o': 'iklp',
            'p': 'ol', 'q': 'wa', 'r': 'edft', 's': 'awzedx', 't': 'rfgy',
            'u': 'yhji', 'v': 'cfgb', 'w': 'qase', 'x': 'zsdc', 'y': 'tghu', 'z': 'asx'
        }

        typed_text = ""
        for char in text:
            # 2% chance for massive typo
            if char.lower() in nearby_keys and random.random() < 0.02:
                typo = random.choice(nearby_keys[char.lower()])
                # Press wrong key
                await asyncio.sleep(random.uniform(0.1, 0.3))
                
                # Realize mistake
                await asyncio.sleep(random.uniform(0.3, 0.8))
                
                # Backspace
                await asyncio.sleep(random.uniform(0.1, 0.2))
                
                # Now correct key will be pressed in next main loop iteration...
                # Actually we need to press it now or let the loop continue?
                # Let's simulate just the delay of correction here.
            
            # Press correct key
            await asyncio.sleep(random.uniform(0.08, 0.35))
            typed_text += char

    async def _view_channel_content(self, entity, short_visit=False, origin='LINK'):
        """
        Общая логика просмотра: скроллинг, чтение.
        Использует client.get_messages вместо сырых запросов.
        """
        try:
            from telethon.tl.types import Channel, Chat
            from models.channel_candidate import ChannelCandidate
            from database import db
            from datetime import datetime
            
            # 0. Save as discovered channel
            await self._save_discovered_channel(entity, origin)

            title = getattr(entity, 'title', getattr(entity, 'username', 'Chat'))
            logger.info(f"{self.log_prefix}   👀 Viewing content in: {title}")

            # 1. Получаем последние сообщения (High-level API)
            # Это замена сломанному GetHistory
            limit = 2 if short_visit else random.randint(5, 8)
            messages = await self.client.get_messages(entity, limit=limit)
            
            if not messages:
                logger.info(f"{self.log_prefix}   -> Channel is empty")
                return

            if short_visit:
                 # Minimal interaction for short visit
                 pass

            # 2. Имитация чтения (скроллинг)
            # Читаем сверху вниз (от более старых к новым в этой выборке)
            # Если short_visit - читаем меньше
            msgs_to_read = messages[:3] if not short_visit else messages[:1]
            
            for msg in reversed(msgs_to_read): 
                text = getattr(msg, 'text', '') or getattr(msg, 'message', '') or ''
                if text:
                    # Скорость чтения: ~15 символов в секунду + база 1 сек
                    read_time = (len(text) / 15) + 1
                    read_time = min(read_time, 8.0) # Не залипаем дольше 8 сек на посте
                    
                    await asyncio.sleep(read_time)
                
                # Шанс развернуть медиа
                if getattr(msg, 'media', None) and random.random() < 0.15:
                    logger.info(f"{self.log_prefix}   🖼️ Maximized photo/video view")
                    await asyncio.sleep(random.uniform(2, 5))

            if short_visit:
                return

            # 3. СКРОЛЛ ВВЕРХ (Context Check) — Шанс 30%
            if len(messages) > 0 and random.random() < 0.3:
                logger.info(f"{self.log_prefix}   ⬆️ Scrolling up to check context...")
                last_id = messages[-1].id # ID самого старого из загруженных
                
                # Подгружаем историю ДО этого сообщения
                older_msgs = await self.client.get_messages(
                    entity, 
                    limit=3, 
                    offset_id=last_id
                )
                await asyncio.sleep(random.uniform(3, 6))
                logger.info(f"{self.log_prefix}   ⬇️ Scrolling back to recent...")
                await asyncio.sleep(random.uniform(2, 4))

        except Exception as e:
            logger.error(f"{self.log_prefix}   ⚠️ Error viewing content: {e}")

    async def _save_discovered_channel(self, entity, origin='LINK'):
        """Persistence logic: save or update discovered channel candidate"""
        try:
            from telethon.tl.types import Channel, Chat
            from models.channel_candidate import ChannelCandidate
            from database import db
            from datetime import datetime
            
            if not isinstance(entity, (Channel, Chat)):
                return

            peer_id = entity.id
            access_hash = getattr(entity, 'access_hash', 0)
            username = getattr(entity, 'username', None)
            title = getattr(entity, 'title', 'Unknown')
            
            type_str = 'CHANNEL' if isinstance(entity, Channel) else 'MEGAGROUP'
            
            # Use app context if not present (usually worker has it)
            # Find existing
            candidate = ChannelCandidate.query.filter_by(
                account_id=self.account_id, 
                peer_id=peer_id
            ).first()
            
            if not candidate:
                candidate = ChannelCandidate(
                    account_id=self.account_id,
                    peer_id=peer_id,
                    access_hash=access_hash,
                    origin=origin
                )
                db.session.add(candidate)
                logger.info(f"{self.log_prefix}   ✨ New channel discovered: {title}")
            
            # Update fields
            candidate.username = username
            candidate.title = title
            candidate.type = type_str
            candidate.last_visit_ts = datetime.utcnow()
            candidate.status = 'VISITED'
            
            # Extract participants count if available
            # Note: entity.participants_count might not be populated in all GetDialogs/GetFullChannel contexts
            # but we try our best.
            if hasattr(entity, 'participants_count') and entity.participants_count:
                candidate.participants_count = entity.participants_count
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"{self.log_prefix}   ❌ Failed to save discovered channel: {e}")
            # Don't raise, persistence failure shouldn't kill the worker

    async def join_channel_humanly(self, entity, mute_notifications=True):
        """
        Executes the complex human behavior of joining a channel:
        1. View content (scroll/read).
        2. Random pause (decision making).
        3. Join action.
        4. Post-join behavior (Muting).
        
        Returns:
            str: 'JOINED', 'PENDING_APPROVAL', 'ALREADY_PARTICIPANT', 'REJECTED'
        """
        from telethon.tl.functions.account import UpdateNotifySettingsRequest
        from telethon.tl.functions.channels import JoinChannelRequest
        from telethon.tl.types import InputPeerNotifySettings
        from telethon import functions
        from telethon.errors import UserAlreadyParticipantError, LinkNotModifiedError
        
        # 1. PRE-JOIN INTERACTION (Look before you leap)
        # Мы используем уже существующую логику просмотра
        # Это создает "глазик" на постах и имитирует интерес
        await self._view_channel_content(entity, short_visit=False, origin='SUBSCRIBE_NODE')

        # 2. DECISION PAUSE
        await self.random_sleep(2.0, 5.0, reason="Thinking about joining")

        # 3. JOIN ACTION
        result_status = 'JOINED'
        try:
            # Пытаемся вступить
            updates = await self.client(JoinChannelRequest(channel=entity))
            
            # Если updates пустой, иногда это Pending, но не всегда.
            if not getattr(updates, 'chats', None):
                pass 

        except UserAlreadyParticipantError:
            logger.info(f"{self.log_prefix}   ℹ️ Already a participant")
            result_status = 'ALREADY_PARTICIPANT'
        except Exception as e:
            # Если ошибка про "Invites" (заявка)
            err_str = str(e).lower()
            if "invite request sent" in err_str or "pending" in err_str:
                logger.info(f"{self.log_prefix}   ⏳ Join Request sent (Pending Approval)")
                return 'PENDING_APPROVAL'
            raise e 

        # 4. POST-JOIN BEHAVIOR (MUTE)
        if mute_notifications and result_status == 'JOINED':
            if random.random() < 0.8:
                await self.random_sleep(1.0, 3.0, reason="Muting notifications")
                try:
                    await self.client(UpdateNotifySettingsRequest(
                        peer=entity,
                        settings=InputPeerNotifySettings(mute_until=2147483647) # Forever
                    ))
                    logger.info(f"{self.log_prefix}   🔕 Notifications muted")
                except Exception as e:
                    logger.warning(f"{self.log_prefix}   ⚠️ Failed to mute: {e}")

        return result_status
    
    # Helper wrapper for internal use
    async def random_sleep(self, min_s, max_s, reason=None):
        duration = random.uniform(min_s, max_s)
        msg = f"☕ Waiting {duration:.1f}s..."
        if reason: msg += f" ({reason})"
        logger.info(f"{self.log_prefix}{msg}")
        await asyncio.sleep(duration)


# === TOP-LEVEL HELPER FUNCTIONS ===
# (Used in modules.telethon.operations and elsewhere)

async def random_sleep(min_s: float, max_s: float, reason: str = None):
    """Wait for a random amount of time with logging"""
    duration = random.uniform(min_s, max_s)
    if reason:
        logger.info(f"☕ Waiting {duration:.1f}s... (Reason: {reason})")
    else:
        logger.info(f"☕ Waiting {duration:.1f}s...")
    await asyncio.sleep(duration)

async def simulate_typing(length: int):
    """Simulate typing delay based on text length"""
    # Average 0.1s - 0.2s per character
    delay = length * random.uniform(0.05, 0.15)
    # Cap delay to avoid hanging too long
    delay = min(delay, 5.0)
    logger.info(f"⌨️ Simulating typing ({length} chars, {delay:.1f}s)...")
    await asyncio.sleep(delay)

async def simulate_scrolling(times: int = 1):
    """Simulate scrolling delay"""
    for i in range(times):
        duration = random.uniform(1.0, 3.0)
        logger.info(f"📜 Simulating scroll {i+1}/{times} ({duration:.1f}s)...")
        await asyncio.sleep(duration)
