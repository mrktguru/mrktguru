from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils.decorators import login_required
from flask_login import current_user
from database import db
from models.account import Account
from models.proxy import Proxy
from models.api_credential import ApiCredential
from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio
import os

phone_login_bp = Blueprint('phone_login', __name__, 
                         template_folder='templates',
                         url_prefix='/accounts/phone')

# Helper to run async in sync route
def run_async(coro):
    import threading
    result = {}
    def target():
        try:
             loop = asyncio.new_event_loop()
             asyncio.set_event_loop(loop)
             result['success'] = loop.run_until_complete(coro)
             loop.close()
        except Exception as e:
             result['error'] = e
    
    t = threading.Thread(target=target)
    t.start()
    t.join()
    
    if 'error' in result:
        raise result['error']
    return result['success']

@phone_login_bp.route('/add', methods=['GET'])
@login_required
def add_phone():
    """Step 1: Form to enter phone number"""
    proxies = Proxy.query.filter_by(status='active').all()
    credentials = ApiCredential.query.all()
    return render_template('accounts/add_phone.html', proxies=proxies, credentials=credentials)

@phone_login_bp.route('/request-code', methods=['POST'])
@login_required
def request_code():
    """Step 2: Connect and request auth code"""
    phone = request.form.get('phone')
    proxy_id = request.form.get('proxy_id')
    api_id_val = int(request.form.get('api_id', 2040))
    api_hash_val = request.form.get('api_hash', 'b18441a1bb607e12738205e450b8ad6b')

    if not phone:
        flash("Phone number required", "error")
        return redirect(url_for('phone_login.add_phone'))
        
    # Create temporary Account entry
    account = Account.query.filter_by(phone=phone).first()
    if not account:
        account = Account(
            phone=phone,
            session_file_path="",  # Will be empty for StringSession
            source_type='phone_login',
            status='authenticating'
        )
        db.session.add(account)
    
    if proxy_id:
        account.proxy_id = proxy_id
        
    db.session.commit()
    
    # Init Client
    session = StringSession()
    client = TelegramClient(session, api_id_val, api_hash_val)
    
    async def _send_code():
        await client.connect()
        if not await client.is_user_authorized():
            return await client.send_code_request(phone)
        return "AUTHORIZED" # Already authorized?
        
    try:
        res = run_async(_send_code())
        
        if res == "AUTHORIZED":
            # Just save session
            account.session_string = client.session.save()
            account.status = 'active'
            db.session.commit()
            flash("Account was already authorized!", "success")
            return redirect(url_for('accounts.list_accounts'))
            
        # Save hash for next step
        account.phone_code_hash = res.phone_code_hash
        # Save PARTIAL session to keep connection settings? 
        # Actually StringSession saves auth key. If not auth'd, it might not save much.
        # But we need to reuse the same session object or at least the hash?
        # Telethon needs phone_code_hash to match the request.
        
        # We need to save the preliminary session string too, 
        # although it doesn't have the user auth yet, it might have DC info.
        account.session_string = client.session.save() 
        db.session.commit()
        
        return redirect(url_for('phone_login.enter_code', account_id=account.id))
        
    except Exception as e:
        flash(f"Failed to send code: {str(e)}", "error")
        return redirect(url_for('phone_login.add_phone'))

@phone_login_bp.route('/enter-code/<int:account_id>', methods=['GET'])
@login_required
def enter_code(account_id):
    """Step 3: Enter OTP code"""
    account = Account.query.get_or_404(account_id)
    return render_template('accounts/enter_code.html', account=account)

@phone_login_bp.route('/submit-code/<int:account_id>', methods=['POST'])
@login_required
def submit_code(account_id):
    """Step 4: Finalize login"""
    account = Account.query.get_or_404(account_id)
    code = request.form.get('code')
    password = request.form.get('password') # 2FA
    
    # Re-hydrate client
    session = StringSession(account.session_string)
    # TODO: We need API ID/Hash. Store in account or assume default?
    # For now assuming default or we should have stored it. 
    # Let's use standard ID for simplicity or fetch if we stored credential ID.
    api_id = 2040 
    api_hash = 'b18441a1bb607e12738205e450b8ad6b'
    
    client = TelegramClient(session, api_id, api_hash)
    
    async def _sign_in():
        await client.connect()
        # Telethon sign_in needs phone, code, and phone_code_hash
        try:
            user = await client.sign_in(
                phone=account.phone,
                code=code,
                phone_code_hash=account.phone_code_hash
            )
            return user
        except Exception as e:
            if "password" in str(e).lower() or "TwoStep" in str(e):
                 if password:
                     return await client.sign_in(password=password)
                 else:
                     raise ValueError("2FA Required")
            raise e

    try:
        user = run_async(_sign_in())
        
        # Success!
        account.session_string = client.session.save()
        account.telegram_id = user.id
        account.username = user.username
        account.first_name = user.first_name
        account.last_name = user.last_name
        account.status = 'active'
        account.phone_code_hash = None # Clear hash
        
        db.session.commit()
        flash("Login successful! Account added.", "success")
        return redirect(url_for('accounts.list_accounts'))
        
    except ValueError as ve:
        if str(ve) == "2FA Required":
             flash("Two-Step Verification Password Required", "warning")
             # Render template again with password field visible or flag
             return render_template('accounts/enter_code.html', account=account, ask_password=True)
        else:
             flash(f"Login failed: {ve}", "error")
             return redirect(url_for('phone_login.enter_code', account_id=account.id))
    except Exception as e:
        flash(f"Login error: {e}", "error")
        return redirect(url_for('phone_login.enter_code', account_id=account.id))
