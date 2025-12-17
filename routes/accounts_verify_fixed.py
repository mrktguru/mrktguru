@accounts_bp.route("/<int:account_id>/verify", methods=["POST"])
@login_required
def verify(account_id):
    """Verify account session"""
    import asyncio
    from utils.telethon_helper import verify_session
    
    account = Account.query.get_or_404(account_id)
    
    try:
        result = asyncio.run(verify_session(account_id))
        
        if result["success"]:
            account.status = "active"
            account.health_score = 100
            
            # Extract Telegram user info
            user = result["user"]
            account.telegram_id = user.id if hasattr(user, "id") else None
            account.first_name = getattr(user, "first_name", None) or "User"
            account.last_name = getattr(user, "last_name", None)
            account.username = getattr(user, "username", None)
            
            # Get bio if available
            try:
                if hasattr(user, "about"):
                    account.bio = user.about
            except:
                pass
            
            # Get photo URL if available
            try:
                if hasattr(user, "photo") and user.photo:
                    # For now just mark that photo exists
                    account.photo_url = "photo_available"
            except:
                pass
            
            username = account.username or "no username"
            flash(f"✅ Session verified! User: {account.first_name} (@{username})", "success")
        else:
            account.status = "invalid"
            account.health_score = 0
            error_msg = result.get("error", "Unknown error")
            flash(f"❌ Verification failed: {error_msg}", "error")
        
        db.session.commit()
        
    except Exception as e:
        account.status = "error"
        db.session.commit()
        flash(f"❌ Error: {str(e)}", "error")
    
    return redirect(url_for("accounts.detail", account_id=account_id))
