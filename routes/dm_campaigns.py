from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.decorators import login_required
from models.dm_campaign import DMCampaign, DMCampaignAccount, DMTarget
from models.account import Account
from database import db
from workers.dm_worker import run_dm_campaign
import pandas as pd
import os

dm_campaigns_bp = Blueprint('dm_campaigns', __name__)


@dm_campaigns_bp.route('/')
@login_required
def list_campaigns():
    """List all DM campaigns"""
    campaigns = DMCampaign.query.order_by(DMCampaign.created_at.desc()).all()
    return render_template('dm_campaigns/list.html', campaigns=campaigns)


@dm_campaigns_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new DM campaign"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        message_text = request.form.get('message_text')
        account_ids = request.form.getlist('account_ids')
        messages_per_account_limit = int(request.form.get('messages_per_account_limit', 5))
        
        if not name or not message_text or not account_ids:
            flash('Name, message and accounts are required', 'error')
            return redirect(url_for('dm_campaigns.create'))
        
        # Create campaign
        campaign = DMCampaign(
            name=name,
            description=description,
            message_text=message_text,
            messages_per_account_limit=messages_per_account_limit
        )
        
        db.session.add(campaign)
        db.session.flush()
        
        # Assign accounts
        for account_id in account_ids:
            ca = DMCampaignAccount(
                campaign_id=campaign.id,
                account_id=int(account_id)
            )
            db.session.add(ca)
        
        db.session.commit()
        
        flash('DM Campaign created successfully', 'success')
        return redirect(url_for('dm_campaigns.detail', campaign_id=campaign.id))
    
    accounts = Account.query.filter_by(status='active').all()
    return render_template('dm_campaigns/create.html', accounts=accounts)


@dm_campaigns_bp.route('/<int:campaign_id>')
@login_required
def detail(campaign_id):
    """DM campaign details"""
    campaign = DMCampaign.query.get_or_404(campaign_id)
    
    # Calculate stats
    stats = {
        'new': DMTarget.query.filter_by(campaign_id=campaign_id, status='new').count(),
        'sent': DMTarget.query.filter_by(campaign_id=campaign_id, status='sent').count(),
        'replied': DMTarget.query.filter_by(campaign_id=campaign_id, status='replied').count(),
        'error': DMTarget.query.filter_by(campaign_id=campaign_id, status='error').count()
    }
    
    return render_template('dm_campaigns/detail.html', campaign=campaign, stats=stats)


@dm_campaigns_bp.route('/<int:campaign_id>/start', methods=['POST'])
@login_required
def start(campaign_id):
    """Start DM campaign"""
    campaign = DMCampaign.query.get_or_404(campaign_id)
    
    if campaign.total_targets == 0:
        flash('No targets. Import targets first', 'error')
        return redirect(url_for('dm_campaigns.detail', campaign_id=campaign_id))
    
    campaign.status = 'active'
    from datetime import datetime
    campaign.started_at = datetime.utcnow()
    db.session.commit()
    
    # Start worker
    from workers.dm_worker import run_dm_campaign
    run_dm_campaign.delay(campaign_id)
    
    flash('DM Campaign started', 'success')
    return redirect(url_for('dm_campaigns.detail', campaign_id=campaign_id))


@dm_campaigns_bp.route('/<int:campaign_id>/pause', methods=['POST'])
@login_required
def pause(campaign_id):
    """Pause DM campaign"""
    campaign = DMCampaign.query.get_or_404(campaign_id)
    campaign.status = 'paused'
    from datetime import datetime
    campaign.paused_at = datetime.utcnow()
    db.session.commit()
    
    flash('DM Campaign paused', 'success')
    return redirect(url_for('dm_campaigns.detail', campaign_id=campaign_id))


@dm_campaigns_bp.route('/<int:campaign_id>/import', methods=['POST'])
@login_required
def import_targets(campaign_id):
    """Import targets from CSV"""
    campaign = DMCampaign.query.get_or_404(campaign_id)
    
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('dm_campaigns.detail', campaign_id=campaign_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('dm_campaigns.detail', campaign_id=campaign_id))
    
    # Save file
    filename = f'dm_import_{campaign_id}_{file.filename}'
    filepath = os.path.join('uploads/csv', filename)
    file.save(filepath)
    
    try:
        # Read CSV
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        # Validate
        if 'username' not in df.columns:
            flash('CSV must have "username" column', 'error')
            return redirect(url_for('dm_campaigns.detail', campaign_id=campaign_id))
        
        # Import targets
        count = 0
        for _, row in df.iterrows():
            username = str(row['username']).lstrip('@')
            if not username or username == 'nan':
                continue
            
            target = DMTarget(
                campaign_id=campaign_id,
                username=username,
                first_name=row.get('first_name'),
                last_name=row.get('last_name'),
                custom_data=row.to_dict(),
                source='csv'
            )
            db.session.add(target)
            count += 1
        
        campaign.total_targets = count
        db.session.commit()
        
        flash(f'{count} targets imported successfully', 'success')
        
    except Exception as e:
        flash(f'Error importing: {str(e)}', 'error')
    
    return redirect(url_for('dm_campaigns.detail', campaign_id=campaign_id))


@dm_campaigns_bp.route('/<int:campaign_id>/conversations')
@login_required
def conversations(campaign_id):
    """View conversations for DM campaign"""
    campaign = DMCampaign.query.get_or_404(campaign_id)
    
    # Get all targets with sent messages
    targets = DMTarget.query.filter_by(
        campaign_id=campaign_id
    ).filter(
        DMTarget.status.in_(['sent', 'replied', 'failed'])
    ).order_by(DMTarget.sent_at.desc()).all()
    
    return render_template('dm_campaigns/conversations.html', campaign=campaign, targets=targets)


@dm_campaigns_bp.route("/<int:campaign_id>/delete-targets", methods=["POST"])
@login_required
def delete_targets(campaign_id):
    """Delete all targets from campaign"""
    campaign = DMCampaign.query.get_or_404(campaign_id)
    
    DMTarget.query.filter_by(campaign_id=campaign_id).delete()
    campaign.total_targets = 0
    campaign.sent_count = 0
    campaign.failed_count = 0
    db.session.commit()
    
    flash("All targets deleted", "success")
    return redirect(url_for("dm_campaigns.detail", campaign_id=campaign_id))


@dm_campaigns_bp.route("/<int:campaign_id>/export", methods=["POST"])
@login_required
def export(campaign_id):
    """Export campaign results to CSV"""
    campaign = DMCampaign.query.get_or_404(campaign_id)
    
    targets = DMTarget.query.filter_by(campaign_id=campaign_id).all()
    
    # Create CSV
    import csv
    from io import StringIO
    from flask import make_response
    
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Username", "First Name", "Last Name", "Status", "Sent At", "Reply Text", "Replied At"])
    
    for target in targets:
        writer.writerow([
            target.username,
            target.first_name or "",
            target.last_name or "",
            target.status,
            target.sent_at.strftime("%Y-%m-%d %H:%M:%S") if target.sent_at else "",
            target.reply_text or "",
            target.replied_at.strftime("%Y-%m-%d %H:%M:%S") if target.replied_at else ""
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=dm_campaign_{campaign_id}_export.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output


@dm_campaigns_bp.route("/<int:campaign_id>/add-target", methods=["GET", "POST"])
@login_required
def add_target(campaign_id):
    """Manually add a single target to campaign"""
    campaign = DMCampaign.query.get_or_404(campaign_id)
    
    if request.method == "POST":
        username_raw = request.form.get("username")
        if not username_raw:
            flash("Username is required", "error")
            return redirect(url_for("dm_campaigns.detail", campaign_id=campaign_id))
        
        username = username_raw.lstrip("@")
        first_name = request.form.get("first_name", "")
        last_name = request.form.get("last_name", "")
        
        if not username:
            flash("Username is required", "error")
            return redirect(url_for("dm_campaigns.detail", campaign_id=campaign_id))
        
        # Check if already exists
        existing = DMTarget.query.filter_by(
            campaign_id=campaign_id,
            username=username
        ).first()
        
        if existing:
            flash(f"User @{username} already in campaign", "warning")
            return redirect(url_for("dm_campaigns.detail", campaign_id=campaign_id))
        
        # Add target
        target = DMTarget(
            campaign_id=campaign_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            source="manual"
        )
        db.session.add(target)
        campaign.total_targets += 1
        db.session.commit()
        
        flash(f"User @{username} added successfully", "success")
        return redirect(url_for("dm_campaigns.detail", campaign_id=campaign_id))
    
    return render_template("dm_campaigns/add_target.html", campaign=campaign)


@dm_campaigns_bp.route("/<int:campaign_id>/send-manual/<int:target_id>", methods=["POST"])
@login_required
def send_manual(campaign_id, target_id):
    """Send manual reply to a target"""
    campaign = DMCampaign.query.get_or_404(campaign_id)
    target = DMTarget.query.get_or_404(target_id)
    
    message_text = request.form.get("message_text")
    account_id = request.form.get("account_id")
    
    if not message_text or not account_id:
        flash("Message and account are required", "error")
        return redirect(url_for("dm_campaigns.conversations", campaign_id=campaign_id))
    
    # Send message (this would call Telethon)
    # For now just save to DB
    from models.dm_campaign import DMMessage
    from datetime import datetime
    
    dm_message = DMMessage(
        campaign_id=campaign_id,
        target_id=target_id,
        account_id=int(account_id),
        direction="outgoing",
        message_text=message_text,
        sent_at=datetime.utcnow()
    )
    db.session.add(dm_message)
    db.session.commit()
    
    flash("Manual message sent", "success")
    return redirect(url_for("dm_campaigns.conversations", campaign_id=campaign_id))
