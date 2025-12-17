from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.decorators import login_required
from models.parser import ParsedUserLibrary, ParseJob
from models.account import Account
from app import db

parser_bp = Blueprint('parser', __name__)


@parser_bp.route('/')
@login_required
def index():
    """Parser dashboard"""
    jobs = ParseJob.query.order_by(ParseJob.created_at.desc()).limit(10).all()
    collections = db.session.query(ParsedUserLibrary.collection_name).distinct().all()
    collections = [c[0] for c in collections]
    return render_template('parser/dashboard.html', jobs=jobs, collections=collections)


@parser_bp.route('/parse', methods=['POST'])
@login_required
def parse():
    """Start parsing job"""
    job_type = request.form.get('job_type')
    channels = request.form.get('channels', '').split(',')
    collection_name = request.form.get('collection_name')
    account_id = request.form.get('account_id')
    
    if not channels or not collection_name or not account_id:
        flash('All fields are required', 'error')
        return redirect(url_for('parser.index'))
    
    # Create parse job
    job = ParseJob(
        name=f'Parse {collection_name}',
        job_type=job_type,
        source_channels=[c.strip().lstrip('@') for c in channels if c.strip()],
        filters={'collection_name': collection_name},
        account_id=int(account_id)
    )
    db.session.add(job)
    db.session.commit()
    
    # Start parsing worker
    from workers.parser_worker import execute_parse_job
    execute_parse_job.delay(job.id)
    
    flash('Parsing started in background', 'info')
    return redirect(url_for('parser.index'))


@parser_bp.route('/library')
@login_required
def library():
    """User library"""
    collection = request.args.get('collection')
    
    query = ParsedUserLibrary.query
    if collection:
        query = query.filter_by(collection_name=collection)
    
    users = query.order_by(ParsedUserLibrary.parsed_at.desc()).limit(100).all()
    
    collections = db.session.query(ParsedUserLibrary.collection_name).distinct().all()
    collections = [c[0] for c in collections]
    
    return render_template('parser/library.html', users=users, collections=collections, current_collection=collection)
