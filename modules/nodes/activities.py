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
            self.log('error', f"Idle node failed: {e}", action='idle_error')
            return {'success': False, 'error': str(e)}


class PassiveActivityExecutor(BaseNodeExecutor):
    """
    Passive Activity Node - emulates Telegram Desktop in background/tray.
    
    Concept:
    - User opened Telegram Desktop and is doing their regular work/life
    - Occasionally glances at the chat list (scroll = looking at sidebar)
    - Does NOT open channels or read messages
    - Ping every 15-40s to keep proxy connection alive
    - In "tray" mode (between scrolls): ping interval is 1.5x slower
    
    Time allocation:
    - Total Duration = Scroll Time + Tray Time (automatic)
    - Example: 60min total, 4 scrolls × 2min = 8min active, 52min in tray
    """
    
    # Mode constants
    MODE_ACTIVE = 'active'  # Window is open, user is looking
    MODE_TRAY = 'tray'      # Minimized to tray
    
    async def execute(self):
        try:
            duration_mins = int(self.get_config('duration_minutes', 30))
            total_seconds = duration_mins * 60
            enable_scroll = self.get_config('enable_scroll', False)
            
            self.log('info', f'🧘 Starting Passive Activity Node ({duration_mins}m)', action='passive_start')
            self.log('info', f'📋 Config: duration={duration_mins}min, scroll={enable_scroll}', action='config_info')
            
            # Generate scroll events (moments when user "opens" the window)
            scroll_events = []
            total_scroll_time = 0
            
            if enable_scroll:
                count = random.randint(
                    int(self.get_config('scroll_count_min', 3)),
                    int(self.get_config('scroll_count_max', 6))
                )
                dur_min = int(self.get_config('scroll_duration_min', 30))
                dur_max = int(self.get_config('scroll_duration_max', 120))
                
                self.log('info', f'📜 Planned scroll events: {count} scrolls of {dur_min}-{dur_max}s each', action='scroll_config')
                
                if total_seconds > 300:
                    for i in range(count):
                        # Distribute events evenly with randomness
                        segment_size = total_seconds // (count + 1)
                        base_time = segment_size * (i + 1)
                        jitter = random.randint(-segment_size // 3, segment_size // 3)
                        start_sec = max(60, min(total_seconds - 120, base_time + jitter))
                        
                        duration = random.randint(dur_min, dur_max)
                        total_scroll_time += duration
                        
                        scroll_events.append({
                            'start_at': start_sec,
                            'duration': duration,
                            'done': False,
                            'index': i + 1
                        })
                    
                    scroll_events.sort(key=lambda x: x['start_at'])
                    
                    # Log schedule
                    for event in scroll_events:
                        mins = event['start_at'] // 60
                        secs = event['start_at'] % 60
                        self.log('info', f"📅 Scroll #{event['index']} scheduled at {mins}m{secs}s for {event['duration']}s", action='scroll_scheduled')
            
            # Calculate tray time
            tray_time = total_seconds - total_scroll_time
            self.log('info', f'📊 Time allocation: {total_scroll_time}s active + {tray_time}s in tray = {total_seconds}s total', action='time_allocation')
            
            # Initial status
            start_time = datetime.now()
            last_ping_time = datetime.now()
            current_mode = self.MODE_TRAY
            ping_count = 0
            
            self.log('info', '⚡ Sending initial online status...', action='status_update')
            try:
                await asyncio.wait_for(self.client(UpdateStatusRequest(offline=False)), timeout=20)
                self.log('info', '✅ Online status sent successfully', action='status_success')
                ping_count += 1
            except asyncio.TimeoutError:
                self.log('warning', '⏰ Initial status update timed out', action='status_timeout')
            except Exception as e:
                self.log('warning', f'⚠️ Initial status update failed: {e}', action='status_error')
            
            self.log('info', '🔄 Starting passive simulation loop...', action='loop_start')
            self.log('info', f'📱 Mode: TRAY (minimized) - ping interval: 22-60s', action='mode_tray')
            
            # Main loop
            while True:
                now = datetime.now()
                elapsed = (now - start_time).total_seconds()
                
                if elapsed >= total_seconds:
                    break
                
                # Check if any scroll event should start
                current_scroll = None
                for event in scroll_events:
                    if not event['done'] and elapsed >= event['start_at']:
                        current_scroll = event
                        break
                
                if current_scroll:
                    # === ACTIVE MODE: Window is open ===
                    if current_mode != self.MODE_ACTIVE:
                        current_mode = self.MODE_ACTIVE
                        self.log('info', f'🖥️ Mode: ACTIVE (window open) - ping interval: 15-40s', action='mode_active')
                    
                    self.log('info', f"👀 Scroll #{current_scroll['index']}: Looking at chat list for {current_scroll['duration']}s", action='scroll_start')
                    
                    # Perform scroll (looking at dialogs, NOT opening channels)
                    await self._scroll_dialogs(current_scroll['duration'])
                    
                    current_scroll['done'] = True
                    last_ping_time = datetime.now()
                    
                    self.log('info', f"💤 Scroll #{current_scroll['index']} finished. Minimizing to tray.", action='scroll_end')
                    current_mode = self.MODE_TRAY
                    self.log('info', f'📱 Mode: TRAY (minimized) - ping interval: 22-60s', action='mode_tray')
                
                else:
                    # === TRAY MODE: Minimized, just keep-alive pings ===
                    
                    # Calculate ping interval based on mode
                    if current_mode == self.MODE_ACTIVE:
                        ping_min, ping_max = 15, 40
                    else:
                        # Tray mode: 1.5x slower
                        ping_min, ping_max = 22, 60
                    
                    time_since_ping = (now - last_ping_time).total_seconds()
                    next_ping_delay = random.randint(ping_min, ping_max)
                    
                    if time_since_ping >= next_ping_delay:
                        # Send keep-alive ping
                        try:
                            await asyncio.wait_for(self.client(UpdateStatusRequest(offline=False)), timeout=15)
                            ping_count += 1
                            elapsed_mins = int(elapsed // 60)
                            elapsed_secs = int(elapsed % 60)
                            self.log('info', f'📡 Ping #{ping_count} sent (elapsed: {elapsed_mins}m{elapsed_secs}s, mode: {current_mode})', action='ping_sent')
                            last_ping_time = datetime.now()
                        except asyncio.TimeoutError:
                            self.log('warning', f'⏰ Ping #{ping_count + 1} timed out', action='ping_timeout')
                        except Exception as e:
                            self.log('warning', f'⚠️ Ping failed: {e}', action='ping_error')
                    
                    # Small sleep to prevent busy loop
                    await asyncio.sleep(5)
            
            # Graceful offline
            self.log('info', '📴 Sending offline status (closing app)...', action='offline_start')
            try:
                await asyncio.wait_for(self.client(UpdateStatusRequest(offline=True)), timeout=15)
                self.log('info', '✅ Offline status sent', action='offline_success')
            except Exception as e:
                self.log('warning', f'⚠️ Offline status failed: {e}', action='offline_error')
            
            # Summary
            completed_scrolls = sum(1 for e in scroll_events if e['done'])
            self.log('success', f'🎉 Passive Activity completed: {duration_mins}m, {ping_count} pings, {completed_scrolls}/{len(scroll_events)} scrolls', action='passive_complete')
            
            return {
                'success': True, 
                'message': f'Completed {duration_mins}m session',
                'stats': {
                    'duration_minutes': duration_mins,
                    'pings': ping_count,
                    'scrolls_completed': completed_scrolls,
                    'scrolls_total': len(scroll_events)
                }
            }
            
        except Exception as e:
            self.log('error', f'❌ Passive Activity failed: {e}', action='passive_error')
            return {'success': False, 'error': str(e)}

    async def _scroll_dialogs(self, duration_seconds):
        """
        Emulates looking at the chat list sidebar (NOT opening channels).
        
        Actions:
        - GetDialogsRequest with different limits (scrolling up/down)
        - Occasional pauses (reading chat names/previews)
        - Keep-alive pings during active window
        
        Does NOT:
        - Open channels
        - Read messages
        - Increment view counters
        """
        try:
            start_time = datetime.now()
            scroll_count = 0
            
            self.log('info', f'📜 Starting dialog scroll for {duration_seconds}s', action='dialog_scroll_start')
            
            while True:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= duration_seconds:
                    break
                
                # Simulate scrolling through dialog list
                scroll_count += 1
                limit = random.choice([10, 15, 20, 25, 30])
                
                try:
                    self.log('info', f'👁️ Looking at dialog list (limit={limit})...', action='get_dialogs')
                    
                    result = await asyncio.wait_for(
                        self.client(GetDialogsRequest(
                            offset_date=None,
                            offset_id=0,
                            offset_peer=InputPeerEmpty(),
                            limit=limit,
                            hash=0
                        )),
                        timeout=20
                    )
                    
                    dialog_count = len(result.dialogs) if hasattr(result, 'dialogs') else 0
                    self.log('info', f'📋 Loaded {dialog_count} dialogs (scroll #{scroll_count})', action='dialogs_loaded')
                    
                except asyncio.TimeoutError:
                    self.log('warning', f'⏰ GetDialogs timed out', action='dialogs_timeout')
                except Exception as e:
                    self.log('warning', f'⚠️ GetDialogs error: {e}', action='dialogs_error')
                
                # Pause between scrolls (reading chat names/previews)
                remaining = duration_seconds - elapsed
                if remaining > 0:
                    pause = min(random.uniform(5, 15), remaining)
                    self.log('info', f'⏸️ Pausing {pause:.1f}s (reading chat previews)', action='scroll_pause')
                    await asyncio.sleep(pause)
            
            self.log('info', f'📜 Dialog scroll complete: {scroll_count} scroll actions', action='dialog_scroll_end')
            
        except Exception as e:
            self.log('warning', f'⚠️ Scroll fallback: {e}', action='scroll_fallback')
            # Fallback: just wait
            await asyncio.sleep(duration_seconds)


class SearchFilterExecutor(BaseNodeExecutor):
    async def execute(self):
        try:
            hb = HumanBehavior(self.client, self.account_id, node_id=self.node_id)
            await hb.process_mixed_links(self.config)
            
            self.log('success', f"Search & Filter session completed", action='search_filter_complete')
            return {'success': True, 'message': 'Search & Filter session completed'}
            
        except Exception as e:
            self.log('error', f"Search & Filter failed: {str(e)}", action='search_filter_error')
            return {'success': False, 'error': str(e)}
