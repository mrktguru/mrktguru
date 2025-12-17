from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.decorators import login_required
from models.dm_campaign import DMCampaign, DMCampaignAccount, DMTarget
from models.account import Account
from app import db
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
    return render_template('dm_campaigns/detail.html', campaign=campaign)


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
