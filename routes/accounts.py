from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils.decorators import login_required
from models.account import Account, DeviceProfile, AccountSubscription
from models.proxy import Proxy
from app import db
from utils.device_emulator import generate_device_profile, get_random_warmup_channels
from utils.telethon_helper import verify_session
import os
from werkzeug.utils import secure_filename

accounts_bp = Blueprint('accounts', __name__)


@accounts_bp.route('/')
@login_required
def list_accounts():
    """List all accounts"""
    accounts = Account.query.order_by(Account.created_at.desc()).all()
    proxies = Proxy.query.filter_by(status='active').all()
    return render_template('accounts/list.html', accounts=accounts, proxies=proxies)


@accounts_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload session files"""
    if request.method == 'POST':
        files = request.files.getlist('session_files')
        proxy_assignments = request.form.get('proxy_assignments', '{}')
        
        if not files:
            flash('No files selected', 'error')
            return redirect(url_for('accounts.upload'))
        
        success_count = 0
        for file in files:
            if file and file.filename.endswith('.session'):
                filename = secure_filename(file.filename)
                filepath = os.path.join('uploads/sessions', filename)
                file.save(filepath)
                
                # Extract phone from filename
                phone = filename.replace('.session', '')
                
                # Create account
                account = Account(
                    phone=phone,
                    session_file_path=filepath,
                    status='active'
                )
                db.session.add(account)
                db.session.flush()
                
                # Generate device profile
                device = generate_device_profile('RU')
                device_profile = DeviceProfile(
                    account_id=account.id,
                    **device
                )
                db.session.add(device_profile)
                
                # Add warmup subscriptions
                warmup_channels = get_random_warmup_channels(15)
                for channel in warmup_channels:
                    subscription = AccountSubscription(
                        account_id=account.id,
                        channel_username=channel,
                        subscription_source='auto'
                    )
                    db.session.add(subscription)
                
                success_count += 1
        
        db.session.commit()
        flash(f'{success_count} accounts uploaded successfully', 'success')
        return redirect(url_for('accounts.list_accounts'))
    
    proxies = Proxy.query.filter_by(status='active').all()
    return render_template('accounts/upload.html', proxies=proxies)


@accounts_bp.route('/<int:account_id>')
@login_required
def detail(account_id):
    """Account details"""
    account = Account.query.get_or_404(account_id)
    return render_template('accounts/detail.html', account=account)


@accounts_bp.route('/<int:account_id>/verify', methods=['POST'])
@login_required
def verify(account_id):
    """Verify account session"""
    import asyncio
    
    account = Account.query.get_or_404(account_id)
    
    try:
        result = asyncio.run(verify_session(account_id))
        
        if result['success']:
            account.status = 'active'
            account.health_score = 100
            flash(f'Account verified: {result["user"]["username"]}', 'success')
        else:
            account.status = 'invalid'
            account.health_score = 0
            flash(f'Verification failed: {result["error"]}', 'error')
        
        db.session.commit()
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('accounts.detail', account_id=account_id))


@accounts_bp.route('/<int:account_id>/delete', methods=['POST'])
@login_required
def delete(account_id):
    """Delete account"""
    account = Account.query.get_or_404(account_id)
    
    # Delete session file
    if os.path.exists(account.session_file_path):
        os.remove(account.session_file_path)
    
    db.session.delete(account)
    db.session.commit()
    
    flash('Account deleted', 'success')
    return redirect(url_for('accounts.list_accounts'))


@accounts_bp.route('/<int:account_id>/assign-proxy', methods=['POST'])
@login_required
def assign_proxy(account_id):
    """Assign proxy to account"""
    account = Account.query.get_or_404(account_id)
    proxy_id = request.form.get('proxy_id')
    
    if proxy_id:
        account.proxy_id = int(proxy_id)
    else:
        account.proxy_id = None
    
    db.session.commit()
    flash('Proxy assignment updated', 'success')
    return redirect(url_for('accounts.detail', account_id=account_id))


@accounts_bp.route('/<int:account_id>/add-subscription', methods=['POST'])
@login_required
def add_subscription(account_id):
    """Add channel subscription"""
    account = Account.query.get_or_404(account_id)
    channel_username = request.form.get('channel_username', '').lstrip('@')
    notes = request.form.get('notes')
    
    if not channel_username:
        flash('Channel username is required', 'error')
        return redirect(url_for('accounts.detail', account_id=account_id))
    
    subscription = AccountSubscription(
        account_id=account_id,
        channel_username=channel_username,
        subscription_source='manual',
        notes=notes
    )
    db.session.add(subscription)
    db.session.commit()
    
    flash(f'Subscription to @{channel_username} added', 'success')
    return redirect(url_for('accounts.detail', account_id=account_id))


@accounts_bp.route('/<int:account_id>/subscriptions/<int:sub_id>/remove', methods=['POST'])
@login_required
def remove_subscription(account_id, sub_id):
    """Remove subscription"""
    subscription = AccountSubscription.query.get_or_404(sub_id)
    
    if subscription.account_id != account_id:
        flash('Invalid subscription', 'error')
        return redirect(url_for('accounts.detail', account_id=account_id))
    
    db.session.delete(subscription)
    db.session.commit()
    
    flash('Subscription removed', 'success')
    return redirect(url_for('accounts.detail', account_id=account_id))
