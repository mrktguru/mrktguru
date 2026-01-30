import random


# Device profiles database
# Device profiles database
# STRICTLY iOS ONLY (High Trust Score logic)
# "Telegram easier verifies iOS due to limited models and predictable behavior"
DEVICE_PROFILES = {
    'RU': [
        ('iPhone 15 Pro Max', 'iOS 17.2', '10.0.0'),
        ('iPhone 15 Pro', 'iOS 17.2', '10.0.0'),
        ('iPhone 14 Pro Max', 'iOS 17.2', '10.0.0'),
        ('iPhone 14 Pro', 'iOS 17.2', '10.0.0'),
        ('iPhone 13 Pro Max', 'iOS 17.2', '10.0.0'),
        ('iPhone 13 Pro', 'iOS 17.2', '10.0.0'),
    ],
    
    'US': [
        ('iPhone 15 Pro Max', 'iOS 17.2', '10.0.0'),
        ('iPhone 15 Pro', 'iOS 17.2', '10.0.0'),
        ('iPhone 14 Pro Max', 'iOS 17.2', '10.0.0'),
    ],
    
    'EU': [
        ('iPhone 15 Pro Max', 'iOS 17.2', '10.0.0'),
        ('iPhone 15 Pro', 'iOS 17.2', '10.0.0'),
        ('iPhone 14 Pro Max', 'iOS 17.2', '10.0.0'),
    ]
}


def generate_device_profile(region='RU'):
    """
    Generate realistic iOS device profile
    
    Args:
        region: Region code (RU, US, EU)
    
    Returns:
        dict: {device_model, system_version, app_version, lang_code, system_lang_code, client_type}
    """
    if region not in DEVICE_PROFILES:
        region = 'RU'
    
    device_model, system_version, app_version = random.choice(DEVICE_PROFILES[region])
    
    # Language codes by region
    lang_codes = {
        'RU': ('ru', 'ru-RU'),
        'US': ('en', 'en-US'),
        'EU': ('en', 'en-GB'),
    }
    
    lang_code, system_lang_code = lang_codes.get(region, ('en', 'en-US'))
    
    # ALWAYS iOS
    client_type = 'ios'
    
    return {
        'device_model': device_model,
        'system_version': system_version,
        'app_version': app_version,
        'lang_code': lang_code,
        'system_lang_code': system_lang_code,
        'client_type': client_type
    }


# Warmup channel functions removed
