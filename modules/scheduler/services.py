from datetime import datetime, timedelta
from database import db
from models.warmup_schedule import WarmupSchedule
from models.warmup_schedule_node import WarmupScheduleNode
from models.account import Account
from models.warmup_log import WarmupLog
from modules.scheduler.exceptions import (
    ScheduleNotFoundError,
    NodeNotFoundError,
    ScheduleAlreadyExistsError,
    ScheduleAlreadyActiveError,
    InvalidNodeDataError,
    SchedulerError
)
from sqlalchemy import or_

class SchedulerService:
    @staticmethod
    def get_full_schedule(account_id: int) -> dict:
        """Get full schedule with real and ghost nodes, sorted"""
        schedule = WarmupSchedule.query.filter_by(account_id=account_id).first()
        
        # Get account's Telegram ID for custom_logic_id format
        account = Account.query.get(account_id)
        telegram_id = account.telegram_id if account else None
        
        if not schedule:
            schedule_dict = {'id': 0, 'status': 'draft'}
            schedule_id = 0
        else:
            schedule_dict = schedule.to_dict()
            schedule_id = schedule.id
            
        nodes = []
        if schedule:
            nodes = WarmupScheduleNode.query.filter_by(schedule_id=schedule.id).all()
            
        node_dicts = [node.to_dict() for node in nodes]
        
        # Ghost nodes are disabled to prevent data duplication and UI confusion
        # ghost_nodes = SchedulerService._get_ghost_nodes(account_id, schedule_id)
        # node_dicts.extend(ghost_nodes)
        
        def sort_key(n):
            d_str = n.get('execution_date')
            t_str = n.get('execution_time', '00:00')
            n_id = n.get('id', 0)
            if not d_str:
                d_str = '1970-01-01'
            return (str(d_str), str(t_str), n_id)

        node_dicts.sort(key=sort_key)
        
        # Assign per-account ordinal IDs and custom_logic_id with Telegram ID
        for idx, node in enumerate(node_dicts, 1):
            node['ordinal_id'] = idx
            # Format: {telegram_id}_{ordinal_id} (e.g., 8524632170_3)
            # Falls back to account_id if telegram_id is not available
            if telegram_id:
                node['custom_logic_id'] = f"{telegram_id}_{idx}"
            else:
                node['custom_logic_id'] = f"{account_id}_{idx}"
            
        return {
            'schedule': schedule_dict,
            'nodes': node_dicts
        }

    @staticmethod
    def create_default_schedule(account_id: int, name: str = None) -> WarmupSchedule:
        """Create a new schedule"""
        account = Account.query.get(account_id)
        if not account:
             raise ValueError(f"Account {account_id} not found")

        existing = WarmupSchedule.query.filter_by(account_id=account_id).first()
        if existing:
            raise ScheduleAlreadyExistsError(f"Schedule for account {account_id} already exists")
            
        if not name:
             name = f"Warmup Schedule - {account.username or account.phone}"

        schedule = WarmupSchedule(
            account_id=account_id,
            name=name,
            status='draft',
            start_date=account.created_at.date() if account.created_at else datetime.now().date()
        )
        
        db.session.add(schedule)
        db.session.commit()
        return schedule
    
    @staticmethod
    def update_schedule(schedule_id: int, data: dict) -> WarmupSchedule:
        """Update schedule metadata"""
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            raise ScheduleNotFoundError(f"Schedule {schedule_id} not found")
        
        if 'name' in data:
            schedule.name = data['name']
        if 'status' in data:
            schedule.status = data['status']
            
        schedule.updated_at = datetime.now()
        db.session.commit()
        return schedule

    @staticmethod
    def delete_schedule(schedule_id: int):
        """Delete schedule"""
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            raise ScheduleNotFoundError(f"Schedule {schedule_id} not found")
            
        db.session.delete(schedule)
        db.session.commit()
        return True

    @staticmethod
    def add_node(schedule_id: int, data: dict) -> WarmupScheduleNode:
        """Add node to schedule"""
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            raise ScheduleNotFoundError(f"Schedule {schedule_id} not found")
            
        if 'node_type' not in data or 'day_number' not in data:
            raise InvalidNodeDataError("node_type and day_number are required")
            
        execution_date = None
        if schedule.start_date:
            execution_date = schedule.start_date + timedelta(days=int(data['day_number']) - 1)
            
        node = WarmupScheduleNode(
            schedule_id=schedule_id,
            node_type=data['node_type'],
            day_number=data['day_number'],
            execution_date=execution_date,
            execution_time=data.get('execution_time'),
            is_random_time=data.get('is_random_time', False),
            config=data.get('config', {}),
            status=data.get('status', 'draft')
        )
        
        db.session.add(node)
        db.session.commit()
        return node

    @staticmethod
    def update_node(node_id: int, data: dict) -> WarmupScheduleNode:
        """Update node"""
        node = WarmupScheduleNode.query.get(node_id)
        if not node:
            raise NodeNotFoundError(f"Node {node_id} not found")
            
        if 'day_number' in data:
            node.day_number = data['day_number']
            
        if 'status' in data:
            node.status = data['status']
            if node.schedule and node.schedule.start_date:
                node.execution_date = node.schedule.start_date + timedelta(days=int(node.day_number) - 1)
                
        if 'execution_time' in data:
            node.execution_time = data['execution_time']
        
        if 'is_random_time' in data:
            node.is_random_time = data['is_random_time']
            
        if 'config' in data:
            node.config = data['config']
            
        if 'status' not in data:
            node.status = 'pending'
            
        node.error_message = None
        node.updated_at = datetime.now()
        
        db.session.commit()
        return node

    @staticmethod
    def delete_node(node_id: int):
        """Delete node"""
        node = WarmupScheduleNode.query.get(node_id)
        if not node:
            raise NodeNotFoundError(f"Node {node_id} not found")
            
        db.session.delete(node)
        db.session.commit()
        return True

    @staticmethod
    def activate_schedule(schedule_id: int) -> WarmupSchedule:
        """activate schedule and fix dates"""
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            raise ScheduleNotFoundError(f"Schedule {schedule_id} not found")
            
        if schedule.status == 'active':
            raise ScheduleAlreadyActiveError("Schedule is already active")
            
        schedule.status = 'active'
        
        if schedule.account and schedule.account.created_at:
             schedule.start_date = schedule.account.created_at.date()
        else:
             schedule.start_date = datetime.now().date()
             
        schedule.end_date = schedule.start_date + timedelta(days=14)
        schedule.updated_at = datetime.now()
        
        db.session.commit()
        return schedule

    @staticmethod
    def pause_schedule(schedule_id: int) -> WarmupSchedule:
        """Pause schedule"""
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            raise ScheduleNotFoundError(f"Schedule {schedule_id} not found")
            
        if schedule.status != 'active':
            raise SchedulerError("Schedule is not active")
            
        schedule.status = 'paused'
        schedule.updated_at = datetime.now()
        db.session.commit()
        return schedule
        
    @staticmethod
    def resume_schedule(schedule_id: int) -> WarmupSchedule:
        """Resume schedule"""
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            raise ScheduleNotFoundError(f"Schedule {schedule_id} not found")
            
        if schedule.status != 'paused':
            raise SchedulerError("Schedule is not paused")
            
        schedule.status = 'active'
        schedule.updated_at = datetime.now()
        db.session.commit()
        return schedule

    @staticmethod
    def get_execution_status(schedule_id: int, account_id: int = None) -> dict:
        """Get detailed execution status"""
        schedule = WarmupSchedule.query.get(schedule_id)
        if not schedule:
            raise ScheduleNotFoundError(f"Schedule {schedule_id} not found")
            
        nodes = WarmupScheduleNode.query.filter_by(schedule_id=schedule_id).all()
        node_dicts = [node.to_dict() for node in nodes]
        
        target_account_id = account_id if account_id else schedule.account_id
        ghost_nodes = SchedulerService._get_ghost_nodes(target_account_id, schedule_id)
        node_dicts.extend(ghost_nodes)
        
        status_counts = {'pending': 0, 'running': 0, 'completed': 0, 'failed': 0}
        
        for node in nodes:
            status_counts[node.status] = status_counts.get(node.status, 0) + 1
            
        for g in ghost_nodes:
             status_counts[g['status']] = status_counts.get(g['status'], 0) + 1
             
        total_nodes = len(nodes) + len(ghost_nodes)
        completed_nodes = status_counts['completed']
        progress_percent = (completed_nodes / total_nodes * 100) if total_nodes > 0 else 0
        
        current_day = None
        if schedule.start_date:
            days_active = (datetime.now().date() - schedule.start_date).days
            current_day = days_active + 1
            
        return {
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
        }
        
    @staticmethod
    def get_execution_status_by_account(account_id: int) -> dict:
        """Get execution status by account ID directly"""
        schedule = WarmupSchedule.query.filter_by(account_id=account_id).first()
        if not schedule:
            return {'schedule': None}
            
        return SchedulerService.get_execution_status(schedule.id, account_id=account_id)

    @staticmethod
    def upload_asset(file) -> dict:
        """Upload asset file"""
        import os
        from werkzeug.utils import secure_filename
        from datetime import datetime
        
        filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
        # Assuming run from app root
        upload_dir = os.path.join(os.getcwd(), 'uploads', 'scheduler')
        os.makedirs(upload_dir, exist_ok=True)
        
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        
        return {
            'message': 'File uploaded',
            'path': filepath,
            'filename': filename
        }

    @staticmethod
    def trigger_node_execution(account_id: int, data: dict) -> dict:
        """Trigger immediate node execution"""
        node_id = data.get('node_id')
        if node_id:
            from workers.scheduler_worker import execute_scheduled_node
            node = WarmupScheduleNode.query.get(node_id)
            if node:
                node.status = 'running'
                node.executed_at = datetime.now()
                db.session.commit()
                
            task = execute_scheduled_node.apply_async(args=[node_id, True])
            return {'message': 'Execution started (persistent)', 'task_id': task.id, 'status': 'running'}
        else:
            node_type = data.get('node_type')
            config = data.get('config', {})
            if not node_type:
                 raise InvalidNodeDataError("node_type required")
                 
            from workers.scheduler_worker import execute_adhoc_node
            task = execute_adhoc_node.apply_async(args=[account_id, node_type, config])
            return {'message': 'Execution started in background', 'task_id': task.id}

    @staticmethod
    def fix_all_schedules() -> dict:
        """Fix dates for all schedules"""
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
                    old = s.start_date
                    s.start_date = c_date
                    s.end_date = s.start_date + timedelta(days=14)
                    count += 1
                    details.append(f"Schedule {s.id}: {old} -> {c_date}")
        if count > 0:
            db.session.commit()
        return {'message': f'Fixed {count} schedules', 'details': details}

    @staticmethod
    def get_account_debug_info(account_id: int) -> dict:
        """Get debug info for account"""
        import os
        from flask import current_app
        account = Account.query.get(account_id)
        if not account:
            raise ValueError("Account not found")
        
        photo_url = account.photo_url
        file_path = "N/A"
        exists = False
        if photo_url:
            clean_path = photo_url.lstrip('/')
            file_path = os.path.join(current_app.root_path, clean_path)
            exists = os.path.exists(file_path)
            
        return {
            'account_id': account.id,
            'photo_url': photo_url,
            'full_path': file_path,
            'exists': exists,
            'cwd': os.getcwd(),
            'app_root': current_app.root_path
        }

    @staticmethod
    def _get_ghost_nodes(account_id: int, schedule_id: int) -> list:
        nodes = []
        account = Account.query.get(account_id)
        created_at = account.created_at if (account and account.created_at) else datetime.now()
        
        logs = WarmupLog.query.filter_by(account_id=account_id, status='success').all()
        
        ghost_id_counter = -1
        for log in logs:
            delta_days = (log.timestamp.date() - created_at.date()).days
            day_num = delta_days + 1
            if day_num < 1: day_num = 1
            
            time_str = log.timestamp.strftime('%H:%M')
            
            node_type = 'passive_activity'
            t = log.action_type or ''
            if t == 'set_photo': node_type = 'photo'
            elif t == 'update_bio': node_type = 'bio'
            elif t == 'update_username': node_type = 'username'
            elif 'subscribe' in t: node_type = 'subscribe'
            elif 'visit' in t: node_type = 'visit'
            elif 'message' in t: node_type = 'send_message'
            
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
