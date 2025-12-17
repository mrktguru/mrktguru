@accounts_bp.route("/<int:account_id>/add-subscription", methods=["POST"])
@login_required
def add_subscription(account_id):
    """Add channel subscription and actually join"""
    import asyncio
    import re
    from utils.telethon_helper import connect_client
    
    account = Account.query.get_or_404(account_id)
    channel_input = request.form.get("channel_username", "").strip()
    notes = request.form.get("notes")
    
    if not channel_input:
        flash("❌ Channel username is required", "error")
        return redirect(url_for("accounts.detail", account_id=account_id))
    
    # Extract username from link or @username
    # Support formats: @username, username, t.me/username, https://t.me/username
    channel_username = channel_input.lstrip("@")
    if "t.me/" in channel_username:
        channel_username = channel_username.split("t.me/")[-1].split("/")[0].split("?")[0]
    
    # Check if already subscribed
    existing = AccountSubscription.query.filter_by(
        account_id=account_id,
        channel_username=channel_username
    ).first()
    
    if existing:
        flash(f"⚠️ Already subscribed to @{channel_username}", "warning")
        return redirect(url_for("accounts.detail", account_id=account_id))
    
    # Try to join the channel/group via Telethon
    subscription_status = "failed"
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            client = loop.run_until_complete(connect_client(account_id))
            
            # Try to get entity and join
            entity = loop.run_until_complete(client.get_entity(channel_username))
            
            # For groups/channels, try to join
            from telethon.tl.functions.channels import JoinChannelRequest
            try:
                loop.run_until_complete(client(JoinChannelRequest(entity)))
                subscription_status = "active"
                flash(f"✅ Successfully joined @{channel_username}", "success")
            except Exception as join_error:
                # Already member or can\t join
