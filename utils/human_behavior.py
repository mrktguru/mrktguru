"""
Human Behavior Simulation for Telegram
========================================
Comprehensive emulation of human behavior patterns for channel discovery.

Key Features:
- 3 Input Types: Direct links, @username, Invite links
- Deep Inspection: Read 3-7 posts with realistic timing
- readHistory: Send read receipts progressively
- Media Interaction: 25% chance to expand photos/videos
- Cooldown: 30-120 second pause between channels
- Filtering: Subscribers > 500, Last post < 7 days
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from telethon import functions, errors
from telethon.tl.types import Channel, Chat, User, ChatInviteAlready, ChatInvite

logger = logging.getLogger(__name__)


class HumanBehavior:
    """
    Simulates realistic human behavior for Telegram actions.
    
    Processing Pipeline:
    1. Parse input (link/username/invite)
    2. Resolve entity via appropriate API
    3. Deep Inspection (read posts, send readHistory)
    4. Filter validation (subscribers, activity)
    5. Save to database
    6. Cooldown pause before next channel
    """

    # Configuration defaults
    CONFIG = {
        'posts_to_view_min': 3,
        'posts_to_view_max': 7,
        'reading_speed_chars_per_sec': 15,
        'media_open_probability': 0.25,
        'video_watch_ratio': 0.3,
        'min_subscribers': 500,
        'max_inactive_days': 7,
        'cooldown_min': 30,
        'cooldown_max': 120,
        'misclick_probability': 0.10,
    }

    def __init__(self, client, account_id=None, node_id=None):
        self.client = client
        self.account_id = account_id
        self.node_id = node_id
        self.log_prefix = f"[{account_id}] " if account_id else ""

    def _log(self, level: str, message: str, action: str = None):
        """
        Dual logging: console (logger) + database (WarmupLog).
        Ensures all HumanBehavior actions appear in UI.
        
        Args:
            level: 'info', 'warning', 'error', 'success', 'debug'
            message: Log message
            action: Action type for DB (hb_start, hb_read, etc.)
        """
        # Console logging (always)
        full_message = f"{self.log_prefix}{message}"
        if level == 'debug':
            logger.debug(full_message)
            return  # Debug logs don't go to DB
        elif level == 'warning':
            logger.warning(full_message)
        elif level == 'error':
            logger.error(full_message)
        else:
            logger.info(full_message)
        
        # Database logging (if we have account_id)
        if self.account_id:
            try:
                from models.warmup_log import WarmupLog
                WarmupLog.log(
                    account_id=self.account_id,
                    status=level.upper() if level != 'success' else 'SUCCESS',
                    message=message,
                    action=action or f'hb_{level}',
                    node_id=self.node_id
                )
            except Exception as e:
                # Don't crash on logging failure
                logger.debug(f"DB log failed: {e}")

    async def process_mixed_links(self, config):
        """
        Main entry point. Processes a mixed list of links and usernames.
        
        Config keys:
        - links: str - newline-separated links/usernames
        - min_subscribers: int - minimum subscriber count (default 500)
        - max_inactive_days: int - max days since last post (default 7)
        - cooldown_min/max: int - seconds between channels (default 30-120)
        """
        links_text = config.get('links', '')
        lines = [line.strip() for line in links_text.split('\n') if line.strip()]
        
        if not lines:
            self._log('warning', 'No links provided for processing', action='hb_no_links')
            return {'success': False, 'error': 'No links provided'}

        # Override config values if provided
        self.min_subscribers = config.get('min_subscribers', self.CONFIG['min_subscribers'])
        self.max_inactive_days = config.get('max_inactive_days', self.CONFIG['max_inactive_days'])
        self.cooldown_min = config.get('cooldown_min', self.CONFIG['cooldown_min'])
        self.cooldown_max = config.get('cooldown_max', self.CONFIG['cooldown_max'])

        # Shuffle execution order to avoid robotic patterns
        random.shuffle(lines)
        total = len(lines)
        self._log('info', f'🚀 Processing {total} items with Full Human Emulation', action='hb_start')
        
        processed = 0
        saved = 0
        filtered_out = 0
        errors_count = 0

        for index, item in enumerate(lines):
            try:
                self._log('info', f'[{index+1}/{total}] Processing: {item}', action='hb_process_item')
                
                result = await self._process_single_item(item)
                
                if result.get('saved'):
                    saved += 1
                elif result.get('filtered'):
                    filtered_out += 1
                
                processed += 1
                
                # === COOLDOWN between channels (30-120 sec) ===
                if index < total - 1:  # Not last item
                    await self._inter_channel_cooldown()

            except Exception as e:
                self._log('error', f"Error processing '{item}': {e}", action='hb_item_error')
                errors_count += 1
                continue
        
        self._log('success', f'✅ Completed: {processed}/{total} processed, {saved} saved, {filtered_out} filtered, {errors_count} errors', action='hb_complete')
        
        return {
            'success': True,
            'processed': processed,
            'saved': saved,
            'filtered_out': filtered_out,
            'errors': errors_count
        }

    async def _process_single_item(self, item):
        """
        Process a single link/username based on its type.
        
        Returns dict with:
        - saved: bool - if channel was saved to DB
        - filtered: bool - if channel was filtered out
        - reason: str - reason for filtering (if filtered)
        """
        # Determine input type and process accordingly
        
        # === SCENARIO C: INVITE LINK (t.me/+AbCd or t.me/joinchat/...) ===
        if '+' in item or 'joinchat' in item:
            return await self._process_invite_link(item)
        
        # === SCENARIO A/B: DIRECT LINK or @USERNAME ===
        elif 't.me/' in item or 'telegram.me/' in item:
            return await self._process_direct_link(item)
        
        # === SCENARIO B: @username or plain username ===
        elif item.startswith('@'):
            return await self._process_username(item.replace('@', ''))
        
        # === SCENARIO D: KEYWORD SEARCH ===
        else:
            return await self._process_search_query(item)

    async def _process_invite_link(self, link):
        """
        Process private invite link (t.me/+AbCd... or t.me/joinchat/...)
        
        Limitations:
        - Cannot see post history before joining
        - Cannot verify last post date
        - Requires join to fully validate
        """
        self._log('info', f'🔐 Processing INVITE link: {link}', action='hb_invite_start')
        
        try:
            # Extract hash from link
            if '+' in link:
                hash_arg = link.split('+')[-1]
            else:
                hash_arg = link.split('joinchat/')[-1]
            hash_arg = hash_arg.replace('/', '').strip()
            
            # Pause: "App switching" delay
            await asyncio.sleep(random.uniform(2, 4))
            
            # CheckChatInvite - peek without joining
            invite_info = await self.client(functions.messages.CheckChatInviteRequest(hash=hash_arg))
            
            # Handle already joined case
            if isinstance(invite_info, ChatInviteAlready):
                self._log('info', '   Already a member of this chat', action='hb_already_member')
                return {'saved': False, 'filtered': True, 'reason': 'already_member'}
            
            if not isinstance(invite_info, ChatInvite):
                self._log('warning', '   Unknown invite response type', action='hb_unknown_invite')
                return {'saved': False, 'filtered': True, 'reason': 'unknown_response'}
            
            title = getattr(invite_info, 'title', 'Private Chat')
            participants = getattr(invite_info, 'participants_count', 0)
            
            self._log('info', f'   -> Viewed invite: {title} ({participants} members)', action='hb_invite_viewed')
            
            # Thinking pause
            await asyncio.sleep(random.uniform(2, 5))
            
            # === FILTER: Minimum subscribers ===
            if participants < self.min_subscribers:
                self._log('info', f'   ❌ Filtered: {participants} < {self.min_subscribers} members', action='hb_filter_low_members')
                return {'saved': False, 'filtered': True, 'reason': f'low_members_{participants}'}
            
            # === SAVE to DB ===
            # For invite links, we save with special flag requiring join to validate
            await self._save_invite_candidate(invite_info, hash_arg)
            
            return {'saved': True, 'filtered': False}

        except errors.InviteHashExpiredError:
            self._log('warning', '   ⚠️ Invite link expired', action='hb_invite_expired')
            return {'saved': False, 'filtered': True, 'reason': 'expired'}
        except errors.InviteHashInvalidError:
            self._log('warning', '   ⚠️ Invalid invite hash', action='hb_invite_invalid')
            return {'saved': False, 'filtered': True, 'reason': 'invalid'}
        except Exception as e:
            self._log('error', f'   ❌ Failed to check invite: {e}', action='hb_invite_error')
            raise

    async def _process_direct_link(self, link):
        """
        Process direct public link (https://t.me/username)
        
        Pipeline:
        1. Parse username from URL
        2. ResolveUsername (emulates browser click)
        3. Deep inspection (read posts)
        4. Filter validation
        5. Save to DB
        """
        self._log('info', f'🔗 Processing DIRECT link: {link}', action='hb_direct_link')
        
        # Parse username from URL
        # Handles: t.me/username, telegram.me/username, https://t.me/username
        username = link.split('t.me/')[-1].split('/')[0].split('?')[0].strip()
        
        if not username:
            return {'saved': False, 'filtered': True, 'reason': 'invalid_link'}
        
        return await self._resolve_and_inspect(username, origin='LINK')

    async def _process_username(self, username):
        """
        Process @username input.
        Same as direct link but origin = DIRECT_MENTION
        """
        self._log('info', f'👤 Processing @USERNAME: @{username}', action='hb_username')
        return await self._resolve_and_inspect(username, origin='DIRECT_MENTION')

    async def _resolve_and_inspect(self, username, origin='LINK'):
        """
        Common logic for resolving public username and deep inspection.
        
        Steps:
        1. App switch delay (2-4 sec)
        2. Resolve username
        3. Quick Glance (check subscribers) - Early Exit if too low
        4. Deep inspection (view posts)
        5. Filter check (only for SEARCH origin)
        6. Save to DB
        
        Note: LINK and DIRECT_MENTION origins skip filtering!
        This allows users to add their own small/new channels.
        """
        # Determine if we should apply filters
        # Direct links and @mentions = user knows what they want, no filtering
        skip_filters = origin in ('LINK', 'DIRECT_MENTION')
        
        try:
            # === STEP 1: App switching delay ===
            await asyncio.sleep(random.uniform(2, 4))
            
            # === STEP 2: Resolve username ===
            entity = await self.client.get_entity(username)
            
            if not isinstance(entity, (Channel, Chat)):
                self._log('info', '   -> Not a channel/group, skipping', action='hb_not_channel')
                return {'saved': False, 'filtered': True, 'reason': 'not_channel'}
            
            title = getattr(entity, 'title', username)
            self._log('info', f'   -> Resolved: {title}', action='hb_resolved')
            
            # === STEP 3: Quick Glance - Early Exit (only for SEARCH) ===
            participants_count = 0
            if not skip_filters:
                try:
                    full_info = await self.client(functions.channels.GetFullChannelRequest(entity))
                    participants_count = full_info.full_chat.participants_count
                    
                    # Early exit if too few subscribers (human sees this immediately)
                    if participants_count < self.min_subscribers:
                        self._log('info', f'   👀 Quick glance: {participants_count} subs - too low, leaving...', action='hb_quick_glance_low')
                        await asyncio.sleep(random.uniform(2, 4))  # Quick exit pause
                        return {'saved': False, 'filtered': True, 'reason': f'low_members_{participants_count}'}
                    
                    self._log('info', f'   👀 Quick glance: {participants_count} subs - looks good!', action='hb_quick_glance_ok')
                except Exception as e:
                    self._log('warning', f'   ⚠️ Could not get subscriber count: {e}', action='hb_subscriber_error')
                    participants_count = getattr(entity, 'participants_count', 0)
            else:
                self._log('info', '   ⏭️ Skipping filters (direct link/mention)', action='hb_skip_filters')
            
            # === STEP 4: Deep Inspection ===
            inspection_result = await self._deep_inspection(entity)
            
            # === STEP 5: Activity filter (only for SEARCH) ===
            if not skip_filters:
                last_post_date = inspection_result.get('last_post_date')
                if last_post_date:
                    now = datetime.now(last_post_date.tzinfo) if last_post_date.tzinfo else datetime.utcnow()
                    days_inactive = (now - last_post_date).days
                    
                    if days_inactive > self.max_inactive_days:
                        self._log('info', f'   ❌ Channel inactive: {days_inactive} days since last post', action='hb_inactive')
                        return {'saved': False, 'filtered': True, 'reason': f'inactive_{days_inactive}_days'}
            
            # === STEP 6: Save to DB ===
            await self._save_discovered_channel(
                entity, 
                origin=origin,
                last_post_date=inspection_result.get('last_post_date'),
                participants_count=participants_count or getattr(entity, 'participants_count', 0)
            )
            
            return {'saved': True, 'filtered': False}

        except errors.UsernameNotOccupiedError:
            self._log('warning', f'   ⚠️ Username not found: {username}', action='hb_username_not_found')
            return {'saved': False, 'filtered': True, 'reason': 'not_found'}
        except errors.UsernameInvalidError:
            self._log('warning', f'   ⚠️ Invalid username: {username}', action='hb_username_invalid')
            return {'saved': False, 'filtered': True, 'reason': 'invalid_username'}
        except Exception as e:
            self._log('error', f'   ❌ Failed to resolve: {e}', action='hb_resolve_error')
            raise

    async def _process_search_query(self, query):
        """
        Process keyword search query.
        
        Steps:
        1. Focus delay
        2. Human typing simulation (or paste for long queries)
        3. Global search
        4. Optional misclick (10% chance)
        5. Select result and deep inspect
        """
        self._log('info', f"🔍 Processing SEARCH query: '{query}'", action='hb_search_start')
        
        # === STEP 1: Focus delay ===
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        # === STEP 2: Typing simulation ===
        if len(query) > 12:
            self._log('info', '   -> Long query, simulating Ctrl+V paste', action='hb_paste')
            await asyncio.sleep(random.uniform(0.5, 1.0))
        else:
            await self._simulate_typing(query)
        
        # === STEP 3: Execute search ===
        try:
            results = await self.client(functions.contacts.SearchRequest(
                q=query,
                limit=5
            ))
            
            all_results = list(results.chats) + list(results.users)
            
            if not all_results:
                self._log('info', f"   -> No results for '{query}'", action='hb_no_results')
                return {'saved': False, 'filtered': True, 'reason': 'no_results'}
            
            # Filter to only channels/chats
            channel_results = [r for r in all_results if isinstance(r, (Channel, Chat))]
            
            if not channel_results:
                self._log('info', '   -> No channels in results', action='hb_no_channels')
                return {'saved': False, 'filtered': True, 'reason': 'no_channels'}
            
            # === STEP 4: Misclick scenario (10% chance) ===
            target_idx = 0
            if len(channel_results) > 1 and random.random() < self.CONFIG['misclick_probability']:
                wrong_target = channel_results[1]
                self._log('info', f"   ⚠️ Misclick! Opened: {getattr(wrong_target, 'title', 'Unknown')}", action='hb_misclick')
                
                # Quick look and back
                await self._deep_inspection(wrong_target, short_visit=True)
                
                self._log('info', '   🔙 Back to search results...', action='hb_back')
                await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # === STEP 5: Select correct result ===
            target = channel_results[target_idx]
            title = getattr(target, 'title', 'Unknown')
            self._log('info', f'   -> Clicked result: {title}', action='hb_clicked_result')
            
            # === STEP 6: Quick Glance - Early Exit ===
            try:
                full_info = await self.client(functions.channels.GetFullChannelRequest(target))
                participants_count = full_info.full_chat.participants_count
                
                if participants_count < self.min_subscribers:
                    self._log('info', f'   👀 Quick glance: {participants_count} subs - too low, leaving...', action='hb_quick_glance_low')
                    await asyncio.sleep(random.uniform(2, 4))
                    return {'saved': False, 'filtered': True, 'reason': f'low_members_{participants_count}'}
                
                self._log('info', f'   👀 Quick glance: {participants_count} subs - looks good!', action='hb_quick_glance_ok')
            except Exception as e:
                self._log('warning', f'   ⚠️ Could not get subscriber count: {e}', action='hb_subscriber_error')
                participants_count = getattr(target, 'participants_count', 0)
            
            # === STEP 7: Deep inspection ===
            inspection_result = await self._deep_inspection(target)
            
            # === STEP 8: Activity filter ===
            last_post_date = inspection_result.get('last_post_date')
            if last_post_date:
                now = datetime.now(last_post_date.tzinfo) if last_post_date.tzinfo else datetime.utcnow()
                days_inactive = (now - last_post_date).days
                
                if days_inactive > self.max_inactive_days:
                    self._log('info', f'   ❌ Channel inactive: {days_inactive} days since last post', action='hb_inactive')
                    return {'saved': False, 'filtered': True, 'reason': f'inactive_{days_inactive}_days'}
            
            # === STEP 9: Save ===
            await self._save_discovered_channel(
                target, 
                origin='SEARCH',
                last_post_date=inspection_result.get('last_post_date'),
                participants_count=participants_count
            )
            
            return {'saved': True, 'filtered': False}

        except Exception as e:
            self._log('error', f'Search failed: {e}', action='hb_search_error')
            raise

    async def _deep_inspection(self, entity, short_visit=False):
        """
        Deep Inspection: Read posts with human-like timing.
        
        Algorithm:
        1. Fetch 5-8 recent posts
        2. Select 3-7 posts for "reading"
        3. For each post:
           - Calculate reading time based on text length
           - 25% chance to open media
           - Occasional micro-pauses (coffee breaks)
        4. Send readHistory progressively (not all at once)
        
        Returns:
            dict with last_post_date, messages_read
        """
        title = getattr(entity, 'title', 'Unknown')
        self._log('info', f'   👀 Deep inspection: {title}', action='hb_deep_inspect')
        
        result = {
            'last_post_date': None,
            'messages_read': 0
        }
        
        try:
            # === STEP 1: Fetch messages ===
            limit = 2 if short_visit else random.randint(5, 8)
            messages = await self.client.get_messages(entity, limit=limit)
            
            if not messages:
                self._log('info', '   -> Channel is empty', action='hb_channel_empty')
                return result
            
            # Record last post date
            if messages:
                result['last_post_date'] = messages[0].date
            
            if short_visit:
                # Minimal interaction for misclick/short visit
                await asyncio.sleep(random.uniform(1.0, 2.0))
                return result
            
            # === STEP 2: Select posts to read ===
            posts_to_read = random.randint(
                self.CONFIG['posts_to_view_min'],
                min(self.CONFIG['posts_to_view_max'], len(messages))
            )
            target_messages = list(reversed(messages[:posts_to_read]))  # Old to new
            
            self._log('info', f'   📖 Reading {len(target_messages)} posts...', action='hb_reading')
            
            # === STEP 3: Read each post ===
            last_read_id = None
            for idx, msg in enumerate(target_messages):
                # Calculate reading time
                text = getattr(msg, 'text', '') or getattr(msg, 'message', '') or ''
                read_time = self._calculate_reading_time(text)
                
                # Log reading action
                text_preview = text[:50] + '...' if len(text) > 50 else text
                logger.debug(f"{self.log_prefix}     Post {msg.id}: {read_time:.1f}s ({len(text)} chars)")
                
                # Simulate reading
                await asyncio.sleep(read_time)
                
                # === STEP 3a: Increment view counter (Critical for organic behavior) ===
                try:
                    from telethon.tl.functions.messages import GetMessagesViewsRequest
                    await self.client(GetMessagesViewsRequest(
                        peer=entity,
                        id=[msg.id],
                        increment=True  # This makes us visible in channel stats
                    ))
                except Exception:
                    # Ignore errors (groups don't have views, some channels restrict)
                    pass
                
                # === STEP 3b: Media interaction (25% chance) ===
                if getattr(msg, 'media', None) and random.random() < self.CONFIG['media_open_probability']:
                    self._log('info', '   🖼️ Viewing media...', action='hb_media')
                    
                    # Different timing for different media types
                    if hasattr(msg.media, 'document'):
                        # Video/GIF - watch portion of it
                        duration = getattr(msg.media.document, 'duration', 10)
                        watch_time = duration * self.CONFIG['video_watch_ratio']
                        watch_time = min(watch_time, 15)  # Cap at 15 sec
                        await asyncio.sleep(watch_time)
                    else:
                        # Photo - viewing time
                        await asyncio.sleep(random.uniform(2, 5))
                
                # === STEP 3c: Micro-pause (10% chance - coffee break) ===
                if random.random() < 0.10:
                    pause = random.uniform(3, 6)
                    logger.debug(f"{self.log_prefix}   ☕ Micro-pause: {pause:.1f}s")
                    await asyncio.sleep(pause)
                
                last_read_id = msg.id
                result['messages_read'] += 1
                
                # === STEP 4: Progressive readHistory ===
                # Send readHistory after ~50% of posts, then again at end
                if idx == len(target_messages) // 2 or idx == len(target_messages) - 1:
                    try:
                        await self.client(functions.messages.ReadHistoryRequest(
                            peer=entity,
                            max_id=last_read_id
                        ))
                        logger.debug(f"{self.log_prefix}   ✓ Sent readHistory up to {last_read_id}")
                    except Exception as e:
                        # readHistory might fail for channels (vs groups), that's OK
                        logger.debug(f"{self.log_prefix}   readHistory skipped: {e}")
            
            # === STEP 5: Optional scroll up (30% chance) ===
            if len(messages) > 0 and random.random() < 0.30:
                self._log('info', '   ⬆️ Scrolling up to check context...', action='hb_scroll_up')
                await asyncio.sleep(random.uniform(2, 4))
                
                # Fetch older messages
                older = await self.client.get_messages(
                    entity,
                    limit=3,
                    offset_id=messages[-1].id
                )
                
                await asyncio.sleep(random.uniform(2, 4))
                self._log('info', '   ⬇️ Scrolling back down...', action='hb_scroll_down')
            
            return result

        except Exception as e:
            self._log('error', f'   ⚠️ Error in deep inspection: {e}', action='hb_inspect_error')
            return result

    async def _validate_channel(self, entity, inspection_result):
        """
        Validate channel against filters.
        
        Checks:
        1. Minimum subscribers (default 500)
        2. Last post date < 7 days (is_alive check)
        3. Can send messages (for groups)
        
        Returns:
            dict with passed: bool, reason: str, participants_count: int
        """
        result = {
            'passed': True,
            'reason': None,
            'participants_count': 0
        }
        
        try:
            # === Get full channel info for participant count ===
            full_info = await self.client(functions.channels.GetFullChannelRequest(entity))
            participants_count = full_info.full_chat.participants_count
            result['participants_count'] = participants_count
            
            # === FILTER 1: Minimum subscribers ===
            if participants_count < self.min_subscribers:
                result['passed'] = False
                result['reason'] = f'low_members_{participants_count}_min_{self.min_subscribers}'
                return result
            
            # === FILTER 2: Last post date (is_alive) ===
            last_post_date = inspection_result.get('last_post_date')
            if last_post_date:
                # Make timezone aware comparison
                now = datetime.now(last_post_date.tzinfo) if last_post_date.tzinfo else datetime.utcnow()
                days_inactive = (now - last_post_date).days
                
                if days_inactive > self.max_inactive_days:
                    result['passed'] = False
                    result['reason'] = f'inactive_{days_inactive}_days'
                    return result
            
            # === FILTER 3: Banned rights (for groups) ===
            if hasattr(entity, 'default_banned_rights') and entity.default_banned_rights:
                if getattr(entity.default_banned_rights, 'send_messages', False):
                    result['passed'] = False
                    result['reason'] = 'cannot_send_messages'
                    return result
            
            return result

        except Exception as e:
            # If we can't get full info, still allow with warning
            self._log('warning', f'   ⚠️ Could not get full channel info: {e}', action='hb_full_info_error')
            # Try to get from entity directly
            result['participants_count'] = getattr(entity, 'participants_count', 0)
            return result

    async def _save_discovered_channel(self, entity, origin='LINK', last_post_date=None, participants_count=None):
        """
        Save or update discovered channel in database.
        
        Sets:
        - status = 'VISITED'
        - origin = LINK/DIRECT_MENTION/SEARCH
        - last_visit_ts = now
        - access_hash for later subscription
        """
        try:
            from models.channel_candidate import ChannelCandidate
            from database import db
            
            peer_id = entity.id
            access_hash = getattr(entity, 'access_hash', 0)
            username = getattr(entity, 'username', None)
            title = getattr(entity, 'title', 'Unknown')
            
            type_str = 'CHANNEL' if isinstance(entity, Channel) else 'MEGAGROUP'
            
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
                self._log('info', f'   ✨ NEW channel discovered: {title}', action='hb_new_channel')
            else:
                self._log('info', f'   🔄 Updated existing: {title}', action='hb_update_channel')
            
            # Update fields
            candidate.username = username
            candidate.title = title
            candidate.type = type_str
            candidate.last_visit_ts = datetime.utcnow()
            candidate.status = 'VISITED'
            
            if participants_count:
                candidate.participants_count = participants_count
            
            if last_post_date:
                candidate.last_post_date = last_post_date
            
            db.session.commit()
            
        except Exception as e:
            self._log('error', f'   ❌ Failed to save channel: {e}', action='hb_save_error')
            # Don't raise - persistence failure shouldn't kill the worker

    async def _save_invite_candidate(self, invite_info, invite_hash):
        """
        Save invite link candidate to database.
        Special handling: cannot verify last post without joining.
        """
        try:
            from models.channel_candidate import ChannelCandidate
            from database import db
            
            title = getattr(invite_info, 'title', 'Private Chat')
            participants = getattr(invite_info, 'participants_count', 0)
            
            # For invites, we don't have peer_id until we join
            # Use hash as temporary identifier (will be updated on join)
            # Actually, let's check if we have any ID from the invite
            peer_id = getattr(invite_info, 'chat_id', None) or hash(invite_hash) & 0x7FFFFFFF
            
            candidate = ChannelCandidate.query.filter_by(
                account_id=self.account_id,
                peer_id=peer_id
            ).first()
            
            if not candidate:
                candidate = ChannelCandidate(
                    account_id=self.account_id,
                    peer_id=peer_id,
                    access_hash=0,  # Don't have it yet
                    origin='INVITE_LINK'
                )
                db.session.add(candidate)
                self._log('info', f'   ✨ NEW invite saved: {title}', action='hb_new_invite')
            
            candidate.title = title
            candidate.type = 'PRIVATE'  # Mark as private
            candidate.last_visit_ts = datetime.utcnow()
            candidate.status = 'VISITED'
            candidate.participants_count = participants
            # Store invite hash for later joining
            candidate.error_reason = f"invite_hash:{invite_hash}"  # Reuse field temporarily
            
            db.session.commit()
            
        except Exception as e:
            self._log('error', f'   ❌ Failed to save invite: {e}', action='hb_invite_save_error')

    async def _inter_channel_cooldown(self):
        """
        Cooldown pause between channels (30-120 seconds).
        Simulates user taking a break between browsing channels.
        """
        delay = random.uniform(self.cooldown_min, self.cooldown_max)
        self._log('info', f'💤 Cooldown: {delay:.1f}s before next channel...', action='hb_cooldown')
        
        # We just sleep - the orchestrator handles keep-alive pings
        await asyncio.sleep(delay)

    def _calculate_reading_time(self, text):
        """
        Calculate realistic reading time for text.
        
        Algorithm:
        - Base: chars / 15 chars per second
        - Short posts (< 50 chars): read more carefully (+20%)
        - Long posts (> 500 chars): skim faster (-30%)
        - Add random noise (0.5-1.5 sec)
        - Cap at 8 seconds max per post
        """
        if not text:
            return random.uniform(0.5, 1.5)
        
        char_count = len(text)
        base_time = char_count / self.CONFIG['reading_speed_chars_per_sec']
        
        # Adjust for text length
        if char_count < 50:
            base_time *= 1.2  # Read short posts more carefully
        elif char_count > 500:
            base_time *= 0.7  # Skim long posts
        
        # Add noise (reaction time)
        noise = random.uniform(0.5, 1.5)
        
        total = base_time + noise
        
        # Cap at 8 seconds
        return min(total, 8.0)

    async def _simulate_typing(self, text):
        """
        Simulate human typing with occasional typos.
        """
        nearby_keys = {
            'a': 'qwsz', 'b': 'vghn', 'c': 'xdfv', 'd': 'serfc', 'e': 'rdsw',
            'f': 'drtgv', 'g': 'ftyhb', 'h': 'gyujn', 'i': 'ujko', 'j': 'hunik',
            'k': 'jilm', 'l': 'kop', 'm': 'njk', 'n': 'bhjm', 'o': 'iklp',
            'p': 'ol', 'q': 'wa', 'r': 'edft', 's': 'awzedx', 't': 'rfgy',
            'u': 'yhji', 'v': 'cfgb', 'w': 'qase', 'x': 'zsdc', 'y': 'tghu', 'z': 'asx'
        }
        
        for char in text:
            # 2% chance for typo
            if char.lower() in nearby_keys and random.random() < 0.02:
                # Press wrong key
                await asyncio.sleep(random.uniform(0.1, 0.3))
                # Realize mistake
                await asyncio.sleep(random.uniform(0.3, 0.8))
                # Backspace
                await asyncio.sleep(random.uniform(0.1, 0.2))
            
            # Press correct key
            await asyncio.sleep(random.uniform(0.08, 0.35))

    async def join_channel_humanly(self, entity, mute_notifications=True):
        """
        Executes the complex human behavior of joining a channel.
        
        Steps:
        1. View content (scroll/read)
        2. Decision pause
        3. Join action
        4. Post-join behavior (muting)
        
        Returns:
            str: 'JOINED', 'PENDING_APPROVAL', 'ALREADY_PARTICIPANT', 'REJECTED'
        """
        from telethon.tl.functions.account import UpdateNotifySettingsRequest
        from telethon.tl.functions.channels import JoinChannelRequest
        from telethon.tl.types import InputPeerNotifySettings
        from telethon.errors import UserAlreadyParticipantError
        
        # 1. PRE-JOIN INTERACTION
        await self._deep_inspection(entity, short_visit=False)
        
        # 2. DECISION PAUSE
        await asyncio.sleep(random.uniform(2.0, 5.0))
        
        # 3. JOIN ACTION
        result_status = 'JOINED'
        try:
            await self.client(JoinChannelRequest(channel=entity))
            
        except UserAlreadyParticipantError:
            self._log('info', '   ℹ️ Already a participant', action='hb_already_member')
            result_status = 'ALREADY_PARTICIPANT'
        except Exception as e:
            err_str = str(e).lower()
            if "invite request sent" in err_str or "pending" in err_str:
                self._log('info', '   ⏳ Join Request sent (Pending)', action='hb_pending')
                return 'PENDING_APPROVAL'
            raise
        
        # 4. POST-JOIN: MUTE (80% of time)
        if mute_notifications and result_status == 'JOINED':
            if random.random() < 0.8:
                await asyncio.sleep(random.uniform(1.0, 3.0))
                try:
                    await self.client(UpdateNotifySettingsRequest(
                        peer=entity,
                        settings=InputPeerNotifySettings(mute_until=2147483647)
                    ))
                    self._log('info', '   🔕 Notifications muted', action='hb_muted')
                except Exception as e:
                    self._log('warning', f'   ⚠️ Failed to mute: {e}', action='hb_mute_error')
        
        return result_status

    async def random_sleep(self, min_s, max_s, reason=None):
        """Helper wrapper for sleep with logging"""
        duration = random.uniform(min_s, max_s)
        msg = f"☕ Waiting {duration:.1f}s..."
        if reason:
            msg += f" ({reason})"
        self._log('info', msg, action='hb_sleep')
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
    delay = length * random.uniform(0.05, 0.15)
    delay = min(delay, 5.0)
    logger.info(f"⌨️ Simulating typing ({length} chars, {delay:.1f}s)...")
    await asyncio.sleep(delay)


async def simulate_scrolling(times: int = 1):
    """Simulate scrolling delay"""
    for i in range(times):
        duration = random.uniform(1.0, 3.0)
        logger.info(f"📜 Simulating scroll {i+1}/{times} ({duration:.1f}s)...")
        await asyncio.sleep(duration)
