from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils.decorators import login_required
from models.account import Account, DeviceProfile, AccountSubscription
from models.tdata_metadata import TDataMetadata
from models.proxy import Proxy
from database import db
from utils.device_emulator import generate_device_profile, get_random_warmup_channels
from utils.telethon_helper import verify_session
import os
from werkzeug.utils import secure_filename
import asyncio
import random

import nest_asyncio
nest_asyncio.apply()
accounts_bp = Blueprint("accounts", __name__)


@accounts_bp.route("/")
@login_required
def list_accounts():
    """List all accounts"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    pagination = Account.query.order_by(Account.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    accounts = pagination.items
    proxies = Proxy.query.filter_by(status="active").all()
    
    return render_template(
        "accounts/list.html", 
        accounts=accounts, 
        proxies=proxies,
        pagination=pagination
    )


@accounts_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """Upload and validate session files with safety checks"""
    from models.proxy import Proxy
    
    if request.method == "POST":
        from utils.activity_logger import ActivityLogger
        from utils.session_validator import SessionValidator
        import shutil
        import json
        from datetime import datetime
        
        files = request.files.getlist("session_files")
        
        if not files or files[0].filename == "":
            flash("No files selected", "error")
            return redirect(url_for("accounts.upload"))
        
        # Get form parameters
        region = request.form.get("region", "US")
        proxy_mode = request.form.get("proxy_mode", "none")
        specific_proxy_id = request.form.get("specific_proxy")
        
        # Get available proxies
        available_proxies = Proxy.query.filter_by(status='active').all()
        proxy_index = 0
        
        # Counters
        uploaded = 0
        skipped = 0
        quarantined = 0
        errors = []
        
        # Initialize validator
        validator = SessionValidator()
        
        for file in files:
            if not file or not file.filename:
                continue
            
            if not file.filename.endswith(".session"):
                errors.append(f"{file.filename}: Not a .session file")
                continue
            
            temp_path = None
            
            try:
                filename = secure_filename(file.filename)
                phone = filename.replace(".session", "")
                
                # 🔍 Check 1: Duplicate account
                existing = Account.query.filter_by(phone=phone).first()
                if existing:
                    errors.append(f"{phone}: Account already exists")
                    skipped += 1
                    continue
                
                # 📁 Save to temp folder first
                temp_dir = "uploads/temp_sessions"
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, filename)
                file.save(temp_path)
                
                # 🔍 Check 2: Validate file
                validation = validator.validate_session_file(temp_path)
                
                if not validation['valid']:
                    os.remove(temp_path)
                    error_msg = validation.get('error', 'Unknown error')
                    errors.append(f"{filename}: Invalid session - {error_msg}")
                    continue
                
                # 📊 Extract metadata
                metadata = validator.extract_metadata(temp_path)
                
                # ⚠️ Check 3: Suspicious session?
                if metadata.get('suspicious', False):
                    # Move to quarantine
                    quarantine_dir = "uploads/quarantine"
                    os.makedirs(quarantine_dir, exist_ok=True)
                    quarantine_path = os.path.join(quarantine_dir, filename)
                    shutil.move(temp_path, quarantine_path)
                    
                    reasons = ', '.join(metadata.get('suspicious_reasons', []))
                    errors.append(f"{filename}: Suspicious session ({reasons}) - moved to quarantine")
                    quarantined += 1
                    continue
                
                # 📂 Create structured folder for account
                account_dir = f"uploads/sessions/{phone}"
                os.makedirs(account_dir, exist_ok=True)
                
                final_path = os.path.join(account_dir, f"{phone}.session")
                
                # 🔄 Move from temp to final location
                shutil.move(temp_path, final_path)
                temp_path = None  # Clear so cleanup doesn't try to remove it
                
                # 📝 Save metadata.json
                metadata_path = os.path.join(account_dir, "metadata.json")
                with open(metadata_path, 'w') as f:
                    json.dump({
                        "uploaded_at": datetime.now().isoformat(),
                        "original_filename": file.filename,
                        "file_size": validation['size'],
                        "format": validation['format'],
                        "validation": validation,
                        "metadata": metadata,
                        "region": region
                    }, f, indent=2)
                
                # 🔧 Determine proxy assignment
                assigned_proxy_id = None
                if proxy_mode == "specific" and specific_proxy_id:
                    assigned_proxy_id = int(specific_proxy_id)
                elif proxy_mode == "round_robin" and available_proxies:
                    assigned_proxy_id = available_proxies[proxy_index % len(available_proxies)].id
                    proxy_index += 1
                elif proxy_mode == "random" and available_proxies:
                    import random
                    assigned_proxy_id = random.choice(available_proxies).id
                
                # 💾 Create account in database
                account = Account(
                    phone=phone,
                    session_file_path=final_path,
                    status="pending",  # Not verified yet
                    health_score=100,
                    proxy_id=assigned_proxy_id,
                    created_at=datetime.now(),
                    session_metadata=metadata
                )
                db.session.add(account)
                db.session.flush()  # Get account ID
                
                # 📱 Create device profile
                device = generate_device_profile(region=region)
                device_profile = DeviceProfile(
                    account_id=account.id,
                    device_model=device["device_model"],
                    system_version=device["system_version"],
                    app_version=device["app_version"],
                    lang_code=device["lang_code"],
                    system_lang_code=device["system_lang_code"],
                    client_type=device.get("client_type", "desktop")
                )
                db.session.add(device_profile)
                
                
                # 🧹 Clean session file (Anti-Ban)
                # Removes "Telethon" traces and sets correct device info in SQLite
                # 📝 Log upload
                logger = ActivityLogger(account.id)
                logger.log(
                    action_type='upload_session',
                    status='success',
                    description=f'Session file uploaded and validated',
                    details=f"File: {filename}, Size: {validation['size']} bytes, Age: {metadata.get('estimated_age', 'unknown')}",
                    category='system'
                )
                
                # 🧹 Clean session file (Anti-Ban)
                # Removes "Telethon" traces and sets correct device info in SQLite
                try:
                    cleaned = validator.clean_session_file(final_path, device)
                    if cleaned:
                        logger.log(
                            action_type='clean_session',
                            status='success',
                            description='Session file signatures cleaned',
                            details=f"Device: {device['device_model']} ({device.get('client_type', 'unknown')})",
                            category='system'
                        )
                except Exception as clean_err:
                    print(f"Warning: Failed to clean session file: {clean_err}")
                
                # 📝 Log proxy assignment if assigned
                if assigned_proxy_id:
                    proxy = Proxy.query.get(assigned_proxy_id)
                    logger.log(
                        action_type='assign_proxy',
                        status='success',
                        description=f"Proxy auto-assigned during upload: {proxy.host}:{proxy.port}",
                        details=f"Mode: {proxy_mode}, Type: {proxy.type}",
                        proxy_used=f"{proxy.host}:{proxy.port}",
                        category='system'
                    )
                
                uploaded += 1
                
            except Exception as e:
                # Cleanup temp file on error
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                errors.append(f"{file.filename}: {str(e)}")
        
        db.session.commit()
        
        # Show notifications
        if uploaded > 0:
            flash(f"✅ Successfully uploaded {uploaded} session file(s)", "success")
        if skipped > 0:
            flash(f"⚠️ Skipped {skipped} duplicate account(s)", "warning")
        if quarantined > 0:
            flash(f"🔒 Quarantined {quarantined} suspicious file(s)", "warning")
        for error in errors[:10]:  # Show first 10 errors
            flash(f"❌ {error}", "error")
        if len(errors) > 10:
            flash(f"... and {len(errors) - 10} more errors", "error")
        
        return redirect(url_for("accounts.list_accounts"))
    
    # GET request - show upload form
    proxies = Proxy.query.filter_by(status='active').all()
    return render_template("accounts/upload.html", proxies=proxies)


@accounts_bp.route("/<int:account_id>")
@login_required
def detail(account_id):
    """Account details with warmup info"""
    from models.warmup import ConversationPair, WarmupActivity
    from models.channel_candidate import ChannelCandidate
    
    account = Account.query.get_or_404(account_id)
    proxies = Proxy.query.filter_by(status="active").all()
    
    # Get conversation pairs for this account
    pairs = ConversationPair.query.filter(
        db.or_(
            ConversationPair.account_a_id == account_id,
            ConversationPair.account_b_id == account_id
        )
    ).all()
    
    # Get partner accounts for each pair
    conversation_partners = []
    for pair in pairs:
        partner_id = pair.account_b_id if pair.account_a_id == account_id else pair.account_a_id
        partner = Account.query.get(partner_id)
        if partner:
            conversation_partners.append({
                "pair_id": pair.id,
                "partner": partner,
                "last_conversation": pair.last_conversation_at,
                "conversation_count": pair.conversation_count
            })
    
    # Get other accounts for pairing
    other_accounts = Account.query.filter(
        Account.id != account_id,
        Account.status.in_(['warming_up', 'active', 'paused'])
    ).all()
    
    # Get recent warmup activities
    recent_activities = WarmupActivity.query.filter_by(
        account_id=account_id
    ).order_by(WarmupActivity.timestamp.desc()).limit(10).all()
    
    # Get discovered channel candidates
    channel_candidates = ChannelCandidate.query.filter_by(
        account_id=account_id
    ).order_by(ChannelCandidate.created_at.desc()).limit(20).all()
    
    # Get JSON device parameters if available
    json_device_params = None
    if account.tdata_metadata and account.tdata_metadata.json_raw_data:
        json_device_params = {
            'device_model': account.tdata_metadata.json_device_model or '',
            'system_version': account.tdata_metadata.json_system_version or '',
            'app_version': account.tdata_metadata.json_app_version or '',
            'lang_code': account.tdata_metadata.json_lang_code or '',
            'system_lang_code': account.tdata_metadata.json_system_lang_code or ''
        }
    
    return render_template(
        "accounts/detail.html",
        account=account,
        proxies=proxies,
        conversation_partners=conversation_partners,
        other_accounts=other_accounts,
        recent_activities=recent_activities,
        channel_candidates=channel_candidates,
        json_device_params=json_device_params  # Add JSON params
    )


@accounts_bp.route("/<int:account_id>/verify", methods=["POST"])
@login_required
def verify(account_id):
    """Verify account safe strategy"""
    from utils.activity_logger import ActivityLogger
    from datetime import datetime
    import asyncio
    
    account = Account.query.get_or_404(account_id)
    
    # Pre-check: Ensure session is configured
    if not account.session_string and not (account.session_file_path and os.path.exists(account.session_file_path)):
        flash("Cannot verify: No session data configured. Please configure TData or login.", "error")
        return redirect(url_for('accounts.detail', account_id=account_id))
    
    # Cooldown check removed per user request
            
    # Update attempt time
    try:
        if hasattr(Account, 'last_verification_attempt'):
             account.last_verification_attempt = datetime.now()
             db.session.commit()
    except:
        db.session.rollback()
    
    logger = ActivityLogger(account_id)
    
    # Log start
    logger.log(
        action_type='verification_start',
        status='pending',
        description='Starting risk-based verification',
        category='system'
    )
            
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Session Orchestrator Refactor
    from utils.session_orchestrator import SessionOrchestrator
    # We must import verify_session from helper to use as a task
    from utils.telethon_helper import verify_session

    # Capture settings before closing session to avoid DetachedInstanceError
    enable_anchor = getattr(account, 'warmup_enabled', False)
    # Allow form to override
    if 'enable_anchor' in request.form:
         enable_anchor = request.form.get('enable_anchor') == 'on'

    # Anti-Lock
    db.session.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    bot = SessionOrchestrator(account_id)
    
    try:
        # Check if anchor is enabled in account settings
        # (moved up)
        
        # Define wrapper task for Orchestrator
        async def task_full_verify(client):
            # We reuse the robust logic in verify_session, passing the Orchestrator's client
            return await verify_session(account_id, force_full=True, disable_anchor=not enable_anchor, client=client)

        # Execute via Orchestrator
        # This ensures we handle connection limits, idle states, and reuse active connections
        result = loop.run_until_complete(bot.execute(task_full_verify))
        
        # Re-fetch account
        account_ref = Account.query.get(account_id)
        if not account_ref:
            return redirect(url_for('accounts.detail', account_id=account_id))

        if result['success']:
            verification_type = result.get('verification_type', 'unknown')
            
            # FULL VERIFICATION - Update all user data
            if verification_type == 'full' and result.get('user'):
                user = result['user']
                
                # Check for name changes
                if account_ref.last_name and not user.get('last_name'):
                    flash("⚠️ Note: Telegram did not return a last name.", "warning")
                
                account_ref.telegram_id = user['id']
                # Only update last_name if Telegram returned non-empty value
                if user.get('last_name') and user['last_name'].strip():
                    account_ref.last_name = user['last_name']
                
                # SAFETY: Don't overwrite existing first_name with None if account is marked active
                if user.get('first_name'):
                    account_ref.first_name = user['first_name']
                elif not account_ref.first_name:
                    account_ref.first_name = user.get('first_name')
                
                if user.get('username'):
                    account_ref.username = user['username']
                account_ref.status = 'active'
                account_ref.last_check_status = 'active'
                
                if user.get('photo') and user.get('photo_path'):
                    account_ref.photo_url = user['photo_path']
                elif user.get('photo'):
                    # Fallback if download failed but photo exists
                    account_ref.photo_url = "photo_available"
                
                if hasattr(Account, 'verified'):
                    try:
                        account_ref.verified = True
                    except:
                        pass
                
                db.session.commit()
                flash("✅ Account verified (Full verification with anti-ban handshake)", "success")
                logger.log(action_type='verification_success', status='success', description='Full verification with handshake')
            
            # LIGHT VERIFICATION - Only update status
            elif verification_type == 'light':
                account_ref.status = 'active'
                account_ref.last_check_status = 'active'
                db.session.commit()
                
                flash("✅ Account check passed (Light verification)", "success")
                logger.log(action_type='verification_success', status='success', description='Light verification passed')
            
            else:
                flash("✅ Verification successful", "success")
            
        else:
            # Handle failure
            error_type = result.get('error_type', 'generic_error')
            
            if error_type == 'flood_wait':
                account_ref.status = 'flood_wait'
                account_ref.last_check_status = 'flood_wait'
                wait_time = result.get('wait', 0)
                flash(f"⏱️ FloodWait: {wait_time}s", "error")
                logger.log(action_type='verification_failed', status='error', description=f"FloodWait: {wait_time}s", category='system')
                
            elif error_type == 'banned':
                account_ref.status = 'banned'
                account_ref.last_check_status = 'banned'
                account_ref.health_score = 0
                flash(f"🚫 Account BANNED: {result.get('error')}", "error")
                logger.log(action_type='verification_failed', status='error', description=f"BANNED: {result.get('error')}", category='system')
                
            elif error_type == 'invalid_session':
                account_ref.status = 'error'
                account_ref.last_check_status = 'session_invalid'
                flash(f"🔑 Session Invalid: {result.get('error')}", "error")
                logger.log(action_type='verification_failed', status='error', description=f"Invalid: {result.get('error')}", category='system')
            
            elif error_type == 'handshake_failed':
                account_ref.status = 'error'
                account_ref.last_check_status = 'handshake_failed'
                flash(f"❌ Handshake failed: {result.get('error')}", "error")
                logger.log(action_type='verification_failed', status='error', description=f"Handshake: {result.get('error')}", category='system')
                
            else:
                account_ref.status = 'error'
                account_ref.last_check_status = 'error'
                flash(f"❌ Failed: {result.get('error')}", "error")
                logger.log(action_type='verification_failed', status='error', description=f"Error: {result.get('error')}", category='system')
            
            db.session.commit()
            
    except Exception as e:
        flash(f"System Error: {str(e)}", "error")
        logger.log(action_type='verification_error', status='error', description=f"System Error: {str(e)}", category='system')
    finally:
        loop.run_until_complete(bot.stop())
        loop.close()
        
    return redirect(url_for('accounts.detail', account_id=account_id))
    
@accounts_bp.route("/<int:account_id>/sync-from-telegram", methods=["POST"])
@login_required
def sync_from_telegram(account_id):
    """Sync profile data from Telegram (with rate limiting)"""
    from utils.telethon_helper import get_telethon_client
    from datetime import datetime, timedelta
    import asyncio
    
    account = Account.query.get_or_404(account_id)
    
    # Check cooldown (5 minutes)
    COOLDOWN_MINUTES = 5
    if account.last_sync_at:
        time_since_sync = datetime.utcnow() - account.last_sync_at
        if time_since_sync < timedelta(minutes=COOLDOWN_MINUTES):
            remaining = COOLDOWN_MINUTES - int(time_since_sync.total_seconds() / 60)
            flash(f"⏱️ Please wait {remaining} more minute(s) before syncing again (cooldown: {COOLDOWN_MINUTES} min)", "warning")
            return redirect(url_for("accounts.detail", account_id=account_id))
    
    # Session Orchestrator Refactor
    from utils.session_orchestrator import SessionOrchestrator
    
    # Anti-Lock
    db.session.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    bot = SessionOrchestrator(account_id)
    
    async def task_sync_profile(client):
        try:
            # Get user info
            me = await client.get_me()
            
            # Prepare result dict to pass back
            result = {
                'id': me.id,
                'first_name': getattr(me, "first_name", None),
                'last_name': getattr(me, "last_name", None),
                'username': getattr(me, "username", None),
                'bio': None,
                'photo_url': None,
                'photo_available': False
            }
            
            # Get bio (about)
            try:
                full_user = await client.get_entity(me)
                if hasattr(full_user, 'about'):
                    result['bio'] = full_user.about
            except:
                pass
            
            # Try to download profile photo
            try:
                if hasattr(me, "photo") and me.photo:
                    photo_path = f"uploads/photos/{account.phone}_profile.jpg"
                    os.makedirs("uploads/photos", exist_ok=True)
                    # We need to await the download
                    await client.download_profile_photo(me, file=photo_path)
                    result['photo_url'] = photo_path
            except Exception as photo_err:
                 pass
            
            # Check availability if download failed or succeeded
            if hasattr(me, "photo") and me.photo:
                 result['photo_available'] = True

            return result
            
        except Exception as e:
            raise e
    
    try:
        user_data = loop.run_until_complete(bot.execute(task_sync_profile))
        
        # Re-fetch account
        account_ref = Account.query.get(account_id)
        if not account_ref:
             # Should not happen
             pass
        else:
            # Check for name changes
            if account_ref.last_name and not user_data.get('last_name'):
                 print(f"⚠️ WARNING: Last name for {account_ref.phone} is being removed (Telegram returned None)")
                 
            # Update fields
            account_ref.telegram_id = user_data['id']
            account_ref.first_name = user_data['first_name'] or account_ref.first_name
            account_ref.last_name = user_data['last_name'] or account_ref.last_name
            account_ref.username = user_data['username']
            
            if user_data.get('bio'):
                account_ref.bio = user_data['bio']
            
            if user_data.get('photo_url'):
                account_ref.photo_url = user_data['photo_url']
            elif user_data.get('photo_available'):
                account_ref.photo_url = "photo_available"
            
            # Update sync timestamp
            account_ref.last_sync_at = datetime.utcnow()
            
            db.session.commit()
            
            msg = f"✅ Profile synced from Telegram: {account_ref.first_name}"
            if not account_ref.last_name:
                 msg += " (Note: No last name returned from Telegram)"
            flash(msg, "success")
            
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    finally:
        loop.run_until_complete(bot.stop())
        loop.close()
    
    return redirect(url_for("accounts.detail", account_id=account_id))



@accounts_bp.route("/<int:account_id>/delete", methods=["POST"])
@login_required
def delete(account_id):
    """Delete account"""
    account = Account.query.get_or_404(account_id)
    
    try:
        # Delete related records first to avoid constraint errors
        from models.dm_campaign import DMCampaignAccount
        from models.campaign import CampaignAccount
        
        # Delete DM campaign associations
        DMCampaignAccount.query.filter_by(account_id=account_id).delete()
        
        # Delete invite campaign associations
        CampaignAccount.query.filter_by(account_id=account_id).delete()
        
        # Delete invite logs
        db.session.execute(db.text("DELETE FROM invite_logs WHERE account_id = :aid"), {"aid": account_id})
        
        # Delete DM messages
        db.session.execute(db.text("DELETE FROM dm_messages WHERE account_id = :aid"), {"aid": account_id})
        
        # Delete warmup-related records
        try:
            db.session.execute(db.text("DELETE FROM account_warmup_channels WHERE account_id = :aid"), {"aid": account_id})
        except Exception:
            # Ignore if table doesn't exist (legacy/migration issue)
            pass
        db.session.execute(db.text("DELETE FROM warmup_activities WHERE account_id = :aid"), {"aid": account_id})
        db.session.execute(db.text("DELETE FROM conversation_pairs WHERE account_a_id = :aid OR account_b_id = :aid"), {"aid": account_id})
        
        # Delete channel candidates (fix for NotNullViolation)
        db.session.execute(db.text("DELETE FROM channel_candidates WHERE account_id = :aid"), {"aid": account_id})

        # Delete warmup logs (fix for NotNullViolation)
        db.session.execute(db.text("DELETE FROM warmup_logs WHERE account_id = :aid"), {"aid": account_id})
        
        # Delete other dependencies to be safe
        db.session.execute(db.text("DELETE FROM warmup_settings WHERE account_id = :aid"), {"aid": account_id})
        db.session.execute(db.text("DELETE FROM tdata_metadata WHERE account_id = :aid"), {"aid": account_id})
        db.session.execute(db.text("DELETE FROM warmup_channels WHERE account_id = :aid"), {"aid": account_id})
        db.session.execute(db.text("DELETE FROM warmup_stages WHERE account_id = :aid"), {"aid": account_id})
        db.session.execute(db.text("DELETE FROM warmup_schedules WHERE account_id = :aid"), {"aid": account_id})
        
        # Delete session file and journal if exist
        if os.path.exists(account.session_file_path):
            os.remove(account.session_file_path)
        
        # Also delete .session-journal file
        journal_path = account.session_file_path + "-journal"
        if os.path.exists(journal_path):
            os.remove(journal_path)
        
        # Delete profile photo if exists
        if account.photo_url:
            photo_path = account.photo_url.replace("/uploads/", "uploads/")
            if os.path.exists(photo_path):
                os.remove(photo_path)
        
        # Delete from database (cascade will handle subscriptions and device_profile)
        db.session.delete(account)
        db.session.commit()
        
        flash("Account deleted successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting account: {str(e)}", "error")
    
    return redirect(url_for("accounts.list_accounts"))


@accounts_bp.route("/<int:account_id>/assign-proxy", methods=["POST"])
@login_required
def assign_proxy(account_id):
    """Assign proxy to account"""
    from utils.activity_logger import ActivityLogger
    from models.proxy import Proxy
    
    account = Account.query.get_or_404(account_id)
    logger = ActivityLogger(account_id)
    proxy_id = request.form.get("proxy_id")
    
    if proxy_id:
        proxy = Proxy.query.get(int(proxy_id))
        account.proxy_id = int(proxy_id)
        db.session.commit()
        
        # Log proxy assignment
        logger.log(
            action_type='assign_proxy',
            status='success',
            description=f"Proxy assigned: {proxy.host}:{proxy.port}",
            details=f"Type: {proxy.type}, IP: {proxy.current_ip or 'Unknown'}",
            proxy_used=f"{proxy.host}:{proxy.port}",
            category='system'
        )
        
        flash("Proxy assigned", "success")
    else:
        old_proxy = account.proxy
        account.proxy_id = None
        db.session.commit()
        
        # Log proxy removal
        logger.log(
            action_type='remove_proxy',
            status='success',
            description='Proxy removed from account',
            details=f"Previous proxy: {old_proxy.host}:{old_proxy.port}" if old_proxy else None,
            category='system'
        )
        
        flash("Proxy removed", "info")
    
    return redirect(url_for("accounts.detail", account_id=account_id))


@accounts_bp.route("/<int:account_id>/add-subscription", methods=["POST"])
@login_required
def add_subscription(account_id):
    """Add channel subscription - actually joins the channel/group"""
    from utils.telethon_helper import get_telethon_client
    from telethon.tl.functions.channels import JoinChannelRequest
    from utils.activity_logger import ActivityLogger
    import asyncio
    
    account = Account.query.get_or_404(account_id)
    logger = ActivityLogger(account_id)
    channel_input = request.form.get("channel_username", "").strip()
    notes = request.form.get("notes", "").strip()
    
    if not channel_input:
        flash("Channel username is required", "error")
        return redirect(url_for("accounts.detail", account_id=account_id))
    
    # Extract username from various formats
    channel_username = channel_input.lstrip("@")
    if "t.me/" in channel_username:
        channel_username = channel_username.split("t.me/")[-1].split("/")[0].split("?")[0]
    
    # Check if account is spam-blocked
    if account.status == "spam-block":
        flash("⚠️ WARNING: This account has spam-block and cannot join channels. Please use a different account.", "error")
        return redirect(url_for("accounts.detail", account_id=account_id))
    
    # Check if already exists
    existing = AccountSubscription.query.filter_by(
        account_id=account_id,
        channel_username=channel_username
    ).first()
    
    if existing:
        flash(f"Already subscribed to @{channel_username}", "warning")
        return redirect(url_for("accounts.detail", account_id=account_id))
    
    # Log join attempt
    logger.log(
        action_type='join_group_attempt',
        status='pending',
        target=f"@{channel_username}",
        description=f"Attempting to join @{channel_username}",
        category='manual'
    )
    
    # Orchestrator Refactor
    from utils.session_orchestrator import SessionOrchestrator
    from tasks.warmup import task_join_channel
    
    db.session.close() # Anti-Lock
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    bot = SessionOrchestrator(account_id)
    
    try:
        result = loop.run_until_complete(bot.execute(task_join_channel, channel_username=channel_username))
        
        subscription_status = result['status']
        message = result['message']
        
        # Log result
        logger = ActivityLogger(account_id)
        if subscription_status == "active":
            logger.log(
                action_type='join_group',
                status='success',
                target=f"@{channel_username}",
                description=message,
                category='manual'
            )
            flash(message, "success")
        else:
            logger.log(
                action_type='join_group',
                status='failed',
                target=f"@{channel_username}",
                description=f"Failed to join @{channel_username}",
                error_message=message,
                category='manual'
            )
            flash(message, "warning")
            
    except Exception as e:
        subscription_status = "failed"
        logger.log(
            action_type='join_group',
            status='failed',
            target=f"@{channel_username}",
            description=f"Error joining @{channel_username}",
            error_message=str(e),
            category='manual'
        )
        flash(f"Error: {str(e)}", "error")
    finally:
        loop.run_until_complete(bot.stop())
        loop.close()
    
    # Save subscription
    subscription = AccountSubscription(
        account_id=account_id,
        channel_username=channel_username,
        subscription_source="manual",
        status=subscription_status,
        notes=notes
    )
    db.session.add(subscription)
    db.session.commit()
    
    return redirect(url_for("accounts.detail", account_id=account_id))


@accounts_bp.route("/<int:account_id>/subscriptions/<int:sub_id>/remove", methods=["POST"])
@login_required
def remove_subscription(account_id, sub_id):
    """Remove subscription"""
    subscription = AccountSubscription.query.get_or_404(sub_id)
    
    if subscription.account_id != account_id:
        flash("Invalid subscription", "error")
        return redirect(url_for("accounts.detail", account_id=account_id))
    
    db.session.delete(subscription)
    db.session.commit()
    
    flash("Subscription removed", "info")
    return redirect(url_for("accounts.detail", account_id=account_id))


@accounts_bp.route("/<int:account_id>/update-profile", methods=["POST"])
@login_required
def update_profile(account_id):
    """Update editable profile fields"""
    from utils.telethon_helper import update_telegram_profile, update_telegram_photo
    import asyncio
    
    account = Account.query.get_or_404(account_id)
    
    # Collect updates
    username = request.form.get("username", "").strip().lstrip("@") if "username" in request.form else None
    bio = request.form.get("bio", "").strip() if "bio" in request.form else None
    
    # Handle photo upload first (save locally)
    photo_file = None
    if "photo" in request.files:
        photo = request.files["photo"]
        if photo and photo.filename:
            filename = secure_filename(f"{account.phone}_{photo.filename}")
            photo_path = os.path.join("uploads/photos", filename)
            os.makedirs("uploads/photos", exist_ok=True)
            photo.save(photo_path)
            photo_file = photo_path
    
    # Session Orchestrator Refactor
    from utils.session_orchestrator import SessionOrchestrator
    from tasks.profile import task_update_profile, task_update_photo, task_update_username
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    bot = SessionOrchestrator(account_id)
    
    # Anti-Lock? We need to keep DB open to read request.form, but for long tasks close it?
    # Request form is already read above. 
    db.session.close() # Close session for long op
    
    try:
        # 1. Update Profile Info (Name/Bio)
        # Note: Username update is separate in Telethon
        if bio: # We can only update Bio via UpdateProfileRequest in some versions, or About.
            # Our task_update_profile handles first_name, last_name, about
            # We don't have first/last name in form? The view code only extracted username/bio.
            # If we want to support name update, we need to add fields to form.
            # Assuming 'bio' maps to 'about'.
            
            res = loop.run_until_complete(bot.execute(task_update_profile, about=bio))
            if not res['success']:
                flash(f"Failed to update bio: {res['error']}", "error")
            else:
                # Re-open session to update info
                account = Account.query.get(account_id)
                account.bio = bio
                db.session.commit()
                db.session.close()

        if username:
             res = loop.run_until_complete(bot.execute(task_update_username, username=username))
             if not res['success']:
                 flash(f"Failed to update username: {res['error']}", "error")
             else:
                 account = Account.query.get(account_id)
                 account.username = username
                 db.session.commit()
                 db.session.close()
                 
        # 2. Update Photo
        if photo_file:
             res = loop.run_until_complete(bot.execute(task_update_photo, photo_path=photo_file))
             if not res['success']:
                 flash(f"Failed to update photo: {res['error']}", "error")
             else:
                 account = Account.query.get(account_id)
                 account.photo_url = photo_file
                 db.session.commit()
                 db.session.close()
                 
        flash("Profile update sequence completed.", "info")
        
    except Exception as e:
        flash(f"Error updating profile: {str(e)}", "error")
    finally:
        loop.run_until_complete(bot.stop())
        loop.close()
    
    return redirect(url_for("accounts.detail", account_id=account_id))


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



@accounts_bp.route("/<int:account_id>/warmup/add-theme", methods=["POST"])
@login_required
def add_warmup_theme(account_id):
    """Add channels from a theme"""
    from models.warmup import AccountWarmupChannel, WarmupChannelTheme
    
    account = Account.query.get_or_404(account_id)
    theme_id = request.form.get("theme_id")
    
    if not theme_id:
        flash("Please select a theme", "error")
        return redirect(url_for("accounts.warmup_settings", account_id=account_id))
    
    theme = WarmupChannelTheme.query.get(theme_id)
    if not theme:
        flash("Theme not found", "error")
        return redirect(url_for("accounts.warmup_settings", account_id=account_id))
    
    # Add channels from theme
    channels = theme.get_channels_list()
    added = 0
    
    for channel in channels:
        existing = AccountWarmupChannel.query.filter_by(
            account_id=account_id,
            channel_username=channel
        ).first()
        
        if not existing:
            warmup_channel = AccountWarmupChannel(
                account_id=account_id,
                channel_username=channel,
                source=f"theme:{theme.name}"
            )
            db.session.add(warmup_channel)
            added += 1
    
    db.session.commit()
    
    flash(f"Added {added} channels from '{theme.display_name}' theme", "success")
    return redirect(url_for("accounts.warmup_settings", account_id=account_id))


@accounts_bp.route("/<int:account_id>/warmup/remove-channel/<int:channel_id>", methods=["POST"])
@login_required
def remove_warmup_channel(account_id, channel_id):
    """Remove a warmup channel"""
    from models.warmup import AccountWarmupChannel
    
    channel = AccountWarmupChannel.query.get_or_404(channel_id)
    
    if channel.account_id != account_id:
        flash("Invalid channel", "error")
        return redirect(url_for("accounts.warmup_settings", account_id=account_id))
    
    db.session.delete(channel)
    db.session.commit()
    
    flash(f"Removed @{channel.channel_username} from warmup", "info")
    return redirect(url_for("accounts.warmup_settings", account_id=account_id))


@accounts_bp.route("/<int:account_id>/warmup/add-pair", methods=["POST"])
@login_required
def add_conversation_pair(account_id):
    """Add a conversation partner (bidirectional)"""
    from models.warmup import ConversationPair
    
    account = Account.query.get_or_404(account_id)
    partner_id = request.form.get("partner_id")
    
    if not partner_id:
        flash("Please select a partner account", "error")
        return redirect(url_for("accounts.warmup_settings", account_id=account_id))
    
    partner_id = int(partner_id)
    
    if partner_id == account_id:
        flash("Cannot pair account with itself", "error")
        return redirect(url_for("accounts.warmup_settings", account_id=account_id))
    
    partner = Account.query.get(partner_id)
    if not partner:
        flash("Partner account not found", "error")
        return redirect(url_for("accounts.warmup_settings", account_id=account_id))
    
    # Check if pair already exists (in either direction)
    existing = ConversationPair.query.filter(
        db.or_(
            db.and_(
                ConversationPair.account_a_id == account_id,
                ConversationPair.account_b_id == partner_id
            ),
            db.and_(
                ConversationPair.account_a_id == partner_id,
                ConversationPair.account_b_id == account_id
            )
        )
    ).first()
    
    if existing:
        flash(f"Already paired with {partner.phone}", "warning")
        return redirect(url_for("accounts.warmup_settings", account_id=account_id))
    
    # Create pair (bidirectional by design)
    pair = ConversationPair(
        account_a_id=account_id,
        account_b_id=partner_id
    )
    db.session.add(pair)
    db.session.commit()
    
    flash(f"Added conversation pair with {partner.phone}", "success")
    return redirect(url_for("accounts.warmup_settings", account_id=account_id))


@accounts_bp.route("/<int:account_id>/warmup/remove-pair/<int:pair_id>", methods=["POST"])
@login_required
def remove_conversation_pair(account_id, pair_id):
    """Remove a conversation pair"""
    from models.warmup import ConversationPair
    
    pair = ConversationPair.query.get_or_404(pair_id)
    
    if pair.account_a_id != account_id and pair.account_b_id != account_id:
        flash("Invalid pair", "error")
        return redirect(url_for("accounts.warmup_settings", account_id=account_id))
    
    db.session.delete(pair)
    db.session.commit()
    
    flash("Removed conversation pair", "info")
    return redirect(url_for("accounts.warmup_settings", account_id=account_id))


@accounts_bp.route("/<int:account_id>/warmup/pause", methods=["POST"])
@login_required
def pause_warmup(account_id):
    """Pause warmup activity for account"""
    account = Account.query.get_or_404(account_id)
    
    if account.status == 'active':
        account.status = 'paused'
        db.session.commit()
        flash("⏸️ Warmup activity paused", "info")
    else:
        flash(f"Cannot pause account with status '{account.status}'", "warning")
    
    return redirect(url_for("accounts.warmup_settings", account_id=account_id))


@accounts_bp.route("/<int:account_id>/warmup/resume", methods=["POST"])
@login_required
def resume_warmup(account_id):
    """Resume warmup activity for account"""
    account = Account.query.get_or_404(account_id)
    
    if account.status == 'paused':
        account.status = 'active'
        db.session.commit()
        flash("▶️ Warmup activity resumed", "success")
    else:
        flash(f"Cannot resume account with status '{account.status}'", "warning")
    
    return redirect(url_for("accounts.warmup_settings", account_id=account_id))



@accounts_bp.route("/<int:account_id>/warmup/enable", methods=["POST"])
@login_required
def enable_warmup(account_id):
    """Enable automatic warmup for account"""
    account = Account.query.get_or_404(account_id)
    
    account.warmup_enabled = True
    db.session.commit()
    
    flash("✅ Automatic warmup enabled! Worker will now run activities for this account.", "success")
    return redirect(url_for("accounts.warmup_settings", account_id=account_id))


@accounts_bp.route("/<int:account_id>/warmup/disable", methods=["POST"])
@login_required
def disable_warmup(account_id):
    """Disable automatic warmup for account"""
    account = Account.query.get_or_404(account_id)
    
    account.warmup_enabled = False
    db.session.commit()
    
    flash("🛑 Automatic warmup disabled. No automatic activities will run.", "warning")
    return redirect(url_for("accounts.warmup_settings", account_id=account_id))



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
    """
    Run Immersive Human-Like SpamBlock Check using SessionOrchestrator.
    This manages the session lifecycle (Cold/Hot start) automatically.
    """
    import asyncio
    from utils.session_orchestrator import SessionOrchestrator
    from tasks.basic import task_check_spamblock
    from utils.activity_logger import ActivityLogger
    
    # Anti-Lock: Release DB session during long operation
    db.session.close()
    
    # Run in ephemeral loop (Orchestrator handles its own state mostly, but we need an event loop for the async execution)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    bot = SessionOrchestrator(account_id)
    
    try:
        # EXECUTE TASK via Orchestrator
        # This will handles: Cold Start (if offline) -> Hot Start (if idle) -> Task -> Idle Timer
        # Note: We are not starting the background monitor here because this is a short-lived HTTP request context.
        # But the state transitions will still work for the execution duration.
        
        result = loop.run_until_complete(bot.execute(task_check_spamblock))
        
        # Determine status
        status = result.get('status', 'unknown')
        log_msgs = result.get('log', [])
        
        # Log to DB (Re-fetch account)
        try:
            account_ref = Account.query.get(account_id)
            
            if status == 'clean':
                if account_ref.status != 'active':
                    account_ref.status = 'active'
                # Update health if needed
            elif status == 'restricted':
                # User policy: Restricted = Banned
                account_ref.status = 'banned'
                account_ref.health_score = 0
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Failed to update account status: {e}")

        logger = ActivityLogger(account_id)
        
        if status == 'clean':
            logger.log(
                action_type='human_check_success',
                status='success',
                description='Human Check (Orchestrator): 🟢 CLEAN. Status -> Active',
                category='system'
            )
            return jsonify({'success': True, 'status': 'clean', 'logs': log_msgs})
            
        elif status == 'restricted':
            reason = result.get('reason', 'Unknown restriction')
            logger.log(
                action_type='human_check_failed',
                status='failed', 
                description=f'Human Check (Orchestrator): 🔴 RESTRICTED. Reason: {reason}',
                category='security'
            )
            return jsonify({'success': True, 'status': 'restricted', 'reason': reason, 'logs': log_msgs})
            
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.log(
                action_type='human_check_error',
                status='error',
                description=f'Human Check Error: {error_msg}',
                category='system'
            )
            return jsonify({'success': False, 'error': error_msg, 'logs': log_msgs})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
        
    finally:
        # Graceful shutdown of the orchestrator (disconnects client)
        loop.run_until_complete(bot.stop())
        loop.close()

@accounts_bp.route("/<int:account_id>/set-2fa", methods=["POST"])
@login_required
def set_2fa(account_id):
    """Set 2FA password with human emulation"""
    from utils.telethon_helper import set_2fa_password
    import string
    import random
    import asyncio
    
    account = Account.query.get_or_404(account_id)
    
    # Generate 10-char password (letters + numbers)
    chars = string.ascii_letters + string.digits
    password = ''.join(random.choice(chars) for _ in range(10))
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(set_2fa_password(account_id, password))
        
        if result['success']:
            account.two_fa_password = password
            db.session.commit()
            
            flash(f"✅ 2FA Password Set Successfully: {password}", "success")
        else:
            flash(f"❌ Failed to set 2FA: {result.get('error')}", "error")
            
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    finally:
        loop.close()
        
    return redirect(url_for('accounts.detail', account_id=account_id))


@accounts_bp.route("/<int:account_id>/sessions", methods=["GET"])
@login_required
def get_sessions(account_id):
    """Get active sessions (JSON)"""
    from utils.telethon_helper import get_active_sessions
    import asyncio
    
    # Run async helper
    # We use a new loop because Flask is synchronous here
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(get_active_sessions(account_id))
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    finally:
        loop.close()


@accounts_bp.route("/<int:account_id>/sessions/terminate", methods=["POST"])
@login_required
def terminate_sessions_route(account_id):
    """Terminate session(s)"""
    from utils.telethon_helper import terminate_session, terminate_all_sessions
    import asyncio
    
    session_hash = request.form.get('session_hash')
    terminate_all = request.form.get('terminate_all') == 'true'
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        if terminate_all:
            result = loop.run_until_complete(terminate_all_sessions(account_id))
        elif session_hash:
            result = loop.run_until_complete(terminate_session(account_id, session_hash))
        else:
            return jsonify({"success": False, "error": "No session hash provided"})
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    finally:
        loop.close()

@accounts_bp.route("/<int:account_id>/remove-2fa", methods=["POST"])
@login_required
def remove_2fa(account_id):
    """Remove 2FA password with human emulation"""
    from utils.telethon_helper import remove_2fa_password
    import asyncio
    
    account = Account.query.get_or_404(account_id)
    
    current_password = account.two_fa_password
    if not current_password:
        flash("Local 2FA password record is missing. Cannot automatically remove.", "error")
        return redirect(url_for('accounts.detail', account_id=account_id))
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(remove_2fa_password(account_id, current_password))
        
        if result['success']:
            account.two_fa_password = None
            db.session.commit()
            
            flash("✅ 2FA Password Removed Successfully", "success")
        else:
            flash(f"❌ Failed to remove 2FA: {result.get('error')}", "error")
            
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    finally:
        loop.close()
        
    return redirect(url_for('accounts.detail', account_id=account_id))



@accounts_bp.route("/<int:account_id>/update_device", methods=["POST"])
@login_required
def update_device(account_id):
    """Update or create device profile"""
    from utils.activity_logger import ActivityLogger
    
    account = Account.query.get_or_404(account_id)
    logger = ActivityLogger(account_id)
    
    # Check if user wants to use original TData
    use_original = request.form.get('use_original', '').lower() == 'true'
    
    if use_original:
        # Delete device profile to use original TData
        if account.device_profile:
            old_model = account.device_profile.device_model
            db.session.delete(account.device_profile)
            db.session.commit()
            
            logger.log(
                action_type='device_deleted',
                status='success',
                description=f"Switched to original TData device (was: {old_model})",
                details="Device profile deleted, using original TData fingerprint",
                category='system'
            )
            
            # Check if AJAX request
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Switched to original TData device'})
            
            flash("✅ Switched to original TData device", "success")
            return redirect(url_for('accounts.detail', account_id=account_id))
        else:
            # Already using original
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Already using original TData device'})
            
            flash("ℹ️ Already using original TData device", "info")
            return redirect(url_for('accounts.detail', account_id=account_id))
    
    # Check if user wants to use JSON parameters
    use_json = request.form.get('use_json', '').lower() == 'true'
    
    if use_json:
        # Switch to JSON device source
        if account.tdata_metadata:
            # Delete device profile if exists
            if account.device_profile:
                db.session.delete(account.device_profile)
            
            # Set device_source to 'json'
            account.tdata_metadata.device_source = 'json'
            db.session.commit()
            
            logger.log(
                action_type='device_source_changed',
                status='success',
                description="Switched to JSON device parameters",
                details="Using JSON metadata for device fingerprint",
                category='system'
            )
            
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Switched to JSON parameters'})
            
            flash("✅ Switched to JSON parameters", "success")
            return redirect(url_for('accounts.detail', account_id=account_id))
        else:
            error_msg = "No TData metadata or JSON data available"
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': error_msg}), 400
            
            flash(f"❌ {error_msg}", "error")
            return redirect(url_for('accounts.detail', account_id=account_id))
    
    # Get form data for custom device
    device_model = request.form.get('device_model', '').strip()
    system_version = request.form.get('system_version', '').strip()
    app_version = request.form.get('app_version', '').strip()
    lang_code = request.form.get('lang_code', 'en').strip()
    system_lang_code = request.form.get('system_lang_code', 'en-US').strip()
    client_type = request.form.get('client_type', 'desktop')
    
    if not all([device_model, system_version, app_version]):
        error_msg = "All device fields (model, system, app version) are required"
        
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': error_msg}), 400
        
        flash(f"❌ {error_msg}", "error")
        return redirect(url_for('accounts.detail', account_id=account_id))
    
    # Update or create device profile
    if account.device_profile:
        dp = account.device_profile
        old_model = dp.device_model
        dp.device_model = device_model
        dp.system_version = system_version
        dp.app_version = app_version
        dp.lang_code = lang_code
        dp.system_lang_code = system_lang_code
        dp.client_type = client_type
        action = 'device_updated'
        msg = f"Device updated: {old_model} → {device_model}"
    else:
        dp = DeviceProfile(
            account_id=account_id,
            device_model=device_model,
            system_version=system_version,
            app_version=app_version,
            lang_code=lang_code,
            system_lang_code=system_lang_code,
            client_type=client_type
        )
        db.session.add(dp)
        account.device_profile = dp
        action = 'device_created'
        msg = f"Device created: {device_model}"
    
    db.session.commit()
    
    logger.log(
        action_type=action,
        status='success',
        description=msg,
        details=f"Model: {device_model}, System: {system_version}, App: {app_version}, Client: {client_type}",
        category='system'
    )
    
    # Check if AJAX request
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'message': msg,
            'device': {
                'model': device_model,
                'system': system_version,
                'app': app_version,
                'lang': f"{lang_code} / {system_lang_code}"
            }
        })
    
    flash(f"✅ {msg}", "success")
    return redirect(url_for('accounts.detail', account_id=account_id))

