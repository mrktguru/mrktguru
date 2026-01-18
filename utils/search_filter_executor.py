"""
Search & Filter Node Executor
Implements smart search for Telegram channels/groups with human emulation
"""
import asyncio
import random
import re
import logging
import json
from datetime import datetime, timedelta
from telethon.tl.functions.contacts import SearchRequest, ResolveUsernameRequest
from telethon.tl.types import Channel, Chat, User
from models.channel_candidate import ChannelCandidate
from models.warmup_log import WarmupLog
from models.activity_log import AccountActivityLog
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
                - keywords: multi-line string of search keywords
                - links: multi-line string of direct links/usernames
                - stopwords: comma-separated blacklist words
                - language: 'EN', 'RU', 'AUTO'
        
        Returns:
            dict with success, message, discovered_count
        """
        try:
            keywords_str = config.get('keywords', '').strip()
            links_str = config.get('links', '').strip()
            language = config.get('language', 'AUTO')
            stopwords_str = config.get('stopwords', '').strip()
            
            # Parse stopwords
            stopwords = [w.strip().lower() for w in stopwords_str.split(',') if w.strip()] if stopwords_str else []
            
            # Parse keywords and links
            keywords = [line.strip() for line in keywords_str.split('\n') if line.strip()]
            links = [line.strip() for line in links_str.split('\n') if line.strip()]
            
            if not keywords and not links:
                return {'success': False, 'error': 'No keywords or links provided'}
            
            # Initialize counters
            attempted_count = len(keywords) + len(links)
            discovered_count = 0
            failed_count = 0
            
            logger.info(f"Account {account_id}: Starting Search & Filter - {len(keywords)} keywords, {len(links)} links")
            WarmupLog.log(account_id, 'info', f'Search & Filter starting: {len(keywords)} keywords, {len(links)} links', action='search_filter_start')
            
            # Create activity log for start
            db.session.add(AccountActivityLog(
                account_id=account_id,
                action_type='search_filter_start',
                action_category='warmup',
                status='info',
                description=f'Starting Search & Filter: {len(keywords)} keywords, {len(links)} links',
                details=json.dumps({'keywords': keywords, 'links': links})
            ))
            db.session.commit()
            
            # Process keywords (organic search)
            for keyword in keywords:
                result = await self._organic_search(client, account_id, keyword, language, stopwords)
                if result.get('success'):
                    discovered_count += 1
                else:
                    failed_count += 1
                # Delay between searches (3-8 sec)
                await asyncio.sleep(random.uniform(3, 8))
            
            # Process links (direct resolution)
            for link in links:
                result = await self._direct_link(client, account_id, link, language, stopwords)
                if result.get('success'):
                    discovered_count += 1
                else:
                    failed_count += 1
                # Delay between searches (3-8 sec)
                await asyncio.sleep(random.uniform(3, 8))
            
            # Log completion with detailed stats
            completion_msg = f'Search & Filter completed: {discovered_count} discovered, {failed_count} failed out of {attempted_count} attempts'
            WarmupLog.log(account_id, 'success', completion_msg)
            
            db.session.add(AccountActivityLog(
                account_id=account_id,
                action_type='search_filter_complete',
                action_category='warmup',
                status='success',
                description=completion_msg,
                details=json.dumps({
                    'attempted': attempted_count,
                    'discovered': discovered_count,
                    'failed': failed_count
                })
            ))
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Discovered {discovered_count} channels ({failed_count} failed)',
                'discovered_count': discovered_count,
                'failed_count': failed_count,
                'attempted_count': attempted_count
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
        from telethon.tl.functions.contacts import SearchRequest as ContactsSearch
        from telethon.tl.types import Channel
        
        try:
            logger.info(f"Account {account_id}: Starting organic search for '{keyword}'")
            WarmupLog.log(account_id, 'info', f'Searching: {keyword}', action='search_start')
            
            # 1. Emulate typing (with 15% chance of typo)
            await self._emulate_typing_with_errors(keyword, error_rate=0.15)
            
            # 2. Global search request using contacts.Search
            results = await client(ContactsSearch(
                q=keyword,
                limit=20
            ))
            
            if not results or not results.results:
                logger.info(f"Account {account_id}: No results for '{keyword}'")
                WarmupLog.log(account_id, 'warning', f"No search results for keyword: {keyword}", action='search_empty')
                return {'success': False, 'error': 'No results'}
            
            logger.info(f"Found {len(results.results)} raw results for '{keyword}'")
            
            # 3. Simulate scrolling (2-5 sec pause)
            await asyncio.sleep(random.uniform(2, 5))
            
            # 4. Extract channels from results
            valid_results = []
            for result in results.results[:20]:  # Check top 20
                # result itself is the Peer object
                chat_id = None
                
                if hasattr(result, 'channel_id'):
                    chat_id = result.channel_id
                elif hasattr(result, 'chat_id'):
                    chat_id = result.chat_id
                else:
                    continue
                
                # Find channel in results.chats
                chat = None
                for c in results.chats:
                    if c.id == chat_id:
                        chat = c
                        break
                
                if not chat or not isinstance(chat, Channel):
                    continue
                
                # Pre-filter
                if self._pre_filter(chat, stopwords):
                    valid_results.append(chat)
                    logger.info(f"Added to valid results: {getattr(chat, 'title', 'Unknown')}")
                else:
                    # Log why filtered
                    reason = self._get_prefilter_reason(chat, stopwords)
                    logger.info(f"Pre-filtered '{getattr(chat, 'title', 'Unknown')}': {reason}")
            
            if not valid_results:
                logger.info(f"Account {account_id}: No valid results after filtering for '{keyword}'")
                WarmupLog.log(account_id, 'warning', f"All search results filtered out for: {keyword}", action='search_filtered')
                return {'success': False, 'error': 'All results filtered out'}
            
            WarmupLog.log(account_id, 'info', f"Found {len(valid_results)} valid channels for keyword: {keyword}", action='search_found')
            
            # Pick random from top-5 (or all if less than 5)
            candidate = random.choice(valid_results[:min(5, len(valid_results))])
            logger.info(f"Selected candidate: {getattr(candidate, 'title', 'Unknown')}")
            
            # 5. Deep inspection
            return await self._deep_inspection(client, account_id, candidate, language, 'SEARCH')
            
        except Exception as e:
            logger.error(f"Organic search failed: {e}", exc_info=True)
            WarmupLog.log(account_id, 'error', f"Search error for '{keyword}': {str(e)}", action='search_error')
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
            
            # 3. Resolve entity - try multiple formats
            try:
                # Try different formats for better compatibility
                entity = None
                last_error = None
                
                # Method 1: Try with @ prefix first, then without, then full URL
                for format_attempt in [f'@{username}', username, f'https://t.me/{username}']:
                    try:
                        logger.debug(f"Trying to resolve: {format_attempt}")
                        entity = await client.get_entity(format_attempt)
                        logger.info(f"✓ Resolved @{username} using format: {format_attempt}")
                        break  # Success!
                    except Exception as attempt_error:
                        last_error = attempt_error
                        logger.debug(f"Failed with {format_attempt}: {attempt_error}")
                        continue
                
                # If all attempts failed, raise the last error
                if not entity:
                    raise last_error if last_error else Exception("Could not resolve entity")
                
                logger.info(f"Resolved @{username}: {getattr(entity, 'title', 'Unknown')} (ID: {entity.id})")
                WarmupLog.log(account_id, 'info', f"Resolved: {getattr(entity, 'title', username)}", action='resolve_success')
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Failed to resolve @{username}: {e}")
                WarmupLog.log(account_id, 'error', f"Channel not found or private: @{username} - {error_msg}", action='resolve_failed')
                
                # Save failed attempt to DB
                await self._save_failed_candidate(account_id, username, error_msg, language, 'LINK')
                
                # Log to activity log
                db.session.add(AccountActivityLog(
                    account_id=account_id,
                    action_type='channel_resolve_failed',
                    action_category='warmup',
                    target=f'@{username}',
                    status='failed',
                    description=f'Failed to resolve channel: @{username}',
                    error_message=error_msg
                ))
                db.session.commit()
                
                return {'success': False, 'error': f'Failed to resolve: {error_msg}'}
            
            # 4. Deep inspection
            # Pre-filter before deep inspection
            if not self._pre_filter(entity, stopwords):
                reason = self._get_prefilter_reason(entity, stopwords)
                WarmupLog.log(account_id, 'warning', f"Pre-filtered @{username}: {reason}", action='prefilter_reject')
                
                # Save as failed (filtered)
                await self._save_failed_candidate(account_id, username, f"Filtered: {reason}", language, 'LINK')
                
                return {'success': False, 'error': f'Filtered: {reason}'}
            
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
            logger.info(f"Starting deep inspection for: {getattr(entity, 'title', 'Unknown')} (ID: {entity.id})")
            WarmupLog.log(account_id, 'info', f"Inspecting: {getattr(entity, 'title', 'Unknown')}", action='inspect_start')
            
            # Get messages (= "visit" for Telegram)
            try:
                messages = await client.get_messages(entity, limit=10)
                logger.info(f"Retrieved {len(messages)} messages")
            except Exception as msg_err:
                logger.error(f"Failed to get messages: {msg_err}")
                WarmupLog.log(account_id, 'error', f"Cannot read messages: {str(msg_err)}", action='messages_failed')
                return {'success': False, 'error': f'Cannot read messages: {str(msg_err)}'}
            
            # Emulate reading
            await self._emulate_reading(messages)
            
            # Validation checks
            validation = await self._validate(entity, messages)
            
            if not validation['is_valid']:
                logger.info(f"Account {account_id}: Entity {entity.id} rejected: {validation['reason']}")
                WarmupLog.log(account_id, 'warning', f"Channel rejected '{entity.title}': {validation['reason']}", action='validation_failed')
                return {'success': False, 'error': validation['reason']}
            
            # Save to database
            try:
                await self._save_candidate(account_id, entity, messages, language, origin, validation)
            except Exception as save_err:
                logger.error(f"Failed to save candidate: {save_err}", exc_info=True)
                WarmupLog.log(account_id, 'error', f"Failed to save to DB: {str(save_err)}", action='save_failed')
            
            logger.info(f"Account {account_id}: Successfully discovered and saved '{entity.title}'")
            WarmupLog.log(account_id, 'success', f"Discovered: {entity.title}", action='discovered')
            
            # Log successful discovery to activity log
            channel_username = getattr(entity, 'username', None) or f"id_{entity.id}"
            db.session.add(AccountActivityLog(
                account_id=account_id,
                action_type='channel_discovered',
                action_category='warmup',
                target=entity.title,
                status='success',
                description=f'Discovered channel: @{channel_username}',
                details=json.dumps({'peer_id': entity.id, 'origin': origin, 'username': channel_username})
            ))
            db.session.commit()
            
            return {'success': True, 'entity_id': entity.id, 'title': entity.title}
            
        except Exception as e:
            logger.error(f"Deep inspection failed: {e}", exc_info=True)
            WarmupLog.log(account_id, 'error', f"Inspection error: {str(e)}", action='inspect_error')
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
    
    def _get_prefilter_reason(self, entity, stopwords=None):
        """Get reason why entity was pre-filtered"""
        from telethon.tl.types import User
        
        # Check bots
        if isinstance(entity, User) and entity.bot:
            return "Bot account"
        
        # Check title for stopwords
        if stopwords:
            title = getattr(entity, 'title', '').lower()
            for word in stopwords:
                if word in title:
                    return f"Blacklisted word '{word}' in title"
        
        return "Unknown reason"
    
    def _pre_filter(self, entity, stopwords=None):
        """Pre-filter checks (before deep inspection)"""
        # Skip bots
        if isinstance(entity, User) and entity.bot:
            return False
        
        # Check title for stopwords
        if stopwords:
            title = getattr(entity, 'title', '').lower()
            if any(word in title for word in stopwords):
                return False
        
        return True
    
    async def _validate(self, entity, messages):
        """Deep validation checks"""
        from telethon.tl.functions.channels import GetFullChannelRequest
        
        # Check type (Channel or Megagroup)
        if not isinstance(entity, Channel):
            return {'is_valid': False, 'reason': 'Not a channel/group'}
        
        # Check size - handle None from Telegram API
        # For large channels, basic entity doesn't include participants_count
        participants_count = getattr(entity, 'participants_count', None)
        
        # If participants_count is None or 0, try to get full channel info
        if not participants_count:
            try:
                from telethon.tl.functions.channels import GetFullChannelRequest
                full_channel = await self.client.get_entity(entity)
                full_info = await self.client(GetFullChannelRequest(channel=entity))
                participants_count = getattr(full_info.full_chat, 'participants_count', None)
                logger.info(f"Retrieved full channel info: {participants_count} participants")
            except Exception as e:
                logger.warning(f"Could not get full channel info: {e}")
                # If we can't get participant count, skip size validation
                # (likely a large channel where count is hidden)
                participants_count = None
        
        # Only validate size if we have the count
        if participants_count is not None:
            if participants_count < 500:
                return {'is_valid': False, 'reason': f'Too small ({participants_count} members)'}
            if participants_count > 30000:
                return {'is_valid': False, 'reason': f'Too large ({participants_count} members)'}
        else:
            # For channels without participant count (large channels), assume valid
            logger.info("Participant count unavailable, skipping size validation")
            participants_count = 0  # Set to 0 for DB storage
        
        # Check liveness (last post < 7 days)
        if messages and len(messages) > 0:
            last_post_date = messages[0].date
            if last_post_date:
                # Handle timezone-aware datetimes from Telegram
                # Convert to naive datetime for comparison
                if last_post_date.tzinfo is not None:
                    last_post_date = last_post_date.replace(tzinfo=None)
                
                days_ago = (datetime.now() - last_post_date).days
                if days_ago > 7:
                    return {'is_valid': False, 'reason': f'Inactive ({days_ago} days since last post)'}
            else:
                return {'is_valid': False, 'reason': 'No post date available'}
        else:
            return {'is_valid': False, 'reason': 'No messages found'}
        
        # Check write permissions
        can_send_messages = True
        if hasattr(entity, 'default_banned_rights') and entity.default_banned_rights:
            can_send_messages = not entity.default_banned_rights.send_messages
        
        return {
            'is_valid': True,
            'participants_count': participants_count or 0,
            'last_post_date': messages[0].date if messages and len(messages) > 0 else None,
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
    
    async def _save_failed_candidate(self, account_id, username, error_message, language, origin):
        """Save failed channel attempt to database for tracking"""
        try:
            # Check if already exists
            existing = ChannelCandidate.query.filter_by(
                account_id=account_id,
                username=username
            ).first()
            
            if existing:
                # Update existing with failure info
                existing.status = 'FAILED'
                existing.last_visit_ts = datetime.utcnow()
                existing.error_reason = error_message
                db.session.commit()
                logger.info(f"Updated existing candidate as FAILED: @{username}")
            else:
                # Create new with FAILED status
                candidate = ChannelCandidate(
                    account_id=account_id,
                    peer_id=0,  # Unknown
                    access_hash=0,  # Unknown
                    username=username,
                    title=f"[Failed] {username}",
                    type='UNKNOWN',
                    language=language,
                    origin=origin,
                    status='FAILED',
                    error_reason=error_message
                )
                db.session.add(candidate)
                db.session.commit()
                logger.info(f"Saved failed candidate to DB: @{username}")
                
        except Exception as e:
            logger.error(f"Failed to save failed candidate: {e}", exc_info=True)
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
