import asyncio
import random
import logging

logger = logging.getLogger(__name__)

async def random_sleep(min_seconds=2, max_seconds=5, action_name="action"):
    """Simulates a random pause between actions"""
    delay = random.uniform(min_seconds, max_seconds)
    logger.info(f"Human Behavior: Pausing {delay:.2f}s for {action_name}...")
    await asyncio.sleep(delay)

async def simulate_typing(text_length, min_char_speed=0.1, max_char_speed=0.3):
    """Simulates time taken to type text"""
    total_delay = 0
    for _ in range(text_length):
        char_delay = random.uniform(min_char_speed, max_char_speed)
        total_delay += char_delay
    
    logger.info(f"Human Behavior: Simulating typing ({text_length} chars) ~{total_delay:.2f}s...")
    await asyncio.sleep(total_delay)

async def simulate_mouse_move():
    """Simulates slight mouse movement delay"""
    await asyncio.sleep(random.uniform(0.5, 1.5))

async def simulate_scrolling(duration_range=(2, 5)):
    """Simulates scrolling through content"""
    duration = random.uniform(*duration_range)
    logger.info(f"Human Behavior: Scrolling feed for {duration:.2f}s...")
    await asyncio.sleep(duration)
