import asyncio
import random
import logging
from datetime import datetime, timedelta

from telethon.tl.functions.messages import GetDialogsRequest, ReadHistoryRequest
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.messages import GetMessagesViewsRequest
from telethon.tl.types import InputPeerEmpty

from modules.nodes.base import BaseNodeExecutor
from utils.human_behavior import HumanBehavior, random_sleep

logger = logging.getLogger(__name__)

class IdleExecutor(BaseNodeExecutor):
    """
    Idle Node - realistic idle period with occasional status updates.
    Uses HumanBehavior for natural timing.
    """
    async def execute(self):
        try:
            duration = self.get_config('duration_minutes', 60)
            
            self.log('info', f"💤 Idle period: {duration} minutes", action='idle_start')
            
            # Split idle into chunks with occasional "wake-ups"
            total_seconds = duration * 60
            elapsed = 0
            
            while elapsed < total_seconds:
                # Sleep for 5-15 minutes at a time
                chunk = min(random.randint(300, 900), total_seconds - elapsed)
                await asyncio.sleep(chunk)
                elapsed += chunk
                
                if elapsed < total_seconds:
                    # Occasional status ping (like user checking phone briefly)
                    try:
                        from telethon.tl.functions.account import UpdateStatusRequest
                        await self.client(UpdateStatusRequest(offline=False))
                        await asyncio.sleep(random.uniform(1, 3))  # Brief "check"
                        await self.client(UpdateStatusRequest(offline=True))
                    except:
                        pass
            
            self.log('success', f"✅ Idle period completed", action='idle_complete')
            
            return {'success': True, 'message': f'Idle for {duration} minutes'}
            
        except Exception as e:
            logger.error(f"Idle node failed: {e}")
            return {'success': False, 'error': str(e)}


class PassiveActivityExecutor(BaseNodeExecutor):
    async def execute(self):
        try:
            duration_mins = int(self.get_config('duration_minutes', 30))
            total_seconds = duration_mins * 60
            enable_scroll = self.get_config('enable_scroll', False)
            
            self.log('info', f'🧘 Starting Passive Activity Node ({duration_mins}m)', action='passive_start')
            self.log('info', f'📋 Config: duration={duration_mins}min, scroll={enable_scroll}', action='config_info')
            
            scroll_events = []
            if enable_scroll:
                count = random.randint(
                    int(self.get_config('scroll_count_min', 3)),
                    int(self.get_config('scroll_count_max', 6))
                )
                dur_min = int(self.get_config('scroll_duration_min', 30))
                dur_max = int(self.get_config('scroll_duration_max', 120))
                
                self.log('info', f'📜 Scroll events: {count} scrolls of {dur_min}-{dur_max}s', action='scroll_config')
                
                if total_seconds > 300:
                    for _ in range(count):
                        start_sec = random.randint(120, total_seconds - 120)
                        duration = random.randint(dur_min, dur_max)
                        scroll_events.append({
                            'start_at': start_sec,
                            'duration': duration,
                            'done': False
                        })
                    scroll_events.sort(key=lambda x: x['start_at'])
            
            start_time = datetime.now()
            last_network_activity = datetime.now()
            next_ping_delay = random.randint(15, 40)
            
            self.log('info', '⚡ Sending online status to Telegram...', action='status_update')
            try:
                await asyncio.wait_for(self.client(UpdateStatusRequest(offline=False)), timeout=20)
                self.log('info', '✅ Online status sent successfully', action='status_success')
            except asyncio.TimeoutError:
                self.log('warning', '⏰ Initial status update timed out', action='status_timeout')
            except Exception as e:
                self.log('warning', f'⚠️ Initial status update failed: {e}', action='status_error')
            
            self.log('info', '🔄 Starting IDLE simulation loop...', action='loop_start')
            self.log('info', f'⏱️ Will run for {duration_mins} minutes', action='duration_info')
            
            while True:
                now = datetime.now()
                elapsed = (now - start_time).total_seconds()
                
                if elapsed >= total_seconds:
                    break
                
                # Check scroll
                current_scroll = None
                for event in scroll_events:
                    if not event['done'] and elapsed >= event['start_at']:
                        current_scroll = event
                        break
                
                # Ping
                if (now - last_network_activity).total_seconds() > next_ping_delay:
                    try:
                        await asyncio.wait_for(self.client(UpdateStatusRequest(offline=False)), timeout=15)
                        last_network_activity = now
                        next_ping_delay = random.randint(15, 40)
                    except Exception as e:
                        pass
                
                if current_scroll:
                     self.log('info', f"👀 Waking up: Reading subscribed channels for {current_scroll['duration']}s", action='scroll_start')
                     try:
                        await asyncio.wait_for(self.client(UpdateStatusRequest(offline=False)), timeout=15)
                     except: pass
                     
                     # Use HumanBehavior for realistic channel reading
                     await self._scroll_with_human_behavior(current_scroll['duration'])
                             
                     current_scroll['done'] = True
                     self.log('info', "💤 Reading finished. Going back to IDLE.", action='scroll_end')
                     last_network_activity = datetime.now()
                     next_ping_delay = random.randint(15, 40)
                
                else:
                    await asyncio.sleep(5)
            
            self.log('success', f'🎉 Passive Activity completed ({duration_mins}m)', action='passive_complete')
            return {'success': True, 'message': f'Completed {duration_mins}m session'}
            
        except Exception as e:
            logger.error(f"Passive Activity failed: {e}")
            self.log('error', f'❌ Passive Activity failed: {e}', action='passive_error')
            return {'success': False, 'error': str(e)}

    async def _scroll_with_human_behavior(self, duration_seconds):
        """
        Human-like scrolling through subscribed channels.
        Uses HumanBehavior deep inspection for realistic reading.
        """
        try:
            from telethon.tl.types import Channel, Chat
            
            start_time = datetime.now()
            hb = HumanBehavior(self.client, self.account_id)
            
            # Get dialogs (subscribed channels)
            dialogs = await self.client.get_dialogs(limit=20)
            channels = [d.entity for d in dialogs if isinstance(d.entity, (Channel, Chat))]
            
            if not channels:
                self.log('info', "No subscribed channels to scroll", action='no_channels')
                await asyncio.sleep(duration_seconds)
                return
            
            # Randomly pick 1-3 channels to "check"
            channels_to_read = random.sample(channels, min(random.randint(1, 3), len(channels)))
            
            for channel in channels_to_read:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= duration_seconds:
                    break
                
                title = getattr(channel, 'title', 'Unknown')
                self.log('info', f"📺 Checking: {title}", action='check_channel')
                
                # Use HumanBehavior for deep inspection
                await hb._deep_inspection(channel, short_visit=False)
                
                # Short pause between channels
                await asyncio.sleep(random.uniform(3, 8))
            
            # If time left, just idle
            remaining = duration_seconds - (datetime.now() - start_time).total_seconds()
            if remaining > 0:
                await asyncio.sleep(remaining)
                
        except Exception as e:
            logger.warning(f"[{self.account_id}] Scroll with HB failed: {e}")
            # Fallback to simple wait
            await asyncio.sleep(duration_seconds)


class SearchFilterExecutor(BaseNodeExecutor):
    async def execute(self):
        try:
            hb = HumanBehavior(self.client, self.account_id)
            await hb.process_mixed_links(self.config)
            
            self.log('success', f"Search & Filter session completed", action='search_filter_complete')
            return {'success': True, 'message': 'Search & Filter session completed'}
            
        except Exception as e:
            logger.error(f"Search & Filter node failed: {e}")
            self.log('error', f"Search & Filter failed: {str(e)}", action='search_filter_error')
            return {'success': False, 'error': str(e)}
