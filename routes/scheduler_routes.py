"""
Scheduler Routes - REST API for Warmup Scheduler
"""
from flask import Blueprint, request, jsonify, Response, stream_with_context
from modules.scheduler.services import SchedulerService
from modules.scheduler.exceptions import (
    ScheduleNotFoundError,
    NodeNotFoundError,
    ScheduleAlreadyExistsError,
    ScheduleAlreadyActiveError,
    InvalidNodeDataError,
    SchedulerError
)
from utils.redis_logger import redis_client
import logging

logger = logging.getLogger(__name__)
scheduler_bp = Blueprint('scheduler', __name__, url_prefix='/scheduler')

@scheduler_bp.route('/accounts/<int:account_id>/schedule', methods=['GET'])
def get_schedule(account_id):
    """Get warmup schedule for an account"""
    try:
        result = SchedulerService.get_full_schedule(account_id)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error getting schedule: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/accounts/<int:account_id>/schedule', methods=['POST'])
def create_schedule(account_id):
    """Create new warmup schedule"""
    try:
        data = request.json or {}
        schedule = SchedulerService.create_default_schedule(account_id, data.get('name'))
        return jsonify({'schedule': schedule.to_dict()}), 201
    except ScheduleAlreadyExistsError as e:
        return jsonify({'error': str(e)}), 400
    except ValueError as e: # Account not found
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error creating schedule: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>', methods=['PUT'])
def update_schedule(schedule_id):
    """Update schedule"""
    try:
        data = request.json or {}
        schedule = SchedulerService.update_schedule(schedule_id, data)
        return jsonify({'schedule': schedule.to_dict()}), 200
    except ScheduleNotFoundError:
        return jsonify({'error': 'Schedule not found'}), 404
    except Exception as e:
        logger.error(f"Error updating schedule: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    """Delete schedule"""
    try:
        SchedulerService.delete_schedule(schedule_id)
        return jsonify({'message': 'Schedule deleted'}), 200
    except ScheduleNotFoundError:
        return jsonify({'error': 'Schedule not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting schedule: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>/nodes', methods=['POST'])
def add_node(schedule_id):
    """Add a node"""
    try:
        data = request.json or {}
        node = SchedulerService.add_node(schedule_id, data)
        return jsonify({'node': node.to_dict()}), 201
    except ScheduleNotFoundError:
        return jsonify({'error': 'Schedule not found'}), 404
    except InvalidNodeDataError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error adding node: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/nodes/<int:node_id>', methods=['PUT'])
def update_node(node_id):
    """Update node"""
    try:
        data = request.json or {}
        node = SchedulerService.update_node(node_id, data)
        return jsonify({'node': node.to_dict()}), 200
    except NodeNotFoundError:
        return jsonify({'error': 'Node not found'}), 404
    except Exception as e:
        logger.error(f"Error updating node: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/nodes/<int:node_id>', methods=['DELETE'])
def delete_node(node_id):
    """Delete node"""
    try:
        SchedulerService.delete_node(node_id)
        return jsonify({'message': 'Node deleted'}), 200
    except NodeNotFoundError:
        return jsonify({'error': 'Node not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting node: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>/start', methods=['POST'])
def start_schedule(schedule_id):
    """Start (activate) schedule"""
    try:
        schedule = SchedulerService.activate_schedule(schedule_id)
        return jsonify({
            'message': 'Schedule started',
            'schedule': schedule.to_dict()
        }), 200
    except ScheduleNotFoundError:
        return jsonify({'error': 'Schedule not found'}), 404
    except ScheduleAlreadyActiveError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error starting schedule: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>/pause', methods=['POST'])
def pause_schedule(schedule_id):
    """Pause schedule"""
    try:
        schedule = SchedulerService.pause_schedule(schedule_id)
        return jsonify({
            'message': 'Schedule paused',
            'schedule': schedule.to_dict()
        }), 200
    except ScheduleNotFoundError:
        return jsonify({'error': 'Schedule not found'}), 404
    except SchedulerError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error pausing schedule: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>/resume', methods=['POST'])
def resume_schedule(schedule_id):
    """Resume schedule"""
    try:
        schedule = SchedulerService.resume_schedule(schedule_id)
        return jsonify({
            'message': 'Schedule resumed',
            'schedule': schedule.to_dict()
        }), 200
    except ScheduleNotFoundError:
        return jsonify({'error': 'Schedule not found'}), 404
    except SchedulerError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error resuming schedule: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/schedules/<int:schedule_id>/status', methods=['GET'])
def get_schedule_status(schedule_id):
    """Get status"""
    try:
        data = SchedulerService.get_execution_status(schedule_id)
        return jsonify(data), 200
    except ScheduleNotFoundError:
        return jsonify({'error': 'Schedule not found'}), 404
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/accounts/<int:account_id>/status', methods=['GET'])
def get_account_schedule_status(account_id):
    """Get status by account_id"""
    try:
        data = SchedulerService.get_execution_status_by_account(account_id)
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Error getting account status: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/upload', methods=['POST'])
def upload_asset():
    """Upload asset"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
            
        result = SchedulerService.upload_asset(file)
        return jsonify(result), 201
    except Exception as e:
        logger.error(f"Error uploading asset: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/accounts/<int:account_id>/run_node', methods=['POST'])
def run_node_immediately(account_id):
    """Execute node immediately"""
    try:
        data = request.json or {}
        result = SchedulerService.trigger_node_execution(account_id, data)
        return jsonify(result), 200
    except InvalidNodeDataError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error running node: {e}")
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/fix-dates', methods=['GET'])
def fix_dates_route():
    """Fix dates"""
    try:
        result = SchedulerService.fix_all_schedules()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/debug-account/<int:account_id>', methods=['GET'])
def debug_account(account_id):
    """Debug account photo"""
    try:
        result = SchedulerService.get_account_debug_info(account_id)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@scheduler_bp.route('/stream/logs/<int:account_id>')
def stream_logs(account_id):
    """SSE Endpoint for real-time log streaming"""
    # Redis logic kept here as it involves stream generation response
    
    @stream_with_context
    def generate():
        yield ": start\n\n"
        channel = f"logs:account:{account_id}"
        
        try:
            history = redis_client.lrange(f"history:{channel}", 0, -1)
            for log_json in history:
                yield f"data: {log_json}\n\n"
        except Exception as e:
            logger.error(f"Error reading log history: {e}")
        
        pubsub = redis_client.pubsub()
        pubsub.subscribe(channel)
        
        try:
            for message in pubsub.listen():
                if message['type'] == 'message':
                    yield f"data: {message['data']}\n\n"
        except GeneratorExit:
            pubsub.unsubscribe()
            pubsub.close()
        except Exception as e:
             logger.error(f"Redis stream error: {e}")

    return Response(generate(), mimetype="text/event-stream")


@scheduler_bp.route('/logs/<int:account_id>/clear', methods=['POST'])
def clear_logs(account_id):
    """Clear log history for an account"""
    try:
        channel = f"logs:account:{account_id}"
        history_key = f"history:{channel}"
        redis_client.delete(history_key)
        return jsonify({'success': True, 'message': 'Log history cleared'})
    except Exception as e:
        logger.error(f"Error clearing logs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
