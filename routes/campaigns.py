from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import os
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
    accounts = Account.query.filter_by(status="active").all()
    return render_template("campaigns/detail.html", campaign=campaign, accounts=accounts)

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


@campaigns_bp.route("/<int:campaign_id>/upload-targets", methods=["POST"])
@login_required
def upload_targets(campaign_id):
    """Upload target users from CSV/XLS file"""
    import csv
    import pandas as pd
    from werkzeug.utils import secure_filename
    
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    
    if "file" not in request.files:
        flash("No file uploaded", "error")
        return redirect(url_for("campaigns.detail", campaign_id=campaign_id))
    
    file = request.files["file"]
    if file.filename == "":
        flash("No file selected", "error")
        return redirect(url_for("campaigns.detail", campaign_id=campaign_id))
    
    if not file.filename.endswith((".csv", ".xlsx", ".xls")):
        flash("Only CSV and Excel files are supported", "error")
        return redirect(url_for("campaigns.detail", campaign_id=campaign_id))
    
    try:
        # Save file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join("uploads/csv", filename)
        os.makedirs("uploads/csv", exist_ok=True)
        file.save(filepath)
        
        # Parse file
        users_data = []
        if filename.endswith(".csv"):
            with open(filepath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                users_data = list(reader)
        else:
            df = pd.read_excel(filepath)
            users_data = df.to_dict("records")
        
        # Import users
        imported = 0
        skipped = 0
        
        for row in users_data:
            # Get username (required field)
            username = row.get("username", "").strip().lstrip("@")
            user_id = row.get("user_id") or row.get("id") or None
            first_name = row.get("first_name", "")
            last_name = row.get("last_name", "")
            
            if not username:
                skipped += 1
                continue
            
            # Check if already exists
            existing = SourceUser.query.filter_by(
                campaign_id=campaign_id,
                username=username
            ).first()
            
            if existing:
                skipped += 1
                continue
            
            # Add user
            source_user = SourceUser(
                campaign_id=campaign_id,
                username=username if username else None,
                user_id=int(user_id) if user_id else None,
                first_name=first_name,
                last_name=last_name,
                source="csv_upload",
                status="pending"
            )
            db.session.add(source_user)
            imported += 1
        
        db.session.commit()
        
        # Cleanup temp file
        os.remove(filepath)
        
        flash(f"Successfully imported {imported} users. Skipped {skipped} duplicates.", "success")
        
    except Exception as e:
        flash(f"Error importing users: {str(e)}", "error")
    
    return redirect(url_for("campaigns.detail", campaign_id=campaign_id))


@campaigns_bp.route("/<int:campaign_id>/assign-accounts", methods=["POST"])
@login_required
def assign_accounts(campaign_id):
    """Assign accounts to campaign"""
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    account_ids = request.form.getlist("account_ids")
    
    if not account_ids:
        flash("No accounts selected", "error")
        return redirect(url_for("campaigns.detail", campaign_id=campaign_id))
    
    # Add new accounts
    added = 0
    for account_id in account_ids:
        # Check if already assigned
        existing = CampaignAccount.query.filter_by(
            campaign_id=campaign_id,
            account_id=int(account_id)
        ).first()
        
        if not existing:
            ca = CampaignAccount(
                campaign_id=campaign_id,
                account_id=int(account_id),
                status="active"
            )
            db.session.add(ca)
            added += 1
    
    db.session.commit()
    flash(f"Added {added} accounts to campaign", "success")
    return redirect(url_for("campaigns.detail", campaign_id=campaign_id))


@campaigns_bp.route("/<int:campaign_id>/edit", methods=["GET", "POST"])
@login_required
def edit(campaign_id):
    """Edit campaign settings"""
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    
    if request.method == "POST":
        campaign.name = request.form.get("name")
        campaign.description = request.form.get("description")
        campaign.strategy = request.form.get("strategy")
        campaign.delay_min = int(request.form.get("delay_min", 60))
        campaign.delay_max = int(request.form.get("delay_max", 120))
        campaign.invites_per_hour_min = int(request.form.get("invites_per_hour_min", 3))
        campaign.invites_per_hour_max = int(request.form.get("invites_per_hour_max", 5))
        
        db.session.commit()
        flash("Campaign settings updated", "success")
        return redirect(url_for("campaigns.detail", campaign_id=campaign_id))
    
    # GET - show edit form
    accounts = Account.query.filter_by(status="active").all()
    channels = Channel.query.all()
    return render_template("campaigns/edit.html", campaign=campaign, accounts=accounts, channels=channels)


@campaigns_bp.route("/<int:campaign_id>/start", methods=["POST"])
@login_required
def start(campaign_id):
    
    # GET - show edit form
    accounts = Account.query.filter_by(status="active").all()
    channels = Channel.query.all()
    return render_template("campaigns/edit.html", campaign=campaign, accounts=accounts, channels=channels)
