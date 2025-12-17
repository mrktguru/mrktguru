@accounts_bp.route("/<int:account_id>/verify", methods=["POST"])
@login_required
def verify(account_id):
    """Verify account session and fetch user info"""
    from utils.telethon_helper import get_telethon_client
    import asyncio
    
    account = Account.query.get_or_404(account_id)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def verify_and_fetch():
        client = None
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
            
            account.status = "active"
            account.health_score = 100
            
            return True, account.first_name, account.username or "no username"
            
        except Exception as e:
            account.status = "error"
            account.health_score = 0
            return False, None, str(e)
            
        finally:
            if client and client.is_connected():
                await client.disconnect()
                # Give time for cleanup
                await asyncio.sleep(0.1)
    
    try:
        success, first_name, info = loop.run_until_complete(verify_and_fetch())
        db.session.commit()
        
        if success:
            flash(f"Session verified! User: {first_name} (@{info})", "success")
        else:
            flash(f"Verification failed: {info}", "error")
            
    except Exception as e:
        account.status = "error"
        db.session.commit()
        flash(f"Error: {str(e)}", "error")
    finally:
        # Wait for all pending tasks before closing loop
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        # Run loop briefly to cancel tasks
        try:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except:
            pass
        loop.close()
    
    return redirect(url_for("accounts.detail", account_id=account_id))
