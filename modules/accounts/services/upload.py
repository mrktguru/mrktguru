"""
Upload Service - Session file handling and validation

Handles session file upload, validation, quarantine, and account creation.
"""
import os
import shutil
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from werkzeug.utils import secure_filename

from database import db
from models.account import Account, DeviceProfile
from models.proxy import Proxy
from utils.device_emulator import generate_device_profile
from utils.session_validator import SessionValidator
from utils.activity_logger import ActivityLogger


@dataclass
class UploadResult:
    """Result of batch upload operation"""
    uploaded: int = 0
    skipped: int = 0
    quarantined: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


@dataclass
class SingleUploadResult:
    """Result of single file upload"""
    success: bool
    account_id: Optional[int] = None
    error: Optional[str] = None
    quarantined: bool = False
    skipped: bool = False


class UploadService:
    """Service for session file upload operations"""
    
    TEMP_DIR = "uploads/temp_sessions"
    QUARANTINE_DIR = "uploads/quarantine"
    SESSIONS_DIR = "uploads/sessions"
    
    @staticmethod
    def _ensure_dirs():
        """Ensure required directories exist"""
        os.makedirs(UploadService.TEMP_DIR, exist_ok=True)
        os.makedirs(UploadService.QUARANTINE_DIR, exist_ok=True)
        os.makedirs(UploadService.SESSIONS_DIR, exist_ok=True)
    
    @staticmethod
    def _get_proxy_id(
        proxy_mode: str, 
        specific_proxy_id: Optional[str],
        available_proxies: List[Proxy],
        proxy_index: int
    ) -> tuple[Optional[int], int]:
        """
        Determine proxy assignment based on mode.
        
        Returns:
            Tuple of (proxy_id, updated_proxy_index)
        """
        import random
        
        if proxy_mode == "specific" and specific_proxy_id:
            return int(specific_proxy_id), proxy_index
        elif proxy_mode == "round_robin" and available_proxies:
            proxy_id = available_proxies[proxy_index % len(available_proxies)].id
            return proxy_id, proxy_index + 1
        elif proxy_mode == "random" and available_proxies:
            return random.choice(available_proxies).id, proxy_index
        return None, proxy_index
    
    @staticmethod
    def upload_single_file(
        file,
        region: str = "US",
        proxy_mode: str = "none",
        specific_proxy_id: Optional[str] = None,
        available_proxies: Optional[List[Proxy]] = None,
        proxy_index: int = 0,
        source: str = "",
        tags: str = ""
    ) -> tuple[SingleUploadResult, int]:
        """
        Process single session file upload.
        
        Args:
            file: Werkzeug FileStorage object
            region: Region for device profile
            proxy_mode: Proxy assignment mode (none/specific/round_robin/random)
            specific_proxy_id: Specific proxy ID if mode is 'specific'
            available_proxies: List of available proxies
            proxy_index: Current index for round-robin
            source: Source tag for account
            tags: Tags for account
            
        Returns:
            Tuple of (SingleUploadResult, updated_proxy_index)
        """
        if not file or not file.filename:
            return SingleUploadResult(success=False, error="Empty file"), proxy_index
        
        if not file.filename.endswith(".session"):
            return SingleUploadResult(success=False, error="Not a .session file"), proxy_index
        
        UploadService._ensure_dirs()
        validator = SessionValidator()
        temp_path = None
        
        try:
            filename = secure_filename(file.filename)
            phone = filename.replace(".session", "")
            
            # Check for duplicate
            existing = Account.query.filter_by(phone=phone).first()
            if existing:
                return SingleUploadResult(success=False, skipped=True, error="Account already exists"), proxy_index
            
            # Save to temp
            temp_path = os.path.join(UploadService.TEMP_DIR, filename)
            file.save(temp_path)
            
            # Validate file
            validation = validator.validate_session_file(temp_path)
            if not validation['valid']:
                os.remove(temp_path)
                error_msg = validation.get('error', 'Unknown error')
                return SingleUploadResult(success=False, error=f"Invalid session - {error_msg}"), proxy_index
            
            # Extract metadata
            metadata = validator.extract_metadata(temp_path)
            
            # Check for suspicious session
            if metadata.get('suspicious', False):
                quarantine_path = os.path.join(UploadService.QUARANTINE_DIR, filename)
                shutil.move(temp_path, quarantine_path)
                reasons = ', '.join(metadata.get('suspicious_reasons', []))
                return SingleUploadResult(
                    success=False, 
                    quarantined=True, 
                    error=f"Suspicious session ({reasons})"
                ), proxy_index
            
            # Create account folder
            account_dir = os.path.join(UploadService.SESSIONS_DIR, phone)
            os.makedirs(account_dir, exist_ok=True)
            
            final_path = os.path.join(account_dir, f"{phone}.session")
            shutil.move(temp_path, final_path)
            temp_path = None
            
            # Save metadata.json
            metadata_path = os.path.join(account_dir, "metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump({
                    "uploaded_at": datetime.now().isoformat(),
                    "original_filename": file.filename,
                    "file_size": validation['size'],
                    "format": validation['format'],
                    "validation": validation,
                    "metadata": metadata,
                    "region": region
                }, f, indent=2)
            
            # Determine proxy
            if available_proxies is None:
                available_proxies = Proxy.query.filter_by(status='active').all()
            
            assigned_proxy_id, proxy_index = UploadService._get_proxy_id(
                proxy_mode, specific_proxy_id, available_proxies, proxy_index
            )
            
            # Create account
            account = Account(
                phone=phone,
                session_file_path=final_path,
                status="pending",
                health_score=100,
                proxy_id=assigned_proxy_id,
                created_at=datetime.now(),
                session_metadata=metadata,
                source=source,
                tags=tags
            )
            db.session.add(account)
            db.session.flush()
            
            # Create device profile
            device = generate_device_profile(region=region)
            device_profile = DeviceProfile(
                account_id=account.id,
                device_model=device["device_model"],
                system_version=device["system_version"],
                app_version=device["app_version"],
                lang_code=device["lang_code"],
                system_lang_code=device["system_lang_code"],
                client_type=device.get("client_type", "desktop")
            )
            db.session.add(device_profile)
            
            # Log upload
            logger = ActivityLogger(account.id)
            logger.log(
                action_type='upload_session',
                status='success',
                description='Session file uploaded and validated',
                details=f"File: {filename}, Size: {validation['size']} bytes",
                category='system'
            )
            
            # Clean session file
            try:
                cleaned = validator.clean_session_file(final_path, device)
                if cleaned:
                    logger.log(
                        action_type='clean_session',
                        status='success',
                        description='Session file signatures cleaned',
                        details=f"Device: {device['device_model']}",
                        category='system'
                    )
            except Exception as clean_err:
                pass  # Non-critical error
            
            # Log proxy assignment
            if assigned_proxy_id:
                proxy = Proxy.query.get(assigned_proxy_id)
                if proxy:
                    logger.log(
                        action_type='assign_proxy',
                        status='success',
                        description=f"Proxy auto-assigned: {proxy.host}:{proxy.port}",
                        proxy_used=f"{proxy.host}:{proxy.port}",
                        category='system'
                    )
            
            return SingleUploadResult(success=True, account_id=account.id), proxy_index
            
        except Exception as e:
            # Cleanup temp file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            return SingleUploadResult(success=False, error=str(e)), proxy_index
    
    @staticmethod
    def upload_batch(
        files,
        region: str = "US",
        proxy_mode: str = "none",
        specific_proxy_id: Optional[str] = None,
        source: str = "",
        tags: str = ""
    ) -> UploadResult:
        """
        Process batch of session files.
        
        Args:
            files: List of Werkzeug FileStorage objects
            region: Region for device profiles
            proxy_mode: Proxy assignment mode
            specific_proxy_id: Specific proxy ID if mode is 'specific'
            source: Source tag for accounts
            tags: Tags for accounts
            
        Returns:
            UploadResult with counts and errors
        """
        available_proxies = Proxy.query.filter_by(status='active').all()
        proxy_index = 0
        
        result = UploadResult()
        
        for file in files:
            single_result, proxy_index = UploadService.upload_single_file(
                file=file,
                region=region,
                proxy_mode=proxy_mode,
                specific_proxy_id=specific_proxy_id,
                available_proxies=available_proxies,
                proxy_index=proxy_index,
                source=source,
                tags=tags
            )
            
            if single_result.success:
                result.uploaded += 1
            elif single_result.skipped:
                result.skipped += 1
                result.errors.append(f"{file.filename}: {single_result.error}")
            elif single_result.quarantined:
                result.quarantined += 1
                result.errors.append(f"{file.filename}: {single_result.error}")
            else:
                result.errors.append(f"{file.filename}: {single_result.error}")
        
        db.session.commit()
        return result
