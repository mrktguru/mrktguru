from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.decorators import login_required
from models.parser import ParsedUserLibrary, ParseJob
from models.account import Account
from database import db

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


@parser_bp.route("/multi-channel", methods=["GET", "POST"])
@login_required
def multi_channel():
    """Parse from multiple channels"""
    from models.account import Account
    from models.parser import ParseJob, ParsedUserLibrary
    
    if request.method == "POST":
        channels = request.form.get("channels").split("\\n")
        collection_name = request.form.get("collection_name")
        account_id = request.form.get("account_id")
        
        # Filters
        exclude_bots = request.form.get("exclude_bots") == "on"
        exclude_without_username = request.form.get("exclude_without_username") == "on"
        min_photo = request.form.get("min_photo") == "on"
        
        if not channels or not collection_name or not account_id:
            flash("Channels, collection name and account are required", "error")
            return redirect(url_for("parser.multi_channel"))
        
        # Create parse job
        parse_job = ParseJob(
            name=f"Multi-channel: {collection_name}",
            job_type="multi_channel",
            source_channels=channels,
            filters={
                "exclude_bots": exclude_bots,
                "exclude_without_username": exclude_without_username,
                "min_photo": min_photo
            },
            account_id=int(account_id),
            status="pending"
        )
        db.session.add(parse_job)
        db.session.commit()
        
        # Start background parsing (would use Celery)
        flash(f"Parsing job created. ID: {parse_job.id}", "success")
        return redirect(url_for("parser.library"))
    
    accounts = Account.query.filter_by(status="active").all()
    return render_template("parser/multi_channel.html", accounts=accounts)


@parser_bp.route("/by-activity", methods=["GET", "POST"])
@login_required
def by_activity():
    """Parse users by activity"""
    from models.account import Account
    from models.parser import ParseJob
    
    if request.method == "POST":
        channel = request.form.get("channel")
        days = int(request.form.get("days", 7))
        min_messages = int(request.form.get("min_messages", 5))
        collection_name = request.form.get("collection_name")
        account_id = request.form.get("account_id")
        
        if not channel or not collection_name or not account_id:
            flash("All fields are required", "error")
            return redirect(url_for("parser.by_activity"))
        
        # Create parse job
        parse_job = ParseJob(
            name=f"Activity: {channel}",
            job_type="by_activity",
            source_channels=[channel],
            filters={
                "days": days,
                "min_messages": min_messages,
                "collection_name": collection_name
            },
            account_id=int(account_id),
            status="pending"
        )
        db.session.add(parse_job)
        db.session.commit()
        
        flash(f"Activity parsing job created. ID: {parse_job.id}", "success")
        return redirect(url_for("parser.library"))
    
    accounts = Account.query.filter_by(status="active").all()
    return render_template("parser/by_activity.html", accounts=accounts)


@parser_bp.route("/by-keyword", methods=["GET", "POST"])
@login_required
def by_keyword():
    """Parse users by keyword"""
    from models.account import Account
    from models.parser import ParseJob
    
    if request.method == "POST":
        channels = request.form.get("channels").split("\\n")
        keyword = request.form.get("keyword")
        search_in_messages = request.form.get("search_in_messages") == "on"
        search_in_bios = request.form.get("search_in_bios") == "on"
        collection_name = request.form.get("collection_name")
        account_id = request.form.get("account_id")
        
        if not channels or not keyword or not collection_name or not account_id:
            flash("All fields are required", "error")
            return redirect(url_for("parser.by_keyword"))
        
        # Create parse job
        parse_job = ParseJob(
            name=f"Keyword: {keyword}",
            job_type="by_keyword",
            source_channels=channels,
            filters={
                "keyword": keyword,
                "search_in_messages": search_in_messages,
                "search_in_bios": search_in_bios,
                "collection_name": collection_name
            },
            account_id=int(account_id),
            status="pending"
        )
        db.session.add(parse_job)
        db.session.commit()
        
        flash(f"Keyword parsing job created. ID: {parse_job.id}", "success")
        return redirect(url_for("parser.library"))
    
    accounts = Account.query.filter_by(status="active").all()
    return render_template("parser/by_keyword.html", accounts=accounts)


@parser_bp.route("/library/export", methods=["POST"])
@login_required
def export_to_campaign():
    """Export parsed users to campaign"""
    from models.parser import ParsedUserLibrary
    from models.campaign import SourceUser
    
    collection_name = request.form.get("collection_name")
    campaign_id = request.form.get("campaign_id")
    
    if not collection_name or not campaign_id:
        flash("Collection and campaign are required", "error")
        return redirect(url_for("parser.library"))
    
    # Get parsed users
    parsed_users = ParsedUserLibrary.query.filter_by(collection_name=collection_name).all()
    
    # Add to campaign
    count = 0
    for parsed_user in parsed_users:
        # Check if already exists
        existing = SourceUser.query.filter_by(
            campaign_id=int(campaign_id),
            user_id=parsed_user.user_id
        ).first()
        
        if not existing:
            source_user = SourceUser(
                campaign_id=int(campaign_id),
                user_id=parsed_user.user_id,
                username=parsed_user.username,
                first_name=parsed_user.first_name,
                last_name=parsed_user.last_name,
                source=parsed_user.source_channel,
                priority_score=50  # Default score
            )
            db.session.add(source_user)
            count += 1
    
    db.session.commit()
    
    flash(f"{count} users exported to campaign", "success")
    return redirect(url_for("campaigns.detail", campaign_id=campaign_id))


@parser_bp.route("/library/delete/<int:id>", methods=["POST"])
@login_required
def delete_from_library(id):
    """Delete user from library"""
    from models.parser import ParsedUserLibrary
    
    parsed_user = ParsedUserLibrary.query.get_or_404(id)
    db.session.delete(parsed_user)
    db.session.commit()
    
    flash("User deleted from library", "success")
    return redirect(url_for("parser.library"))


@parser_bp.route("/jobs")
@login_required
def jobs():
    """View all parse jobs"""
    from models.parser import ParseJob
    
    jobs = ParseJob.query.order_by(ParseJob.created_at.desc()).all()
    return render_template("parser/jobs.html", jobs=jobs)
