from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils.decorators import login_required
from models.account import Account, DeviceProfile, AccountSubscription
from models.tdata_metadata import TDataMetadata
from models.proxy import Proxy
from models.proxy_network import ProxyNetwork
from database import db
from utils.device_emulator import generate_device_profile
from utils.telethon_helper import verify_session
from utils.proxy_manager import assign_dynamic_port, release_dynamic_port
import os
from werkzeug.utils import secure_filename
import asyncio
import random

import nest_asyncio
nest_asyncio.apply()

# Service Layer imports
from modules.accounts.services import (
    CrudService, 
    MetadataService, 
    ProxyService,
    VerificationService,
    SecurityService,
    UploadService,
    ProfileService,
    SubscriptionService,
    DeviceProfileService,
    DeviceConfig
)
from modules.accounts.exceptions import (
    AccountNotFoundError,
    ProxyNotFoundError,
    ProxyNetworkNotFoundError,
    ProxyAssignmentError,
    SessionNotConfiguredError,
    TwoFANotSetError,
    CooldownError
)

accounts_bp = Blueprint("accounts", __name__)


@accounts_bp.route("/")
@login_required
def list_accounts():
    """List all accounts"""
    page = request.args.get('page', 1, type=int)
    
    # Use CrudService for business logic
    result = CrudService.list_accounts(page=page, per_page=50)
    
    return render_template(
        "accounts/list.html", 
        accounts=result.accounts, 
        proxies=result.proxies,
        pagination=result.pagination
    )


@accounts_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """Upload and validate session files with safety checks"""
    from models.proxy import Proxy
    
    if request.method == "POST":
        files = request.files.getlist("session_files")
        
        if not files or files[0].filename == "":
            flash("No files selected", "error")
            return redirect(url_for("accounts.upload"))
        
        # Get form parameters
        region = request.form.get("region", "US")
        proxy_mode = request.form.get("proxy_mode", "none")
        specific_proxy_id = request.form.get("specific_proxy")
        source = request.form.get("source", "")
        tags = request.form.get("tags", "")
        
        # Process uploads via service
        result = UploadService.upload_batch(
            files=files,
            region=region,
            proxy_mode=proxy_mode,
            specific_proxy_id=specific_proxy_id,
            source=source,
            tags=tags
        )
        
        # Show notifications
        if result.uploaded > 0:
            flash(f"✅ Successfully uploaded {result.uploaded} session file(s)", "success")
        if result.skipped > 0:
            flash(f"⚠️ Skipped {result.skipped} duplicate account(s)", "warning")
        if result.quarantined > 0:
            flash(f"🔒 Quarantined {result.quarantined} suspicious file(s)", "warning")
        for error in result.errors[:10]:
            flash(f"❌ {error}", "error")
        if len(result.errors) > 10:
            flash(f"... and {len(result.errors) - 10} more errors", "error")
        
        return redirect(url_for("accounts.list_accounts"))
    
    # GET request - show upload form
    proxies = Proxy.query.filter_by(status='active').all()
    return render_template("accounts/upload.html", proxies=proxies)


@accounts_bp.route("/<int:account_id>")
@login_required
def detail(account_id):
    """Account details"""
    from models.account_session import AccountSession
    from utils.debug_logger import debug_log
    
    try:
        # Use CrudService for business logic
        result = CrudService.get_account_detail(account_id)
        
        # DEBUG: Check persisted sessions
        session_count_rel = result.account.active_sessions.count()
        session_count_direct = AccountSession.query.filter_by(account_id=account_id).count()
        debug_log(f"Route Detail: Account {account_id} - Rel count: {session_count_rel}, Direct count: {session_count_direct}")
        
        return render_template(
            "accounts/detail.html",
            account=result.account,
            proxies=result.proxies,
            proxy_networks=result.proxy_networks,
            json_device_params=result.json_device_params,
            recent_logs=result.recent_logs
        )
    except AccountNotFoundError:
        flash("Account not found", "error")
        return redirect(url_for("accounts.list_accounts"))


@accounts_bp.route("/<int:account_id>/verify", methods=["POST"])
@login_required
def verify(account_id):
    """Verify account safe strategy"""
    # Get enable_anchor from form
    enable_anchor = request.form.get('enable_anchor') == 'on'
    
    try:
        result = VerificationService.verify_account(account_id, enable_anchor=enable_anchor)
        
        if result.success:
            flash(f"✅ {result.message}", "success")
        else:
            # Map error types to icons
            icons = {
                'flood_wait': '⏱️',
                'banned': '🚫',
                'invalid_session': '🔑',
                'handshake_failed': '❌'
            }
            icon = icons.get(result.error_type, '❌')
            flash(f"{icon} {result.message}", "error")
            
    except SessionNotConfiguredError:
        flash("Cannot verify: No session data configured. Please configure TData or login.", "error")
    except AccountNotFoundError:
        flash("Account not found", "error")
    except Exception as e:
        flash(f"System Error: {str(e)}", "error")
        
    return redirect(url_for('accounts.detail', account_id=account_id))
    
@accounts_bp.route("/<int:account_id>/sync-from-telegram", methods=["POST"])
@login_required
def sync_from_telegram(account_id):
    """Sync profile data from Telegram (with rate limiting)"""
    try:
        result = VerificationService.sync_profile(account_id)
        
        if result.success:
            flash("✅ Profile synced successfully", "success")
            if request.is_json:
                return jsonify({'success': True, 'data': result.data})
        else:
            flash(f"❌ Sync failed: {result.error}", "error")
            if request.is_json:
                return jsonify({'success': False, 'error': result.error})
                
    except CooldownError as e:
        flash(f"⏱️ {str(e)}", "warning")
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)})
    except AccountNotFoundError:
        flash("Account not found", "error")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    
    return redirect(url_for("accounts.detail", account_id=account_id))



@accounts_bp.route("/<int:account_id>/delete", methods=["POST"])
@login_required
def delete(account_id):
    """Delete account"""
    try:
        CrudService.delete_account(account_id)
        flash("Account deleted successfully", "success")
    except AccountNotFoundError:
        flash("Account not found", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting account: {str(e)}", "error")
    
    return redirect(url_for("accounts.list_accounts"))


@accounts_bp.route("/<int:account_id>/assign-proxy", methods=["POST"])
@login_required
def assign_proxy(account_id):
    """Assign proxy (individual or network) to account"""
    selection = request.form.get("proxy_selection")
    
    try:
        result = ProxyService.assign_proxy_from_selection(account_id, selection)
        flash(result.message, "success" if result.success else "error")
    except AccountNotFoundError:
        flash("Account not found", "error")
    except (ProxyNotFoundError, ProxyNetworkNotFoundError):
        flash("Proxy or network not found", "error")
    except ProxyAssignmentError as e:
        flash(str(e), "error")
    except Exception as e:
        db.session.rollback()
        flash(f"Error assigning proxy: {str(e)}", "error")
    
    return redirect(url_for("accounts.detail", account_id=account_id))


@accounts_bp.route('/<int:account_id>/add_tag', methods=['POST'])
@login_required
def add_tag(account_id):
    """Add a single tag to account"""
    new_tag = request.form.get('new_tag', '').strip()
    
    if new_tag:
        try:
            added = MetadataService.add_tag(account_id, new_tag)
            if added:
                flash(f"Added tag: {new_tag}", 'success')
        except AccountNotFoundError:
            flash("Account not found", "error")
            
    return redirect(url_for('accounts.detail', account_id=account_id))


@accounts_bp.route('/<int:account_id>/remove_tag', methods=['POST'])
@login_required
def remove_tag(account_id):
    """Remove a single tag from account"""
    tag_to_remove = request.form.get('tag')
    
    if tag_to_remove:
        try:
            removed = MetadataService.remove_tag(account_id, tag_to_remove)
            if removed:
                flash(f"Removed tag: {tag_to_remove}", 'success')
        except AccountNotFoundError:
            flash("Account not found", "error")
            
    return redirect(url_for('accounts.detail', account_id=account_id))


@accounts_bp.route('/<int:account_id>/update_source', methods=['POST'])
@login_required
def update_source(account_id):
    """Update account source inline"""
    new_source = request.form.get('source', '').strip()
    
    try:
        changed = MetadataService.update_source(account_id, new_source)
        if changed:
            flash("Source updated", "success")
    except AccountNotFoundError:
        flash("Account not found", "error")
            
    return redirect(url_for('accounts.detail', account_id=account_id))

@accounts_bp.route("/<int:account_id>/add-subscription", methods=["POST"])
@login_required
def add_subscription(account_id):
    """Add channel subscription - actually joins the channel/group"""
    channel_input = request.form.get("channel_username", "").strip()
    notes = request.form.get("notes", "").strip()
    
    if not channel_input:
        flash("Channel username is required", "error")
        return redirect(url_for("accounts.detail", account_id=account_id))
    
    try:
        result = SubscriptionService.join_channel(
            account_id=account_id,
            channel_input=channel_input,
            notes=notes,
            source="manual"
        )
        
        if result.success:
            flash(result.message, "success")
        elif result.status == 'exists':
            flash(result.message, "warning")
        else:
            flash(result.message, "error")
            
    except AccountNotFoundError:
        flash("Account not found", "error")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    
    return redirect(url_for("accounts.detail", account_id=account_id))


@accounts_bp.route("/<int:account_id>/subscriptions/<int:sub_id>/remove", methods=["POST"])
@login_required
def remove_subscription(account_id, sub_id):
    """Remove subscription"""
    if SubscriptionService.remove_subscription(account_id, sub_id):
        flash("Subscription removed", "info")
    else:
        flash("Subscription not found", "error")
    return redirect(url_for("accounts.detail", account_id=account_id))


@accounts_bp.route("/<int:account_id>/update-profile", methods=["POST"])
@login_required
def update_profile(account_id):
    """Update editable profile fields"""
    # Get form data
    username = request.form.get("username", "").strip().lstrip("@") if "username" in request.form else None
    bio = request.form.get("bio", "").strip() if "bio" in request.form else None
    source = request.form.get("source", "").strip()
    tags_str = request.form.get("tags", "")
    tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else None
    
    # Get photo file
    photo_file = None
    if "photo" in request.files:
        photo = request.files["photo"]
        if photo and photo.filename:
            photo_file = photo
    
    try:
        # Update Telegram profile (async operations)
        if username or bio or photo_file:
            result = ProfileService.update_telegram_profile(
                account_id=account_id,
                username=username if username else None,
                bio=bio if bio else None,
                photo_file=photo_file
            )
            
            if result.updated_fields:
                flash(f"✅ Updated: {', '.join(result.updated_fields)}", "success")
            if result.errors:
                for error in result.errors:
                    flash(f"⚠️ {error}", "warning")
        
        # Update local metadata (sync, no Telegram API)
        if source is not None or tags is not None:
            ProfileService.update_local_metadata(
                account_id=account_id,
                source=source,
                tags=tags
            )
            flash("Metadata updated", "success")
            
    except AccountNotFoundError:
        flash("Account not found", "error")
    except Exception as e:
        flash(f"Error updating profile: {str(e)}", "error")
    
    return redirect(url_for('accounts.detail', account_id=account_id))


# ==================== WARMUP SETTINGS ROUTES ====================

# WARMUP DISABLED: @accounts_bp.route("/<int:account_id>/warmup")
# WARMUP DISABLED: @login_required
# WARMUP DISABLED: def warmup_settings(account_id):
# WARMUP DISABLED:     """View warmup settings for account"""
# WARMUP DISABLED:     from models.warmup import ConversationPair, WarmupActivity, WarmupChannelTheme
# WARMUP DISABLED:     from models.account import AccountSubscription
# WARMUP DISABLED:     
# WARMUP DISABLED:     account = Account.query.get_or_404(account_id)
# WARMUP DISABLED:     
# WARMUP DISABLED:     # Get subscriptions (these are used for warmup reading)
# WARMUP DISABLED:     warmup_channels = AccountSubscription.query.filter_by(
# WARMUP DISABLED:         account_id=account_id,
# WARMUP DISABLED:         is_active=True
# WARMUP DISABLED:     ).all()
# WARMUP DISABLED:     
# WARMUP DISABLED:     # Get conversation pairs
# WARMUP DISABLED:     pairs = ConversationPair.query.filter(
# WARMUP DISABLED:         db.or_(
# WARMUP DISABLED:             ConversationPair.account_a_id == account_id,
# WARMUP DISABLED:             ConversationPair.account_b_id == account_id
# WARMUP DISABLED:         )
# WARMUP DISABLED:     ).all()
# WARMUP DISABLED:     
# WARMUP DISABLED:     # Get partner accounts for each pair
# WARMUP DISABLED:     conversation_partners = []
# WARMUP DISABLED:     for pair in pairs:
# WARMUP DISABLED:         partner_id = pair.account_b_id if pair.account_a_id == account_id else pair.account_a_id
# WARMUP DISABLED:         partner = Account.query.get(partner_id)
# WARMUP DISABLED:         if partner:
# WARMUP DISABLED:             conversation_partners.append({
# WARMUP DISABLED:                 "pair_id": pair.id,
# WARMUP DISABLED:                 "partner": partner,
# WARMUP DISABLED:                 "last_conversation": pair.last_conversation_at,
# WARMUP DISABLED:                 "conversation_count": pair.conversation_count
# WARMUP DISABLED:             })
# WARMUP DISABLED:     
# WARMUP DISABLED:     # Get recent warmup activities
# WARMUP DISABLED:     recent_activities = WarmupActivity.query.filter_by(
# WARMUP DISABLED:         account_id=account_id
# WARMUP DISABLED:     ).order_by(WarmupActivity.timestamp.desc()).limit(20).all()
# WARMUP DISABLED:     
# WARMUP DISABLED:     # Get available themes
# WARMUP DISABLED:     themes = WarmupChannelTheme.query.all()
# WARMUP DISABLED:     
# WARMUP DISABLED:     # Get other accounts for pairing
# WARMUP DISABLED:     other_accounts = Account.query.filter(
# WARMUP DISABLED:         Account.id != account_id,
# WARMUP DISABLED:         Account.status.in_(['warming_up', 'active'])
# WARMUP DISABLED:     ).all()
# WARMUP DISABLED:     
# WARMUP DISABLED:     return render_template(
# WARMUP DISABLED:         "accounts/warmup_settings.html",
# WARMUP DISABLED:         account=account,
# WARMUP DISABLED:         warmup_channels=warmup_channels,
# WARMUP DISABLED:         conversation_partners=conversation_partners,
# WARMUP DISABLED:         recent_activities=recent_activities,
# WARMUP DISABLED:         themes=themes,
# WARMUP DISABLED:         other_accounts=other_accounts
# WARMUP DISABLED:     )


# DEPRECATED: Moved to warmup_routes.py
# @accounts_bp.route("/<int:account_id>/warmup/add-channel", methods=["POST"])
# @login_required
# def add_warmup_channel(account_id):
#     """Add a channel for warmup reading"""
#     from models.warmup import AccountWarmupChannel
#     
#     account = Account.query.get_or_404(account_id)
#     channel_username = request.form.get("channel_username", "").strip().lstrip("@")
#     
#     if not channel_username:
#         flash("Channel username is required", "error")
#         return redirect(url_for("accounts.warmup_settings", account_id=account_id))
#     
#     # Check if already exists
#     existing = AccountWarmupChannel.query.filter_by(
#         account_id=account_id,
#         channel_username=channel_username
#     ).first()
#     
#     if existing:
#         flash(f"Channel @{channel_username} already added", "warning")
#         return redirect(url_for("accounts.warmup_settings", account_id=account_id))
#     
#     # Add channel
#     warmup_channel = AccountWarmupChannel(
#         account_id=account_id,
#         channel_username=channel_username,
#         source="manual"
#     )
#     db.session.add(warmup_channel)
#     db.session.commit()
#     
#     flash(f"Added @{channel_username} for warmup reading", "success")
#     return redirect(url_for("accounts.warmup_settings", account_id=account_id))



# Warmup theme route removed


# Warmup remove channel route removed


# Pair routes removed


# Warmup control routes removed



@accounts_bp.route("/<int:account_id>/activity-logs")
@login_required
def activity_logs(account_id):
    """View activity logs for account"""
    from models.activity_log import AccountActivityLog
    
    account = Account.query.get_or_404(account_id)
    
    # Get filter parameters
    action_type = request.args.get("action_type")
    category = request.args.get("category")
    status = request.args.get("status")
    limit = int(request.args.get("limit", 100))
    
    # Build query
    query = AccountActivityLog.query.filter_by(account_id=account_id)
    
    if action_type:
        query = query.filter_by(action_type=action_type)
    if category:
        query = query.filter_by(action_category=category)
    if status:
        query = query.filter_by(status=status)
    
    # Get logs
    logs = query.order_by(AccountActivityLog.timestamp.desc()).limit(limit).all()
    
    # Get unique action types and categories for filters
    all_logs = AccountActivityLog.query.filter_by(account_id=account_id).all()
    action_types = sorted(set(log.action_type for log in all_logs if log.action_type))
    categories = sorted(set(log.action_category for log in all_logs if log.action_category))
    
    return render_template(
        "accounts/activity_logs.html",
        account=account,
        logs=logs,
        action_types=action_types,
        categories=categories,
        current_filters={
            "action_type": action_type,
            "category": category,
            "status": status,
            "limit": limit
        }
    )



# ==================== TDATA ROUTES ====================
# Import TData-specific routes
from routes.tdata_routes import upload_tdata, configure_tdata, add_tdata_api_to_manager

# Register TData routes
accounts_bp.add_url_rule('/upload-tdata', view_func=upload_tdata, methods=['GET', 'POST'])
accounts_bp.add_url_rule('/<int:account_id>/configure-tdata', view_func=configure_tdata, methods=['GET', 'POST'])
accounts_bp.add_url_rule('/<int:account_id>/add-tdata-api-to-manager', view_func=add_tdata_api_to_manager, methods=['POST'])

"""
Safe Verification Route - Add this to routes/accounts.py after the verify route
"""

@accounts_bp.route("/<int:account_id>/verify-safe", methods=["POST"])
@login_required
def verify_safe(account_id):
    """
    Safe verification with three methods:
    - self_check: Safest (Saved Messages)
    - public_channel: Safe (Read public channel)
    - get_me: Moderate (with delays and cooldown)
    """
    from utils.telethon_helper import get_telethon_client
    from utils.safe_verification import safe_self_check, safe_get_me, check_via_public_channel
    from utils.activity_logger import ActivityLogger
    import asyncio
    from datetime import datetime
    
    account = Account.query.get_or_404(account_id)
    method = request.form.get('method', 'self_check')  # Default to safest
    
    # Validate method
    valid_methods = ['self_check', 'get_me', 'public_channel']
    if method not in valid_methods:
        return jsonify({'success': False, 'error': f'Invalid method. Use: {", ".join(valid_methods)}'}), 400
    
    # Run with Session Orchestrator
    from utils.session_orchestrator import SessionOrchestrator
    from tasks.verification import task_safe_self_check, task_safe_get_me, task_public_channel_verify, task_perform_alignment_check
    
    # Anti-Lock
    db.session.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    bot = SessionOrchestrator(account_id)
    
    try:
        task_func = None
        args = []
        
        if method == 'self_check':
            task_func = task_safe_self_check
        elif method == 'get_me':
            task_func = task_safe_get_me
            args = [account.last_verification_time]
        elif method == 'public_channel':
            task_func = task_public_channel_verify
            
        # Execute via Orchestrator
        result = loop.run_until_complete(bot.execute(task_func, *args))
        
        if result['success']:
            # ... (success logic remains similar, but we need to re-fetch account)
            try:
                account_ref = Account.query.get(account_id)
                
                # Check mapping from task result
                user = result
                # task_safe_self_check returns user_id, username etc top level? 
                # Yes, checking utils/safe_verification.py, returns dict with keys.
                
                if user.get('user_id'): account_ref.telegram_id = user.get('user_id')
                if user.get('first_name'): account_ref.first_name = user.get('first_name')
                if user.get('last_name'): account_ref.last_name = user.get('last_name')
                if user.get('username'): account_ref.username = user.get('username')
                
                account_ref.status = 'active'
                account_ref.verified = True
                account_ref.last_activity = datetime.utcnow()
                
                account_ref.last_verification_method = method
                account_ref.last_verification_time = datetime.utcnow()
                account_ref.verification_count = (account_ref.verification_count or 0) + 1
                
                db.session.commit()
            except Exception as db_err:
                 db.session.rollback()
                 print(f"DB Error: {db_err}")
            
            logger.log(
                action_type='safe_verification_success',
                status='success',
                description=f'Verification successful via {method}. ({result.get("debug_info", "")})',
                category='system'
            )
            
            flash(f"✅ Verification successful via {method}! {result.get('debug_info', '')}", "success")
            return jsonify({
                 'success': True,
                 'method': method,
                 'user': {
                     'id': result.get('user_id'),
                     'username': result.get('username'),
                     'first_name': result.get('first_name')
                 },
                 'duration': result.get('duration'),
                 'next_check_allowed': result.get('next_check_allowed'),
                 'debug_info': result.get('debug_info')
            })
            
        else:
             # Handle failures (Error logic same as before, just using result dict)
             error_type = result.get('error_type', 'generic_error')
             
             # Re-fetch for updating status
             try:
                account_ref = Account.query.get(account_id)
                
                if error_type == 'flood_wait':
                    account_ref.status = 'flood_wait'
                    wait_time = result.get('wait', 0)
                    flash(f"❌ Telegram FloodWait limit. Please wait {wait_time} seconds.", "error")
                    
                elif error_type == 'banned':
                    account_ref.status = 'banned'
                    account_ref.health_score = 0
                    flash(f"❌ Account is BANNED by Telegram: {result.get('error')}", "error")
                    
                elif error_type == 'invalid_session':
                    account_ref.status = 'error'
                    flash(f"❌ Session Invalid: {result.get('error')}", "error")
                    
                else:
                    account_ref.status = 'error'
                    flash(f"❌ Verification failed: {result.get('error')}", "error")
                    
                db.session.commit()
             except:
                 pass
                 
             return jsonify(result), 400 if error_type == 'invalid_session' else (429 if error_type == 'flood_wait' or error_type == 'cooldown' else 500)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
        
    finally:
        loop.run_until_complete(bot.stop())
        loop.close()


# Warmup routes moved to routes/warmup_routes.py


@accounts_bp.route("/<int:account_id>/sync-profile", methods=["POST"])
@login_required
def sync_profile_from_telegram(account_id):
    """
    Sync profile info from Telegram (Manual Trigger)
    """
    # Session Orchestrator Refactor
    from utils.session_orchestrator import SessionOrchestrator
    from tasks.profile import task_sync_profile, task_update_profile
    from utils.activity_logger import ActivityLogger
    import asyncio
    
    # Anti-Lock
    db.session.close()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    bot = SessionOrchestrator(account_id)
    
    try:
        # Execute Task
        result = loop.run_until_complete(bot.execute(task_sync_profile))
        
        # Re-fetch account
        account_ref = Account.query.get(account_id)
        if not account_ref:
            return jsonify({"success": False, "error": "Account not found"}), 404
            
        if result['success']:
            data = result['data']
            
            # Update local DB
            # Use getattr with default to avoid None if key missing
            if data.get('username') is not None: account_ref.username = data.get('username')
            if data.get('first_name') is not None: account_ref.first_name = data.get('first_name')
            if data.get('last_name') is not None: account_ref.last_name = data.get('last_name')
            # phone? likely matches, but ignore for safety unless needed
            if data.get('bio') is not None: account_ref.bio = data.get('bio')
            if data.get('photo_path'): account_ref.photo_url = data.get('photo_path')
            
            account_ref.last_sync_at = datetime.utcnow()
            
            # Log
            logger = ActivityLogger(account_id)
            logger.log_sync(status='success', items_synced=5)
            
            db.session.commit()
            return jsonify({"success": True, "data": data})
        else:
            return jsonify({"success": False, "error": result.get('error')}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        loop.run_until_complete(bot.stop())
        loop.close()


@accounts_bp.route('/channel_candidates/<int:candidate_id>', methods=['DELETE'])
@login_required
def delete_channel_candidate(candidate_id):
    """Delete a channel candidate from the database"""
    try:
        from models.channel_candidate import ChannelCandidate
        
        candidate = ChannelCandidate.query.get(candidate_id)
        
        if not candidate:
            return jsonify({'error': 'Channel candidate not found'}), 404
        
        channel_title = candidate.title
        db.session.delete(candidate)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Channel "{channel_title}" deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# Human-Like Check Route
@accounts_bp.route('/<int:account_id>/human_check', methods=['POST'])
@login_required
def human_check(account_id):
    """Run Immersive Human-Like SpamBlock Check"""
    try:
        result = VerificationService.human_check(account_id)
        
        if result.success:
            return jsonify({'success': True, 'status': 'clean', 'message': result.message})
        else:
            if result.error_type == 'restricted':
                return jsonify({'success': True, 'status': 'restricted', 'reason': result.message})
            return jsonify({'success': False, 'error': result.message})
            
    except AccountNotFoundError:
        return jsonify({'success': False, 'error': 'Account not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@accounts_bp.route("/<int:account_id>/set-2fa", methods=["POST"])
@login_required
def set_2fa(account_id):
    """Set 2FA password with human emulation"""
    try:
        result = SecurityService.set_2fa(account_id)
        
        if result.success:
            flash(f"✅ 2FA Password Set Successfully: {result.password}", "success")
        else:
            flash(f"❌ Failed to set 2FA: {result.error}", "error")
            
    except AccountNotFoundError:
        flash("Account not found", "error")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        
    return redirect(url_for('accounts.detail', account_id=account_id))


@accounts_bp.route("/<int:account_id>/sessions", methods=["GET"])
@login_required
def get_sessions(account_id):
    """Get active sessions (JSON)"""
    try:
        result = SecurityService.get_active_sessions(account_id)
        return jsonify({
            'success': result.success,
            'sessions': result.sessions,
            'error': result.error
        })
    except AccountNotFoundError:
        return jsonify({'success': False, 'error': 'Account not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@accounts_bp.route("/<int:account_id>/sessions/terminate", methods=["POST"])
@login_required
def terminate_sessions_route(account_id):
    """Terminate session(s)"""
    session_hash = request.form.get('session_hash')
    terminate_all = request.form.get('terminate_all') == 'true'
    
    try:
        if terminate_all:
            result = SecurityService.terminate_all_sessions(account_id)
        elif session_hash:
            result = SecurityService.terminate_session(account_id, session_hash)
        else:
            return jsonify({'success': False, 'error': 'No session hash provided'})
            
        return jsonify({
            'success': result.success,
            'message': result.message,
            'error': result.error
        })
        
    except AccountNotFoundError:
        return jsonify({'success': False, 'error': 'Account not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@accounts_bp.route("/<int:account_id>/remove-2fa", methods=["POST"])
@login_required
def remove_2fa(account_id):
    """Remove 2FA password with human emulation"""
    try:
        result = SecurityService.remove_2fa(account_id)
        
        if result.success:
            flash("✅ 2FA Password Removed Successfully", "success")
        else:
            flash(f"❌ Failed to remove 2FA: {result.error}", "error")
            
    except AccountNotFoundError:
        flash("Account not found", "error")
    except TwoFANotSetError:
        flash("Local 2FA password record is missing. Cannot automatically remove.", "error")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
        
    return redirect(url_for('accounts.detail', account_id=account_id))



@accounts_bp.route("/<int:account_id>/update_device", methods=["POST"])
@login_required
def update_device(account_id):
    """Update or create device profile"""
    is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    try:
        # Check if user wants to use original TData
        if request.form.get('use_original', '').lower() == 'true':
            result = DeviceProfileService.use_original_tdata(account_id)
        
        # Check if user wants to use JSON parameters
        elif request.form.get('use_json', '').lower() == 'true':
            result = DeviceProfileService.use_json_parameters(account_id)
        
        # Custom device profile
        else:
            device_model = request.form.get('device_model', '').strip()
            system_version = request.form.get('system_version', '').strip()
            app_version = request.form.get('app_version', '').strip()
            
            if not all([device_model, system_version, app_version]):
                error_msg = "All device fields (model, system, app version) are required"
                if is_ajax:
                    return jsonify({'success': False, 'error': error_msg}), 400
                flash(f"❌ {error_msg}", "error")
                return redirect(url_for('accounts.detail', account_id=account_id))
            
            config = DeviceConfig(
                device_model=device_model,
                system_version=system_version,
                app_version=app_version,
                lang_code=request.form.get('lang_code', 'en').strip(),
                system_lang_code=request.form.get('system_lang_code', 'en-US').strip(),
                client_type=request.form.get('client_type', 'desktop')
            )
            result = DeviceProfileService.update_custom_device(account_id, config)
        
        # Return response
        if is_ajax:
            if result.success:
                response = {'success': True, 'message': result.message}
                if result.device:
                    response['device'] = {
                        'model': result.device.device_model,
                        'system': result.device.system_version,
                        'app': result.device.app_version
                    }
                return jsonify(response)
            else:
                return jsonify({'success': False, 'error': result.message}), 400
        else:
            if result.success:
                flash(f"✅ {result.message}", "success")
            else:
                flash(f"❌ {result.message}", "error")
            return redirect(url_for('accounts.detail', account_id=account_id))
            
    except AccountNotFoundError:
        if is_ajax:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        flash("Account not found", "error")
        return redirect(url_for('accounts.list_accounts'))


# -------------------------------------------------------------------------
# DISCOVERED CHANNELS ROUTES (Warmup V2)
# -------------------------------------------------------------------------

@accounts_bp.route("/<int:account_id>/warmup/search-channels", methods=["POST"])
@login_required
def search_channels(account_id):
    """Search discovered channels (candidates)"""
    try:
        from models.channel_candidate import ChannelCandidate
        
        query = request.json.get('query', '').strip()
        
        base_query = ChannelCandidate.query.filter(ChannelCandidate.account_id == account_id)
        
        if query:
            # Search by title or username
            base_query = base_query.filter(
                (ChannelCandidate.title.ilike(f"%{query}%")) | 
                (ChannelCandidate.username.ilike(f"%{query}%"))
            )
            
        candidates = base_query.order_by(ChannelCandidate.last_visit_ts.desc()).limit(50).all()
        
        results = [c.to_dict() for c in candidates]
        return jsonify({'success': True, 'results': results})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@accounts_bp.route("/<int:account_id>/warmup/add-channel", methods=["POST"])
@login_required
def add_channel_to_warmup(account_id):
    """Add a channel candidate to the warmup schedule"""
    try:
        from models.warmup_schedule import WarmupSchedule
        from models.warmup_schedule_node import WarmupScheduleNode
        from models.channel_candidate import ChannelCandidate
        from datetime import datetime, timedelta
        
        data = request.json
        channel_id = data.get('channel_id')
        action = data.get('action', 'view_only') # view_only or subscribe
        read_count = data.get('read_count', 5)
        
        # Verify candidate exists
        candidate = ChannelCandidate.query.get(channel_id)
        if not candidate or candidate.account_id != account_id:
            return jsonify({'success': False, 'error': 'Channel candidate not found'})
            
        # Get or Create active schedule
        schedule = WarmupSchedule.query.filter_by(account_id=account_id).first()
        if not schedule:
            # Create default schedule
            schedule = WarmupSchedule(
                account_id=account_id,
                name=f"Default Schedule",
                status='active',
                start_date=datetime.now().date()
            )
            db.session.add(schedule)
            db.session.commit()
            
        # Determine node type
        node_type = 'subscribe' if action == 'subscribe' else 'visit'
        
        # Create Node (Pending)
        # We set it for TODAY, NOW
        
        # Quick fix: Calculate current relative day
        account = Account.query.get(account_id)
        days_active = (datetime.now().date() - account.created_at.date()).days + 1
        days_active = max(1, days_active)
        
        # Execution time: Now + 1 min
        exec_time = (datetime.now() + timedelta(minutes=1)).strftime("%H:%M")
        
        node = WarmupScheduleNode(
            schedule_id=schedule.id,
            day_number=days_active,
            execution_time=exec_time,
            node_type=node_type,
            status='pending',
            config={
                'target': f"@{candidate.username}" if candidate.username else f"https://t.me/c/{candidate.peer_id}", # Target identifier
                'username': candidate.username,
                'peer_id': candidate.peer_id,
                'access_hash': candidate.access_hash,
                'read_count': read_count, 
                'origin': 'discovered_ui'
            }
        )
        
        db.session.add(node)
        db.session.commit()
        
        return jsonify({'success': True, 'node_id': node.id})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@accounts_bp.route("/<int:account_id>/warmup/execute-channels", methods=["POST"])
@login_required
def execute_channels_now(account_id):
    """Trigger execution of pending channel nodes"""
    try:
        # Trigger the worker check immediately
        from workers.scheduler_worker import check_warmup_schedules
        
        # Asynchronously trigger the global check
        check_warmup_schedules.delay()
        
        return jsonify({'success': True, 'message': 'Execution triggered'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
