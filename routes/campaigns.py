from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils.decorators import login_required
from models.campaign import InviteCampaign, CampaignAccount, SourceUser
from models.channel import Channel
from models.account import Account
from database import db
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
    from workers.invite_worker import run_invite_campaign
    run_invite_campaign.delay(campaign_id)
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


@campaigns_bp.route("/<int:campaign_id>/parse-source", methods=["GET", "POST"])
@login_required
def parse_source(campaign_id):
    """Parse users from source channel"""
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    
    if request.method == "POST":
        source_channel = request.form.get("source_channel")
        limit = int(request.form.get("limit", 1000))
        
        # Filters
        exclude_bots = request.form.get("exclude_bots") == "on"
        exclude_admins = request.form.get("exclude_admins") == "on"
        min_score = int(request.form.get("min_score", 0))
        
        if not source_channel:
            flash("Source channel is required", "error")
            return redirect(url_for("campaigns.parse_source", campaign_id=campaign_id))
        
        # Mock parsing (в реальности использовать Telethon)
        # Здесь добавить реальную логику парсинга через parser_worker
        
        flash(f"Parsing started from @{source_channel}. This will take a few minutes.", "info")
        return redirect(url_for("campaigns.detail", campaign_id=campaign_id))
    
    return render_template("campaigns/parse_source.html", campaign=campaign)


@campaigns_bp.route("/<int:campaign_id>/logs")
@login_required
def logs(campaign_id):
    """View campaign logs"""
    from models.campaign import InviteLog
    
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    
    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = 50
    
    logs_query = InviteLog.query.filter_by(campaign_id=campaign_id).order_by(InviteLog.timestamp.desc())
    logs_paginated = logs_query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template("campaigns/logs.html", campaign=campaign, logs=logs_paginated)


@campaigns_bp.route("/<int:campaign_id>/export", methods=["POST"])
@login_required
def export(campaign_id):
    """Export campaign results to CSV"""
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    
    from models.campaign import SourceUser
    import csv
    from io import StringIO
    from flask import make_response
    
    targets = SourceUser.query.filter_by(campaign_id=campaign_id).all()
    
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Username", "First Name", "Last Name", "Status", "Invited At", "Priority Score", "Source"])
    
    for target in targets:
        writer.writerow([
            target.username or "",
            target.first_name or "",
            target.last_name or "",
            target.status,
            target.invited_at.strftime("%Y-%m-%d %H:%M:%S") if target.invited_at else "",
            target.priority_score,
            target.source
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=invite_campaign_{campaign_id}_export.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output


@campaigns_bp.route("/<int:campaign_id>/stats")
@login_required
def stats(campaign_id):
    """Detailed campaign statistics"""
    from models.campaign import InviteLog
    from sqlalchemy import func
    
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    
    # Overall stats
    total_sent = campaign.invited_count + campaign.failed_count
    success_rate = (campaign.invited_count / total_sent * 100) if total_sent > 0 else 0
    
    # Stats by status
    status_stats = db.session.query(
        InviteLog.status,
        func.count(InviteLog.id).label("count")
    ).filter(
        InviteLog.campaign_id == campaign_id
    ).group_by(InviteLog.status).all()
    
    # Stats by account
    account_stats = db.session.query(
        Account.phone,
        func.count(InviteLog.id).label("total"),
        func.sum(db.case((InviteLog.status == "success", 1), else_=0)).label("success")
    ).join(InviteLog, InviteLog.account_id == Account.id).filter(
        InviteLog.campaign_id == campaign_id
    ).group_by(Account.phone).all()
    
    # Hourly distribution
    hourly_stats = db.session.query(
        func.date_trunc("hour", InviteLog.timestamp).label("hour"),
        func.count(InviteLog.id).label("count")
    ).filter(
        InviteLog.campaign_id == campaign_id
    ).group_by("hour").order_by("hour").all()
    
    return render_template(
        "campaigns/stats.html",
        campaign=campaign,
        success_rate=success_rate,
        status_stats=status_stats,
        account_stats=account_stats,
        hourly_stats=hourly_stats
    )
