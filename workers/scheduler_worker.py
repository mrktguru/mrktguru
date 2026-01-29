"""
Scheduler Worker for Warmup Automation
Celery tasks for checking and executing scheduled warmup nodes
"""
import sys
# Increase recursion limit for heavy async operations
sys.setrecursionlimit(5000)

import logging
from datetime import datetime, time, timedelta
import random
from celery_app import celery
from models.warmup_schedule import WarmupSchedule
from models.warmup_schedule_node import WarmupScheduleNode
from models.warmup_log import WarmupLog
from modules.nodes import execute_node
from modules.telethon import ClientFactory
from database import db
from utils.proxy_manager import release_dynamic_port 
from utils.proxy_manager import release_dynamic_port 
from utils.redis_logger import setup_redis_logging, redis_client # Added redis_client

logger = logging.getLogger(__name__)

# Setup Redis logging
setup_redis_logging()


@celery.task(name='workers.scheduler_worker.check_warmup_schedules')
def check_warmup_schedules():
    """
    Periodic task (runs every minute) to check all active schedules
    and execute pending nodes that are due
    """
    from app import app
    from config import Config
    import pytz
    
    with app.app_context():
        try:
            tz = pytz.timezone(Config.TIMEZONE)
            now = datetime.now(tz)
            logger.info(f"Checking warmup schedules at {now}")
            
            # Find all active schedules
            schedules = WarmupSchedule.query.filter_by(status='active').all()
            
            if not schedules:
                logger.debug("No active schedules found")
                return
            
            logger.info(f"Found {len(schedules)} active schedule(s)")
            
            for schedule in schedules:
                try:
                    # Calculate current day number (1-14)
                    if not schedule.start_date:
                        logger.warning(f"Schedule {schedule.id} has no start_date, skipping")
                        continue
                    
                    # DATE-BASED SCHEDULING
                    # We now strictly check for nodes scheduled for TODAY's date.
                    today_date = now.date()
                    
                    # Check if schedule is completed (legacy check based on days or if end_date passed)
                    if schedule.end_date and today_date > schedule.end_date:
                         logger.info(f"Schedule {schedule.id} past end date {schedule.end_date}")
                         schedule.status = 'completed'
                         db.session.commit()
                         continue

                    # Find pending nodes for TODAY (execution_date)
                    # Use fallback to day_number if execution_date is null (legacy support)
                    
                    # Logic: 
                    # 1. Fetch nodes where execution_date == today
                    # 2. OR where execution_date is NULL AND day_number == (today - start + 1)
                    
                    days_elapsed = (today_date - schedule.start_date).days
                    day_number = days_elapsed + 1
                    
                    logger.info(f"Schedule {schedule.id}: Checking for nodes on {today_date} (Day {day_number})")
                    
                    nodes = WarmupScheduleNode.query.filter(
                        WarmupScheduleNode.schedule_id == schedule.id,
                        WarmupScheduleNode.status == 'pending',
                        db.or_(
                            WarmupScheduleNode.execution_date <= today_date,
                            db.and_(
                                WarmupScheduleNode.execution_date == None,
                                WarmupScheduleNode.day_number <= day_number
                            )
                        )
                    ).all()
                    

                    
                    
                    # Check for empty nodes list and log next pending
                    if not nodes:
                        # Fetch info about next pending node
                        next_node = WarmupScheduleNode.query.filter_by(
                            schedule_id=schedule.id,
                            status='pending'
                        ).order_by(WarmupScheduleNode.day_number.asc(), WarmupScheduleNode.execution_time.asc()).first()
                        
                        msg = f"No pending nodes for schedule {schedule.id} today ({today_date})."
                        if next_node:
                            exec_date_info = f"Date={next_node.execution_date}" if next_node.execution_date else "Date=Not Set"
                            msg += f" Next task: Node {next_node.id} ({next_node.node_type}) on Day {next_node.day_number} ({exec_date_info}) at {next_node.execution_time}"
                        else:
                            msg += " No future tasks found."
                            
                        logger.info(msg)
                        continue
                    
                    # Check if there are any currently running nodes for this schedule
                    # We want to strictly enforce SERIAL execution per account to avoid collisions
                    running_nodes_count = WarmupScheduleNode.query.filter_by(
                        schedule_id=schedule.id,
                        status='running'
                    ).count()
                    
                    if running_nodes_count > 0:
                        # Check if any running node is stuck (e.g. running > 60 mins)
                        stuck_nodes = WarmupScheduleNode.query.filter_by(
                            schedule_id=schedule.id,
                            status='running'
                        ).all()
                        
                        has_active_running = False
                        for r_node in stuck_nodes:
                            # Use execution_started_at (set when status→running) instead of updated_at
                            # This prevents false positives when nodes are edited but not yet running
                            execution_start = r_node.execution_started_at or r_node.updated_at  # Fallback for old nodes
                            current_now = now
                            
                            # If DB time is naive (common), make 'now' naive for comparison
                            if execution_start and execution_start.tzinfo is None and current_now.tzinfo is not None:
                                current_now = current_now.replace(tzinfo=None)
                            
                            if execution_start and execution_start < current_now - timedelta(minutes=120):
                                logger.warning(f"Node {r_node.id} appears stuck (running since {execution_start}). Marking as failed.")
                                r_node.status = 'failed'
                                r_node.error_message = "Timeout: Execution stuck for > 120 mins"
                                r_node.executed_at = now
                                db.session.commit()
                                WarmupLog.log(schedule.account_id, 'error', f"Node {r_node.id} timed out (stuck)", action='timeout_error')
                            else:
                                has_active_running = True
                                logger.info(f"Node {r_node.id} is currently running (started {execution_start})")
                        
                        if has_active_running:
                            logger.info(f"Schedule {schedule.id} has active running nodes. Waiting for completion.")
                            continue

                    logger.info(f"Schedule {schedule.id}: Found {len(nodes)} pending node(s) for day {day_number}")
                    # Log details of each candidate
                    for n in nodes:
                         d_str = str(n.execution_date) if n.execution_date else "None"
                         logger.info(f"  -> Candidate Node {n.id}: Type={n.node_type}, Date={d_str}, Time={n.execution_time}")
                    
                    # === SMART STACKING & SERIAL EXECUTION ===
                    # 1. Collect all executable candidates for this schedule
                    executable_candidates = []
                    
                    for node in nodes:
                        # Safety: Only execute PENDING nodes (skip 'draft')
                        if node.status != 'pending':
                            continue

                        # Check expiration (skip if > 15 mins late)
                        if is_node_expired(node, now):
                            logger.info(f"Node {node.id} expired (Target: {node.execution_time}). Skipping.")
                            node.status = 'skipped'
                            node.executed_at = now
                            db.session.commit()
                            continue

                        if should_execute_now(node, now):
                            executable_candidates.append(node)
                        else:
                            # logger.debug(f"Node {node.id} not ready yet (time: {node.execution_time})")
                            pass

                    if not executable_candidates:
                         continue
                         
                    if not executable_candidates:
                         continue
                         
                    # 2. Sort by Date -> Time -> ID to match frontend Ordinal Logic
                    def sort_key(n):
                         d_str = str(n.execution_date) if n.execution_date else '1970-01-01'
                         t_str = n.execution_time or '00:00'
                         return (d_str, t_str, n.id)
                    
                    executable_candidates.sort(key=sort_key)
                    
                    # 3. Pick the Target Node (The first one)
                    target_node = executable_candidates[0]
                    
                    # 3.1 Calculate Ordinal ID (Dynamic)
                    # Count nodes with (date,time,id) < target
                    # Efficient Sort Key tuple comparison in DB is hard, so we just sort all nodes in memory or query simple count
                    # Optimisation: We already know this node's position relative to *pending* nodes, but we need Global Ordinal.
                    # Let's do a quick query for Global Ordinal
                    try:
                        all_sch_nodes = WarmupScheduleNode.query.filter_by(schedule_id=schedule.id).all()
                        all_sch_nodes.sort(key=sort_key)
                        target_ordinal = next((i for i, n in enumerate(all_sch_nodes, 1) if n.id == target_node.id), '?')
                    except:
                        target_ordinal = '?'

                    # 4. Check Distributed Lock (Is account busy?)
                    lock_key = f"lock:account:{schedule.account_id}"
                    if redis_client.get(lock_key):
                         logger.info(f"[{schedule.account_id}] ⏳ Account is busy (Redis Lock). Queuing Node #{target_ordinal} ({target_node.id}).")
                         # We do nothing. Node stays 'pending'. Worker will pick it up next tick when lock is free.
                         continue
                    
                    # 5. Check 'Running' DB status (Legacy/Manual check)
                    # (Optional but good for safety if Redis fails or was flushed)
                    if schedule.account and schedule.account.status == 'flood_wait':
                         # Skip if flood wait (redundant as should_execute_now checks it, but safe)
                         continue

                    # 6. Execute!
                    logger.info(f"[{schedule.account_id}] 🚀 Smart Stack: Executing Node #{target_ordinal} (ID {target_node.id}, Type: {target_node.node_type})")
                    execute_scheduled_node.delay(target_node.id)
                    
                    # Stop processing this schedule for this tick (only 1 execute per account per tick)
                    continue
                
                except Exception as e:
                    logger.error(f"Error processing schedule {schedule.id}: {e}")
                    continue
            
            logger.info("Schedule check completed")
            
        except Exception as e:
            logger.error(f"Error in check_warmup_schedules: {e}")


def should_execute_now(node, current_time):
    """
    Determine if a node should execute at the current time
    
    Args:
        node: WarmupScheduleNode instance
        current_time: datetime object
    
    Returns:
        bool: True if node should execute now
    """
    from models.account import Account
    
    # Check if account is in flood_wait status
    account = node.schedule.account
    if account.status == 'flood_wait' and account.flood_wait_until:
        if account.flood_wait_until > current_time:
            logger.debug(f"Account {account.id} in flood_wait until {account.flood_wait_until}, skipping node {node.id}")
            return False
        else:
            # Flood wait expired, clear status
            account.status = 'active'
            account.flood_wait_until = None
            account.flood_wait_action = None
            db.session.commit()
            logger.info(f"Account {account.id} flood_wait expired, resuming")
    
    if not node.execution_time:
        # No time specified, execute immediately
        return True
    
    current_hour = current_time.hour
    current_minute = current_time.minute
    
    if node.is_random_time:
        # Random time format: "random:10:00-18:00"
        start_time_str, end_time_str = node.get_execution_time_range()
        
        if not start_time_str or not end_time_str:
            return True
        
        # Parse time strings
        start_hour, start_min = map(int, start_time_str.split(':'))
        end_hour, end_min = map(int, end_time_str.split(':'))
        
        # Check if current time is within range
        current_minutes = current_hour * 60 + current_minute
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        if start_minutes <= current_minutes <= end_minutes:
            # Within range, execute with 10% probability per minute
            # This spreads execution randomly across the time window
            return random.random() < 0.1
        
        return False
    
    else:
        # Fixed time format: "14:00" or "14:00:00"
        try:
            parts = node.execution_time.split(':')
            if len(parts) < 2:
                 raise ValueError("Invalid format")
            
            target_hour = int(parts[0])
            target_min = int(parts[1])
            
            # Convert to minutes for easier comparison
            target_total = target_hour * 60 + target_min
            current_total = current_hour * 60 + current_minute
            
            # Execute if:
            # 1. We are exactly on time or slightly early (diff >= -1)
            # 2. We are late but within catch-up window (diff <= 15) or even 30 to be safe
            
            diff = current_total - target_total
            
            # Log specific check details for debugging
            logger.info(f"Node {node.id} Check: Target={target_hour:02d}:{target_min:02d} ({target_total}m), Now={current_hour:02d}:{current_minute:02d} ({current_total}m), Diff={diff}")
            
            # Execute if time has arrived (diff >= -1).
            # Remove upper bound to allow "Supernode" (sequential) catch-up regardless of delay.
            if diff >= -1:
                 return True
                 
            return False
        
        except Exception as e:
            logger.error(f"Error checking time for node {node.id} ('{node.execution_time}'): {e}")
            # If time is invalid, maybe we SHOULD execute it to process it? 
            # Or better, return False so we don't spam.
            # But previous logic returned True. Let's return False to be safe and avoid loops.
            return False


def is_node_expired(node, current_time, threshold_minutes=1440): # Default 24h (effectively disabled for same day)
    """Check if node execution time is passed by threshold"""
    if not node.execution_time or node.is_random_time:
        return False # Random/Immediate nodes don't expire simple way
        
    try:
        t_hour, t_min = map(int, node.execution_time.split(':'))
        
        # Compare with current time (same day assumed as we filtered by day)
        target_dt = current_time.replace(hour=t_hour, minute=t_min, second=0, microsecond=0)
        
        # If target is more than threshold in the past
        if current_time > target_dt + timedelta(minutes=threshold_minutes):
            return True
            
        return False
    except:
        return False



# 🔥 GLOBAL SESSION CACHE
# Stores live SessionOrchestrator objects between tasks
ACTIVE_SESSIONS = {} 

@celery.task(name='workers.scheduler_worker.execute_scheduled_node')
def execute_scheduled_node(node_id, is_adhoc=False):
    # Ensure redis logging is setup in this worker process
    setup_redis_logging()
    
    from app import app
    
    with app.app_context():
        try:
            node = WarmupScheduleNode.query.get(node_id)
            if not node:
                return
                
            # If it's already completed or failed, don't re-run
            if node.status in ['completed', 'failed', 'skipped']:
                logger.info(f"Node {node_id} already in final status {node.status}. Skipping.")
                return
                
            # If it's already running and NOT an adhoc request (user 'Run Now'), abort
            # This prevents overlapping scheduler runs from doubling the task
            if node.status == 'running' and not is_adhoc:
                logger.warning(f"Node {node_id} is already RUNNING. Aborting duplicate scheduler trigger.")
                return

            if node.status != 'running':
                node.status = 'running'
                node.execution_started_at = datetime.now()  # Track actual execution start time
                db.session.commit()
            
            account_id = node.schedule.account_id
            logger.info(f"▶️ Executing node {node_id}: {node.node_type} for account {account_id}")

            # --- DISTRIBUTED LOCK CHECK ---
            lock_key = f"lock:account:{account_id}"
            # TTL 30 mins (1800s) to match heavy tasks 
            is_locked = redis_client.set(lock_key, "locked", nx=True, ex=1800)
            
            if not is_locked:
                logger.warning(f"[{account_id}] ⚠️ Account is busy! Skipping overlapping task {node_id} (Race Condition).")
                # Do NOT mark as failed. Likely another worker picked it up or just finished.
                # If we mark failed, we might overwrite the actual running task's status or confuse user.
                WarmupLog.log(account_id, 'warning', f"Skipped overlap task {node_id}", action='lock_overlap')
                db.session.rollback() # Rollback status='running' change from this session
                return

            try:
                # --- ORCHESTRATOR LOGIC WITH CACHING ---
                from modules.telethon import SessionOrchestrator
                import asyncio
                
                async def run_with_orchestrator():
                    # 1. Check for live session
                    orch = ACTIVE_SESSIONS.get(account_id)
                    
                    # If no session or disconnected -> create new
                    if not orch or not orch.client or not orch.client.is_connected():
                        if account_id in ACTIVE_SESSIONS:
                            del ACTIVE_SESSIONS[account_id] # Cleaning
                        
                        orch = SessionOrchestrator(account_id)
                        ACTIVE_SESSIONS[account_id] = orch
                        
                        # 🔥 IMPORTANT: Start monitor so it auto-kills session after 10-15 min
                        await orch.start_monitoring()
                        logger.info(f"[{account_id}] Created NEW SessionOrchestrator (Cached)")
                    else:
                        logger.info(f"[{account_id}] ♻️ Reusing EXISTING active session")

                    # 2. Task Wrapper
                    async def task_wrapper(client):
                        # Connection check
                        if not client.is_connected():
                             await client.connect()
                        
                        if not await client.is_user_authorized():
                             raise Exception("Client not authorized")

                        return await execute_node(
                            client,
                            node.node_type,
                            account_id,
                            node.config or {}
                        )
                
                # 3. Execute
                # ❌ WE REMOVED FINALLY WITH ORCH.STOP()
                # Session stays in ACTIVE_SESSIONS
                    return await orch.execute(task_wrapper)

                # Run on global background loop
                try:
                    from utils.bg_loop import BackgroundLoop
                    result = BackgroundLoop.submit(run_with_orchestrator())
                except Exception as loop_e:
                     logger.exception(f"Orchestrator error: {loop_e}")
                     result = {'success': False, 'error': str(loop_e)}
                     
                     # On crash, remove from cache to start fresh next time
                     if account_id in ACTIVE_SESSIONS:
                         del ACTIVE_SESSIONS[account_id]

                # --- RESULT HANDLING (Same as before) ---
                if result and result.get('success'):
                    node.status = 'completed'
                    node.executed_at = datetime.now()
                    node.schedule.account.last_activity = datetime.now()
                    WarmupLog.log(account_id, 'success', f"{node.node_type} completed", action=f'{node.node_type}_complete')
                else:
                    # Check for FLOOD_WAIT
                    if result and result.get('flood_wait'):
                        account = node.schedule.account
                        if account and result.get('flood_wait_until'):
                            account.status = 'flood_wait'
                            account.flood_wait_until = result['flood_wait_until']
                            account.flood_wait_action = node.node_type
                            account.last_flood_wait = datetime.now()
                            account.flood_wait_reason = f"Warmup {node.node_type}"
                            logger.critical(f"FLOOD_WAIT triggered for account {account_id}")
                            WarmupLog.log(account_id, 'critical', f"FLOOD_WAIT until {account.flood_wait_until}", action='flood_wait_critical')
                    
                    # Check for BAN
                    err_msg = (result.get('error') or '').lower()
                    if 'banned' in err_msg or 'userdeactivated' in err_msg:
                        account = node.schedule.account
                        logger.critical(f"[{account_id}] ❌ ACCOUNT BANNED! Marking as banned and releasing port.")
                        account.status = 'banned'
                        
                        # AUTO-RELEASE PORT
                        if account.assigned_port:
                             if release_dynamic_port(account):
                                 logger.info(f"[{account_id}] Port released.")
                        
                        WarmupLog.log(account_id, 'critical', "Account Banned", action='account_banned')
                        db.session.commit()

                    node.status = 'failed'
                    node.error_message = result.get('error', 'Unknown error') if result else 'Unknown'
                    node.executed_at = datetime.now()
                    WarmupLog.log(account_id, 'error', f"Node failed: {node.error_message}", action=f'{node.node_type}_error')

                db.session.commit()
            
            finally:
                # RELEASE LOCK
                redis_client.delete(lock_key)
                logger.info(f"[{account_id}] 🔓 Lock released.")

        except Exception as e:
            logger.exception(f"System error node {node_id}: {e}")


@celery.task(name='workers.scheduler_worker.execute_adhoc_node')
def execute_adhoc_node(account_id, node_type, config):
    setup_redis_logging()
    
    from app import app
    
    with app.app_context():
        try:
            logger.info(f"Executing ADHOC node: {node_type} for account {account_id}")
            
            # --- DISTRIBUTED LOCK CHECK ---
            lock_key = f"lock:account:{account_id}"
            is_locked = redis_client.set(lock_key, "locked", nx=True, ex=1800)
            
            if not is_locked:
                 logger.warning(f"[{account_id}] ⚠️ Account is busy! Skipping ADHOC task.")
                 # For adhoc we just return, maybe logging to notify user could be nice but no DB node to update
                 return

            # Wrapper to keep indentation
            if True:
                from modules.telethon import SessionOrchestrator
                import asyncio
                
                async def run_with_orchestrator():
                    # CACHING LOGIC
                    orch = ACTIVE_SESSIONS.get(account_id)
                    
                    if not orch or not orch.client or not orch.client.is_connected():
                        if account_id in ACTIVE_SESSIONS: del ACTIVE_SESSIONS[account_id]
                        orch = SessionOrchestrator(account_id)
                        ACTIVE_SESSIONS[account_id] = orch
                        await orch.start_monitoring() # Start auto-kill timer
                        logger.info(f"[{account_id}] Adhoc: Created NEW session")
                    else:
                        logger.info(f"[{account_id}] Adhoc: Reusing EXISTING session")

                    async def task_wrapper(client):
                        if not client.is_connected(): await client.connect()
                        return await execute_node(client, node_type, account_id, config)
                    
                    # NO finally: stop()
                    return await orch.execute(task_wrapper)

            try:
                from utils.bg_loop import BackgroundLoop
                result = BackgroundLoop.submit(run_with_orchestrator())
            except Exception as e:
                logger.error(f"Adhoc Orchestrator error: {e}")
                if account_id in ACTIVE_SESSIONS: del ACTIVE_SESSIONS[account_id]
                result = {'success': False, 'error': str(e)}
            
            # Log result
            if result and result.get('success'):
                logger.info(f"Adhoc {node_type} success")
                from models.account import Account
                account = Account.query.get(account_id)
                if account:
                    account.last_activity = datetime.now()
                    db.session.commit()
            else:
                logger.error(f"Adhoc {node_type} failed")

        except Exception as e:
            logger.error(f"Error in execute_adhoc_node: {e}")

        finally:
             # RELEASE LOCK
             redis_client.delete(lock_key)
             logger.info(f"[{account_id}] 🔓 Adhoc Lock released.")
