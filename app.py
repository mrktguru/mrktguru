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
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    
    # Import models after app context
    with app.app_context():
        from models.user import User
        
        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))
    
    
    # Serve uploaded files
    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(os.path.join(app.root_path, "uploads"), filename)
    
    # Register blueprints
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
    
    app.register_blueprint(auth_bp)
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
    
    # Logging
    if not app.debug:
        if not os.path.exists("logs"):
            os.mkdir("logs")
        file_handler = logging.FileHandler("logs/app.log")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info("Application started")
    
    return app

# Create app instance for Flask CLI
app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0", 
        port=8080, 
        debug=os.getenv("FLASK_DEBUG", "False").lower() == "true",
        use_reloader=os.getenv("FLASK_DEBUG", "False").lower() == "true"
    )
