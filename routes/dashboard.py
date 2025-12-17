from flask import Blueprint, render_template
from utils.decorators import login_required
from models.account import Account
from models.proxy import Proxy
from models.campaign import InviteCampaign
from models.dm_campaign import DMCampaign
from models.channel import Channel
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard"""
    
    # Get statistics
    stats = {
        'total_accounts': Account.query.count(),
        'active_accounts': Account.query.filter_by(status='active').count(),
        'total_proxies': Proxy.query.count(),
        'active_proxies': Proxy.query.filter_by(status='active').count(),
        'total_channels': Channel.query.count(),
        'invite_campaigns': InviteCampaign.query.count(),
        'dm_campaigns': DMCampaign.query.count(),
        'active_invite_campaigns': InviteCampaign.query.filter_by(status='active').count(),
        'active_dm_campaigns': DMCampaign.query.filter_by(status='active').count(),
    }
    
    # Get recent campaigns
    recent_invite_campaigns = InviteCampaign.query.order_by(
        InviteCampaign.created_at.desc()
    ).limit(5).all()
    
    recent_dm_campaigns = DMCampaign.query.order_by(
        DMCampaign.created_at.desc()
    ).limit(5).all()
    
    # Get accounts with issues
    accounts_with_issues = Account.query.filter(
        Account.status.in_(['cooldown', 'banned'])
    ).limit(5).all()
    
    return render_template(
        'dashboard.html',
        stats=stats,
        recent_invite_campaigns=recent_invite_campaigns,
        recent_dm_campaigns=recent_dm_campaigns,
        accounts_with_issues=accounts_with_issues
    )
