import requests
from datetime import datetime


def test_proxy_connection(proxy):
    """
    Test proxy by making request to IP check service
    
    Args:
        proxy: Proxy model instance
    
    Returns:
        dict: {success: bool, ip: str, error: str}
    """
    try:
        proxy_url = f"{proxy.type}://"
        if proxy.username and proxy.password:
            proxy_url += f"{proxy.username}:{proxy.password}@"
        proxy_url += f"{proxy.host}:{proxy.port}"
        
        proxies = {
            'http': proxy_url,
            'https': proxy_url,
        }
        
        response = requests.get(
            'https://api.ipify.org?format=json',
            proxies=proxies,
            timeout=10
        )
        
        if response.status_code == 200:
            ip = response.json().get('ip')
            return {
                'success': True,
                'ip': ip,
                'error': None
            }
        else:
            return {
                'success': False,
                'ip': None,
                'error': f"HTTP {response.status_code}"
            }
            
    except requests.exceptions.ProxyError as e:
        return {
            'success': False,
            'ip': None,
            'error': f"Proxy connection failed: {str(e)}"
        }
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'ip': None,
            'error': "Connection timeout"
        }
    except Exception as e:
        return {
            'success': False,
            'ip': None,
            'error': str(e)
        }


def rotate_mobile_proxy(proxy):
    """
    Rotate mobile proxy IP address
    
    Args:
        proxy: Proxy model instance
    
    Returns:
        dict: {success: bool, new_ip: str, error: str}
    """
    if not proxy.is_mobile or not proxy.rotation_url:
        return {
            'success': False,
            'new_ip': None,
            'error': 'Not a mobile proxy or no rotation URL'
        }
    
    try:
        # Call rotation URL
        response = requests.get(proxy.rotation_url, timeout=15)
        
        if response.status_code != 200:
            return {
                'success': False,
                'new_ip': None,
                'error': f"Rotation failed: HTTP {response.status_code}"
            }
        
        # Wait for IP to change
        import time
        time.sleep(5)
        
        # Get new IP
        test_result = test_proxy_connection(proxy)
        
        if test_result['success']:
            # Update proxy record
            from app import db
            proxy.current_ip = test_result['ip']
            proxy.last_rotation = datetime.utcnow()
            proxy.status = 'active'
            db.session.commit()
            
            return {
                'success': True,
                'new_ip': test_result['ip'],
                'error': None
            }
        else:
            return {
                'success': False,
                'new_ip': None,
                'error': 'Failed to verify new IP'
            }
            
    except Exception as e:
        return {
            'success': False,
            'new_ip': None,
            'error': str(e)
        }


def get_proxy_for_telethon(proxy):
    """
    Convert Proxy model to dict for Telethon
    
    Args:
        proxy: Proxy model instance
    
    Returns:
        dict: Proxy configuration for Telethon
    """
    import socks
    
    proxy_type = socks.SOCKS5 if proxy.type == 'socks5' else socks.HTTP
    
    return {
        'proxy_type': proxy_type,
        'addr': proxy.host,
        'port': proxy.port,
        'username': proxy.username,
        'password': proxy.password,
    }


def extract_country_from_username(username):
    """
    Extract country code directly from username (DataImpulse format)
    Format: user__cr.XX (where XX is country code)
    
    Args:
        username: Proxy username
        
    Returns:
        str: Country code (uppercase) or None
    """
    if not username:
        return None
        
    try:
        # Check for DataImpulse format (__cr.XX)
        if '__cr.' in username:
            parts = username.split('__cr.')
            if len(parts) > 1:
                # Get the country code (first 2 chars after cr.)
                code = parts[1][:2].upper()
                return code
                
        # Fallback: Check for other common patterns if needed
        # e.g., user-country-us
        
        return None
    except Exception:
        return None


def get_country_flag(country_code):
    """
    Get emoji flag for country code
    
    Args:
        country_code: 2-letter country code (ISO 3166-1 alpha-2)
    
    Returns:
        str: Emoji flag or None
    """
    if not country_code or len(country_code) != 2:
        return None
        
    # Convert to regional indicator symbols
    try:
        base = 127397
        first = ord(country_code[0].upper()) + base
        second = ord(country_code[1].upper()) + base
        return chr(first) + chr(second)
    except:
        return None

