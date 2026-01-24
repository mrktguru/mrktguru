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
                        logger.debug(f"No pending nodes for schedule {schedule.id} day {day_number}")
                        continue
                    
                    # Check if there are any currently running nodes for this schedule
                    # We want to strictly enforce SERIAL execution per account to avoid collisions
                    running_nodes_count = WarmupScheduleNode.query.filter_by(
                        schedule_id=schedule.id,
                        status='running'
                    ).count()
                    
                    if running_nodes_count > 0:
                        logger.debug(f"Schedule {schedule.id} has {running_nodes_count} running nodes. Skipping new checks to prevent parallel execution.")
                        continue

                    logger.info(f"Schedule {schedule.id}: Found {len(nodes)} pending node(s) for day {day_number}")
                    
                    # Check each node if it should execute now
                    for node in nodes:
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
            
            # Execute if current time matches (within 1 minute window)
            # LOGGING DEBUG
            logger.info(f"Checking node {node.id}: Target={target_hour}:{target_min} vs Current={current_hour}:{current_minute}")
            
            if current_hour == target_hour and abs(current_minute - target_min) <= 1:
                return True
            
            return False
        
        except:
            logger.error(f"Invalid execution_time format for node {node.id}: {node.execution_time}")
            return True


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
            
            if node.status != 'pending':
                logger.warning(f"Node {node_id} status is {node.status}, skipping")
                return
            
            # Update status to running
            node.status = 'running'
            db.session.commit()
            
            account_id = node.schedule.account_id
            
            logger.info(f"Executing node {node_id}: {node.node_type} for account {account_id}")
            WarmupLog.log(account_id, 'info', f"Starting {node.node_type} node", action=f'{node.node_type}_start')
            
            # Get Telethon client
            client = get_telethon_client(account_id)
            
            if not client:
                error_msg = "Failed to get Telethon client"
                logger.error(error_msg)
                node.status = 'failed'
                node.error_message = error_msg
                node.executed_at = datetime.now()
                db.session.commit()
                WarmupLog.log(account_id, 'error', error_msg, action=f'{node.node_type}_error')
                return
            
            # Execute node using async wrapper
            import asyncio
            result = asyncio.run(execute_node(
                node.node_type,
                client,
                account_id,
                node.config or {}
            ))
            
            # Update node status based on result
            if result.get('success'):
                node.status = 'completed'
                node.executed_at = datetime.now()
                logger.info(f"Node {node_id} completed successfully")
                WarmupLog.log(account_id, 'success', f"{node.node_type} node completed", action=f'{node.node_type}_complete')
            else:
                # Check if this is a FLOOD_WAIT error
                if result.get('flood_wait'):
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
                node.error_message = result.get('error', 'Unknown error')
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
            logger.error(f"Error executing node {node_id}: {e}")
            
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
