from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.decorators import login_required
from models.automation import ScheduledTask, AutoAction
from app import db
from datetime import datetime

automation_bp = Blueprint('automation', __name__)


@automation_bp.route('/')
@login_required
def index():
    """Automation dashboard"""
    scheduled_tasks = ScheduledTask.query.filter_by(status='pending').order_by(ScheduledTask.scheduled_for).all()
    auto_actions = AutoAction.query.filter_by(is_enabled=True).all()
    return render_template('automation/dashboard.html', scheduled_tasks=scheduled_tasks, auto_actions=auto_actions)


@automation_bp.route('/scheduled', methods=['GET', 'POST'])
@login_required
def scheduled_tasks():
    """Manage scheduled tasks"""
    if request.method == 'POST':
        task_type = request.form.get('task_type')
        entity_type = request.form.get('entity_type')
        entity_id = request.form.get('entity_id')
        scheduled_for = request.form.get('scheduled_for')
        
        task = ScheduledTask(
            task_type=task_type,
            entity_type=entity_type,
            entity_id=int(entity_id) if entity_id else None,
            scheduled_for=datetime.fromisoformat(scheduled_for),
            payload={}
        )
        db.session.add(task)
        db.session.commit()
        
        flash('Task scheduled', 'success')
        return redirect(url_for('automation.index'))
    
    return render_template('automation/scheduled.html')


@automation_bp.route('/auto-actions', methods=['GET', 'POST'])
@login_required
def auto_actions():
    """Manage auto-actions"""
    if request.method == 'POST':
        name = request.form.get('name')
        trigger_type = request.form.get('trigger_type')
        action_type = request.form.get('action_type')
        
        action = AutoAction(
            name=name,
            trigger_type=trigger_type,
            trigger_condition={},
            action_type=action_type,
            action_params={}
        )
        db.session.add(action)
        db.session.commit()
        
        flash('Auto-action created', 'success')
        return redirect(url_for('automation.index'))
    
    return render_template('automation/auto_actions.html')
