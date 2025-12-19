from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.decorators import login_required
from models.channel import Channel
from models.account import Account
from database import db

channels_bp = Blueprint('channels', __name__)


@channels_bp.route('/')
@login_required
def list_channels():
    """List all channels"""
    channels = Channel.query.order_by(Channel.created_at.desc()).all()
    return render_template('channels/list.html', channels=channels)


@channels_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add new channel"""
    if request.method == 'POST':
        username = request.form.get('username', '').lstrip('@')
        account_id = request.form.get('account_id')
        
        if not username or not account_id:
            flash('Username and account are required', 'error')
            return redirect(url_for('channels.add'))
        
        # Check if already exists
        existing = Channel.query.filter_by(username=username).first()
        if existing:
            flash('Channel already exists', 'warning')
            return redirect(url_for('channels.detail', channel_id=existing.id))
        
        # Get channel info via Telethon
        import asyncio
        from utils.telethon_helper import get_channel_info
        
        result = asyncio.run(get_channel_info(int(account_id), username))
        
        if result['success']:
            channel_data = result['channel']
            channel = Channel(
                type=channel_data['type'],
                username=username,
                chat_id=channel_data['id'],
                title=channel_data['title'],
                is_admin=channel_data['is_admin'],
                admin_rights=channel_data['admin_rights'],
                owner_account_id=int(account_id)
            )
            db.session.add(channel)
            db.session.commit()
            
            flash(f'Channel {channel.title} added successfully', 'success')
            return redirect(url_for('channels.detail', channel_id=channel.id))
        else:
            flash(f'Failed to fetch channel info: {result["error"]}', 'error')
    
    accounts = Account.query.filter_by(status='active').all()
    return render_template('channels/add.html', accounts=accounts)


@channels_bp.route('/<int:channel_id>')
@login_required
def detail(channel_id):
    """Channel details"""
    channel = Channel.query.get_or_404(channel_id)
    return render_template('channels/detail.html', channel=channel)


@channels_bp.route('/<int:channel_id>/delete', methods=['POST'])
@login_required
def delete(channel_id):
    """Delete channel"""
    channel = Channel.query.get_or_404(channel_id)
    db.session.delete(channel)
    db.session.commit()
    flash('Channel deleted', 'success')
    return redirect(url_for('channels.list_channels'))

# Stub routes for future features
@channels_bp.route("/<int:channel_id>/posts")
@login_required
def posts(channel_id):
    """Channel posts (stub)"""
    channel = Channel.query.get_or_404(channel_id)
    flash("Posts feature coming soon", "info")
    return redirect(url_for("channels.detail", channel_id=channel_id))

@channels_bp.route("/<int:channel_id>/create-post", methods=["GET", "POST"])
@login_required
def create_post(channel_id):
    """Create post (stub)"""
    channel = Channel.query.get_or_404(channel_id)
    flash("Create post feature coming soon", "info")
    return redirect(url_for("channels.detail", channel_id=channel_id))

@channels_bp.route("/<int:channel_id>/messages")
@login_required
def messages(channel_id):
    """Channel messages (stub)"""
    channel = Channel.query.get_or_404(channel_id)
    flash("Messages feature coming soon", "info")
    return redirect(url_for("channels.detail", channel_id=channel_id))

@channels_bp.route("/<int:channel_id>/message/<int:message_id>/reply", methods=["POST"])
@login_required
def reply_message(channel_id, message_id):
    """Reply to message (stub)"""
    flash("Reply feature coming soon", "info")
    return redirect(url_for("channels.detail", channel_id=channel_id))

@channels_bp.route("/<int:channel_id>/post/<int:post_id>/pin", methods=["POST"])
@login_required
def pin_post(channel_id, post_id):
    """Pin post (stub)"""
    flash("Pin post feature coming soon", "info")
    return redirect(url_for("channels.detail", channel_id=channel_id))
