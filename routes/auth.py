from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.user import User
from app import db
from datetime import datetime

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler"""
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please provide both username and password', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Account is deactivated', 'error')
                return render_template('login.html')
            
            # Set session
            session['user_id'] = user.id
            session['username'] = user.username
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """Logout handler"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))
