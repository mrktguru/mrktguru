from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from utils.decorators import login_required
from modules.proxies.services import ProxyManagementService, NetworkManagementService
from modules.proxies.exceptions import (
    ProxyValidationError,
    ProxyNotFoundError,
    NetworkValidationError,
    NetworkInUseError,
    BulkImportError,
    NetworkNotFoundError
)
from utils.proxy_helper import get_country_flag

proxies_bp = Blueprint('proxies', __name__)


@proxies_bp.route('/')
@login_required
def list_proxies():
    """List all proxies"""
    proxies = ProxyManagementService.list_proxies()
    networks = NetworkManagementService.list_networks()
    return render_template('proxies/list.html', proxies=proxies, networks=networks, get_country_flag=get_country_flag)


@proxies_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add new proxy"""
    if request.method == 'POST':
        try:
            # Prepare data
            data = request.form.to_dict()
            is_mobile = request.form.get('is_mobile') == 'on'
            data['is_mobile'] = is_mobile
            
            proxy = ProxyManagementService.create_proxy(data)
            
            flag = get_country_flag(proxy.country) or "" if proxy.country else ""
            flash(f'Proxy added successfully {flag}.', 'success')
            return redirect(url_for('proxies.list_proxies'))
            
        except ProxyValidationError as e:
            flash(str(e), 'error')
            return render_template('proxies/add.html')
        except Exception as e:
            flash(f'Error adding proxy: {str(e)}', 'error')
            return render_template('proxies/add.html')
    
    return render_template('proxies/add.html')


@proxies_bp.route('/<int:proxy_id>/test', methods=['POST'])
@login_required
def test(proxy_id):
    """Test proxy connection"""
    try:
        result = ProxyManagementService.test_proxy(proxy_id)
        if result['success']:
             return jsonify({'success': True, 'ip': result['ip']})
        else:
             return jsonify({'success': False, 'error': result['error']}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@proxies_bp.route('/<int:proxy_id>/rotate', methods=['POST'])
@login_required
def rotate(proxy_id):
    """Rotate mobile proxy"""
    try:
        result = ProxyManagementService.rotate_proxy(proxy_id)
        if result['success']:
             return jsonify({'success': True, 'new_ip': result.get('new_ip')})
        else:
             return jsonify({'success': False, 'error': result.get('error')}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@proxies_bp.route('/<int:proxy_id>/update', methods=['POST'])
@login_required
def update(proxy_id):
    """Update proxy settings"""
    try:
        data = request.form.to_dict()
        proxy = ProxyManagementService.update_proxy(proxy_id, data)
        
        flag = get_country_flag(proxy.country) or "" if proxy.country else ""
        flash(f'Proxy updated {flag}', 'success')
        
    except ProxyValidationError as e:
        flash(f'Invalid data: {str(e)}', 'error')
    except Exception as e:
        flash(f'Error updating proxy: {str(e)}', 'error')
        
    return redirect(url_for('proxies.list_proxies'))


@proxies_bp.route('/<int:proxy_id>/delete', methods=['POST'])
@login_required
def delete(proxy_id):
    """Delete proxy"""
    try:
        ProxyManagementService.delete_proxy(proxy_id)
        flash('Proxy deleted', 'success')
    except ProxyValidationError as e:
        flash(str(e), 'error')
    except Exception as e:
        flash(f'Error deleting proxy: {str(e)}', 'error')
        
    return redirect(url_for('proxies.list_proxies'))


@proxies_bp.route('/bulk-import', methods=['POST'])
@login_required
def bulk_import():
    """Bulk import proxies from list"""
    try:
        proxy_list = request.form.get('proxy_list', '').strip()
        result = ProxyManagementService.bulk_import(proxy_list)
        
        success = result['success']
        errors = result['errors']
        
        flash(f'Imported {success} proxies. {errors} errors.', 'success' if success > 0 else 'warning')
        
    except BulkImportError as e:
        flash(str(e), 'error')
    except Exception as e:
        flash(f'Error during import: {str(e)}', 'error')
        
    return redirect(url_for('proxies.list_proxies'))


@proxies_bp.route('/networks/add', methods=['POST'])
@login_required
def add_network():
    """Add new proxy network"""
    try:
        data = request.form.to_dict()
        NetworkManagementService.create_network(data)
        flash('Proxy Network added', 'success')
        
    except NetworkValidationError as e:
        flash(str(e), 'error')
    except Exception as e:
        flash(f'Error adding network: {str(e)}', 'error')
        
    return redirect(url_for('proxies.list_proxies'))


@proxies_bp.route('/networks/<int:id>/delete', methods=['POST'])
@login_required
def delete_network(id):
    """Delete proxy network"""
    try:
        NetworkManagementService.delete_network(id)
        flash('Proxy Network deleted', 'success')
        
    except (NetworkInUseError, NetworkNotFoundError) as e:
        flash(str(e), 'error')
    except Exception as e:
        flash(f'Error deleting network: {str(e)}', 'error')
        
    return redirect(url_for('proxies.list_proxies'))
