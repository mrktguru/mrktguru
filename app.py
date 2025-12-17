import os
import logging
from flask import Flask, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()

def create_app(config_name=None):
    """Application factory pattern"""
    
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Setup logging
    setup_logging(app)
    
    # Create upload directories
    create_directories(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Context processors
    @app.context_processor
    def inject_user():
        """Inject current user into templates"""
        from models.user import User
        if 'user_id' in session:
            user = User.query.get(session['user_id'])
            return {'current_user': user}
        return {'current_user': None}
    
    return app


def setup_logging(app):
    """Configure application logging"""
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    logging.basicConfig(
        level=getattr(logging, app.config['LOG_LEVEL']),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(app.config['LOG_FILE']),
            logging.StreamHandler()
        ]
    )
    
    app.logger.info('Application started')


def create_directories(app):
    """Create necessary directories"""
    directories = [
        app.config['SESSIONS_FOLDER'],
        app.config['MEDIA_FOLDER'],
        app.config['CSV_FOLDER'],
        app.config['REPORTS_FOLDER'],
        app.config['EXPORTS_FOLDER'],
        'logs',
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            app.logger.info(f'Created directory: {directory}')


def register_blueprints(app):
    """Register all blueprints"""
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.accounts import accounts_bp
    from routes.proxies import proxies_bp
    from routes.channels import channels_bp
    from routes.campaigns import campaigns_bp
    from routes.dm_campaigns import dm_campaigns_bp
    from routes.parser import parser_bp
    from routes.analytics import analytics_bp
    from routes.automation import automation_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(accounts_bp, url_prefix='/accounts')
    app.register_blueprint(proxies_bp, url_prefix='/proxies')
    app.register_blueprint(channels_bp, url_prefix='/channels')
    app.register_blueprint(campaigns_bp, url_prefix='/campaigns')
    app.register_blueprint(dm_campaigns_bp, url_prefix='/dm-campaigns')
    app.register_blueprint(parser_bp, url_prefix='/parser')
    app.register_blueprint(analytics_bp, url_prefix='/analytics')
    app.register_blueprint(automation_bp, url_prefix='/automation')


def register_error_handlers(app):
    """Register error handlers"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000)
