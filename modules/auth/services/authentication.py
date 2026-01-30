from models.user import User
from database import db
from datetime import datetime

class AuthService:
    @staticmethod
    def authenticate(username, password):
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            return None, "Invalid username or password"
        
        if not user.is_active:
            return None, "Account is deactivated"
            
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        return user, "Welcome back!"
