import random


# Device profiles database
DEVICE_PROFILES = {
    'RU': [
        # iPhone models
        ('iPhone 14 Pro', 'iOS 17.1', '10.2.1'),
        ('iPhone 13 Pro', 'iOS 16.6', '10.1.3'),
        ('iPhone 13', 'iOS 16.5', '10.1.2'),
        ('iPhone 12 Pro Max', 'iOS 16.3', '10.0.5'),
        ('iPhone 12', 'iOS 16.2', '10.0.4'),
        ('iPhone 11 Pro', 'iOS 15.7', '9.8.2'),
        ('iPhone 11', 'iOS 15.6', '9.8.1'),
        ('iPhone XS Max', 'iOS 15.5', '9.7.5'),
        ('iPhone XR', 'iOS 15.4', '9.7.4'),
        
        # Samsung models
        ('Samsung Galaxy S23 Ultra', 'Android 14', '10.2.2'),
        ('Samsung Galaxy S22 Ultra', 'Android 13', '10.1.4'),
        ('Samsung Galaxy S22', 'Android 13', '10.1.3'),
        ('Samsung Galaxy S21 FE', 'Android 13', '10.0.6'),
        ('Samsung Galaxy S21', 'Android 12', '10.0.5'),
        ('Samsung Galaxy S20 Ultra', 'Android 12', '9.9.3'),
        ('Samsung Galaxy Note 20', 'Android 12', '9.9.2'),
        ('Samsung Galaxy A53', 'Android 13', '10.1.1'),
        ('Samsung Galaxy A52', 'Android 12', '10.0.3'),
        
        # Xiaomi models
        ('Xiaomi 13 Pro', 'Android 14', '10.2.3'),
        ('Xiaomi 12 Pro', 'Android 13', '10.1.5'),
        ('Xiaomi 12', 'Android 13', '10.1.4'),
        ('Xiaomi Mi 11', 'Android 12', '10.0.7'),
        ('Xiaomi Mi 10T Pro', 'Android 12', '10.0.6'),
        ('Redmi Note 12 Pro', 'Android 13', '10.1.2'),
        ('Redmi Note 11 Pro', 'Android 12', '10.0.4'),
        ('POCO F4', 'Android 13', '10.1.3'),
        
        # Huawei models
        ('Huawei P40 Pro', 'Android 12', '10.0.5'),
        ('Huawei Mate 40 Pro', 'Android 12', '10.0.6'),
        ('Honor 50', 'Android 11', '9.9.5'),
        
        # OnePlus models
        ('OnePlus 11', 'Android 14', '10.2.1'),
        ('OnePlus 10 Pro', 'Android 13', '10.1.4'),
        ('OnePlus 9 Pro', 'Android 12', '10.0.5'),
        ('OnePlus 8T', 'Android 12', '10.0.4'),
    ],
    
    'US': [
        ('iPhone 14 Pro Max', 'iOS 17.2', '10.2.2'),
        ('iPhone 14 Pro', 'iOS 17.1', '10.2.1'),
        ('iPhone 13 Pro', 'iOS 16.6', '10.1.3'),
        ('Samsung Galaxy S23 Ultra', 'Android 14', '10.2.2'),
        ('Samsung Galaxy S22 Ultra', 'Android 13', '10.1.4'),
        ('Google Pixel 8 Pro', 'Android 14', '10.2.3'),
        ('Google Pixel 7 Pro', 'Android 14', '10.2.1'),
        ('OnePlus 11', 'Android 14', '10.2.1'),
    ],
    
    'EU': [
        ('iPhone 14 Pro', 'iOS 17.1', '10.2.1'),
        ('Samsung Galaxy S23', 'Android 14', '10.2.2'),
        ('Google Pixel 8', 'Android 14', '10.2.3'),
        ('OnePlus 10 Pro', 'Android 13', '10.1.4'),
        ('Xiaomi 13', 'Android 14', '10.2.3'),
    ]
}


def generate_device_profile(region='RU'):
    """
    Generate realistic device profile
    
    Args:
        region: Region code (RU, US, EU)
    
    Returns:
        dict: {device_model, system_version, app_version, lang_code, system_lang_code}
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
    
    # Determine client type
    client_type = 'android'
    if 'iPhone' in device_model or 'iPad' in device_model:
        client_type = 'ios'
    
    return {
        'device_model': device_model,
        'system_version': system_version,
        'app_version': app_version,
        'lang_code': lang_code,
        'system_lang_code': system_lang_code,
        'client_type': client_type
    }


def get_warmup_channels(category='general'):
    """
    Get list of channels for warm-up subscriptions
    
    Args:
        category: Channel category (general/tech/news/crypto/etc)
    
    Returns:
        list: List of channel usernames
    """
    warmup_channels = {
        'general': [
            'durov',
            'telegram',
            'ru2ch',
            'varlamov',
            'rian_ru',
            'rbc_news',
            'lentachold',
            'breakingmash',
            'meduzalive',
            'tass_agency',
            'interfaxonline',
        ],
        'tech': [
            'techcrunch',
            'tproger',
            'wylsa',
            'appleinsider_ru',
            'tgblog',
            'tginfo',
        ],
        'crypto': [
            'forklog',
            'bitnovosti',
            'cryptorussia',
            'incrypted',
        ],
        'news': [
            'rian_ru',
            'rbc_news',
            'tass_agency',
            'interfaxonline',
            'kommersant',
        ],
        'business': [
            'rbc_news',
            'forbesrussia',
            'vedomosti',
            'kommersant',
        ]
    }
    
    return warmup_channels.get(category, warmup_channels['general'])


def get_random_warmup_channels(count=15, categories=None):
    """
    Get random mix of warm-up channels
    
    Args:
        count: Number of channels to return
        categories: List of categories to mix (None = all)
    
    Returns:
        list: Random list of channel usernames
    """
    if categories is None:
        categories = ['general', 'tech', 'news', 'business']
    
    all_channels = []
    for category in categories:
        all_channels.extend(get_warmup_channels(category))
    
    # Remove duplicates
    all_channels = list(set(all_channels))
    
    # Return random sample
    return random.sample(all_channels, min(count, len(all_channels)))
