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
                invite_info = await self.client(functions.messages.CheckChatInvite(hash=hash_arg))
                
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
            results = await self.client(functions.contacts.Search(
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
                
                await self._view_channel_content(wrong_target, short_visit=True)
                
                logger.info(f"{self.log_prefix}   🔙 Back to search results...")
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                target_idx = 0 # Correct target
            
            real_target = all_results[target_idx]
            tit = getattr(real_target, 'title', getattr(real_target, 'username', 'Unknown'))
            logger.info(f"{self.log_prefix}   -> Clicked result: {tit}")
            
            await self._view_channel_content(real_target)

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
            # 15% chance for massive typo
            if char.lower() in nearby_keys and random.random() < 0.15:
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

    async def _view_channel_content(self, entity, short_visit=False):
        """
        Simulates viewing channel content: scrolling, reading, media expansion.
        """
        try:
            initial_limit = 5 if not short_visit else 2
            history = await self.client(functions.messages.GetHistory(
                peer=entity,
                limit=initial_limit
            ))
            
            if not history.messages:
                return

            logger.info(f"{self.log_prefix}   👀 Viewing content in {getattr(entity, 'title', 'chat')}...")

            # 1. Read latest post
            await asyncio.sleep(random.uniform(2.0, 5.0))

            if short_visit:
                return

            # 2. SCROLL UP SCENARIO (40% chance)
            if random.random() < 0.4:
                logger.info(f"{self.log_prefix}   ⬆️ Scrolling up to check history...")
                if history.messages:
                    last_msg_id = history.messages[-1].id
                    await self.client(functions.messages.GetHistory(
                        peer=entity, 
                        offset_id=last_msg_id, 
                        limit=5
                    ))
                    await asyncio.sleep(random.uniform(3.0, 8.0))
                
                logger.info(f"{self.log_prefix}   ⬇️ Scrolling back to bottom...")

            # 3. Media Interaction
            # Check top 3 messages for media
            for msg in history.messages[:3]:
                if msg.message:
                    # Reading speed
                    read_time = min(len(msg.message) / 15, 8.0) 
                    await asyncio.sleep(read_time)
                
                # Media Preview (30% chance)
                if getattr(msg, 'media', None) and random.random() < 0.3:
                    logger.info(f"{self.log_prefix}   🖼️ Maximized photo/video view")
                    await asyncio.sleep(random.uniform(3.0, 7.0))

        except Exception as e:
            logger.error(f"{self.log_prefix}Error viewing content: {e}")
