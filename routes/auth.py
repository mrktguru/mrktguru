from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from modules.auth.services.authentication import AuthService

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
        
        user, msg = AuthService.authenticate(username, password)
        
        if user:
            # Set session
            session['user_id'] = user.id
            session['username'] = user.username
            
            flash(f'{msg} {user.username}!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash(msg, 'error')
    
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """Logout handler"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))
