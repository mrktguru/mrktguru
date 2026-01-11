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

import nest_asyncio
nest_asyncio.apply()
accounts_bp = Blueprint("accounts", __name__)


@accounts_bp.route("/")
@login_required
def list_accounts():
    """List all accounts"""
    accounts = Account.query.order_by(Account.created_at.desc()).all()
    proxies = Proxy.query.filter_by(status="active").all()
    return render_template("accounts/list.html", accounts=accounts, proxies=proxies)


@accounts_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """Upload session files"""
    if request.method == "POST":
        files = request.files.getlist("session_files")
        
        if not files or files[0].filename == "":
            flash("No files selected", "error")
            return redirect(url_for("accounts.upload"))
        
        uploaded = 0
        skipped = 0
        errors = []
        
        for file in files:
            if file and file.filename.endswith(".session"):
                try:
                    filename = secure_filename(file.filename)
                    phone = filename.replace(".session", "")
                    
                    # Check if account already exists
                    existing = Account.query.filter_by(phone=phone).first()
                    if existing:
                        errors.append(f"{phone}: Account already exists (delete it first)")
                        skipped += 1
                        continue
                    
                    # Save file
                    filepath = os.path.join("uploads/sessions", filename)
                    os.makedirs("uploads/sessions", exist_ok=True)
                    file.save(filepath)
                    
                    # Create account
                    account = Account(
                        phone=phone,
                        session_file_path=filepath,
                        status="pending",
                        health_score=100
                    )
                    db.session.add(account)
                    db.session.flush()
                    
                    # Create device profile
                    device = generate_device_profile()
                    device_profile = DeviceProfile(
                        account_id=account.id,
                        device_model=device["device_model"],
                        system_version=device["system_version"],
                        app_version=device["app_version"],
                        lang_code=device["lang_code"],
                        system_lang_code=device["system_lang_code"]
                    )
                    db.session.add(device_profile)
                    
                    uploaded += 1
                    
                except Exception as e:
                    errors.append(f"{file.filename}: {str(e)}")
        
        db.session.commit()
        
        # Show notifications
        if uploaded > 0:
            flash(f"Successfully uploaded {uploaded} session file(s)", "success")
        if skipped > 0:
            flash(f"Skipped {skipped} duplicate account(s)", "warning")
        for error in errors:
            flash(error, "error")
        
        return redirect(url_for("accounts.list_accounts"))
    
    proxies = Proxy.query.filter_by(status="active").all()
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
    """Verify account session, fetch user info, and import existing subscriptions"""
    from utils.telethon_helper import get_telethon_client
    from models.account import AccountSubscription
    import asyncio
    
    account = Account.query.get_or_404(account_id)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def verify_and_fetch():
        client = None
        subscriptions_found = 0
        try:
            client = get_telethon_client(account_id)
            await client.connect()
            
            # Get user info
            me = await client.get_me()
            account.telegram_id = me.id if hasattr(me, "id") else None
            account.first_name = getattr(me, "first_name", None) or "User"
            account.last_name = getattr(me, "last_name", None)
            account.username = getattr(me, "username", None)
            
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
            
            # Get existing subscriptions from Telegram
            try:
                from telethon.tl.types import Channel
                
                dialogs = await client.get_dialogs()
                
                for dialog in dialogs:
                    entity = dialog.entity
                    
                    # Check if it is a channel or megagroup
                    if isinstance(entity, Channel):
                        channel_username = getattr(entity, "username", None)
                        channel_title = getattr(entity, "title", "Unknown")
                        
                        if not channel_username:
                            continue
                        
                        # Check if already in our database
                        existing = AccountSubscription.query.filter_by(
                            account_id=account_id,
                            channel_username=channel_username
                        ).first()
                        
                        if not existing:
                            # Add to subscriptions
                            subscription = AccountSubscription(
                                account_id=account_id,
                                channel_username=channel_username,
                                status="active",
                                subscription_source="imported",
                                notes=f"Auto-imported: {channel_title}"
                            )
                            db.session.add(subscription)
                            subscriptions_found += 1
                            
            except Exception as subs_err:
                print(f"Error fetching subscriptions: {subs_err}")
            
            # Check if account can access channels (spam-block test)
            can_access_channels = False
            try:
                # Try to find a known public CHANNEL (not user profile)
                # Using @telegram channel as test
                test_entity = await client.get_entity("@telegram")
                # Also check if it is actually a channel
                from telethon.tl.types import Channel
                if isinstance(test_entity, Channel):
                    can_access_channels = True
            except Exception as test_err:
                # If cannot find @telegram, account is spam-blocked
                print(f"Spam-block test failed: {test_err}")
                pass
            
            if not can_access_channels:
                account.status = "spam-block"
                account.health_score = 30
                account.notes = "WARNING: Account cannot search/join channels. Possible spam-block."
            else:
                account.status = "active"
                account.health_score = 100
            
            return True, account.first_name, account.username or "no username", subscriptions_found
            
        except Exception as e:
            account.status = "error"
            account.health_score = 0
            return False, None, str(e), 0
            
        finally:
            if client and client.is_connected():
                await client.disconnect()
                await asyncio.sleep(0.1)
    
    try:
        success, first_name, info, subs_count = loop.run_until_complete(verify_and_fetch())
        db.session.commit()
        
        if success:
            msg = f"Session verified! User: {first_name} (@{info})"
            if subs_count > 0:
                msg += f". Imported {subs_count} existing subscriptions."
            flash(msg, "success")
        else:
            flash(f"Verification failed: {info}", "error")
            
    except Exception as e:
        account.status = "error"
        db.session.commit()
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
    account = Account.query.get_or_404(account_id)
    proxy_id = request.form.get("proxy_id")
    
    if proxy_id:
        account.proxy_id = int(proxy_id)
        db.session.commit()
        flash("Proxy assigned", "success")
    else:
        account.proxy_id = None
        db.session.commit()
        flash("Proxy removed", "info")
    
    return redirect(url_for("accounts.detail", account_id=account_id))


@accounts_bp.route("/<int:account_id>/add-subscription", methods=["POST"])
@login_required
def add_subscription(account_id):
    """Add channel subscription - actually joins the channel/group"""
    from utils.telethon_helper import get_telethon_client
    from telethon.tl.functions.channels import JoinChannelRequest
    import asyncio
    
    account = Account.query.get_or_404(account_id)
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
        
        if subscription_status == "active":
            flash(message, "success")
        else:
            flash(message, "warning")
            
    except Exception as e:
        subscription_status = "failed"
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
    account = Account.query.get_or_404(account_id)
    
    # Update editable fields
    if "username" in request.form:
        account.username = request.form["username"].strip().lstrip("@")
    
    if "bio" in request.form:
        account.bio = request.form["bio"].strip()
    
    # Handle photo upload
    if "photo" in request.files:
        photo = request.files["photo"]
        if photo and photo.filename:
            filename = secure_filename(f"{account.phone}_{photo.filename}")
            photo_path = os.path.join("uploads/photos", filename)
            os.makedirs("uploads/photos", exist_ok=True)
            photo.save(photo_path)
            account.photo_url = photo_path
    
    db.session.commit()
    flash("Profile updated successfully", "success")
    return redirect(url_for("accounts.detail", account_id=account_id))


# ==================== WARMUP SETTINGS ROUTES ====================

@accounts_bp.route("/<int:account_id>/warmup")
@login_required
def warmup_settings(account_id):
    """View warmup settings for account"""
    from models.warmup import AccountWarmupChannel, ConversationPair, WarmupActivity, WarmupChannelTheme
    
    account = Account.query.get_or_404(account_id)
    
    # Get warmup channels
    warmup_channels = AccountWarmupChannel.query.filter_by(
        account_id=account_id
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

