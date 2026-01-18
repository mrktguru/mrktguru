"""
Search & Filter Node Executor
Implements smart search for Telegram channels/groups with human emulation
"""
import asyncio
import random
import re
import logging
from datetime import datetime, timedelta
from telethon.tl.functions.contacts import SearchRequest, ResolveUsernameRequest
from telethon.tl.types import Channel, Chat, User
from models.channel_candidate import ChannelCandidate
from models.warmup_log import WarmupLog
from database import db

logger = logging.getLogger(__name__)


class SearchFilterExecutor:
    """
    Executor for Search & Filter node
    Discovers and validates Telegram channels/groups
    """
    
    def __init__(self):
        pass
    
    async def execute_search_filter(self, client, account_id, config):
        """
        Main entry point for search & filter execution
        
        Args:
            client: Telethon client
            account_id: Account ID
            config: Node configuration dict with keys:
                - strategy: 'organic', 'targeted', 'hybrid'
                - search_input: multi-line string of keywords/links
                - language: 'EN', 'RU', 'AUTO'
        
        Returns:
            dict with success, message, discovered_count
        """
        try:
            strategy = config.get('strategy', 'hybrid')
            search_input = config.get('search_input', '').strip()
            language = config.get('language', 'AUTO')
            stopwords_str = config.get('stopwords', '').strip()
            
            # Parse stopwords
            stopwords = [w.strip().lower() for w in stopwords_str.split(',') if w.strip()] if stopwords_str else []
            
            if not search_input:
                return {'success': False, 'error': 'No search input provided'}
            
            # Parse input lines
            lines = [line.strip() for line in search_input.split('\n') if line.strip()]
            
            discovered_count = 0
            
            for line in lines:
                # Determine if link or keyword
                if 't.me/' in line or line.startswith('@'):
                    # Scenario B: Direct link
                    result = await self._direct_link(client, account_id, line, language, stopwords)
                else:
                    # Scenario A: Organic search
                    result = await self._organic_search(client, account_id, line, language, stopwords)
                
                if result.get('success'):
                    discovered_count += 1
                
                # Delay between searches (3-8 sec)
                await asyncio.sleep(random.uniform(3, 8))
            
            WarmupLog.log(account_id, 'success', f'Search & Filter completed: {discovered_count} channels discovered')
            
            return {
                'success': True,
                'message': f'Discovered {discovered_count} channels',
                'discovered_count': discovered_count
            }
            
        except Exception as e:
            logger.error(f"Search & Filter execution failed: {e}", exc_info=True)
            WarmupLog.log(account_id, 'error', f'Search & Filter failed: {str(e)}')
            return {'success': False, 'error': str(e)}
    
    async def _organic_search(self, client, account_id, keyword, language, stopwords):
        """
        Scenario A: Organic search using contacts.Search
        
        Flow:
        1. Emulate typing with possible errors
        2. Send search request
        3. Simulate scrolling results
        4. Pick random candidate from top-5
        5. Deep inspection
        """
        try:
            logger.info(f"Account {account_id}: Starting organic search for '{keyword}'")
            WarmupLog.log(account_id, 'info', f'Searching: {keyword}', action='search_start')
            
            # 1. Emulate typing (with 15% chance of typo)
            await self._emulate_typing_with_errors(keyword, error_rate=0.15)
            
            # 2. Search request
            results = await client(SearchRequest(
                q=keyword,
                limit=20
            ))
            
            if not results or not results.results:
                logger.info(f"Account {account_id}: No results for '{keyword}'")
                return {'success': False, 'error': 'No results'}
            
            # 3. Simulate scrolling (2-5 sec pause)
            await asyncio.sleep(random.uniform(2, 5))
            
            # 4. Pre-filter and select
            valid_results = []
            for result in results.results[:10]:  # Check top 10
                peer = result.peer
                chat = results.chats.get(getattr(peer, 'channel_id', None) or getattr(peer, 'chat_id', None))
                
                if not chat:
                    continue
                
                # Pre-filter
                chat._custom_stopwords = stopwords  # Pass to pre_filter via attribute
                if self._pre_filter(chat, stopwords):
                    valid_results.append(chat)
            
            if not valid_results:
                logger.info(f"Account {account_id}: No valid results after filtering")
                return {'success': False, 'error': 'All results filtered out'}
            
            # Pick random from top-5 (or all if less than 5)
            candidate = random.choice(valid_results[:5])
            
            # 5. Deep inspection
            return await self._deep_inspection(client, account_id, candidate, language, 'SEARCH')
            
        except Exception as e:
            logger.error(f"Organic search failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _direct_link(self, client, account_id, link, language, stopwords):
        """
        Scenario B: Direct link resolution
        
        Flow:
        1. Extract username from link
        2. Pause (simulating app switch)
        3. Resolve entity
        4. Deep inspection
        """
        try:
            # 1. Extract username
            username = self._extract_username(link)
            if not username:
                return {'success': False, 'error': f'Invalid link: {link}'}
            
            logger.info(f"Account {account_id}: Resolving direct link @{username}")
            WarmupLog.log(account_id, 'info', f'Resolving: @{username}', action='resolve_start')
            
            # 2. Pause "app switch" (2-4 sec)
            await asyncio.sleep(random.uniform(2, 4))
            
            # 3. Resolve entity
            try:
                entity = await client.get_entity(username)
            except Exception as e:
                logger.warning(f"Failed to resolve @{username}: {e}")
                return {'success': False, 'error': f'Failed to resolve: {str(e)}'}
            
            # 4. Deep inspection
            # Pre-filter before deep inspection
            if not self._pre_filter(entity, stopwords):
                return {'success': False, 'error': 'Filtered by stopwords'}
            
            return await self._deep_inspection(client, account_id, entity, language, 'LINK')
            
        except Exception as e:
            logger.error(f"Direct link resolution failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _deep_inspection(self, client, account_id, entity, language, origin):
        """
        Deep inspection: Visit channel, validate, save to DB
        
        Args:
            entity: Telethon entity (Channel/Chat)
            language: Language code
            origin: 'SEARCH' or 'LINK'
        """
        try:
            # Get messages (= "visit" for Telegram)
            messages = await client.get_messages(entity, limit=10)
            
            # Emulate reading
            await self._emulate_reading(messages)
            
            # Validation checks
            validation = await self._validate(entity, messages)
            
            if not validation['is_valid']:
                logger.info(f"Account {account_id}: Entity {entity.id} rejected: {validation['reason']}")
                WarmupLog.log(account_id, 'info', f"Rejected {entity.title}: {validation['reason']}", action='filtered')
                return {'success': False, 'error': validation['reason']}
            
            # Save to database
            await self._save_candidate(account_id, entity, messages, language, origin, validation)
            
            logger.info(f"Account {account_id}: Successfully discovered and saved '{entity.title}'")
            WarmupLog.log(account_id, 'success', f"Discovered: {entity.title}", action='discovered')
            
            return {'success': True, 'entity_id': entity.id, 'title': entity.title}
            
        except Exception as e:
            logger.error(f"Deep inspection failed: {e}")
            return {'success': False, 'error': str(e)}
    
    # ==================== HELPER METHODS ====================
    
    async def _emulate_typing_with_errors(self, text, error_rate=0.15):
        """Emulate typing with occasional typos"""
        if random.random() < error_rate:
            # Type with error
            await asyncio.sleep(random.uniform(1, 2))
            # Pause (realize mistake)
            await asyncio.sleep(random.uniform(0.5, 1))
            # Backspace + correct
            await asyncio.sleep(random.uniform(0.5, 1))
        else:
            # Normal typing
            await asyncio.sleep(random.uniform(2, 4))
    
    async def _emulate_reading(self, messages):
        """Emulate reading messages"""
        if not messages:
            return
        
        # Calculate read time based on message count
        read_time = min(len(messages) * random.uniform(1, 2), 15)  # Max 15 sec
        await asyncio.sleep(read_time)
    
    def _pre_filter(self, entity, stopwords=None):
        """Pre-filter checks (before deep inspection)"""
        # Skip bots
        if isinstance(entity, User) and entity.bot:
            return False
        
        # Skip if already left
        if hasattr(entity, 'left') and entity.left:
            return False
        
        # Check title for stopwords
        if stopwords:
            title = getattr(entity, 'title', '').lower()
            if any(word in title for word in stopwords):
            return False
        
        return True
    
    async def _validate(self, entity, messages):
        """Deep validation checks"""
        # Check type (Channel or Megagroup)
        if not isinstance(entity, Channel):
            return {'is_valid': False, 'reason': 'Not a channel/group'}
        
        # Check size
        participants_count = getattr(entity, 'participants_count', 0)
        if participants_count < 500:
            return {'is_valid': False, 'reason': f'Too small ({participants_count} members)'}
        if participants_count > 30000:
            return {'is_valid': False, 'reason': f'Too large ({participants_count} members)'}
        
        # Check liveness (last post < 7 days)
        if messages:
            last_post_date = messages[0].date
            days_ago = (datetime.now() - last_post_date).days
            if days_ago > 7:
                return {'is_valid': False, 'reason': f'Inactive ({days_ago} days since last post)'}
        else:
            return {'is_valid': False, 'reason': 'No messages found'}
        
        # Check write permissions
        can_send_messages = True
        if hasattr(entity, 'default_banned_rights') and entity.default_banned_rights:
            can_send_messages = not entity.default_banned_rights.send_messages
        
        return {
            'is_valid': True,
            'participants_count': participants_count,
            'last_post_date': messages[0].date if messages else None,
            'can_send_messages': can_send_messages
        }
    
    async def _save_candidate(self, account_id, entity, messages, language, origin, validation):
        """Save discovered channel to database"""
        try:
            # Check if already exists
            existing = ChannelCandidate.query.filter_by(
                account_id=account_id,
                peer_id=entity.id
            ).first()
            
            if existing:
                # Update existing
                existing.last_visit_ts = datetime.utcnow()
                existing.participants_count = validation.get('participants_count')
                existing.last_post_date = validation.get('last_post_date')
                db.session.commit()
                logger.info(f"Updated existing candidate: {entity.title}")
                return
            
            # Create new candidate
            candidate = ChannelCandidate(
                account_id=account_id,
                peer_id=entity.id,
                access_hash=entity.access_hash,
                username=getattr(entity, 'username', None),
                title=getattr(entity, 'title', None),
                type='MEGAGROUP' if getattr(entity, 'megagroup', False) else 'CHANNEL',
                language=language,
                origin=origin,
                status='VISITED',
                participants_count=validation.get('participants_count'),
                last_post_date=validation.get('last_post_date'),
                can_send_messages=validation.get('can_send_messages', True)
            )
            
            db.session.add(candidate)
            db.session.commit()
            
            logger.info(f"Saved new candidate to DB: {entity.title} (peer_id={entity.id})")
            
        except Exception as e:
            logger.error(f"Failed to save candidate: {e}", exc_info=True)
            db.session.rollback()
    
    def _extract_username(self, link):
        """Extract username from t.me link or @username"""
        # Handle @username
        if link.startswith('@'):
            return link[1:]
        
        # Handle t.me/username
        match = re.search(r't\.me/([a-zA-Z0-9_]+)', link)
        if match:
            return match.group(1)
        
        return None
