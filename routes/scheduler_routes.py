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
            return jsonify({'schedule': None}), 200
        
        # Get all nodes for this schedule
        nodes = WarmupScheduleNode.query.filter_by(schedule_id=schedule.id).all()
        
        return jsonify({
            'schedule': schedule.to_dict(),
            'nodes': [node.to_dict() for node in nodes]
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
            status='draft'
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
        
        # Create node
        node = WarmupScheduleNode(
            schedule_id=schedule_id,
            node_type=data['node_type'],
            day_number=data['day_number'],
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
        
        if 'execution_time' in data:
            node.execution_time = data['execution_time']
        
        if 'is_random_time' in data:
            node.is_random_time = data['is_random_time']
        
        if 'config' in data:
            node.config = data['config']
        
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
def get_schedule_status(schedule_id):
    """Get detailed status of schedule execution"""
    try:
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            return jsonify({'error': 'Schedule not found'}), 404
        
        # Get all nodes grouped by status
        nodes = WarmupScheduleNode.query.filter_by(schedule_id=schedule_id).all()
        
        status_counts = {
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0
        }
        
        for node in nodes:
            status_counts[node.status] = status_counts.get(node.status, 0) + 1
        
        # Calculate progress
        total_nodes = len(nodes)
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
            'nodes': [node.to_dict() for node in nodes]
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting schedule status: {e}")
        return jsonify({'error': str(e)}), 500

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
            upload_dir = os.path.join(os.getcwd(), 'storage', 'scheduler_uploads')
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
