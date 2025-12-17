import re
from werkzeug.utils import secure_filename


def validate_phone(phone):
    """Validate phone number format"""
    # Remove spaces, dashes, etc
    phone = re.sub(r'[^\d+]', '', phone)
    
    # Should start with + and have 10-15 digits
    if re.match(r'^\+\d{10,15}$', phone):
        return True, phone
    
    return False, "Invalid phone format. Use international format: +1234567890"


def validate_username(username):
    """Validate Telegram username"""
    # Remove @ if present
    username = username.lstrip('@')
    
    # Telegram username: 5-32 chars, alphanumeric + underscore
    if re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
        return True, username
    
    return False, "Invalid username. Must be 5-32 characters, alphanumeric and underscores only"


def validate_proxy(proxy_string):
    """
    Validate and parse proxy string
    Format: type://username:password@host:port or type://host:port
    
    Returns:
        (bool, dict or str): (success, proxy_dict or error_message)
    """
    try:
        # Parse proxy string
        pattern = r'^(socks5|http)://(([^:]+):([^@]+)@)?([^:]+):(\d+)$'
        match = re.match(pattern, proxy_string.strip())
        
        if not match:
            return False, "Invalid proxy format. Use: type://host:port or type://user:pass@host:port"
        
        proxy_type = match.group(1)
        username = match.group(3) if match.group(3) else None
        password = match.group(4) if match.group(4) else None
        host = match.group(5)
        port = int(match.group(6))
        
        if port < 1 or port > 65535:
            return False, "Invalid port number"
        
        return True, {
            'type': proxy_type,
            'host': host,
            'port': port,
            'username': username,
            'password': password,
        }
        
    except Exception as e:
        return False, f"Error parsing proxy: {str(e)}"


def allowed_file(filename, category='document'):
    """Check if file extension is allowed"""
    from config import Config
    
    if '.' not in filename:
        return False
    
    ext = '.' + filename.rsplit('.', 1)[1].lower()
    
    allowed_extensions = Config.ALLOWED_EXTENSIONS.get(category, [])
    return ext in allowed_extensions


def validate_time_range(start_time, end_time):
    """Validate working hours time range"""
    from datetime import time
    
    try:
        if isinstance(start_time, str):
            h, m = map(int, start_time.split(':'))
            start_time = time(h, m)
        
        if isinstance(end_time, str):
            h, m = map(int, end_time.split(':'))
            end_time = time(h, m)
        
        if start_time >= end_time:
            return False, "Start time must be before end time"
        
        return True, (start_time, end_time)
        
    except Exception as e:
        return False, f"Invalid time format: {str(e)}"


def validate_delay_range(min_delay, max_delay):
    """Validate delay range"""
    try:
        min_delay = int(min_delay)
        max_delay = int(max_delay)
        
        if min_delay < 1:
            return False, "Minimum delay must be at least 1 second"
        
        if max_delay <= min_delay:
            return False, "Maximum delay must be greater than minimum delay"
        
        if max_delay > 3600:
            return False, "Maximum delay cannot exceed 1 hour"
        
        return True, (min_delay, max_delay)
        
    except ValueError:
        return False, "Delays must be integers"


def sanitize_filename(filename):
    """Sanitize filename for safe storage"""
    return secure_filename(filename)


def validate_csv_headers(headers, required_headers):
    """Validate CSV file has required headers"""
    headers = [h.strip().lower() for h in headers]
    required = [h.lower() for h in required_headers]
    
    missing = [h for h in required if h not in headers]
    
    if missing:
        return False, f"Missing required columns: {', '.join(missing)}"
    
    return True, None


def is_working_hours(campaign):
    """Check if current time is within campaign working hours"""
    from datetime import datetime
    
    now = datetime.now().time()
    
    start = campaign.working_hours_start
    end = campaign.working_hours_end
    
    if start <= end:
        return start <= now <= end
    else:
        # Handle overnight range (e.g., 22:00 - 02:00)
        return now >= start or now <= end
