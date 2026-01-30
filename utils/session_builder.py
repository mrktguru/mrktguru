"""
Session Builder - Create Telethon sessions from TData auth_key
"""
import os
import logging
from typing import Optional
from telethon.sessions import SQLiteSession
from telethon.crypto import AuthKey

logger = logging.getLogger(__name__)


class SessionBuilder:
    """Build Telethon session files from TData metadata"""
    
    # DC ID to server address mapping
    DC_MAP = {
        1: ('149.154.175.53', 443),      # pluto (US)
        2: ('149.154.167.51', 443),      # venus (EU)
        3: ('149.154.175.100', 443),     # aurora (US)
        4: ('149.154.167.91', 443),      # vesta (EU)
        5: ('91.108.56.130', 443),       # flora (Singapore)
    }
    
    @staticmethod
    def get_dc_address(dc_id: int) -> tuple:
        """
        Get server address and port for DC ID
        
        Args:
            dc_id: Data Center ID (1-5)
            
        Returns:
            tuple: (server_address, port)
        """
        return SessionBuilder.DC_MAP.get(dc_id, SessionBuilder.DC_MAP[2])
    
    
    @staticmethod
    def create_from_tdata(account_id: int, auth_key_override: Optional[bytes] = None) -> str:
        """
        Create Telethon session from TData metadata
        
        Args:
            account_id: Account ID
            auth_key_override: Optional manual auth_key (already decrypted bytes)
            
        Returns:
            str: Path to created .session file
        """
        from models.account import Account
        from utils.encryption import decrypt_auth_key
        
        try:
            account = Account.query.get(account_id)
            if not account:
                raise Exception(f"Account {account_id} not found")
            
            if not account.tdata_metadata:
                raise Exception(f"Account {account_id} has no TData metadata")
            
            tdata = account.tdata_metadata
            
            # 1. Determine auth_key (manual override or from TData)
            if auth_key_override:
                auth_key_bytes = auth_key_override
                logger.info(f"Using manual auth_key override for account {account_id}")
            elif tdata.auth_key:
                auth_key_bytes = decrypt_auth_key(tdata.auth_key)
                logger.info(f"Using auth_key from TData for account {account_id}")
            else:
                raise Exception("No auth_key available (neither in TData nor manual override)")
            
            # 2. Get DC info
            dc_id = tdata.dc_id or tdata.main_dc_id
            if not dc_id:
                raise Exception("DC ID not found in TData metadata")
            
            server_address, port = SessionBuilder.get_dc_address(dc_id)
            
            # 3. Create session file path
            session_dir = f"uploads/sessions/{account.phone}"
            os.makedirs(session_dir, exist_ok=True)
            session_path = os.path.join(session_dir, f"{account.phone}.session")
            
            # 4. Create Telethon session
            session = SQLiteSession(session_path)
            
            # 5. Set DC info
            session.set_dc(dc_id, server_address, port)
            
            # 6. Set auth key
            auth_key = AuthKey(data=auth_key_bytes)
            session.auth_key = auth_key
            
            # 7. Save and close session
            session.save()
            session.close()
            
            logger.info(f"✅ Created Telethon session: {session_path}")
            logger.info(f"   DC ID: {dc_id}, Server: {server_address}:{port}")
            
            return session_path
            
        except Exception as e:
            logger.error(f"Failed to create session from TData: {e}")
            raise Exception(f"Session creation failed: {str(e)}")
    
    
    @staticmethod
    def validate_session(session_path: str) -> bool:
        """
        Validate that session file is valid
        
        Args:
            session_path: Path to .session file
            
        Returns:
            bool: True if valid
        """
        try:
            if not os.path.exists(session_path):
                return False
            
            session = SQLiteSession(session_path)
            
            # Check if auth_key exists
            if not session.auth_key:
                session.close()
                return False
            
            # Check if DC is set
            dc_id, server_address, port = session.get_dc()
            if not dc_id:
                session.close()
                return False
            
            session.close()
            return True
            
        except Exception as e:
            logger.error(f"Session validation failed: {e}")
            return False
