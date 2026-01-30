from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils.decorators import login_required
from models.api_credential import ApiCredential
from modules.settings.services.credentials import CredentialManager

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
    success, msg = CredentialManager.add_credential(request.form)
    if success:
        flash(f"✅ {msg}", "success")
    else:
        flash(f"Error: {msg}", "error")
    return redirect(url_for("api_credentials.list_credentials"))


@api_credentials_bp.route("/settings/api-credentials/<int:credential_id>/edit", methods=["POST"])
@login_required
def edit_credential(credential_id):
    """Edit existing API credential"""
    success, msg = CredentialManager.edit_credential(credential_id, request.form)
    if success:
        flash(f"✅ {msg}", "success")
    else:
        flash(f"Error: {msg}", "error")
    return redirect(url_for("api_credentials.list_credentials"))


@api_credentials_bp.route("/settings/api-credentials/<int:credential_id>/delete", methods=["POST"])
@login_required
def delete_credential(credential_id):
    """Delete API credential"""
    success, msg = CredentialManager.delete_credential(credential_id)
    if success:
        flash(f"✅ {msg}", "success")
    else:
        flash(f"Error: {msg}", "error")
    return redirect(url_for("api_credentials.list_credentials"))


@api_credentials_bp.route("/settings/api-credentials/<int:credential_id>/set-default", methods=["POST"])
@login_required
def set_default(credential_id):
    """Set API credential as default"""
    success, msg = CredentialManager.set_default(credential_id)
    if success:
        flash(f"✅ {msg}", "success")
    else:
        flash(f"Error: {msg}", "error")
    return redirect(url_for("api_credentials.list_credentials"))


@api_credentials_bp.route("/api/credentials/<int:credential_id>/decrypt-hash")
@login_required
def decrypt_hash(credential_id):
    """API endpoint to decrypt API hash (for editing)"""
    try:
        decrypted = CredentialManager.get_decrypted_hash(credential_id)
        return jsonify({"api_hash": decrypted})
    except ValueError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_credentials_bp.route("/settings/api-credentials/import-from-env", methods=["POST"])
@login_required
def import_from_env():
    """Import API credentials from .env file"""
    success, msg = CredentialManager.import_from_env()
    if success:
        flash(f"✅ {msg}", "success")
    else:
        flash(f"❌ Error: {msg}", "error")
    return redirect(url_for("api_credentials.list_credentials"))
