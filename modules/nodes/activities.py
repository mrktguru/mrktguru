import asyncio
import random
import logging
from datetime import datetime, timedelta

from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.types import InputPeerEmpty

from modules.nodes.base import BaseNodeExecutor
from utils.human_behavior import HumanBehavior

logger = logging.getLogger(__name__)

class IdleExecutor(BaseNodeExecutor):
    async def execute(self):
        try:
            duration = self.get_config('duration_minutes', 60)
            
            self.log('info', f"Idle period: {duration} minutes", action='idle_start')
            await asyncio.sleep(duration * 60)
            self.log('success', f"Idle period completed", action='idle_complete')
            
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
                     self.log('info', f"👀 Waking up: Scrolling feed for {current_scroll['duration']}s", action='scroll_start')
                     try:
                        await asyncio.wait_for(self.client(UpdateStatusRequest(offline=False)), timeout=15)
                     except: pass
                     
                     scroll_end = datetime.now() + timedelta(seconds=current_scroll['duration'])
                     while datetime.now() < scroll_end:
                         await asyncio.sleep(random.uniform(2.0, 5.0))
                         try:
                             await asyncio.wait_for(self.client(GetDialogsRequest(
                                 offset_date=None, offset_id=0,
                                 offset_peer=InputPeerEmpty(), limit=10, hash=0
                             )), timeout=20)
                             last_network_activity = datetime.now()
                         except asyncio.TimeoutError:
                             logger.warning(f"[{self.account_id}] GetDialogsRequest timed out")
                         except Exception as e:
                             logger.warning(f"[{self.account_id}] GetDialogsRequest error: {e}")
                             
                     current_scroll['done'] = True
                     self.log('info', "💤 Scroll finished. Going back to IDLE.", action='scroll_end')
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
