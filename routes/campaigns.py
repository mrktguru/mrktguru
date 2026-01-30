from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from utils.decorators import login_required
from models.campaign import InviteCampaign
from models.channel import Channel
from models.account import Account
from modules.campaigns.services.management import CampaignManager
from modules.campaigns.services.importing import CampaignImporter
from modules.campaigns.services.stats import CampaignStats
from modules.campaigns.services.targets import TargetManager

campaigns_bp = Blueprint('campaigns', __name__)

@campaigns_bp.route('/')
@login_required
def list_campaigns():
    """List all invite campaigns"""
    # Direct query for read efficiency, or could move to Manager
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
        
        CampaignManager.create_campaign(name, description, channel_id, strategy, account_ids)
        
        flash('Campaign created successfully', 'success')
        # We need the ID. CampaignManager should return object.
        # Assuming create_campaign returns the created campaign object
        # I need to verify my Manager implementation returns it. Yes it does.
        # But I need to fetch it again or assign. simpler to redirect to list if I don't catch ID immediately,
        # but Manager returns 'campaign', so I can use campaign.id if I capture it.
        # However, create_campaign commits, so it has ID.
        return redirect(url_for('campaigns.list_campaigns')) 
    
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


@campaigns_bp.route('/<int:campaign_id>/pause', methods=['POST'])
@login_required
def pause(campaign_id):
    """Pause campaign"""
    CampaignManager.pause_campaign(campaign_id)
    flash('Campaign paused', 'success')
    return redirect(url_for('campaigns.detail', campaign_id=campaign_id))


@campaigns_bp.route('/<int:campaign_id>/stop', methods=['POST'])
@login_required
def stop(campaign_id):
    """Stop campaign"""
    CampaignManager.stop_campaign(campaign_id)
    flash('Campaign stopped', 'success')
    return redirect(url_for('campaigns.detail', campaign_id=campaign_id))


@campaigns_bp.route('/<int:campaign_id>/start', methods=["POST"])
@login_required
def start(campaign_id):
    success, msg = CampaignManager.start_campaign(campaign_id)
    if success:
        flash(msg + "! First invite scheduled immediately.", "success")
    else:
        flash(msg, "warning")
    return redirect(url_for("campaigns.detail", campaign_id=campaign_id))


@campaigns_bp.route('/<int:campaign_id>/import-users', methods=['POST'])
@login_required
def import_users(campaign_id):
    """Import users from source channel (Simple)"""
    source_channel = request.form.get('source_channel')
    if not source_channel:
        flash('Source channel is required', 'error')
        return redirect(url_for('campaigns.detail', campaign_id=campaign_id))
        
    success, msg = CampaignImporter.parse_from_channel(campaign_id, source_channel)
    if success:
        flash('Parsing users in background...', 'info')
    else:
        flash(msg, 'error')
        
    return redirect(url_for('campaigns.detail', campaign_id=campaign_id))


@campaigns_bp.route("/<int:campaign_id>/parse-source", methods=["GET", "POST"])
@login_required
def parse_source(campaign_id):
    """Parse users from source channel (Advanced)"""
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    
    if request.method == "POST":
        source_channel = request.form.get("source_channel")
        limit = int(request.form.get("limit", 1000))
        # Filters logic is passed via options if implemented in Importer, 
        # For now, default logic handles it via worker arguments usually. 
        # My Importer wrapper assumes simple call. 
        # I'll use the same wrapper for now.
        
        success, msg = CampaignImporter.parse_from_channel(campaign_id, source_channel, limit)
        if success:
            flash(f"Parsing started from @{source_channel}. This will take a few minutes.", "info")
            return redirect(url_for("campaigns.detail", campaign_id=campaign_id))
        else:
            flash(msg, "error")
            
    return render_template("campaigns/parse_source.html", campaign=campaign)


@campaigns_bp.route("/<int:campaign_id>/upload-targets", methods=["POST"])
@login_required
def upload_targets(campaign_id):
    """Upload target users from CSV/XLS file"""
    if "file" not in request.files:
        flash("No file uploaded", "error")
        return redirect(url_for("campaigns.detail", campaign_id=campaign_id))
    
    file = request.files["file"]
    imported, skipped, error = CampaignImporter.import_from_file(campaign_id, file)
    
    if error:
        flash(error, "error")
    else:
        flash(f"Successfully imported {imported} users. Skipped {skipped} duplicates.", "success")
        
    return redirect(url_for("campaigns.detail", campaign_id=campaign_id))


@campaigns_bp.route("/<int:campaign_id>/logs")
@login_required
def logs(campaign_id):
    """View campaign logs"""
    # View logic stays in route or moved to stats? Stays here for pagination handling convenience
    from models.campaign import InviteLog
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    page = request.args.get("page", 1, type=int)
    per_page = 50
    logs_query = InviteLog.query.filter_by(campaign_id=campaign_id).order_by(InviteLog.timestamp.desc())
    logs_paginated = logs_query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template("campaigns/logs.html", campaign=campaign, logs=logs_paginated)


@campaigns_bp.route("/<int:campaign_id>/stats")
@login_required
def stats(campaign_id):
    """Detailed campaign statistics"""
    data = CampaignStats.get_detailed_stats(campaign_id)
    return render_template("campaigns/stats.html", **data)


@campaigns_bp.route("/<int:campaign_id>/export", methods=["POST"])
@login_required
def export(campaign_id):
    """Export campaign results to CSV"""
    csv_data = CampaignStats.generate_csv_export(campaign_id)
    
    output = make_response(csv_data)
    output.headers["Content-Disposition"] = f"attachment; filename=invite_campaign_{campaign_id}_export.csv"
    output.headers["Content-type"] = "text/csv"
    return output


@campaigns_bp.route("/<int:campaign_id>/assign-accounts", methods=["POST"])
@login_required
def assign_accounts(campaign_id):
    account_ids = request.form.getlist("account_ids")
    if not account_ids:
        flash("No accounts selected", "error")
    else:
        count = CampaignManager.assign_accounts(campaign_id, account_ids)
        flash(f"Added {count} accounts to campaign", "success")
        
    return redirect(url_for("campaigns.detail", campaign_id=campaign_id))


@campaigns_bp.route("/<int:campaign_id>/remove-account/<int:account_id>", methods=["POST"])
@login_required
def remove_account(campaign_id, account_id):
    if CampaignManager.remove_account(campaign_id, account_id):
        flash("Account removed from campaign", "success")
    else:
        flash("Account not found in campaign", "error")
    return redirect(url_for("campaigns.detail", campaign_id=campaign_id))


@campaigns_bp.route("/<int:campaign_id>/edit", methods=["GET", "POST"])
@login_required
def edit(campaign_id):
    """Edit campaign settings"""
    campaign = InviteCampaign.query.get_or_404(campaign_id)
    
    if request.method == "POST":
        CampaignManager.update_settings(campaign_id, request.form)
        flash("Campaign settings updated", "success")
        return redirect(url_for("campaigns.detail", campaign_id=campaign_id))
    
    accounts = Account.query.filter_by(status="active").all()
    channels = Channel.query.all()
    return render_template("campaigns/edit.html", campaign=campaign, accounts=accounts, channels=channels)


@campaigns_bp.route("/<int:campaign_id>/update-settings", methods=["POST"])
@login_required  
def update_settings(campaign_id):
    """Update campaign settings (Quick)"""
    CampaignManager.update_settings(campaign_id, request.form)
    flash("Settings saved successfully", "success")
    return redirect(url_for("campaigns.detail", campaign_id=campaign_id))


@campaigns_bp.route("/<int:campaign_id>/delete-target/<int:user_id>", methods=["POST"])
@login_required
def delete_target(campaign_id, user_id):
    """Delete a target user from campaign"""
    TargetManager.delete_target(campaign_id, user_id)
    flash("User deleted successfully", "success")
    return redirect(url_for("campaigns.detail", campaign_id=campaign_id))
