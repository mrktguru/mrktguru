from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils.decorators import login_required
from models.campaign import InviteCampaign, CampaignAccount, SourceUser
from models.channel import Channel
from models.account import Account
from app import db
from workers.invite_worker import run_invite_campaign

campaigns_bp = Blueprint('campaigns', __name__)


@campaigns_bp.route('/')
@login_required
def list_campaigns():
    """List all invite campaigns"""
    campaigns = InviteCampaign.query.order_by(InviteCampaign.created_at.desc()).all()
    return render_template('campaigns/list.html', campaigns=campaigns)


@campaigns_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new invite campaign"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        channel_id = request.form.get('channel_id')
        strategy = request.form.get('strategy', 'safe')
        account_ids = request.form.getlist('account_ids')
        
        if not name or not channel_id or not account_ids:
            flash('Name, channel and accounts are required', 'error')
            return redirect(url_for('campaigns.create'))
        
        # Create campaign
        campaign = InviteCampaign(
            name=name,
            description=description,
            channel_id=int(channel_id),
            strategy=strategy
        )
        
        # Set delays based on strategy
        if strategy == 'safe':
            campaign.delay_min = 60
            campaign.delay_max = 120
            campaign.invites_per_hour_min = 3
            campaign.invites_per_hour_max = 5
        elif strategy == 'normal':
            campaign.delay_min = 45
            campaign.delay_max = 90
            campaign.invites_per_hour_min = 5
            campaign.invites_per_hour_max = 10
        elif strategy == 'aggressive':
            campaign.delay_min = 30
            campaign.delay_max = 60
            campaign.invites_per_hour_min = 8
            campaign.invites_per_hour_max = 15
        
        db.session.add(campaign)
        db.session.flush()
        
        # Assign accounts
        for account_id in account_ids:
            ca = CampaignAccount(
                campaign_id=campaign.id,
                account_id=int(account_id)
            )
            db.session.add(ca)
        
        db.session.commit()
        
        flash('Campaign created successfully', 'success')
        return redirect(url_for('campaigns.detail', campaign_id=campaign.id))
    
    channels = Channel.query.filter_by(status='active').all()
    accounts = Account.query.filter_by(status='active').all()
    return render_template('campaigns/create.html', channels=channels, accounts=accounts)


@campaigns_bp.route('/<int:campaign_id>')
@login_required
def detail(campaign_id):
    """Campaign details"""
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    return render_template('campaigns/detail.html', campaign=campaign)


@campaigns_bp.route('/<int:campaign_id>/start', methods=['POST'])
@login_required
def start(campaign_id):
    """Start campaign"""
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    
    if campaign.status != 'draft' and campaign.status != 'paused':
        flash('Campaign cannot be started in current state', 'error')
        return redirect(url_for('campaigns.detail', campaign_id=campaign_id))
    
    if campaign.total_targets == 0:
        flash('No targets to invite. Import users first', 'error')
        return redirect(url_for('campaigns.detail', campaign_id=campaign_id))
    
    campaign.status = 'active'
    from datetime import datetime
    campaign.started_at = datetime.utcnow()
    db.session.commit()
    
    # Start worker
    run_invite_campaign.delay(campaign_id)
    
    flash('Campaign started', 'success')
    return redirect(url_for('campaigns.detail', campaign_id=campaign_id))


@campaigns_bp.route('/<int:campaign_id>/pause', methods=['POST'])
@login_required
def pause(campaign_id):
    """Pause campaign"""
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    campaign.status = 'paused'
    from datetime import datetime
    campaign.paused_at = datetime.utcnow()
    db.session.commit()
    
    flash('Campaign paused', 'success')
    return redirect(url_for('campaigns.detail', campaign_id=campaign_id))


@campaigns_bp.route('/<int:campaign_id>/stop', methods=['POST'])
@login_required
def stop(campaign_id):
    """Stop campaign"""
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    campaign.status = 'stopped'
    from datetime import datetime
    campaign.completed_at = datetime.utcnow()
    db.session.commit()
    
    flash('Campaign stopped', 'success')
    return redirect(url_for('campaigns.detail', campaign_id=campaign_id))


@campaigns_bp.route('/<int:campaign_id>/import-users', methods=['POST'])
@login_required
def import_users(campaign_id):
    """Import users from source channel"""
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    source_channel = request.form.get('source_channel', '').lstrip('@')
    
    if not source_channel:
        flash('Source channel is required', 'error')
        return redirect(url_for('campaigns.detail', campaign_id=campaign_id))
    
    # Start parsing task
    from workers.parser_worker import parse_users_for_campaign
    parse_users_for_campaign.delay(campaign_id, source_channel)
    
    flash('Parsing users in background...', 'info')
    return redirect(url_for('campaigns.detail', campaign_id=campaign_id))
