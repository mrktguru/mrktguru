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
    def convert_to_session_string(tdata_path: str, proxy_tuple: tuple = None) -> str:
        """
        Convert TData folder to Telethon StringSession using opentele native conversion.
        This runs the async conversion in a synchronous wrapper.
        
        Args:
            tdata_path: Path to extracted tdata folder
            proxy_tuple: Optional proxy tuple ('socks5', 'host', port, True, 'user', 'pass')
            
        Returns:
            str: The session string
        """
        import asyncio
        from telethon.sessions import StringSession
        from opentele.td import TDesktop
        
        # Define async conversion logic
        async def _convert():
            logger.info(f"Native converting TData from: {tdata_path}")
            if proxy_tuple:
                logger.info(f"🔒 TData conversion WILL USE PROXY: {proxy_tuple[1]}:{proxy_tuple[2]}")
            else:
                logger.warning("⚠️ TData conversion WITHOUT PROXY - SERVER IP WILL BE EXPOSED!")
                
            tdesk = TDesktop(tdata_path)
            
            # Check if loaded
            if not tdesk.isLoaded():
                raise Exception("Failed to load TData (encrypted or invalid)")
                
            # Convert to Telethon client with StringSession
            # CRITICAL: Pass proxy to prevent IP leak during conversion!
            client = await tdesk.ToTelethon(
                session=StringSession(),
                proxy=proxy_tuple  # ← CRITICAL: Proxy for TData conversion
            )
            
            # Save and return string
            return client.session.save()
            
        # Run async in sync wrapper
        # Run async in separate thread to guarantee loop isolation
        # This prevents 502 errors if main thread has a loop that gets closed or corrupted
        import threading
        result_container = {}

        def thread_target():
            try:
                logger.info("Conversion thread started")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                session = loop.run_until_complete(_convert())
                loop.close()
                if not session:
                    result_container['error'] = Exception("Generated session string is empty")
                else:
                    result_container['result'] = session
                logger.info("Conversion thread finished successfully")
            except BaseException as thread_e:
                # Catch EVERYTHING including GeneratorExit, etc.
                logger.error(f"Conversion thread crashed: {thread_e}")
                result_container['error'] = thread_e

        t = threading.Thread(target=thread_target)
        t.start()
        t.join()

        if 'error' in result_container:
            e = result_container['error']
            # Check for unauthorized error specifically
            error_str = str(e)
            if "TDesktopUnauthorized" in error_str:
                logger.warning(f"TData unauthorized: {e}")
                raise Exception("This TData session is invalid or logged out (Unauthorized)")
            
            logger.error(f"Native TData conversion failed: {e}")
            raise Exception(f"Native conversion failed: {str(e)}")
            
        result = result_container.get('result')
        if not result:
             raise Exception("Thread finished but returned no result (Unknown error)")
        return result
    
    
    @staticmethod
    def parse_json_metadata(json_path: str) -> Dict:
        """
        Parse JSON metadata file (often included with TData)
        
        Args:
            json_path: Path to JSON file
            
        Returns:
            dict: Standardized metadata structure
        """
        import json
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"📄 Parsing JSON metadata from: {json_path}")
            
            # Standardize field names (different sellers use different formats)
            metadata = {
                'auth_data': {},
                'device_info': {},
                'network': {},
                'session_info': {},
                'raw_json': data
            }
            
            # Extract device info (flexible field name matching)
            device_info = metadata['device_info']
            
            # API credentials
            device_info['original_api_id'] = (
                data.get('app_id') or 
                data.get('api_id') or 
                data.get('appId')
            )
            
            device_info['original_api_hash'] = (
                data.get('app_hash') or 
                data.get('api_hash') or 
                data.get('appHash')
            )
            
            # Device model
            device_info['device_model'] = (
                data.get('device') or 
                data.get('device_model') or 
                data.get('deviceModel')
            )
            
            # System version
            device_info['system_version'] = (
                data.get('sdk') or 
                data.get('system_version') or 
                data.get('systemVersion')
            )
            
            # App version
            device_info['app_version'] = (
                data.get('app_version') or 
                data.get('appVersion') or 
                data.get('version')
            )
            
            # Language codes
            device_info['lang_code'] = (
                data.get('lang_code') or 
                data.get('langCode') or 
                'en'
            )
            
            device_info['system_lang_code'] = (
                data.get('system_lang_code') or 
                data.get('systemLangCode') or 
                'en-US'
            )
            
            device_info['lang_pack'] = (
                data.get('system_lang_pack') or 
                data.get('lang_pack') or 
                data.get('langPack') or 
                'tdesktop'
            )
            
            # Auth data
            auth_data = metadata['auth_data']
            auth_data['phone'] = data.get('phone')
            auth_data['user_id'] = data.get('id')
            
            # Session info
            session_info = metadata['session_info']
            session_info['register_time'] = data.get('register_time')
            session_info['last_check_time'] = data.get('last_check_time')
            session_info['is_premium'] = data.get('is_premium', False)
            session_info['has_profile_pic'] = data.get('has_profile_pic', False)
            session_info['spamblock'] = data.get('spamblock')
            
            # Network
            metadata['network'] = {
                'proxy': data.get('proxy'),
                'ipv6': data.get('ipv6', False)
            }
            
            logger.info(f"✅ JSON parsed successfully")
            logger.info(f"   Device: {device_info.get('device_model', 'Unknown')}")
            logger.info(f"   App: {device_info.get('app_version', 'Unknown')}")
            logger.info(f"   API ID: {device_info.get('original_api_id', 'Unknown')}")
            
            return metadata
            
        except FileNotFoundError:
            raise Exception(f"JSON file not found: {json_path}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to parse JSON metadata: {e}")
            raise Exception(f"JSON parsing failed: {str(e)}")
    
    
    @staticmethod
    def compare_sources(tdata_meta: Dict, json_meta: Dict) -> Dict:
        """
        Compare TData and JSON metadata sources
        
        Args:
            tdata_meta: Metadata from TData parsing
            json_meta: Metadata from JSON parsing
            
        Returns:
            dict: Comparison results with recommendations
        """
        comparison = {
            'tdata': {},
            'json': {},
            'differences': [],
            'recommended_source': None
        }
        
        # Extract device info from both sources
        tdata_device = tdata_meta.get('device_info', {})
        json_device = json_meta.get('device_info', {})
        
        # Compare key fields
        fields_to_compare = [
            'original_api_id',
            'device_model',
            'system_version',
            'app_version',
            'lang_code',
            'system_lang_code'
        ]
        
        for field in fields_to_compare:
            tdata_val = tdata_device.get(field)
            json_val = json_device.get(field)
            
            comparison['tdata'][field] = tdata_val
            comparison['json'][field] = json_val
            
            if tdata_val != json_val:
                comparison['differences'].append({
                    'field': field,
                    'tdata': tdata_val,
                    'json': json_val
                })
        
        # Recommendation logic
        # Prefer JSON if it has more complete data
        json_completeness = sum(1 for f in fields_to_compare if json_device.get(f))
        tdata_completeness = sum(1 for f in fields_to_compare if tdata_device.get(f))
        
        if json_completeness > tdata_completeness:
            comparison['recommended_source'] = 'json'
            comparison['reason'] = f"JSON has more complete data ({json_completeness}/{len(fields_to_compare)} vs {tdata_completeness}/{len(fields_to_compare)})"
        elif tdata_completeness > json_completeness:
            comparison['recommended_source'] = 'tdata'
            comparison['reason'] = f"TData has more complete data ({tdata_completeness}/{len(fields_to_compare)} vs {json_completeness}/{len(fields_to_compare)})"
        else:
            # If equal, prefer JSON (typically more accurate for device fingerprinting)
            comparison['recommended_source'] = 'json'
            comparison['reason'] = "Both sources complete, JSON preferred for accuracy"
        
        return comparison
    
    
    @staticmethod
    def merge_metadata(tdata_meta: Dict, json_meta: Optional[Dict], source_preference: str = 'json') -> Dict:
        """
        Merge TData and JSON metadata, preferring specified source
        
        Args:
            tdata_meta: Metadata from TData
            json_meta: Metadata from JSON (optional)
            source_preference: 'tdata' or 'json'
            
        Returns:
            dict: Merged metadata with source tracking
        """
        if not json_meta:
            # No JSON, use TData only
            merged = tdata_meta.copy()
            merged['_source'] = 'tdata'
            return merged
        
        # Start with TData as base
        merged = tdata_meta.copy()
        
        # Override device info based on preference
        if source_preference == 'json':
            # Use JSON device parameters
            json_device = json_meta.get('device_info', {})
            merged_device = merged.get('device_info', {})
            
            # Override key fields from JSON
            override_fields = [
                'device_model',
                'system_version',
                'app_version',
                'lang_code',
                'system_lang_code',
                'lang_pack'
            ]
            
            for field in override_fields:
                if json_device.get(field):
                    merged_device[field] = json_device[field]
            
            merged['device_info'] = merged_device
            merged['_source'] = 'json'
            merged['_json_data'] = json_meta.get('raw_json', {})
        else:
            # Keep TData device parameters
            merged['_source'] = 'tdata'
            if json_meta:
                merged['_json_data'] = json_meta.get('raw_json', {})
        
        return merged
