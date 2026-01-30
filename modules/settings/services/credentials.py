from models.api_credential import ApiCredential
from models.account import Account
from database import db
from utils.encryption import encrypt_api_hash, decrypt_api_hash
from config import Config

class CredentialManager:
    @staticmethod
    def add_credential(data):
        name = data.get("name")
        api_id = data.get("api_id")
        api_hash = data.get("api_hash")
        client_type = data.get("client_type", "custom")
        notes = data.get("notes", "")
        
        if not name or not api_id or not api_hash:
            return False, "Name, API ID, and API Hash are required"
        
        # Check duplicate
        existing = ApiCredential.query.filter_by(api_id=int(api_id)).first()
        if existing:
            return False, f"API ID {api_id} already exists"
        
        encrypted_hash = encrypt_api_hash(api_hash)
        
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
        return True, f"API credential '{name}' added successfully"

    @staticmethod
    def edit_credential(credential_id, data):
        credential = ApiCredential.query.get_or_404(credential_id)
        
        if credential.is_official:
            return False, "Cannot edit official API credentials"
        
        # Manually checking keys because request.form might not contain them if unchecked/empty
        if 'name' in data: credential.name = data['name']
        if 'client_type' in data: credential.client_type = data['client_type']
        if 'notes' in data: credential.notes = data['notes']
        
        new_api_hash = data.get("api_hash")
        if new_api_hash:
            credential.api_hash = encrypt_api_hash(new_api_hash)
        
        db.session.commit()
        return True, f"API credential '{credential.name}' updated successfully"

    @staticmethod
    def delete_credential(credential_id):
        credential = ApiCredential.query.get_or_404(credential_id)
        
        if credential.is_official:
            return False, "Cannot delete official API credentials"
        
        accounts_using = Account.query.filter_by(api_credential_id=credential_id).count()
        if accounts_using > 0:
            return False, f"Cannot delete: {accounts_using} account(s) are using this credential"
        
        name = credential.name
        db.session.delete(credential)
        db.session.commit()
        return True, f"API credential '{name}' deleted successfully"

    @staticmethod
    def set_default(credential_id):
        # Unset all defaults
        ApiCredential.query.update({ApiCredential.is_default: False})
        
        # Set new default
        credential = ApiCredential.query.get_or_404(credential_id)
        credential.is_default = True
        
        db.session.commit()
        return True, f"'{credential.name}' set as default API credential"

    @staticmethod
    def import_from_env():
        api_id = Config.TG_API_ID
        api_hash = Config.TG_API_HASH
        
        if not api_id or not api_hash:
            return False, "TG_API_ID or TG_API_HASH not found in .env file"
        
        existing = ApiCredential.query.filter_by(api_id=int(api_id)).first()
        if existing:
            return False, f"API ID {api_id} already exists in manager"
        
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
        return True, f"Successfully imported API ID {api_id} from .env and set as default"

    @staticmethod
    def get_decrypted_hash(credential_id):
        credential = ApiCredential.query.get_or_404(credential_id)
        if credential.is_official:
            raise ValueError("Cannot decrypt official credentials")
        return decrypt_api_hash(credential.api_hash)
