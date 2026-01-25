from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils.decorators import login_required
from flask_login import current_user
from database import db
from models.account import Account, DeviceProfile
from models.proxy import Proxy
from models.proxy_network import ProxyNetwork
from models.api_credential import ApiCredential
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
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

# Helper for device parameters
def get_device_params(api_credential=None):
    """Generate realistic device parameters based on API credential type"""
    params = {
        'device_model': 'Unknown',
        'system_version': 'Unknown',
        'app_version': '1.0',
        'lang_code': 'en',
        'system_lang_code': 'en-US'
    }
    
    client_type = 'desktop'
    if api_credential and api_credential.client_type:
        client_type = api_credential.client_type.lower()
        
    if client_type == 'android':
        params = {
            'device_model': 'Samsung Galaxy S24 Ultra',
            'system_version': 'Android 14',
            'app_version': '10.9.1', # Example active version
            'lang_code': 'en',
            'system_lang_code': 'en-US'
        }
    elif client_type == 'ios':
        params = {
            'device_model': 'iPhone 15 Pro',
            'system_version': 'iOS 17.4',
            'app_version': '10.8',
            'lang_code': 'en',
            'system_lang_code': 'en-US'
        }
    elif client_type == 'desktop':
        params = {
            'device_model': 'Desktop',
            'system_version': 'Windows 11',
            'app_version': '4.16.8 x64',
            'lang_code': 'en',
            'system_lang_code': 'en-US'
        }
    
    return params

@phone_login_bp.route('/add', methods=['GET'])
@login_required
def add_phone():
    """Step 1: Form to enter phone number"""
    proxies = Proxy.query.filter_by(status='active').all()
    proxy_networks = ProxyNetwork.query.all()
    credentials = ApiCredential.query.all()
    return render_template('accounts/add_phone.html', proxies=proxies, proxy_networks=proxy_networks, credentials=credentials)

@phone_login_bp.route('/request-code', methods=['POST'])
@login_required
def request_code():
    """Step 2: Connect and request auth code"""
    phone = request.form.get('phone')
    proxy_id = request.form.get('proxy_id')
    api_cred_id = request.form.get('api_cred_id')
    
    from flask import current_app
    
    # Defaults
    api_id_val = 2040
    api_hash_val = 'b18441a1bb607e12738205e450b8ad6b'
    
    # Try using selected credential
    api_credential = None
    if api_cred_id:
        api_credential = ApiCredential.query.get(api_cred_id)
        if api_credential:
            api_id_val = api_credential.api_id
            api_hash_val = api_credential.api_hash
            
    # Fallback to manual input
    if not api_credential:
         manual_id = request.form.get('api_id')
         if manual_id:
             api_id_val = int(manual_id)
             api_hash_val = request.form.get('api_hash')

    if not phone:
        flash("Phone number required", "error")
        return redirect(url_for('phone_login.add_phone'))
        
    # Create temporary Account entry
    account = Account.query.filter_by(phone=phone).first()
    if not account:
        account = Account(
            phone=phone,
            session_file_path="",  
            source_type='phone_login',
            status='authenticating'
        )
        db.session.add(account)
    
    proxy_config = None
    selection = request.form.get("proxy_selection")
    
    if selection:
        import python_socks
        if selection.startswith("proxy_"):
            p_id = int(selection.replace("proxy_", ""))
            account.proxy_id = p_id
            proxy_obj = Proxy.query.get(p_id)
            if proxy_obj:
                proxy_type = python_socks.ProxyType.SOCKS5 if 'socks5' in proxy_obj.type.lower() else python_socks.ProxyType.HTTP
                proxy_config = {
                    'proxy_type': proxy_type,
                    'addr': proxy_obj.host,
                    'port': proxy_obj.port,
                    'rdns': True
                }
                if proxy_obj.username and proxy_obj.password:
                    proxy_config['username'] = proxy_obj.username
                    proxy_config['password'] = proxy_obj.password
                    
        elif selection.startswith("network_"):
            n_id = int(selection.replace("network_", ""))
            # Dynamic port assignment (Atomic assignment is better here)
            # We assign now to know which port to use for connection
            port = assign_dynamic_port(account, n_id, commit=False)
            network = ProxyNetwork.query.get(n_id)
            if network:
                # Build config from base_url and assigned port
                # Expected base_url: socks5://user:pass@host
                from utils.validators import validate_proxy
                is_valid, res = validate_proxy(f"{network.base_url}:{port}")
                if is_valid:
                    proxy_type = python_socks.ProxyType.SOCKS5 if 'socks5' in res['type'].lower() else python_socks.ProxyType.HTTP
                    proxy_config = {
                        'proxy_type': proxy_type,
                        'addr': res['host'],
                        'port': res['port'],
                        'rdns': True
                    }
                    if res.get('username'):
                        proxy_config['username'] = res['username']
                        proxy_config['password'] = res['password']
    
    if api_credential:
        account.api_credential_id = api_credential.id
        
    db.session.commit()
    
    # Device Params
    device_params = get_device_params(api_credential)
    current_app.logger.info(f"Using Device Params: {device_params}")

    # Init Client with device params
    session = StringSession()
    client = TelegramClient(
        session, 
        api_id_val, 
        api_hash_val, 
        proxy=proxy_config,
        device_model=device_params['device_model'],
        system_version=device_params['system_version'],
        app_version=device_params['app_version'],
        lang_code=device_params['lang_code'],
        system_lang_code=device_params['system_lang_code']
    )
    
    async def _send_code():
        await client.connect()
        if not await client.is_user_authorized():
            return await client.send_code_request(phone)
        return "AUTHORIZED"
        
    try:
        res = run_async(_send_code())
        
        if res == "AUTHORIZED":
            account.session_string = client.session.save()
            account.status = 'active'
            
            # Save Device Profile
            if not account.device_profile:
                dp = DeviceProfile(
                    device_model=device_params['device_model'],
                    system_version=device_params['system_version'],
                    app_version=device_params['app_version'],
                    lang_code=device_params['lang_code'],
                    system_lang_code=device_params['system_lang_code'],
                    client_type=api_credential.client_type if api_credential else 'desktop'
                )
                account.device_profile = dp
                
            db.session.commit()
            flash("Account was already authorized!", "success")
            return redirect(url_for('accounts.list_accounts'))
            
        account.phone_code_hash = res.phone_code_hash
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
    # Retrieve correct API ID/Hash
    api_id = 2040
    api_hash = 'b18441a1bb607e12738205e450b8ad6b'
    
    api_credential = None
    if account.api_credential_id: # load from DB to get type
        api_credential = ApiCredential.query.get(account.api_credential_id)

    if api_credential:
        api_id = api_credential.api_id
        api_hash = api_credential.api_hash
        
    # Re-construct proxy config from account
    proxy_config = None
    if account.proxy_id:
        proxy_obj = Proxy.query.get(account.proxy_id)
        if proxy_obj:
            import python_socks
            proxy_type = python_socks.ProxyType.SOCKS5 if 'socks5' in proxy_obj.type.lower() else python_socks.ProxyType.HTTP
            proxy_config = {
                'proxy_type': proxy_type,
                'addr': proxy_obj.host,
                'port': proxy_obj.port,
                'rdns': True
            }
            if proxy_obj.username and proxy_obj.password:
                proxy_config['username'] = proxy_obj.username
                proxy_config['password'] = proxy_obj.password
    
    # Device Params
    device_params = get_device_params(api_credential)

    client = TelegramClient(
        session, 
        api_id, 
        api_hash, 
        proxy=proxy_config,
        device_model=device_params['device_model'],
        system_version=device_params['system_version'],
        app_version=device_params['app_version'],
        lang_code=device_params['lang_code'],
        system_lang_code=device_params['system_lang_code']
    )
    
    async def _sign_in():
        await client.connect()
        try:
            user = await client.sign_in(
                phone=account.phone,
                code=code,
                phone_code_hash=account.phone_code_hash
            )
            return user
        except SessionPasswordNeededError:
             if password:
                 return await client.sign_in(password=password)
             else:
                 raise ValueError("2FA Required")
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
        
        # 📱 Update or create device profile (PRESERVE existing)
        if account.device_profile:
            # ✅ UPDATE existing device profile instead of deleting
            dp = account.device_profile
            dp.device_model = device_params['device_model']
            dp.system_version = device_params['system_version']
            dp.app_version = device_params['app_version']
            dp.lang_code = device_params['lang_code']
            dp.system_lang_code = device_params['system_lang_code']
            dp.client_type = api_credential.client_type if api_credential else 'desktop'
        else:
            # Create new device profile
            dp = DeviceProfile(
                account_id=account.id,
                device_model=device_params['device_model'],
                system_version=device_params['system_version'],
                app_version=device_params['app_version'],
                lang_code=device_params['lang_code'],
                system_lang_code=device_params['system_lang_code'],
                client_type=api_credential.client_type if api_credential else 'desktop'
            )
            db.session.add(dp)
            account.device_profile = dp
        
        db.session.commit()
        flash("Login successful! Account added.", "success")
        return redirect(url_for('accounts.list_accounts'))
        
    except ValueError as ve:
        if str(ve) == "2FA Required":
             flash("Two-Step Verification Password Required", "warning")
             return render_template('accounts/enter_code.html', account=account, ask_password=True)
        else:
             flash(f"Login failed: {ve}", "error")
             return redirect(url_for('phone_login.enter_code', account_id=account.id))
    except Exception as e:
        flash(f"Login error: {e}", "error")
        return redirect(url_for('phone_login.enter_code', account_id=account.id))
