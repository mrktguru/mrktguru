from flask import Blueprint, render_template
from utils.decorators import login_required
from modules.dashboard.services.stats import DashboardStatsService

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard"""
    stats = DashboardStatsService.get_overview_stats()
    recent_invite, recent_dm = DashboardStatsService.get_recent_campaigns()
    accounts_with_issues = DashboardStatsService.get_accounts_with_issues()
    
    return render_template(
        'dashboard.html',
        stats=stats,
        recent_invite_campaigns=recent_invite,
        recent_dm_campaigns=recent_dm,
        accounts_with_issues=accounts_with_issues
    )
