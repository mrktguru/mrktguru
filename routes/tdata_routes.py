"""
TData Upload Routes - Handle TData archive upload and configuration
"""
from flask import request, redirect, url_for, flash, render_template
from utils.decorators import login_required
from models.account import Account
from models.tdata_metadata import TDataMetadata
from models.api_credential import ApiCredential
from models.proxy import Proxy
from database import db
from utils.tdata_parser import TDataParser
from utils.encryption import encrypt_auth_key, encrypt_api_hash, decrypt_api_hash
from werkzeug.utils import secure_filename
import os
import uuid
import json
from datetime import datetime


@login_required
def upload_tdata():
    """Upload TData archive (.zip)"""
    if request.method == 'POST':
        tdata_file = request.files.get('tdata_file')
        
        if not tdata_file or not tdata_file.filename:
            flash("❌ No file selected", "error")
            return redirect(url_for('accounts.list_accounts'))
        
        if not tdata_file.filename.endswith('.zip'):
            flash("❌ Only .zip archives are supported", "error")
            return redirect(url_for('accounts.list_accounts'))
        
        try:
            # 1. Save uploaded file to temp
            temp_dir = f"uploads/temp_tdata/{uuid.uuid4()}"
            os.makedirs(temp_dir, exist_ok=True)
            
            filename = secure_filename(tdata_file.filename)
            zip_path = os.path.join(temp_dir, filename)
            tdata_file.save(zip_path)
            
            # 2. Extract archive
            extract_result = TDataParser.extract_archive(zip_path, temp_dir)
            tdata_path = extract_result['tdata_path']
            
            # 3. Parse TData metadata
            metadata = TDataParser.extract_all_metadata(tdata_path)
            
            # 4. Extract phone number for account creation
            phone = metadata.get('auth_data', {}).get('phone', f"tdata_{uuid.uuid4().hex[:8]}")
            
            # Check for duplicate
            existing = Account.query.filter_by(phone=phone).first()
            if existing:
                flash(f"❌ Account with phone {phone} already exists", "error")
                TDataParser.cleanup_temp(temp_dir)
                return redirect(url_for('accounts.list_accounts'))
            
            # 5. Create Account record (status='tdata_extracted')
            account = Account(
                phone=phone,
                source_type='tdata',
                status='tdata_extracted',  # Not ready yet, needs configuration
                session_file_path='',  # Will be created later
                created_at=datetime.now()
            )
            db.session.add(account)
            db.session.flush()  # Get account ID
            
            # 6. Store TData metadata
            auth_data = metadata.get('auth_data', {})
            device_info = metadata.get('device_info', {})
            network = metadata.get('network', {})
            session_info = metadata.get('session_info', {})
            
            # Encrypt sensitive data
            auth_key_encrypted = None
            if auth_data.get('auth_key'):
                auth_key_encrypted = encrypt_auth_key(auth_data['auth_key'])
            
            original_api_hash_encrypted = None
            if device_info.get('original_api_hash'):
                original_api_hash_encrypted = encrypt_api_hash(device_info['original_api_hash'])
            
            # Prepare raw_metadata for JSON storage (convert bytes to hex)
            def serialize_metadata(data):
                """Convert bytes to hex strings for JSON serialization"""
                if isinstance(data, dict):
                    return {k: serialize_metadata(v) for k, v in data.items()}
                elif isinstance(data, list):
                    return [serialize_metadata(item) for item in data]
                elif isinstance(data, bytes):
                    return data.hex()  # Convert bytes to hex string
                elif isinstance(data, datetime):
                    return data.isoformat()
                else:
                    return data
            
            raw_metadata_serialized = serialize_metadata(metadata)
            
            tdata_meta = TDataMetadata(
                account_id=account.id,
                # Auth data
                auth_key=auth_key_encrypted,
                auth_key_id=str(auth_data.get('auth_key_id')) if auth_data.get('auth_key_id') else None,
                dc_id=auth_data.get('dc_id'),
                main_dc_id=auth_data.get('main_dc_id'),
                user_id=auth_data.get('user_id'),
                # Original API
                original_api_id=device_info.get('original_api_id'),
                original_api_hash=original_api_hash_encrypted,
                # Device fingerprint
                device_model=device_info.get('device_model'),
                system_version=device_info.get('system_version'),
                app_version=device_info.get('app_version'),
                device_brand=device_info.get('device_brand'),
                lang_pack=device_info.get('lang_pack'),
                system_lang_code=device_info.get('system_lang_code'),
                lang_code=device_info.get('lang_code'),
                # Network
                proxy_settings=network.get('proxy_settings'),
                connection_type=network.get('connection_type'),
                mtproto_secret=network.get('mtproto_secret'),
                # Session info
                session_count=session_info.get('session_count'),
                last_update_time=session_info.get('last_update_time'),
                # Raw metadata for debugging (serialized for JSON)
                raw_metadata=raw_metadata_serialized
            )
            db.session.add(tdata_meta)
            
            # 7. Move archive to permanent storage
            final_dir = f"uploads/tdata/{account.id}"
            os.makedirs(final_dir, exist_ok=True)
            final_path = os.path.join(final_dir, filename)
            
            import shutil
            shutil.move(zip_path, final_path)
            account.tdata_archive_path = final_path
            
            # 8. Cleanup temp
            TDataParser.cleanup_temp(temp_dir)
            
            db.session.commit()
            
            flash(f"✅ TData extracted successfully! Phone: {phone}", "success")
            
            # Redirect to configuration page
            return redirect(url_for('accounts.configure_tdata', account_id=account.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error processing TData: {str(e)}", "error")
            if 'temp_dir' in locals():
                TDataParser.cleanup_temp(temp_dir)
            return redirect(url_for('accounts.list_accounts'))
    
    # GET request - show upload form
    return render_template('accounts/upload_tdata.html')


@login_required
def configure_tdata(account_id):
    """Configure TData account before session creation"""
    account = Account.query.get_or_404(account_id)
    
    if account.source_type != 'tdata':
        flash("❌ This account is not from TData", "error")
        return redirect(url_for('accounts.detail', account_id=account_id))
    
    if not account.tdata_metadata:
        flash("❌ TData metadata not found", "error")
        return redirect(url_for('accounts.detail', account_id=account_id))
    
    if request.method == 'POST':
        try:
            # Get form data
            api_credential_id = request.form.get('api_credential_id')
            proxy_id = request.form.get('proxy_id')
            auth_key_manual = request.form.get('auth_key_manual')  # Optional override
            
            # Validate API credential selection
            if not api_credential_id:
                flash("❌ Please select an API credential", "error")
                return redirect(url_for('accounts.configure_tdata', account_id=account_id))
            
            # Update account
            account.api_credential_id = int(api_credential_id)
            if proxy_id:
                account.proxy_id = int(proxy_id)
            
            # Manual auth_key override (if provided)
            if auth_key_manual:
                try:
                    auth_key_bytes = bytes.fromhex(auth_key_manual)
                    account.tdata_metadata.auth_key = encrypt_auth_key(auth_key_bytes)
                except Exception as e:
                    flash(f"⚠️ Invalid auth_key format: {e}", "warning")
            
            # Update status to 'pending' (ready for session creation)
            account.status = 'pending'
            
            db.session.commit()
            
            flash("✅ TData configuration saved! Account ready for session creation.", "success")
            return redirect(url_for('accounts.detail', account_id=account_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error saving configuration: {str(e)}", "error")
    
    # GET request - show configuration form
    tdata = account.tdata_metadata
    api_credentials = ApiCredential.query.order_by(
        ApiCredential.is_default.desc(),
        ApiCredential.is_official.desc()
    ).all()
    proxies = Proxy.query.filter_by(status='active').all()
    
    # Determine recommended API credential
    recommended_api_id = None
    if tdata.original_api_id:
        recommended_api_id = tdata.original_api_id
    
    return render_template(
        'accounts/configure_tdata.html',
        account=account,
        tdata=tdata,
        api_credentials=api_credentials,
        proxies=proxies,
        recommended_api_id=recommended_api_id
    )


@login_required
def add_tdata_api_to_manager(account_id):
    """Add TData's original API to API Manager"""
    account = Account.query.get_or_404(account_id)
    
    if not account.tdata_metadata:
        flash("❌ No TData metadata found", "error")
        return redirect(url_for('accounts.configure_tdata', account_id=account_id))
    
    tdata = account.tdata_metadata
    
    if not tdata.original_api_id or not tdata.original_api_hash:
        flash("❌ Original API credentials not found in TData", "error")
        return redirect(url_for('accounts.configure_tdata', account_id=account_id))
    
    try:
        # Check if already exists
        existing = ApiCredential.query.filter_by(api_id=tdata.original_api_id).first()
        if existing:
            flash(f"⚠️ API ID {tdata.original_api_id} already exists in manager", "warning")
            return redirect(url_for('accounts.configure_tdata', account_id=account_id))
        
        # Decrypt from TData and re-encrypt for ApiCredential
        api_hash_decrypted = decrypt_api_hash(tdata.original_api_hash)
        api_hash_encrypted = encrypt_api_hash(api_hash_decrypted)
        
        # Determine client type
        client_type = 'desktop'
        if tdata.original_api_id == 6:
            client_type = 'ios'
        elif tdata.original_api_id == 4:
            client_type = 'android'
        elif tdata.original_api_id == 2040:
            client_type = 'desktop'
        
        # Create credential
        credential = ApiCredential(
            name=f"From TData ({account.phone})",
            api_id=tdata.original_api_id,
            api_hash=api_hash_encrypted,
            client_type=client_type,
            is_official=False,
            is_default=False,
            notes=f"Extracted from TData archive on {datetime.now().strftime('%Y-%m-%d')}"
        )
        
        db.session.add(credential)
        db.session.commit()
        
        flash(f"✅ API ID {tdata.original_api_id} added to API Manager!", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error adding API to manager: {str(e)}", "error")
    
    return redirect(url_for('accounts.configure_tdata', account_id=account_id))
