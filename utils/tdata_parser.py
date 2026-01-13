"""
TData Parser - Extract metadata from Telegram Desktop tdata folders
Uses opentele library for parsing
"""
import os
import zipfile
import shutil
from typing import Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TDataParser:
    """Parser for Telegram Desktop tdata folders"""
    
    @staticmethod
    def extract_archive(zip_path: str, extract_to: str) -> Dict[str, str]:
        """
        Extract TData archive (.zip) to temporary folder
        
        Args:
            zip_path: Path to .zip file
            extract_to: Destination folder
            
        Returns:
            dict: {
                'tdata_path': path to extracted tdata folder,
                'files': list of extracted files
            }
        """
        try:
            os.makedirs(extract_to, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            
            # Find tdata folder (might be nested)
            tdata_path = None
            for root, dirs, files in os.walk(extract_to):
                if 'tdata' in dirs:
                    tdata_path = os.path.join(root, 'tdata')
                    break
                # Sometimes the extracted folder itself is tdata
                if os.path.basename(root) == 'tdata':
                    tdata_path = root
                    break
            
            if not tdata_path:
                # Maybe the extract_to itself contains tdata files
                tdata_path = extract_to
            
            extracted_files = []
            for root, dirs, files in os.walk(tdata_path):
                extracted_files.extend(files)
            
            return {
                'tdata_path': tdata_path,
                'files': extracted_files,
                'extract_dir': extract_to
            }
            
        except Exception as e:
            logger.error(f"Failed to extract TData archive: {e}")
            raise Exception(f"Archive extraction failed: {str(e)}")
    
    
    @staticmethod
    def extract_all_metadata(tdata_path: str, passcode: Optional[str] = None) -> Dict:
        """
        Extract all metadata from TData folder using opentele
        
        Args:
            tdata_path: Path to tdata folder
            passcode: Optional local passcode for encrypted tdata
            
        Returns:
            dict: Complete metadata including auth_key, device info, etc.
        """
        try:
            from opentele.td import TDesktop
            from opentele.api import API
            
            # Load TData
            logger.info(f"Loading TData from: {tdata_path}")
            tdesk = TDesktop(tdata_path)
            
            # Check if passcode is needed
            if tdesk.isLoaded() == False:
                if passcode:
                    # Try to unlock with passcode
                    # Note: opentele handles this internally
                    pass
                else:
                    raise Exception("TData is encrypted but no passcode provided")
            
            # Extract auth data
            auth_data = {}
            if hasattr(tdesk, 'mainAccount') and tdesk.mainAccount:
                account = tdesk.mainAccount
                
                # Auth key and DC info
                if hasattr(account, 'authKey'):
                    auth_data['auth_key'] = account.authKey.key  # bytes
                    auth_data['auth_key_id'] = int.from_bytes(
                        account.authKey.key[-8:], 
                        byteorder='little', 
                        signed=False
                    )
                
                if hasattr(account, 'mainDcId'):
                    auth_data['main_dc_id'] = account.mainDcId
                    auth_data['dc_id'] = account.mainDcId
                
                # User info
                if hasattr(account, 'userId'):
                    auth_data['user_id'] = account.userId
                
                # Phone (might not always be available)
                if hasattr(account, 'phone'):
                    auth_data['phone'] = account.phone
            
            # Extract device info
            device_info = {}
            if hasattr(tdesk, 'mainAccount') and tdesk.mainAccount:
                account = tdesk.mainAccount
                
                # Try to get API info (this tells us original client type)
                if hasattr(account, 'api'):
                    api = account.api
                    if hasattr(api, 'api_id'):
                        device_info['original_api_id'] = api.api_id
                    if hasattr(api, 'api_hash'):
                        device_info['original_api_hash'] = api.api_hash
                    if hasattr(api, 'device_model'):
                        device_info['device_model'] = api.device_model
                    if hasattr(api, 'system_version'):
                        device_info['system_version'] = api.system_version
                    if hasattr(api, 'app_version'):
                        device_info['app_version'] = api.app_version
                    if hasattr(api, 'lang_code'):
                        device_info['lang_code'] = api.lang_code
                    if hasattr(api, 'system_lang_code'):
                        device_info['system_lang_code'] = api.system_lang_code
            
            # Network settings
            network = {}
            # Proxy info (if available)
            # Note: opentele might not expose this directly
            
            # Session info
            session_info = {
                'last_update_time': datetime.now(),
                'session_count': 1  # TData typically has one main session
            }
            
            # Combine all metadata
            metadata = {
                'auth_data': auth_data,
                'device_info': device_info,
                'network': network,
                'session_info': session_info,
                'extraction_time': datetime.now().isoformat(),
                'tdata_path': tdata_path
            }
            
            logger.info(f"Successfully extracted TData metadata")
            logger.info(f"  - User ID: {auth_data.get('user_id', 'N/A')}")
            logger.info(f"  - DC ID: {auth_data.get('dc_id', 'N/A')}")
            logger.info(f"  - Device: {device_info.get('device_model', 'N/A')}")
            
            return metadata
            
        except ImportError:
            raise Exception("opentele library not installed. Run: pip install opentele")
        except Exception as e:
            logger.error(f"Failed to extract TData metadata: {e}")
            raise Exception(f"TData parsing failed: {str(e)}")
    
    
    @staticmethod
    def cleanup_temp(extract_dir: str):
        """
        Clean up temporary extraction directory
        
        Args:
            extract_dir: Directory to remove
        """
        try:
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
                logger.info(f"Cleaned up temp directory: {extract_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {e}")
