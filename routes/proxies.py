from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils.decorators import login_required
from models.proxy import Proxy
from database import db
from utils.validators import validate_proxy
from utils.proxy_helper import test_proxy_connection, rotate_mobile_proxy, extract_country_from_username

proxies_bp = Blueprint('proxies', __name__)


@proxies_bp.route('/')
@login_required
def list_proxies():
    """List all proxies"""
    proxies = Proxy.query.order_by(Proxy.created_at.desc()).all()
    from utils.proxy_helper import get_country_flag
    return render_template('proxies/list.html', proxies=proxies, get_country_flag=get_country_flag)


@proxies_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add new proxy"""
    if request.method == 'POST':
        proxy_string = request.form.get('proxy_string')
        is_mobile = request.form.get('is_mobile') == 'on'
        rotation_url = request.form.get('rotation_url') if is_mobile else None
        rotation_interval = int(request.form.get('rotation_interval', 1200)) if is_mobile else None
        notes = request.form.get('notes')
        
        # Validate proxy
        is_valid, result = validate_proxy(proxy_string)
        if not is_valid:
            flash(result, 'error')
            return render_template('proxies/add.html')
        
        # Extract country from username
        country = extract_country_from_username(result.get('username'))
        
        # Create proxy
        proxy = Proxy(
            type=result['type'],
            host=result['host'],
            port=result['port'],
            username=result['username'],
            password=result['password'],
            is_mobile=is_mobile,
            rotation_url=rotation_url,
            rotation_interval=rotation_interval,
            country=country,
            notes=notes
        )
        
        db.session.add(proxy)
        db.session.commit()
        
        # Test proxy
        test_result = test_proxy_connection(proxy)
        if test_result['success']:
            proxy.current_ip = test_result['ip']
            proxy.status = 'active'
            db.session.commit()
            
            flag = ""
            if country:
                from utils.proxy_helper import get_country_flag
                flag = get_country_flag(country) or ""
                
            flash(f'Proxy added successfully {flag}. IP: {test_result["ip"]}', 'success')
        else:
            proxy.status = 'error'
            db.session.commit()
            flash(f'Proxy added but test failed: {test_result["error"]}', 'warning')
        
        return redirect(url_for('proxies.list_proxies'))
    
    return render_template('proxies/add.html')


@proxies_bp.route('/<int:proxy_id>/test', methods=['POST'])
@login_required
def test(proxy_id):
    """Test proxy connection"""
    proxy = Proxy.query.get_or_404(proxy_id)
    
    result = test_proxy_connection(proxy)
    
    if result['success']:
        proxy.current_ip = result['ip']
        proxy.status = 'active'
        db.session.commit()
        return jsonify({'success': True, 'ip': result['ip']})
    else:
        proxy.status = 'error'
        db.session.commit()
        return jsonify({'success': False, 'error': result['error']}), 400


@proxies_bp.route('/<int:proxy_id>/rotate', methods=['POST'])
@login_required
def rotate(proxy_id):
    """Rotate mobile proxy"""
    proxy = Proxy.query.get_or_404(proxy_id)
    
    result = rotate_mobile_proxy(proxy)
    
    if result['success']:
        return jsonify({'success': True, 'new_ip': result['new_ip']})
    else:
        return jsonify({'success': False, 'error': result['error']}), 400


@proxies_bp.route('/<int:proxy_id>/update', methods=['POST'])
@login_required
def update(proxy_id):
    """Update proxy settings"""
    proxy = Proxy.query.get_or_404(proxy_id)
    
    try:
        # Update proxy string if provided
        proxy_string = request.form.get('proxy_string')
        if proxy_string:
            from utils.validators import validate_proxy
            is_valid, result = validate_proxy(proxy_string)
            if is_valid:
                proxy.type = result['type']
                proxy.host = result['host']
                proxy.port = result['port']
                proxy.username = result['username']
                proxy.password = result['password']
                
                # Update country
                proxy.country = extract_country_from_username(result.get('username'))
                
                # Reset status to allow re-testing
                proxy.status = 'active'
                proxy.current_ip = None
            else:
                flash(f'Invalid proxy format: {result}', 'error')
                return redirect(url_for('proxies.list_proxies'))

        if proxy.is_mobile:
            proxy.rotation_url = request.form.get('rotation_url')
            proxy.rotation_interval = int(request.form.get('rotation_interval', 1200))
        
        proxy.notes = request.form.get('notes')
        db.session.commit()
    except RecursionError:
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash('System Error: Recursion Depth Exceeded. Check logs.', 'error')
        return redirect(url_for('proxies.list_proxies'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating proxy: {str(e)}', 'error')
        return redirect(url_for('proxies.list_proxies'))
    
    # Auto-test if credentials changed
    if proxy_string:
        from utils.proxy_helper import test_proxy_connection
        test_result = test_proxy_connection(proxy)
        if test_result['success']:
            proxy.current_ip = test_result['ip']
            proxy.status = 'active'
            db.session.commit()
            
            # Flash with flag
            flag = ""
            if proxy.country:
                from utils.proxy_helper import get_country_flag
                flag = get_country_flag(proxy.country) or ""
            
            flash(f'Proxy updated and verified {flag}. IP: {test_result["ip"]}', 'success')
        else:
            proxy.status = 'error'
            db.session.commit()
            flash(f'Proxy updated but connection failed: {test_result["error"]}', 'warning')
    else:
        flash('Proxy updated', 'success')
    return redirect(url_for('proxies.list_proxies'))


@proxies_bp.route('/<int:proxy_id>/delete', methods=['POST'])
@login_required
def delete(proxy_id):
    """Delete proxy"""
    proxy = Proxy.query.get_or_404(proxy_id)
    
    # Check if proxy is in use
    if proxy.accounts.count() > 0:
        flash('Cannot delete proxy: it is assigned to accounts', 'error')
        return redirect(url_for('proxies.list_proxies'))
    
    db.session.delete(proxy)
    db.session.commit()
    
    flash('Proxy deleted', 'success')
    return redirect(url_for('proxies.list_proxies'))


@proxies_bp.route('/bulk-import', methods=['POST'])
@login_required
def bulk_import():
    """Bulk import proxies from list"""
    proxy_list = request.form.get('proxy_list', '').strip()
    
    if not proxy_list:
        flash('No proxies provided', 'error')
        return redirect(url_for('proxies.add'))
    
    lines = proxy_list.split('\n')
    success_count = 0
    error_count = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Validate proxy
        is_valid, result = validate_proxy(line)
        if not is_valid:
            error_count += 1
            continue
        
        # Check if exists
        existing = Proxy.query.filter_by(
            host=result['host'],
            port=result['port']
        ).first()
        
        if existing:
            continue
        
        # Extract country
        country = extract_country_from_username(result.get('username'))
        
        # Create proxy
        proxy = Proxy(
            type=result['type'],
            host=result['host'],
            port=result['port'],
            username=result['username'],
            password=result['password'],
            country=country
        )
        
        db.session.add(proxy)
        success_count += 1
    
    db.session.commit()
    
    flash(f'Imported {success_count} proxies. {error_count} errors.', 'success' if success_count > 0 else 'warning')
    return redirect(url_for('proxies.list_proxies'))
