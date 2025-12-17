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
            
            # Get channel entity
            entity = await client.get_entity(channel_username)
            
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
