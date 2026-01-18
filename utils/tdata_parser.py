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
                
                # Write debug to file
                try:
                    with open('/tmp/tdata_debug.txt', 'w') as f:
                        f.write(f"=== TDATA DEBUG ===\n")
                        f.write(f"Account type: {type(account)}\n")
                        f.write(f"Account attributes:\n")
                        for attr in dir(account):
                            if not attr.startswith('_'):
                                try:
                                    value = getattr(account, attr)
                                    f.write(f"  {attr}: {type(value)} = {value}\n")
                                except:
                                    f.write(f"  {attr}: <error reading>\n")
                except Exception as e:
                    logger.error(f"Failed to write debug file: {e}")
                
                print(f"[TDATA DEBUG] Main account found!")
                print(f"[TDATA DEBUG] Account attributes: {dir(account)}")
                print(f"[TDATA DEBUG] Account type: {type(account)}")
                
                # Auth key and DC info
                if hasattr(account, 'authKey') and account.authKey:
                    auth_data['auth_key'] = account.authKey.key  # bytes
                    auth_data['auth_key_id'] = int.from_bytes(
                        account.authKey.key[-8:], 
                        byteorder='little', 
                        signed=False
                    )
                    print(f"[TDATA DEBUG] Auth key extracted: {len(account.authKey.key)} bytes")
                
                # Try multiple ways to get DC ID (opentele uses CamelCase!)
                dc_id = None
                print(f"[TDATA DEBUG] Checking for DC ID...")
                print(f"[TDATA DEBUG] Has MainDcId: {hasattr(account, 'MainDcId')}")
                print(f"[TDATA DEBUG] Has mainDcId: {hasattr(account, 'mainDcId')}")
                print(f"[TDATA DEBUG] Has dcId: {hasattr(account, 'dcId')}")
                
                if hasattr(account, 'MainDcId'):  # opentele uses CamelCase!
                    dc_id = int(account.MainDcId)  # Convert DcId enum to int
                    print(f"[TDATA DEBUG] DC ID from MainDcId: {dc_id}")
                elif hasattr(account, 'mainDcId'):
                    dc_id = account.mainDcId
                    print(f"[TDATA DEBUG] DC ID from mainDcId: {dc_id}")
                elif hasattr(account, 'dcId'):
                    dc_id = account.dcId
                    print(f"[TDATA DEBUG] DC ID from dcId: {dc_id}")
                
                if dc_id:
                    auth_data['main_dc_id'] = dc_id
                    auth_data['dc_id'] = dc_id
                else:
                    print(f"[TDATA DEBUG] DC ID not found in account")
                    logger.warning("DC ID not found in account")
                
                # Try multiple ways to get User ID (opentele uses CamelCase!)
                user_id = None
                print(f"[TDATA DEBUG] Checking for User ID...")
                print(f"[TDATA DEBUG] Has UserId: {hasattr(account, 'UserId')}")
                print(f"[TDATA DEBUG] Has userId: {hasattr(account, 'userId')}")
                print(f"[TDATA DEBUG] Has id: {hasattr(account, 'id')}")
                
                if hasattr(account, 'UserId'):  # opentele uses CamelCase!
                    user_id = account.UserId
                    print(f"[TDATA DEBUG] User ID from UserId: {user_id}")
                elif hasattr(account, 'userId'):
                    user_id = account.userId
                    print(f"[TDATA DEBUG] User ID from userId: {user_id}")
                elif hasattr(account, 'id'):
                    user_id = account.id
                    print(f"[TDATA DEBUG] User ID from id: {user_id}")
                
                if user_id:
                    auth_data['user_id'] = user_id
                else:
                    print(f"[TDATA DEBUG] User ID not found in account")
                    logger.warning("User ID not found in account")
                
                # Phone (might not always be available)
                if hasattr(account, 'phone'):
                    auth_data['phone'] = account.phone
                    logger.info(f"Phone: {account.phone}")
                elif hasattr(account, 'phoneNumber'):
                    auth_data['phone'] = account.phoneNumber
                    logger.info(f"Phone from phoneNumber: {account.phoneNumber}")
            else:
                logger.warning("mainAccount not found in TDesktop object")
            
            # Extract device info
            device_info = {}
            if hasattr(tdesk, 'mainAccount') and tdesk.mainAccount:
                account = tdesk.mainAccount
                
                # Try to get API info (this tells us original client type)
                if hasattr(account, 'api') and account.api:
                    api = account.api
                    logger.info(f"API object found. Attributes: {dir(api)}")
                    
                    # API ID
                    if hasattr(api, 'api_id'):
                        device_info['original_api_id'] = api.api_id
                    elif hasattr(api, 'apiId'):
                        device_info['original_api_id'] = api.apiId
                    
                    # API Hash - CRITICAL for adding to manager!
                    if hasattr(api, 'api_hash'):
                        device_info['original_api_hash'] = api.api_hash
                        print(f"[TDATA DEBUG] API Hash extracted: {api.api_hash[:20]}...")
                    elif hasattr(api, 'apiHash'):
                        device_info['original_api_hash'] = api.apiHash
                        print(f"[TDATA DEBUG] API Hash extracted: {api.apiHash[:20]}...")
                    
                    # Device info
                    if hasattr(api, 'device_model'):
                        device_info['device_model'] = api.device_model
                    elif hasattr(api, 'deviceModel'):
                        device_info['device_model'] = api.deviceModel
                    
                    if hasattr(api, 'system_version'):
                        device_info['system_version'] = api.system_version
                    elif hasattr(api, 'systemVersion'):
                        device_info['system_version'] = api.systemVersion
                    
                    if hasattr(api, 'app_version'):
                        device_info['app_version'] = api.app_version
                    elif hasattr(api, 'appVersion'):
                        device_info['app_version'] = api.appVersion
                    
                    if hasattr(api, 'lang_code'):
                        device_info['lang_code'] = api.lang_code
                    elif hasattr(api, 'langCode'):
                        device_info['lang_code'] = api.langCode
                    
                    if hasattr(api, 'system_lang_code'):
                        device_info['system_lang_code'] = api.system_lang_code
                    elif hasattr(api, 'systemLangCode'):
                        device_info['system_lang_code'] = api.systemLangCode
                else:
                    logger.warning("API object not found in account")

            
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
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {e}")

    @staticmethod
    def convert_to_session_string(tdata_path: str) -> str:
        """
        Convert TData folder to Telethon StringSession using opentele native conversion.
        This runs the async conversion in a synchronous wrapper.
        
        Args:
            tdata_path: Path to extracted tdata folder
            
        Returns:
            str: The session string
        """
        import asyncio
        from telethon.sessions import StringSession
        from opentele.td import TDesktop
        
        # Define async conversion logic
        async def _convert():
            logger.info(f"Native converting TData from: {tdata_path}")
            tdesk = TDesktop(tdata_path)
            
            # Check if loaded
            if not tdesk.isLoaded():
                raise Exception("Failed to load TData (encrypted or invalid)")
                
            # Convert to Telethon client with StringSession
            # Note: We don't specify API ID/Hash to let opentele use defaults (Official Desktop)
            # or it uses what's in TData.
            client = await tdesk.ToTelethon(session=StringSession())
            
            # Save and return string
            return client.session.save()
            
        # Run async in sync wrapper
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            session_string = loop.run_until_complete(_convert())
            loop.close()
            return session_string
        except Exception as e:
            logger.error(f"Native TData conversion failed: {e}")
            raise Exception(f"Native conversion failed: {str(e)}")
