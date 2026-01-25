"""
Scheduler Worker for Warmup Automation
Celery tasks for checking and executing scheduled warmup nodes
"""
import logging
from datetime import datetime, time, timedelta
import random
from celery_app import celery
from models.warmup_schedule import WarmupSchedule
from models.warmup_schedule_node import WarmupScheduleNode
from models.warmup_log import WarmupLog
from workers.node_executors import execute_node
from utils.telethon_helper import get_telethon_client
from database import db

logger = logging.getLogger(__name__)


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
                    
                    days_elapsed = (now.date() - schedule.start_date).days
                    day_number = days_elapsed + 1
                    
                    # DIAGNOSTIC LOG
                    logger.info(f"Schedule {schedule.id}: Start={schedule.start_date}, Now={now.date()}, Day={day_number}")

                    # Check if schedule is completed
                    if day_number > 14:
                        logger.info(f"Schedule {schedule.id} completed (day {day_number})")
                        schedule.status = 'completed'
                        schedule.end_date = now.date()
                        db.session.commit()
                        continue
                    
                    # Find pending nodes for current day
                    nodes = WarmupScheduleNode.query.filter_by(
                        schedule_id=schedule.id,
                        day_number=day_number,
                        status='pending'
                    ).all()
                    
                    if not nodes:
                        # Fetch ALL pending nodes to see where they are
                        all_pending = WarmupScheduleNode.query.filter_by(
                            schedule_id=schedule.id,
                            status='pending'
                        ).count()
                        logger.info(f"No pending nodes for schedule {schedule.id} day {day_number}. (Total pending in schedule: {all_pending})")
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
                            # If updated_at is older than 60 mins, it's stuck
                            if r_node.updated_at < now - timedelta(minutes=60):
                                logger.warning(f"Node {r_node.id} appears stuck (running since {r_node.updated_at}). Marking as failed.")
                                r_node.status = 'failed'
                                r_node.error_message = "Timeout: Execution stuck for > 60 mins"
                                r_node.executed_at = now
                                db.session.commit()
                                WarmupLog.log(schedule.account_id, 'error', f"Node {r_node.id} timed out (stuck)", action='timeout_error')
                            else:
                                has_active_running = True
                                logger.info(f"Node {r_node.id} is currently running (started {r_node.updated_at})")
                        
                        if has_active_running:
                            logger.info(f"Schedule {schedule.id} has active running nodes. Waiting for completion.")
                            continue

                    logger.info(f"Schedule {schedule.id}: Found {len(nodes)} pending node(s) for day {day_number}")
                    
                    # Check each node if it should execute now
                    for node in nodes:
                        # Check expiration (skip if > 15 mins late)
                        if is_node_expired(node, now):
                            logger.info(f"Node {node.id} expired (Target: {node.execution_time}). Skipping.")
                            node.status = 'skipped'
                            node.executed_at = now
                            db.session.commit()
                            continue

                        if should_execute_now(node, now):
                            logger.info(f"Executing node {node.id} ({node.node_type}) for account {schedule.account_id}")
                            execute_scheduled_node.delay(node.id)
                        else:
                            logger.debug(f"Node {node.id} not ready yet (time: {node.execution_time})")
                
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
        # Fixed time format: "14:00"
        try:
            target_hour, target_min = map(int, node.execution_time.split(':'))
            
            # Convert to minutes for easier comparison
            target_total = target_hour * 60 + target_min
            current_total = current_hour * 60 + current_minute
            
            # Handle day rollover comparison conceptually (though usually we filter by day_number)
            # If target is 23:59 and current is 00:05 (next day), logic might differ, 
            # but here we rely on the main loop selecting `nodes` for `day_number`.
            # Assuming 'now' matches 'day_number' approximately.
            
            # LOGGING DEBUG
            # logger.info(f"Checking node {node.id}: Target={target_hour}:{target_min} vs Current={current_hour}:{current_minute}")
            
            # Allow execution if we are ON TIME or LATE (Catch-up)
            # But not if we are TOO LATE (expired handled by is_node_expired, usually > 15m)
            # And not if we are too early (wait)
            
            diff = current_total - target_total
            
            # Execute if:
            # 1. We are exactly on time or slightly early (diff >= -1)
            # 2. We are late but within catch-up window (diff <= 15)
            # Note: is_node_expired checks > 15. So here we handle <= 15.
            
            if -1 <= diff <= 15:
                 return True
                 
            return False
        
        except:
            logger.error(f"Invalid execution_time format for node {node.id}: {node.execution_time}")
            return True


def is_node_expired(node, current_time, threshold_minutes=15):
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



@celery.task(name='workers.scheduler_worker.execute_scheduled_node')
def execute_scheduled_node(node_id):
    """
    Execute a single scheduled warmup node
    
    Args:
        node_id: ID of WarmupScheduleNode to execute
    """
    from app import app
    
    with app.app_context():
        try:
            node = WarmupScheduleNode.query.get(node_id)
            
            if not node:
                logger.error(f"Node {node_id} not found")
                return
            
            if node.status not in ['pending', 'running']:
                logger.warning(f"Node {node_id} status is {node.status}, skipping")
                return
            
            # Update status to running (if not already)
            if node.status != 'running':
                node.status = 'running'
                db.session.commit()
            
            account_id = node.schedule.account_id
            
            logger.info(f"Executing node {node_id}: {node.node_type} for account {account_id}")
            WarmupLog.log(account_id, 'info', f"Starting {node.node_type} node", action=f'{node.node_type}_start')
            
            # Execute node using SessionOrchestrator
            from utils.session_orchestrator import SessionOrchestrator
            import asyncio
            
            async def run_with_orchestrator():
                logger.info(f"SessionOrchestrator initializing for account {account_id}")
                orch = SessionOrchestrator(account_id)
                try:
                    # Inner function passed to orchestrator
                    async def task_wrapper(client):
                        logger.info(f"Task wrapper received client. Connected: {client.is_connected()}")
                        
                        if not client.is_connected():
                             logger.warning("⚠️ Client disconnected in wrapper! Forcing connection...")
                             await client.connect()
                        
                        # Verify auth
                        if not await client.is_user_authorized():
                             return {'success': False, 'error': 'Client not authorized (checked in wrapper)'}

                        return await execute_node(
                            client,
                            node.node_type,
                            account_id,
                            node.config or {}
                        )
                    
                    logger.info("Calling orch.execute(task_wrapper)...")
                    res = await orch.execute(task_wrapper)
                    logger.info("orch.execute finished.")
                    return res
                finally:
                    logger.info("Calling orch.stop()...")
                    try:
                        await orch.stop()
                        logger.info("orch.stop() finished.")
                    except Exception as e:
                         # Log but don't crash the result if the task actually succeeded
                         logger.error(f"Error in orch.stop(): {e}")
                         if "NoneType" in str(e) and "await" in str(e):
                             logger.critical("Detecting the Async NoneType error in orch.stop()!")

            try:
                result = asyncio.run(run_with_orchestrator())
            except Exception as loop_e:
                 logger.exception(f"Orchestrator error: {loop_e}")
                 result = {'success': False, 'error': f"Orchestrator failed: {loop_e}"}
            
            # Update node status based on result
            if result and result.get('success'):
                node.status = 'completed'
                node.executed_at = datetime.now()
                logger.info(f"Node {node_id} completed successfully")
                WarmupLog.log(account_id, 'success', f"{node.node_type} node completed", action=f'{node.node_type}_complete')
            else:
                # Check if this is a FLOOD_WAIT error
                if result and result.get('flood_wait'):
                    # Critical: Update account status and pause entire warmup
                    account = Account.query.get(account_id)
                    if account and result.get('flood_wait_until'):
                        account.status = 'flood_wait'
                        account.flood_wait_until = result['flood_wait_until']
                        account.flood_wait_action = node.node_type
                        account.last_flood_wait = datetime.now()
                        logger.critical(f"FLOOD_WAIT triggered for account {account_id} until {account.flood_wait_until}")
                        WarmupLog.log(account_id, 'critical', f"FLOOD_WAIT: All warmup paused until {account.flood_wait_until}", action='flood_wait_critical')
                
                node.status = 'failed'
                node.error_message = result.get('error', 'Unknown error') if result else 'Unknown error'
                node.executed_at = datetime.now()
                logger.error(f"Node {node_id} failed: {node.error_message}")
                WarmupLog.log(account_id, 'error', f"{node.node_type} failed: {node.error_message}", action=f'{node.node_type}_error')
            
            db.session.commit()
            
            # Disconnect client
            try:
                import asyncio
                asyncio.run(client.disconnect())
            except:
                pass
            
        except Exception as e:
            logger.exception(f"Error executing node {node_id}: {e}")
            
            try:
                node = WarmupScheduleNode.query.get(node_id)
                if node:
                    node.status = 'failed'
                    node.error_message = str(e)
                    node.executed_at = datetime.now()
                    db.session.commit()
                    
                    if node.schedule:
                        WarmupLog.log(
                            node.schedule.account_id,
                            'error',
                            f"Node execution failed: {str(e)}",
                            action=f'{node.node_type}_error'
                        )
            except:
                pass

@celery.task(name='workers.scheduler_worker.execute_adhoc_node')
def execute_adhoc_node(account_id, node_type, config):
    """
    Execute a node immediately (adhoc) without a schedule record
    """
    from app import app
    from models.account import Account
    
    with app.app_context():
        try:
            logger.info(f"Executing ADHOC node: {node_type} for account {account_id}")
            WarmupLog.log(account_id, 'info', f"Starting manual {node_type} execution", action=f'{node_type}_manual_start')
            
            # Execute logic
            from utils.session_orchestrator import SessionOrchestrator
            import asyncio
            
            async def run_with_orchestrator():
                orch = SessionOrchestrator(account_id)
                try:
                    async def task_wrapper(client):
                        if not client.is_connected():
                             await client.connect()
                        
                        return await execute_node(
                            client,
                            node_type,
                            account_id,
                            config
                        )
                    return await orch.execute(task_wrapper)
                finally:
                    await orch.stop()

            try:
                result = asyncio.run(run_with_orchestrator())
            except Exception as loop_e:
                 logger.exception(f"Orchestrator error: {loop_e}")
                 result = {'success': False, 'error': f"Orchestrator failed: {loop_e}"}
            
            if result and result.get('success'):
                logger.info(f"Adhoc node {node_type} completed")
                WarmupLog.log(account_id, 'success', f"Manual {node_type} completed", action=f'{node_type}_manual_complete')
            else:
                error = result.get('error', 'Unknown error') if result else 'Unknown error'
                logger.error(f"Adhoc node {node_type} failed: {error}")
                WarmupLog.log(account_id, 'error', f"Manual {node_type} failed: {error}", action=f'{node_type}_manual_error')
                
        except Exception as e:
            logger.error(f"Error in execute_adhoc_node: {e}")
            WarmupLog.log(account_id, 'error', f"System error executing {node_type}: {str(e)}", action='system_error')
