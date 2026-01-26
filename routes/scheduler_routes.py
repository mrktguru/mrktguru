"""
Scheduler Routes - REST API for Warmup Scheduler
CRUD operations for schedules and nodes
"""
from flask import Blueprint, request, jsonify
from database import db
from models.warmup_schedule import WarmupSchedule
from models.warmup_schedule_node import WarmupScheduleNode
from models.account import Account
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
import logging

logger = logging.getLogger(__name__)

scheduler_bp = Blueprint('scheduler', __name__, url_prefix='/scheduler')


@scheduler_bp.route('/accounts/<int:account_id>/schedule', methods=['GET'])
def get_schedule(account_id):
    """Get warmup schedule for an account"""
    try:
        schedule = WarmupSchedule.query.filter_by(account_id=account_id).first()
        
        if not schedule:
            # Create dummy schedule dict if none exists, to allow showing logs
            schedule_dict = {'id': 0, 'status': 'draft'}
        else:
            schedule_dict = schedule.to_dict()
            
        # Get all nodes for this schedule
        nodes = []
        if schedule:
            nodes = WarmupScheduleNode.query.filter_by(schedule_id=schedule.id).all()
        
        node_dicts = [node.to_dict() for node in nodes]

        # ---------------------------------------------------------
        # BACKFILL: Fetch historical logs and convert to ghost nodes
        # ---------------------------------------------------------
        ghost_nodes = _get_ghost_nodes(account_id, schedule.id if schedule else 0)
        node_dicts.extend(ghost_nodes)

        return jsonify({
            'schedule': schedule_dict,
            'nodes': node_dicts
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting schedule: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/accounts/<int:account_id>/schedule', methods=['POST'])
def create_schedule(account_id):
    """Create new warmup schedule for an account"""
    try:
        # Check if account exists
        account = Account.query.get(account_id)
        if not account:
            return jsonify({'error': 'Account not found'}), 404
        
        # Check if schedule already exists
        existing = WarmupSchedule.query.filter_by(account_id=account_id).first()
        if existing:
            return jsonify({'error': 'Schedule already exists'}), 400
        
        data = request.json or {}
        
        # Create schedule
        schedule = WarmupSchedule(
            account_id=account_id,
            name=data.get('name', f'Warmup Schedule - {account.username or account.phone}'),
            status='draft',
            start_date=account.created_at.date() if account.created_at else datetime.now().date()
        )
        
        db.session.add(schedule)
        db.session.commit()
        
        logger.info(f"Created schedule {schedule.id} for account {account_id}")
        
        return jsonify({'schedule': schedule.to_dict()}), 201
        
    except Exception as e:
        logger.error(f"Error creating schedule: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>', methods=['PUT'])
def update_schedule(schedule_id):
    """Update schedule (name, status)"""
    try:
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        data = request.json or {}
        
        if 'name' in data:
            schedule.name = data['name']
        
        if 'status' in data:
            schedule.status = data['status']
        
        schedule.updated_at = datetime.now()
        db.session.commit()
        
        return jsonify({'schedule': schedule.to_dict()}), 200
        
    except Exception as e:
        logger.error(f"Error updating schedule: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    """Delete schedule and all its nodes"""
    try:
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        db.session.delete(schedule)
        db.session.commit()
        
        logger.info(f"Deleted schedule {schedule_id}")
        
        return jsonify({'message': 'Schedule deleted'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting schedule: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>/nodes', methods=['POST'])
def add_node(schedule_id):
    """Add a node to schedule"""
    try:
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        data = request.json or {}
        
        # Validate required fields
        if 'node_type' not in data:
            return jsonify({'error': 'node_type is required'}), 400
        
        if 'day_number' not in data:
            return jsonify({'error': 'day_number is required'}), 400
        
        # Calculate execution date if schedule is active
        execution_date = None
        if schedule.start_date:
            from datetime import timedelta
            execution_date = schedule.start_date + timedelta(days=int(data['day_number']) - 1)
        
        # Create node
        node = WarmupScheduleNode(
            schedule_id=schedule_id,
            node_type=data['node_type'],
            day_number=data['day_number'],
            execution_date=execution_date,
            execution_time=data.get('execution_time'),
            is_random_time=data.get('is_random_time', False),
            config=data.get('config', {}),
            status='pending'
        )
        
        db.session.add(node)
        db.session.commit()
        
        logger.info(f"Added node {node.id} to schedule {schedule_id}")
        
        return jsonify({'node': node.to_dict()}), 201
        
    except Exception as e:
        logger.error(f"Error adding node: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/nodes/<int:node_id>', methods=['PUT'])
def update_node(node_id):
    """Update node configuration"""
    try:
        node = WarmupScheduleNode.query.get(node_id)
        if not node:
            return jsonify({'error': 'Node not found'}), 404
        
        data = request.json or {}
        
        # Update fields
        if 'day_number' in data:
            node.day_number = data['day_number']
            # Recalculate date if schedule is active
            if node.schedule and node.schedule.start_date:
                from datetime import timedelta
                node.execution_date = node.schedule.start_date + timedelta(days=int(node.day_number) - 1)
        
        if 'execution_time' in data:
            node.execution_time = data['execution_time']
        
        if 'is_random_time' in data:
            node.is_random_time = data['is_random_time']
        
        if 'config' in data:
            node.config = data['config']
        
        # Reset status if critical fields changed (so it runs again)
        # But NOT if just position changed? Arguably even then.
        # Simplest: always reset status to pending on update.
        node.status = 'pending'
        node.error_message = None
        
        node.updated_at = datetime.now()
        db.session.commit()
        
        return jsonify({'node': node.to_dict()}), 200
        
    except Exception as e:
        logger.error(f"Error updating node: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/nodes/<int:node_id>', methods=['DELETE'])
def delete_node(node_id):
    """Delete a node from schedule"""
    try:
        node = WarmupScheduleNode.query.get(node_id)
        if not node:
            return jsonify({'error': 'Node not found'}), 404
        
        db.session.delete(node)
        db.session.commit()
        
        logger.info(f"Deleted node {node_id}")
        
        return jsonify({'message': 'Node deleted'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting node: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>/start', methods=['POST'])
def start_schedule(schedule_id):
    """Start (activate) a schedule"""
    try:
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        if schedule.status == 'active':
            return jsonify({'error': 'Schedule is already active'}), 400
        
        # Set start date to today
        schedule.status = 'active'
        
        # USE CREATION DATE AS START DATE (to align Warmup Day 1 with Account Day 1)
        if schedule.account and schedule.account.created_at:
             schedule.start_date = schedule.account.created_at.date()
        else:
             schedule.start_date = datetime.now().date()
             
        schedule.end_date = schedule.start_date + timedelta(days=14)
        schedule.updated_at = datetime.now()
        
        db.session.commit()
        
        logger.info(f"Started schedule {schedule_id}")
        
        return jsonify({
            'message': 'Schedule started',
            'schedule': schedule.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Error starting schedule: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>/pause', methods=['POST'])
def pause_schedule(schedule_id):
    """Pause an active schedule"""
    try:
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        if schedule.status != 'active':
            return jsonify({'error': 'Schedule is not active'}), 400
        
        schedule.status = 'paused'
        schedule.updated_at = datetime.now()
        
        db.session.commit()
        
        logger.info(f"Paused schedule {schedule_id}")
        
        return jsonify({
            'message': 'Schedule paused',
            'schedule': schedule.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Error pausing schedule: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>/resume', methods=['POST'])
def resume_schedule(schedule_id):
    """Resume a paused schedule"""
    try:
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        if schedule.status != 'paused':
            return jsonify({'error': 'Schedule is not paused'}), 400
        
        schedule.status = 'active'
        schedule.updated_at = datetime.now()
        
        db.session.commit()
        
        logger.info(f"Resumed schedule {schedule_id}")
        
        return jsonify({
            'message': 'Schedule resumed',
            'schedule': schedule.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Error resuming schedule: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>/status', methods=['GET'])
def get_schedule_status(schedule_id, account_id=None):
    """Get detailed status of schedule execution"""
    try:
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        # Get all nodes grouped by status
        nodes = WarmupScheduleNode.query.filter_by(schedule_id=schedule_id).all()
        node_dicts = [node.to_dict() for node in nodes]
        
        # BACKFILL GHOST NODES (if account_id provided via kwargs or derived)
        # We need account_id. Schedule has it.
        ghost_nodes = _get_ghost_nodes(schedule.account_id, schedule_id)
        
        # Merge ghost nodes
        # Note: Ghost nodes are dictionaries, real nodes are models
        for ghost in ghost_nodes:
            # Add to list
            node_dicts.append(ghost)
            
            # Add to status counts (only completed ones usually)
            # Actually status_counts logic below iterates over 'nodes' (models).
            # We should probably update the iteration or the returned list.
        
        status_counts = {
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0
        }
        
        # Count real nodes
        for node in nodes:
            status_counts[node.status] = status_counts.get(node.status, 0) + 1
            
        # Count ghost nodes
        for g in ghost_nodes:
             status_counts[g['status']] = status_counts.get(g['status'], 0) + 1
        
        # Calculate progress
        total_nodes = len(nodes) + len(ghost_nodes)
        completed_nodes = status_counts['completed']
        progress_percent = (completed_nodes / total_nodes * 100) if total_nodes > 0 else 0
        
        # Calculate current day
        current_day = None
        if schedule.start_date:
            days_elapsed = (datetime.now().date() - schedule.start_date).days
            current_day = days_elapsed + 1
        
        return jsonify({
            'schedule': schedule.to_dict(),
            'current_day': current_day,
            'total_nodes': total_nodes,
            'status_counts': status_counts,
            'progress_percent': round(progress_percent, 1),
            'nodes': node_dicts,
            'account_info': {
                'username': schedule.account.username,
                'bio': schedule.account.bio
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting schedule status: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/accounts/<int:account_id>/status', methods=['GET'])
def get_account_schedule_status(account_id):
    """Get schedule status by account_id"""
    try:
        schedule = WarmupSchedule.query.filter_by(account_id=account_id).first()
        if not schedule:
            return jsonify({'schedule': None}), 200
        
        return get_schedule_status(schedule.id, account_id=account_id)
    except Exception as e:
        logger.error(f"Error getting account schedule status: {e}")
        return jsonify({'error': str(e)}), 500

def _get_ghost_nodes(account_id, schedule_id):
    """Helper to fetch historical logs and convert to ghost nodes"""
    from models.warmup_log import WarmupLog
    from models.account import Account
    
    nodes = []
    account = Account.query.get(account_id)
    # If no creation date, fallback to now (though logic requires it)
    created_at = account.created_at if (account and account.created_at) else datetime.now()
        
    # Fetch ALL successful logs
    logs = WarmupLog.query.filter_by(
        account_id=account_id, 
        status='success'
    ).all()
    
    ghost_id_counter = -1
    for log in logs:
        # --- FIXED DAY CALCULATION ---
        # Calculate diff in days
        delta_days = (log.timestamp.date() - created_at.date()).days
        
        # Day 1 = creation day. Day 0 (or negative) = before creation.
        day_num = delta_days + 1
        
        # If log is older than account creation (rare but possible), clamp to 1 or handled by UI
        if day_num < 1: 
             day_num = 1 

        time_str = log.timestamp.strftime('%H:%M')
        
        # Determine Node Type
        node_type = 'passive_activity' 
        if log.action_type == 'set_photo': node_type = 'photo'
        elif log.action_type == 'update_bio': node_type = 'bio'
        elif log.action_type == 'update_username': node_type = 'username'
        elif 'subscribe' in (log.action_type or ''): node_type = 'subscribe'
        elif 'visit' in (log.action_type or ''): node_type = 'visit'
        elif 'message' in (log.action_type or ''): node_type = 'send_message'
        
        ghost_node = {
            'id': ghost_id_counter,
            'is_ghost': True,
            'schedule_id': schedule_id,
            'node_type': node_type,
            'day_number': day_num,
            'execution_time': time_str,
            'is_random_time': False,
            'config': {'description': log.message},
            'status': 'completed',
            'executed_at': log.timestamp.isoformat(),
            'error_message': None,
            'created_at': log.timestamp.isoformat(),
            'updated_at': log.timestamp.isoformat()
        }
        nodes.append(ghost_node)
        ghost_id_counter -= 1
        
    return nodes


@scheduler_bp.route('/upload', methods=['POST'])
def upload_asset():
    """Upload asset for scheduler node (e.g. photo)"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
            
        if file:
            filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
            # Use 'uploads/scheduler' so it is served by Flask static route and accessible via web
            upload_dir = os.path.join(os.getcwd(), 'uploads', 'scheduler')
            os.makedirs(upload_dir, exist_ok=True)
            
            filepath = os.path.join(upload_dir, filename)
            file.save(filepath)
            
            # Return absolute path for internal use
            return jsonify({
                'message': 'File uploaded',
                'path': filepath,
                'filename': filename
            }), 201
            
    except Exception as e:
        logger.error(f"Error uploading asset: {e}")
        return jsonify({'error': str(e)}), 500

@scheduler_bp.route('/accounts/<int:account_id>/run_node', methods=['POST'])
def run_node_immediately(account_id):
    """Execute a single node logic immediately"""
    try:
        from workers.node_executors import execute_node
        from utils.telethon_helper import get_telethon_client
        import asyncio
        
        account = Account.query.get(account_id)
        if not account:
            return jsonify({'error': 'Account not found'}), 404
        
        data = request.json or {}
        
        # Check if we are running an existing persistent node
        node_id = data.get('node_id')
        if node_id:
            # Persistent execution
            from workers.scheduler_worker import execute_scheduled_node
            
            # Reset status to pending so worker picks it up (or set running immediately?)
            # Actually worker expects pending, but if we want visual immediate feedback
            # we can set running here? Or let worker set running.
            # Worker checks: if node.status != 'pending' -> return.
            # BUT user wants to force run.
            # So we should probably force status back to pending if it was failed/completed?
            # Or better: The JS already sets it to 'running' visually?
            # Wait, if JS sets visually 'running', but DB is 'pending', worker sets 'running'.
            # If we set DB 'running' here, worker skips it!
            
            # Re-read worker logic:
            # if node.status != 'pending': skip.
            
            # So here we MUST ensure it's pending or running?
            # We set it to 'running' so UI sees it immediately even after reload.
            # Worker is updated to accept 'running'.
            node = WarmupScheduleNode.query.get(node_id)
            if node:
                node.status = 'running' 
                node.executed_at = datetime.now() # Mark start time
                db.session.commit()
                
            task = execute_scheduled_node.apply_async(args=[node_id])
            
            return jsonify({
                'message': 'Execution started (persistent)', 
                'task_id': task.id,
                'status': 'running' 
            }), 200

        else:
            # ADHOC Execution (old logic)
            node_type = data.get('node_type')
            config = data.get('config', {})
            
            if not node_type:
                return jsonify({'error': 'node_type required'}), 400
                
            # Execute asynchronously via Celery
            from workers.scheduler_worker import execute_adhoc_node
            
            # Launch task
            task = execute_adhoc_node.apply_async(args=[account_id, node_type, config])
            
            return jsonify({
                'message': 'Execution started in background', 
                'task_id': task.id
            }), 200

    except Exception as e:
        logger.error(f"Error executing node immediate: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/fix-dates', methods=['GET'])
def fix_dates_route():
    """Temporary route to fix schedule start dates"""
    try:
        # Import needed models if not at top (but they are)
        
        # Fix active schedules OR draft schedules with missing start_date
        schedules = WarmupSchedule.query.filter(
            (WarmupSchedule.status == 'active') | 
            ((WarmupSchedule.status == 'draft') & (WarmupSchedule.start_date == None))
        ).all()
        count = 0
        details = []
        for s in schedules:
            if s.account and s.account.created_at:
                c_date = s.account.created_at.date()
                if s.start_date != c_date:
                    old_date = s.start_date
                    s.start_date = c_date
                    # Also update end date to keep duration from new start
                    s.end_date = s.start_date + timedelta(days=14)
                    
                    count += 1
                    details.append(f"Schedule {s.id}: {old_date} -> {c_date}")
        
        if count > 0:
            db.session.commit()
            
        return jsonify({
            'message': f'Fixed {count} schedules',
            'details': details
        }), 200
    except Exception as e:
        logger.error(f"Error fixing dates: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/debug-account/<int:account_id>', methods=['GET'])
def debug_account(account_id):
    """Debug route to check account photo path"""
    try:
        from models.account import Account
        import os
        from flask import current_app
        
        account = Account.query.get(account_id)
        if not account:
            return jsonify({'error': 'Account not found'}), 404
            
        photo_url = account.photo_url
        
        # Check file existence
        file_path = "N/A"
        exists = False
        
        if photo_url:
            # Remove leading slash if present (though it likely doesn't have one in DB usually)
            clean_path = photo_url.lstrip('/')
            file_path = os.path.join(current_app.root_path, clean_path)
            exists = os.path.exists(file_path)
            
        return jsonify({
            'account_id': account.id,
            'photo_url': photo_url,
            'full_path': file_path,
            'exists': exists,
            'cwd': os.getcwd(),
            'app_root': current_app.root_path
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
