from flask import Blueprint, render_template, request
from utils.decorators import login_required
from models.campaign import InviteCampaign, InviteLog
from models.dm_campaign import DMCampaign, DMTarget
from models.account import Account
from sqlalchemy import func
from datetime import datetime, timedelta

analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/')
@login_required
def index():
    """Analytics dashboard"""
    
    # Overall stats
    stats = {
        'total_invites': InviteLog.query.filter_by(status='success').count(),
        'total_dms': DMTarget.query.filter_by(status='sent').count(),
        'active_campaigns': InviteCampaign.query.filter_by(status='active').count() + 
                          DMCampaign.query.filter_by(status='active').count(),
        'accounts_in_use': Account.query.filter_by(status='active').count(),
    }
    
    # Last 7 days activity
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    daily_invites = db.session.query(
        func.date(InviteLog.timestamp).label('date'),
        func.count(InviteLog.id).label('count')
    ).filter(
        InviteLog.timestamp >= seven_days_ago
    ).group_by('date').order_by('date').all()
    
    return render_template('analytics/dashboard.html', stats=stats, daily_invites=daily_invites)


@analytics_bp.route('/campaigns/<int:campaign_id>')
@login_required
def campaign_detail(campaign_id):
    """Campaign analytics"""
    campaign_type = request.args.get('type', 'invite')
    
    if campaign_type == 'invite':
        campaign = InviteCampaign.query.get_or_404(campaign_id)
    else:
        campaign = DMCampaign.query.get_or_404(campaign_id)
    
    return render_template('analytics/campaign_detail.html', campaign=campaign, campaign_type=campaign_type)
