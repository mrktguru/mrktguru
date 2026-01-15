import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://postgres:password@127.0.0.1:5432/telegram_system')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Celery
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = 'UTC'
    CELERY_ENABLE_UTC = True
    
    # Telegram API
    TG_API_ID = os.getenv('TG_API_ID')
    TG_API_HASH = os.getenv('TG_API_HASH')
    
    # Upload settings
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 52428800))  # 50MB
    ALLOWED_EXTENSIONS = {
        'session': ['.session'],
        'document': ['.csv', '.xls', '.xlsx'],
        'image': ['.jpg', '.jpeg', '.png', '.gif'],
        'video': ['.mp4', '.avi', '.mov'],
        'audio': ['.mp3', '.wav', '.ogg'],
    }
    
    # Session
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Security
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/app.log')
    
    # Application paths
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SESSIONS_FOLDER = os.path.join(BASE_DIR, 'uploads', 'sessions')
    MEDIA_FOLDER = os.path.join(BASE_DIR, 'uploads', 'media')
    CSV_FOLDER = os.path.join(BASE_DIR, 'uploads', 'csv')
    REPORTS_FOLDER = os.path.join(BASE_DIR, 'outputs', 'reports')
    EXPORTS_FOLDER = os.path.join(BASE_DIR, 'outputs', 'exports')
    
    # Anti-ban settings (defaults)
    DEFAULT_INVITE_DELAY_MIN = 45
    DEFAULT_INVITE_DELAY_MAX = 90
    DEFAULT_INVITES_PER_HOUR_MIN = 5
    DEFAULT_INVITES_PER_HOUR_MAX = 10
    DEFAULT_DM_DELAY_MIN = 60
    DEFAULT_DM_DELAY_MAX = 180
    DEFAULT_MESSAGES_PER_ACCOUNT_LIMIT = 5
    DEFAULT_WORKING_HOURS_START = '09:00'
    DEFAULT_WORKING_HOURS_END = '22:00'
    
    # Account warm-up settings
    WARMUP_DAYS = 7
    WARMUP_SUBSCRIPTIONS_MIN = 10
    WARMUP_SUBSCRIPTIONS_MAX = 20
    WARMUP_ACTIVITY_DELAY_MIN = 3600  # 1 hour
    WARMUP_ACTIVITY_DELAY_MAX = 7200  # 2 hours


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:password@localhost:5432/telegram_system_test'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
