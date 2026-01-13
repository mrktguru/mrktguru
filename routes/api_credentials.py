from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils.decorators import login_required
from models.api_credential import ApiCredential
from database import db
from utils.encryption import encrypt_api_hash, decrypt_api_hash

api_credentials_bp = Blueprint("api_credentials", __name__)


@api_credentials_bp.route("/settings/api-credentials")
@login_required
def list_credentials():
    """List all API credentials"""
    credentials = ApiCredential.query.order_by(
        ApiCredential.is_default.desc(),
        ApiCredential.is_official.desc(),
        ApiCredential.created_at.desc()
    ).all()
    
    return render_template("settings/api_credentials.html", credentials=credentials)


@api_credentials_bp.route("/settings/api-credentials/add", methods=["POST"])
@login_required
def add_credential():
    """Add new API credential"""
    try:
        name = request.form.get("name")
        api_id = request.form.get("api_id")
        api_hash = request.form.get("api_hash")
        client_type = request.form.get("client_type", "custom")
        notes = request.form.get("notes", "")
        
        # Validation
        if not name or not api_id or not api_hash:
            flash("Name, API ID, and API Hash are required", "error")
            return redirect(url_for("api_credentials.list_credentials"))
        
        # Check for duplicate API ID
        existing = ApiCredential.query.filter_by(api_id=int(api_id)).first()
        if existing:
            flash(f"API ID {api_id} already exists", "error")
            return redirect(url_for("api_credentials.list_credentials"))
        
        # Encrypt API hash
        encrypted_hash = encrypt_api_hash(api_hash)
        
        # Create credential
        credential = ApiCredential(
            name=name,
            api_id=int(api_id),
            api_hash=encrypted_hash,
            client_type=client_type,
            is_official=False,
            is_default=False,
            notes=notes
        )
        
        db.session.add(credential)
        db.session.commit()
        
        flash(f"✅ API credential '{name}' added successfully", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding credential: {str(e)}", "error")
    
    return redirect(url_for("api_credentials.list_credentials"))


@api_credentials_bp.route("/settings/api-credentials/<int:credential_id>/edit", methods=["POST"])
@login_required
def edit_credential(credential_id):
    """Edit existing API credential"""
    try:
        credential = ApiCredential.query.get_or_404(credential_id)
        
        # Don't allow editing official credentials
        if credential.is_official:
            flash("Cannot edit official API credentials", "error")
            return redirect(url_for("api_credentials.list_credentials"))
        
        credential.name = request.form.get("name", credential.name)
        credential.client_type = request.form.get("client_type", credential.client_type)
        credential.notes = request.form.get("notes", credential.notes)
        
        # Update API hash if provided
        new_api_hash = request.form.get("api_hash")
        if new_api_hash:
            credential.api_hash = encrypt_api_hash(new_api_hash)
        
        db.session.commit()
        
        flash(f"✅ API credential '{credential.name}' updated successfully", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating credential: {str(e)}", "error")
    
    return redirect(url_for("api_credentials.list_credentials"))


@api_credentials_bp.route("/settings/api-credentials/<int:credential_id>/delete", methods=["POST"])
@login_required
def delete_credential(credential_id):
    """Delete API credential"""
    try:
        credential = ApiCredential.query.get_or_404(credential_id)
        
        # Don't allow deleting official credentials
        if credential.is_official:
            flash("Cannot delete official API credentials", "error")
            return redirect(url_for("api_credentials.list_credentials"))
        
        # Check if in use
        from models.account import Account
        accounts_using = Account.query.filter_by(api_credential_id=credential_id).count()
        
        if accounts_using > 0:
            flash(f"Cannot delete: {accounts_using} account(s) are using this credential", "error")
            return redirect(url_for("api_credentials.list_credentials"))
        
        name = credential.name
        db.session.delete(credential)
        db.session.commit()
        
        flash(f"✅ API credential '{name}' deleted successfully", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting credential: {str(e)}", "error")
    
    return redirect(url_for("api_credentials.list_credentials"))


@api_credentials_bp.route("/settings/api-credentials/<int:credential_id>/set-default", methods=["POST"])
@login_required
def set_default(credential_id):
    """Set API credential as default"""
    try:
        # Unset all defaults
        ApiCredential.query.update({ApiCredential.is_default: False})
        
        # Set new default
        credential = ApiCredential.query.get_or_404(credential_id)
        credential.is_default = True
        
        db.session.commit()
        
        flash(f"✅ '{credential.name}' set as default API credential", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error setting default: {str(e)}", "error")
    
    return redirect(url_for("api_credentials.list_credentials"))


@api_credentials_bp.route("/api/credentials/<int:credential_id>/decrypt-hash")
@login_required
def decrypt_hash(credential_id):
    """API endpoint to decrypt API hash (for editing)"""
    try:
        credential = ApiCredential.query.get_or_404(credential_id)
        
        # Don't decrypt official credentials
        if credential.is_official:
            return jsonify({"error": "Cannot decrypt official credentials"}), 403
        
        decrypted = decrypt_api_hash(credential.api_hash)
        
        return jsonify({"api_hash": decrypted})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_credentials_bp.route("/settings/api-credentials/import-from-env", methods=["POST"])
@login_required
def import_from_env():
    """Import API credentials from .env file"""
    try:
        from config import Config
        
        api_id = Config.TG_API_ID
        api_hash = Config.TG_API_HASH
        
        if not api_id or not api_hash:
            flash("⚠️ TG_API_ID or TG_API_HASH not found in .env file", "error")
            return redirect(url_for("api_credentials.list_credentials"))
        
        # Check if already exists
        existing = ApiCredential.query.filter_by(api_id=int(api_id)).first()
        if existing:
            flash(f"⚠️ API ID {api_id} already exists in manager", "warning")
            return redirect(url_for("api_credentials.list_credentials"))
        
        # Encrypt and create
        encrypted_hash = encrypt_api_hash(api_hash)
        
        credential = ApiCredential(
            name=f"Personal API (from .env)",
            api_id=int(api_id),
            api_hash=encrypted_hash,
            client_type="custom",
            is_official=False,
            is_default=True,  # Set as default since it's user's personal API
            notes="Imported from .env configuration"
        )
        
        db.session.add(credential)
        db.session.commit()
        
        flash(f"✅ Successfully imported API ID {api_id} from .env and set as default", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error importing from .env: {str(e)}", "error")
    
    return redirect(url_for("api_credentials.list_credentials"))
