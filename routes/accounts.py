from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils.decorators import login_required
from models.account import Account, DeviceProfile, AccountSubscription
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
                    created_at=datetime.now()
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
                    system_lang_code=device["system_lang_code"]
                )
                db.session.add(device_profile)
                
                # 📝 Log upload
                logger = ActivityLogger(account.id)
                logger.log(
                    action_type='upload_session',
                    status='success',
                    description=f'Session file uploaded and validated',
                    details=f"File: {filename}, Size: {validation['size']} bytes, Age: {metadata.get('estimated_age', 'unknown')}",
                    category='system'
                )
                
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
    
    return render_template(
        "accounts/detail.html",
        account=account,
        proxies=proxies,
        conversation_partners=conversation_partners,
        other_accounts=other_accounts,
        recent_activities=recent_activities
    )


@accounts_bp.route("/<int:account_id>/verify", methods=["POST"])
@login_required
def verify(account_id):
    """Verify account safe strategy"""
    from utils.telethon_helper import get_telethon_client
    from utils.activity_logger import ActivityLogger
    from telethon.errors import FloodWaitError
    from datetime import datetime
    import asyncio
    import random
    import json
    
    account = Account.query.get_or_404(account_id)
    
    # 1. Cooldown check (5 minutes)
    if hasattr(account, 'last_verification_attempt') and account.last_verification_attempt:
        seconds_since = (datetime.now() - account.last_verification_attempt).total_seconds()
        if seconds_since < 300: # 5 minutes
            mins_left = int((300 - seconds_since) / 60)
            flash(f"Please wait {mins_left + 1} minutes before retrying verification", "warning")
            return redirect(url_for('accounts.detail', account_id=account_id))
            
    # Update attempt time
    try:
        if hasattr(Account, 'last_verification_attempt'):
             account.last_verification_attempt = datetime.now()
             db.session.commit()
    except:
        db.session.rollback()
    
    logger = ActivityLogger(account_id)
    logger.log(
        action_type='verification_start',
        status='pending',
        description='Starting risk-based verification',
        category='system'
    )
    
    # Determine strategy based on age
    age_category = 'new'
    if hasattr(account, 'metadata') and account.metadata:
        try:
            meta = json.loads(account.metadata) if isinstance(account.metadata, str) else account.metadata
            if isinstance(meta, dict):
                age_category = meta.get('estimated_age', 'new')
        except:
            pass
            
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def safe_verify():
        client = None
        try:
            client = get_telethon_client(account_id)
            await client.connect()
            
            # Step 1: minimal verification
            me = await client.get_me()
            account.telegram_id = me.id
            account.first_name = me.first_name
            account.last_name = me.last_name
            account.username = me.username
            account.status = 'active'
            
            # Basic photo check (no download yet for new accounts)
            if hasattr(me, "photo") and me.photo:
                account.photo_url = "photo_available"
            
            # Random delay
            await asyncio.sleep(random.uniform(2, 5))
            
            return {"success": True}
            
        except FloodWaitError as e:
            return {"success": False, "error": f"FloodWait: {e.seconds}s", "wait": e.seconds}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if client and client.is_connected():
                await client.disconnect()
                
    # Run loop
    try:
        result = loop.run_until_complete(safe_verify())
    finally:
        loop.close()
    
    if result['success']:
        if hasattr(Account, 'verified'):
            try:
                account.verified = True
            except:
                pass
        db.session.commit()
        flash("Account verified successfully", "success")
        logger.log(action_type='verification_success', status='success', description='Verification passed, active status set')
    else:
        if "FloodWait" in str(result.get('error')):
            account.status = 'flood_wait'
            wait_time = result.get('wait', 0)
            flash(f"Telegram FloodWait limit. Please wait {wait_time} seconds.", "error")
            logger.log(action_type='verification_failed', status='error', description=f"FloodWait: {wait_time}s", category='system')
        else:
            account.status = 'error'
            flash(f"Verification failed: {result.get('error')}", "error")
            logger.log(action_type='verification_failed', status='error', description=f"Error: {result.get('error')}", category='system')
        db.session.commit()
        
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
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def sync_profile():
        client = None
        try:
            client = get_telethon_client(account_id)
            await client.connect()
            
            # Get user info
            me = await client.get_me()
            
            # Update fields
            account.telegram_id = me.id if hasattr(me, "id") else account.telegram_id
            account.first_name = getattr(me, "first_name", None) or account.first_name
            account.last_name = getattr(me, "last_name", None)
            account.username = getattr(me, "username", None)
            
            # Get bio (about)
            try:
                full_user = await client.get_entity(me)
                if hasattr(full_user, 'about'):
                    account.bio = full_user.about
            except:
                pass
            
            # Try to download profile photo
            try:
                if hasattr(me, "photo") and me.photo:
                    photo_path = f"uploads/photos/{account.phone}_profile.jpg"
                    os.makedirs("uploads/photos", exist_ok=True)
                    await client.download_profile_photo(me, file=photo_path)
                    account.photo_url = photo_path
            except Exception as photo_err:
                if hasattr(me, "photo") and me.photo:
                    account.photo_url = "photo_available"
            
            # Update sync timestamp
            account.last_sync_at = datetime.utcnow()
            
            return True, account.first_name
            
        except Exception as e:
            return False, str(e)
            
        finally:
            if client and client.is_connected():
                await client.disconnect()
                await asyncio.sleep(0.1)
    
    try:
        success, info = loop.run_until_complete(sync_profile())
        db.session.commit()
        
        if success:
            flash(f"✅ Profile synced from Telegram: {info}", "success")
        else:
            flash(f"❌ Sync failed: {info}", "error")
            
    except Exception as e:
        flash(f"Error: {str(e)}", "error")
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        try:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except:
            pass
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
        db.session.execute(db.text("DELETE FROM account_warmup_channels WHERE account_id = :aid"), {"aid": account_id})
        db.session.execute(db.text("DELETE FROM warmup_activities WHERE account_id = :aid"), {"aid": account_id})
        db.session.execute(db.text("DELETE FROM conversation_pairs WHERE account_a_id = :aid OR account_b_id = :aid"), {"aid": account_id})
        
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
    
    # Create new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def join_channel():
        client = None
        try:
            client = get_telethon_client(account_id)
            await client.connect()
            
            # Get channel entity - try different formats
            try:
                # Try as @username
                entity = await client.get_entity(f"@{channel_username}")
            except:
                try:
                    # Try without @
                    entity = await client.get_entity(channel_username)
                except:
                    # Try as t.me link
                    entity = await client.get_entity(f"https://t.me/{channel_username}")
            
            # Try to join
            try:
                await client(JoinChannelRequest(entity))
                return "active", f"Successfully joined @{channel_username}"
            except Exception as join_err:
                # Check if already member
                try:
                    me = await client.get_me()
                    participants = await client.get_participants(entity, limit=100)
                    if any(p.id == me.id for p in participants):
                        return "active", f"Already a member of @{channel_username}"
                    else:
                        return "failed", f"Could not join: {str(join_err)}"
                except Exception as check_err:
                    return "failed", f"Could not verify membership: {str(check_err)}"
                    
        except Exception as e:
            return "failed", f"Error: {str(e)}"
            
        finally:
            if client and client.is_connected():
                await client.disconnect()
                # Give time for cleanup
                await asyncio.sleep(0.1)
    
    try:
        subscription_status, message = loop.run_until_complete(join_channel())
        
        # Log result
        if subscription_status == "active":
            logger.log(
                action_type='join_group',
                status='success',
                target=f"@{channel_username}",
                description=f"Successfully joined @{channel_username}",
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
        # Cancel all pending tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        try:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except:
            pass
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
    
    # Create new event loop for async operations
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Update profile info (username, bio)
        if username or bio:
            result = loop.run_until_complete(update_telegram_profile(
                account_id,
                username=username if username else None,
                bio=bio if bio else None
            ))
            
            if not result['success']:
                flash(f"Failed to update Telegram profile: {result['error']}", "error")
                return redirect(url_for("accounts.detail", account_id=account_id))
            
            # Update local database only if Telegram update succeeded
            if username:
                account.username = username
            if bio:
                account.bio = bio
            
            flash(f"Profile updated in Telegram: {', '.join(result['updated_fields'])}", "success")
        
        # Update photo
        if photo_file:
            photo_result = loop.run_until_complete(update_telegram_photo(
                account_id,
                photo_file
            ))
            
            if photo_result['success']:
                account.photo_url = photo_file
                flash("Profile photo updated in Telegram", "success")
            else:
                flash(f"Failed to update photo: {photo_result['error']}", "error")
        
        db.session.commit()
        
    except Exception as e:
        flash(f"Error updating profile: {str(e)}", "error")
    finally:
        # Cleanup event loop
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        try:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except:
            pass
        loop.close()
    
    return redirect(url_for("accounts.detail", account_id=account_id))


# ==================== WARMUP SETTINGS ROUTES ====================

@accounts_bp.route("/<int:account_id>/warmup")
@login_required
def warmup_settings(account_id):
    """View warmup settings for account"""
    from models.warmup import ConversationPair, WarmupActivity, WarmupChannelTheme
    from models.account import AccountSubscription
    
    account = Account.query.get_or_404(account_id)
    
    # Get subscriptions (these are used for warmup reading)
    warmup_channels = AccountSubscription.query.filter_by(
        account_id=account_id,
        is_active=True
    ).all()
    
    # Get conversation pairs
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
    
    # Get recent warmup activities
    recent_activities = WarmupActivity.query.filter_by(
        account_id=account_id
    ).order_by(WarmupActivity.timestamp.desc()).limit(20).all()
    
    # Get available themes
    themes = WarmupChannelTheme.query.all()
    
    # Get other accounts for pairing
    other_accounts = Account.query.filter(
        Account.id != account_id,
        Account.status.in_(['warming_up', 'active'])
    ).all()
    
    return render_template(
        "accounts/warmup_settings.html",
        account=account,
        warmup_channels=warmup_channels,
        conversation_partners=conversation_partners,
        recent_activities=recent_activities,
        themes=themes,
        other_accounts=other_accounts
    )


@accounts_bp.route("/<int:account_id>/warmup/add-channel", methods=["POST"])
@login_required
def add_warmup_channel(account_id):
    """Add a channel for warmup reading"""
    from models.warmup import AccountWarmupChannel
    
    account = Account.query.get_or_404(account_id)
    channel_username = request.form.get("channel_username", "").strip().lstrip("@")
    
    if not channel_username:
        flash("Channel username is required", "error")
        return redirect(url_for("accounts.warmup_settings", account_id=account_id))
    
    # Check if already exists
    existing = AccountWarmupChannel.query.filter_by(
        account_id=account_id,
        channel_username=channel_username
    ).first()
    
    if existing:
        flash(f"Channel @{channel_username} already added", "warning")
        return redirect(url_for("accounts.warmup_settings", account_id=account_id))
    
    # Add channel
    warmup_channel = AccountWarmupChannel(
        account_id=account_id,
        channel_username=channel_username,
        source="manual"
    )
    db.session.add(warmup_channel)
    db.session.commit()
    
    flash(f"Added @{channel_username} for warmup reading", "success")
    return redirect(url_for("accounts.warmup_settings", account_id=account_id))


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

