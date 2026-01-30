from models.proxy import Proxy
from models.account import Account
from database import db
from utils.validators import validate_proxy
from utils.proxy_helper import test_proxy_connection, rotate_mobile_proxy, extract_country_from_username
from modules.proxies.exceptions import (
    ProxyValidationError,
    ProxyNotFoundError,
    BulkImportError
)
from sqlalchemy import or_

class ProxyManagementService:
    @staticmethod
    def list_proxies():
        """List all proxies ordered by creation date"""
        return Proxy.query.order_by(Proxy.created_at.desc()).all()

    @staticmethod
    def get_proxy(proxy_id: int) -> Proxy:
        """Get proxy by ID or raise error"""
        proxy = Proxy.query.get(proxy_id)
        if not proxy:
            raise ProxyNotFoundError(f"Proxy {proxy_id} not found")
        return proxy

    @staticmethod
    def create_proxy(data: dict) -> Proxy:
        """
        Create a new proxy.
        Data keys: proxy_string, is_mobile, rotation_url, rotation_interval, notes
        """
        proxy_string = data.get('proxy_string')
        if not proxy_string:
            raise ProxyValidationError("Proxy string is required")

        # Validate
        is_valid, result = validate_proxy(proxy_string)
        if not is_valid:
            raise ProxyValidationError(result)

        # Extract country
        country = extract_country_from_username(result.get('username'))

        proxy = Proxy(
            type=result['type'],
            host=result['host'],
            port=result['port'],
            username=result['username'],
            password=result['password'],
            is_mobile=data.get('is_mobile', False),
            rotation_url=data.get('rotation_url') if data.get('is_mobile') else None,
            rotation_interval=int(data.get('rotation_interval', 1200)) if data.get('is_mobile') else None,
            country=country,
            notes=data.get('notes')
        )

        db.session.add(proxy)
        db.session.commit()

        # Initial Test
        ProxyManagementService.test_proxy(proxy.id)
        
        return proxy

    @staticmethod
    def update_proxy(proxy_id: int, data: dict) -> Proxy:
        """Update proxy settings"""
        proxy = ProxyManagementService.get_proxy(proxy_id)
        
        proxy_string = data.get('proxy_string')
        if proxy_string:
            is_valid, result = validate_proxy(proxy_string)
            if not is_valid:
                raise ProxyValidationError(result)
            
            proxy.type = result['type']
            proxy.host = result['host']
            proxy.port = result['port']
            proxy.username = result['username']
            proxy.password = result['password']
            proxy.country = extract_country_from_username(result.get('username'))
            
            # Reset status and IP
            proxy.status = 'active'
            proxy.current_ip = None

        if data.get('is_mobile') is not None:
             # Logic from controller checks: if proxy.is_mobile: proxy.rotation...
             # We assume caller passes correct data.
             # Controller had: if proxy.is_mobile: update rotation params.
             # We will update if provided.
             pass

        if proxy.is_mobile:
            if 'rotation_url' in data:
                proxy.rotation_url = data['rotation_url']
            if 'rotation_interval' in data:
                proxy.rotation_interval = int(data.get('rotation_interval', 1200))
        
        if 'notes' in data:
            proxy.notes = data['notes']
            
        db.session.commit()
        
        # Re-test if credentials changed
        if proxy_string:
            ProxyManagementService.test_proxy(proxy.id)
            
        return proxy

    @staticmethod
    def delete_proxy(proxy_id: int):
        """Delete proxy if not in use"""
        proxy = ProxyManagementService.get_proxy(proxy_id)
        
        if proxy.accounts.count() > 0:
            raise ProxyValidationError("Cannot delete proxy: it is assigned to accounts")
            
        db.session.delete(proxy)
        db.session.commit()
        return True

    @staticmethod
    def bulk_import(proxy_list_text: str) -> dict:
        """
        Bulk import proxies.
        Returns dict with success_count and error_count.
        """
        if not proxy_list_text:
            raise BulkImportError("No proxies provided")
            
        lines = proxy_list_text.split('\n')
        success_count = 0
        error_count = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            is_valid, result = validate_proxy(line)
            if not is_valid:
                error_count += 1
                continue
                
            # Check duplicate
            existing = Proxy.query.filter_by(
                host=result['host'],
                port=result['port']
            ).first()
            
            if existing:
                continue
                
            country = extract_country_from_username(result.get('username'))
            
            proxy = Proxy(
                type=result['type'],
                host=result['host'],
                port=result['port'],
                username=result['username'],
                password=result['password'],
                country=country,
                status='active' # Default active? Controller didn't set it in bulk
            )
            
            db.session.add(proxy)
            success_count += 1
            
        db.session.commit()
        
        return {
            'success': success_count,
            'errors': error_count
        }

    @staticmethod
    def test_proxy(proxy_id: int) -> dict:
        """Test proxy connection and update status"""
        proxy = ProxyManagementService.get_proxy(proxy_id)
        
        try:
            result = test_proxy_connection(proxy)
            
            if result['success']:
                proxy.current_ip = result['ip']
                proxy.status = 'active'
                db.session.commit()
                return {'success': True, 'ip': result['ip']}
            else:
                proxy.status = 'error'
                db.session.commit()
                return {'success': False, 'error': result['error']}
                
        except Exception as e:
            proxy.status = 'error'
            db.session.commit()
            return {'success': False, 'error': str(e)}

    @staticmethod
    def rotate_proxy(proxy_id: int) -> dict:
        """Rotate mobile proxy"""
        proxy = ProxyManagementService.get_proxy(proxy_id)
        
        if not proxy.is_mobile:
            return {'success': False, 'error': 'Not a mobile proxy'}
            
        result = rotate_mobile_proxy(proxy)
        return result
