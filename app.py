# 🔥 Monkey Patching for Gevent (Must be first)
# This fixes "maximum recursion depth exceeded" in requests when running with gevent/telethon
try:
    from gevent import monkey
    monkey.patch_all()
except ImportError:
    pass

import sys
# Increase recursion limit for Gevent + Telethon operations in Flask
sys.setrecursionlimit(10000)

from flask import Flask, render_template, redirect, url_for, send_from_directory
from database import db, login_manager
import logging
import os

def create_app():
    app = Flask(__name__)
    
    # Load config
    app.config.from_object("config.Config")
    
    # Initialize extensions with app
    db.init_app(app)
    
    # Configure Logging
    log_file = app.config.get('LOG_FILE', 'logs/app.log')
    log_level = app.config.get('LOG_LEVEL', 'INFO')
    
    # Ensure logs directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Setup standard logging to file
    # Setup standard logging to file
    if not app.debug:
        # Configure root logger to catch all logs (app and modules)
        logging.basicConfig(
            filename=log_file,
            level=getattr(logging, log_level),
            format='%(asctime)s %(levelname)s: %(message)s'
        )
        
        # Remove default handlers if any to prevent stdout duplication if desired
        app.logger.handlers = []
        
    app.logger.info("🚀 Application startup")
    
    # Configure SQLite for better concurrency - run immediately on startup
    with app.app_context():
        if 'sqlite' in app.config.get('SQLALCHEMY_DATABASE_URI', ''):
            from sqlalchemy import event, text
            
            # Force WAL mode on the database file immediately
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("PRAGMA journal_mode=WAL"))
                    conn.execute(text("PRAGMA synchronous=NORMAL"))
                    conn.execute(text("PRAGMA busy_timeout=30000"))
                    result = conn.execute(text("PRAGMA journal_mode")).fetchone()
                    app.logger.info(f"SQLite journal mode: {result[0] if result else 'unknown'}")
                    conn.commit()
            except Exception as e:
                app.logger.error(f"Failed to set WAL mode: {e}")
            
            # Also set for all future connections
            @event.listens_for(db.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.close()
    
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    
    # Import models after app context
    with app.app_context():
        from models.user import User
        # Import other models to ensure relationships are registered
        from models.account_session import AccountSession
        
        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))
    
    
    # Serve uploaded files
    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(os.path.join(app.root_path, "uploads"), filename)
    
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.accounts import accounts_bp
    from routes.proxies import proxies_bp
    from routes.logs import logs_bp
    from routes.channels import channels_bp
    from routes.campaigns import campaigns_bp
    from routes.dm_campaigns import dm_campaigns_bp
    from routes.parser import parser_bp
    from routes.analytics import analytics_bp
    from routes.automation import automation_bp
    from routes.api_credentials import api_credentials_bp
    from routes.scheduler_routes import scheduler_bp
    from routes.phone_login_routes import phone_login_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(phone_login_bp)
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(accounts_bp, url_prefix="/accounts")
    app.register_blueprint(proxies_bp, url_prefix="/proxies")
    app.register_blueprint(logs_bp)
    app.register_blueprint(channels_bp, url_prefix="/channels")
    app.register_blueprint(campaigns_bp, url_prefix="/campaigns")
    app.register_blueprint(dm_campaigns_bp, url_prefix="/dm-campaigns")
    app.register_blueprint(parser_bp, url_prefix="/parser")
    app.register_blueprint(analytics_bp, url_prefix="/analytics")
    app.register_blueprint(automation_bp, url_prefix="/automation")
    app.register_blueprint(api_credentials_bp)
    app.register_blueprint(scheduler_bp)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404
    
    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403
    
    # Root redirect - go to login if not authenticated, else dashboard
    @app.route("/")
    def index():
        from flask import session
        if "user_id" in session:
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("auth.login"))
    
    # Final app startup log
    app.logger.info("Application instance created")
    
    return app

# Create app instance for Flask CLI
app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0", 
        port=int(os.getenv('PORT', 8081)), 
        debug=os.getenv("FLASK_DEBUG", "False").lower() == "true",
        use_reloader=os.getenv("FLASK_DEBUG", "False").lower() == "true"
    )
