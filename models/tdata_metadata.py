from datetime import datetime
from database import db


class TDataMetadata(db.Model):
    """TData metadata storage - all extracted information from Telegram Desktop"""
    __tablename__ = 'tdata_metadata'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), unique=True, nullable=False)
    
    # ==================== AUTH DATA (encrypted) ====================
    auth_key = db.Column(db.LargeBinary)  # 256 bytes, encrypted
    auth_key_id = db.Column(db.BigInteger)
    dc_id = db.Column(db.Integer)
    main_dc_id = db.Column(db.Integer)
    user_id = db.Column(db.BigInteger)
    
    # ==================== ORIGINAL API (critical for matching) ====================
    original_api_id = db.Column(db.Integer)
    original_api_hash = db.Column(db.String(255))  # Encrypted
    
    # ==================== DEVICE FINGERPRINT (exact from TData) ====================
    device_model = db.Column(db.String(100))
    system_version = db.Column(db.String(50))
    app_version = db.Column(db.String(50))
    device_brand = db.Column(db.String(50))
    lang_pack = db.Column(db.String(50))
    system_lang_code = db.Column(db.String(10))
    lang_code = db.Column(db.String(10))
    
    # ==================== NETWORK SETTINGS ====================
    proxy_settings = db.Column(db.JSON)
    connection_type = db.Column(db.String(20))
    mtproto_secret = db.Column(db.String(255))
    
    # ==================== ENCRYPTION ====================
    local_salt = db.Column(db.LargeBinary)
    encryption_key = db.Column(db.LargeBinary)
    
    # ==================== SESSION INFO ====================
    session_count = db.Column(db.Integer)
    last_update_time = db.Column(db.DateTime)
    
    # ==================== RAW METADATA (for debugging) ====================
    raw_metadata = db.Column(db.JSON)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TDataMetadata account_id={self.account_id} dc_id={self.dc_id}>'
