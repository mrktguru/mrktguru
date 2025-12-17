#!/usr/bin/env python3
"""Create default admin user"""

from app import create_app, db
from models.user import User

def create_admin():
    """Create default admin user"""
    app = create_app()
    
    with app.app_context():
        # Check if admin exists
        admin = User.query.filter_by(username='admin').first()
        
        if admin:
            print("Admin user already exists")
            return
        
        # Create admin
        admin = User(
            username='admin',
            email='admin@example.com'
        )
        admin.set_password('admin123')
        
        db.session.add(admin)
        db.session.commit()
        
        print("Admin user created successfully")
        print("Username: admin")
        print("Password: admin123")
        print("\nPlease change the password after first login!")

if __name__ == '__main__':
    create_admin()
