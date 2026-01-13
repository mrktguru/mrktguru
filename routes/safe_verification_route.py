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
    
    logger = ActivityLogger(account_id)
    logger.log(
        action_type='safe_verification_started',
        status='info',
        description=f'Starting safe verification: {method}',
        category='system'
    )
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Get Telethon client
        client = get_telethon_client(account_id)
        
        # Call appropriate verification method
        if method == 'self_check':
            result = loop.run_until_complete(safe_self_check(client))
        elif method == 'get_me':
            result = loop.run_until_complete(safe_get_me(client, account.last_verification_time))
        elif method == 'public_channel':
            result = loop.run_until_complete(check_via_public_channel(client))
        
        if result['success']:
            # Update account info
            user = result
            account.telegram_id = user.get('user_id')
            account.first_name = user.get('first_name')
            account.last_name = user.get('last_name')
            account.username = user.get('username')
            account.status = 'active'
            account.verified = True
            account.last_activity = datetime.utcnow()
            
            # Update verification tracking
            account.last_verification_method = method
            account.last_verification_time = datetime.utcnow()
            account.verification_count = (account.verification_count or 0) + 1
            
            db.session.commit()
            
            logger.log(
                action_type='safe_verification_success',
                status='success',
                description=f'Verification successful via {method}',
                category='system'
            )
            
            flash(f"✅ Verification successful via {method}!", "success")
            return jsonify({
                'success': True,
                'method': method,
                'user': {
                    'id': user.get('user_id'),
                    'username': user.get('username'),
                    'first_name': user.get('first_name')
                },
                'duration': result.get('duration'),
                'next_check_allowed': result.get('next_check_allowed')
            })
            
        else:
            # Handle errors
            error_type = result.get('error_type', 'generic_error')
            
            if error_type == 'cooldown':
                flash(f"⏱️ {result.get('error')}", "warning")
                return jsonify({
                    'success': False,
                    'error': result.get('error'),
                    'error_type': 'cooldown',
                    'remaining_minutes': result.get('remaining_minutes')
                }), 429
                
            elif error_type == 'flood_wait':
                account.status = 'flood_wait'
                wait_time = result.get('wait', 0)
                db.session.commit()
                
                flash(f"❌ Telegram FloodWait limit. Please wait {wait_time} seconds.", "error")
                logger.log(
                    action_type='safe_verification_failed',
                    status='error',
                    description=f"FloodWait: {wait_time}s (method: {method})",
                    category='system'
                )
                
                return jsonify({
                    'success': False,
                    'error': result.get('error'),
                    'error_type': 'flood_wait',
                    'wait': wait_time
                }), 429
                
            elif error_type == 'banned':
                account.status = 'banned'
                account.health_score = 0
                db.session.commit()
                
                flash(f"❌ Account is BANNED by Telegram", "error")
                logger.log(
                    action_type='safe_verification_failed',
                    status='error',
                    description=f"ACCOUNT BANNED (method: {method})",
                    category='system'
                )
                
                return jsonify({
                    'success': False,
                    'error': 'Account is banned',
                    'error_type': 'banned'
                }), 403
                
            elif error_type == 'invalid_session':
                account.status = 'error'
                db.session.commit()
                
                flash(f"❌ Session Invalid: {result.get('error')}", "error")
                logger.log(
                    action_type='safe_verification_failed',
                    status='error',
                    description=f"Invalid Session (method: {method})",
                    category='system'
                )
                
                return jsonify({
                    'success': False,
                    'error': result.get('error'),
                    'error_type': 'invalid_session'
                }), 400
                
            else:
                account.status = 'error'
                db.session.commit()
                
                flash(f"❌ Verification failed: {result.get('error')}", "error")
                logger.log(
                    action_type='safe_verification_failed',
                    status='error',
                    description=f"Error: {result.get('error')} (method: {method})",
                    category='system'
                )
                
                return jsonify({
                    'success': False,
                    'error': result.get('error'),
                    'error_type': error_type
                }), 500
                
    except Exception as e:
        db.session.rollback()
        flash(f"❌ System Error: {str(e)}", "error")
        logger.log(
            action_type='safe_verification_failed',
            status='error',
            description=f"System Error: {str(e)} (method: {method})",
            category='system'
        )
        
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': 'system_error'
        }), 500
        
    finally:
        loop.close()
