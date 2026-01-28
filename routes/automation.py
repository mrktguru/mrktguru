from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.decorators import login_required
from models.automation import ScheduledTask, AutoAction
from modules.settings.services.automation import AutomationManager

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
        AutomationManager.schedule_task(request.form)
        flash('Task scheduled', 'success')
        return redirect(url_for('automation.index'))
    
    return render_template('automation/scheduled.html')


@automation_bp.route('/auto-actions', methods=['GET', 'POST'])
@login_required
def auto_actions():
    """Manage auto-actions"""
    if request.method == 'POST':
        AutomationManager.create_auto_action(request.form)
        flash('Auto-action created', 'success')
        return redirect(url_for('automation.index'))
    
    return render_template('automation/auto_actions.html')
