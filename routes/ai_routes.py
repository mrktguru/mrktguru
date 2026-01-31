"""
AI Planner API Routes
- Generate schedule
- Topics CRUD
- Tiers CRUD
- Settings pages
"""
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required
from datetime import datetime, date
import logging

from database import db
from models.account import Account
from models.topic import Topic
from models.tier import Tier
from modules.ai.scheduler_service import AISchedulerService
from modules.ai.persona_builder import PersonaBuilder

logger = logging.getLogger(__name__)

# API Blueprint (for JSON endpoints)
ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

# Settings Blueprint (for HTML pages)
ai_settings_bp = Blueprint('ai_settings', __name__, url_prefix='/settings/ai')


# ==================== SETTINGS PAGES (HTML) ====================

@ai_settings_bp.route('/topics')
@login_required
def settings_topics():
    """Страница настройки Topics"""
    topics = Topic.query.order_by(Topic.sort_order).all()
    return render_template('ai/settings_topics.html', topics=topics)


@ai_settings_bp.route('/tiers')
@login_required
def settings_tiers():
    """Страница настройки Tiers"""
    tiers = Tier.query.order_by(Tier.sort_order).all()
    return render_template('ai/settings_tiers.html', tiers=tiers)


# ==================== SCHEDULE GENERATION ====================

@ai_bp.route('/generate_schedule/<int:account_id>', methods=['POST'])
@login_required
def generate_schedule(account_id):
    """
    Генерирует AI расписание для аккаунта.
    
    Body:
    {
        "tier": "tier_1",
        "days": 7,
        "node_types": ["passive_activity"],
        "start_date": "2026-02-01" (optional)
    }
    """
    try:
        account = Account.query.get_or_404(account_id)
        data = request.get_json() or {}
        
        tier_slug = data.get('tier', 'tier_1')
        days = int(data.get('days', 7))
        node_types = data.get('node_types', ['passive_activity'])
        
        # Parse start_date if provided
        start_date = None
        if data.get('start_date'):
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        
        # Validate days
        if days < 1 or days > 30:
            return jsonify({'success': False, 'error': 'Days must be between 1 and 30'}), 400
        
        # Generate schedule
        service = AISchedulerService(account)
        result = service.generate_schedule(
            tier_slug=tier_slug,
            days=days,
            node_types=node_types,
            start_date=start_date
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Schedule generation error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/preview_schedule/<int:account_id>', methods=['POST'])
@login_required
def preview_schedule(account_id):
    """
    Генерирует preview расписания БЕЗ сохранения.
    """
    try:
        account = Account.query.get_or_404(account_id)
        data = request.get_json() or {}
        
        tier_slug = data.get('tier', 'tier_1')
        days = int(data.get('days', 7))
        node_types = data.get('node_types', ['passive_activity'])
        
        start_date = None
        if data.get('start_date'):
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        
        service = AISchedulerService(account)
        result = service.preview_schedule(
            tier_slug=tier_slug,
            days=days,
            node_types=node_types,
            start_date=start_date
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Preview generation error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/persona/<int:account_id>', methods=['GET'])
@login_required
def get_persona(account_id):
    """Возвращает персону аккаунта (генерирует если нужно)"""
    try:
        account = Account.query.get_or_404(account_id)
        builder = PersonaBuilder(account)
        persona = builder.get_or_create_persona()
        
        return jsonify({'success': True, 'persona': persona})
        
    except Exception as e:
        logger.error(f"Persona error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/persona/<int:account_id>/regenerate', methods=['POST'])
@login_required
def regenerate_persona(account_id):
    """Принудительно регенерирует персону"""
    try:
        account = Account.query.get_or_404(account_id)
        builder = PersonaBuilder(account)
        persona = builder.regenerate_persona()
        
        return jsonify({'success': True, 'persona': persona})
        
    except Exception as e:
        logger.error(f"Persona regeneration error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== TOPICS CRUD ====================

@ai_bp.route('/topics', methods=['GET'])
@login_required
def list_topics():
    """Список всех тематик"""
    topics = Topic.query.filter_by(is_active=True).order_by(Topic.sort_order).all()
    return jsonify({
        'success': True,
        'topics': [t.to_dict() for t in topics]
    })


@ai_bp.route('/topics/all', methods=['GET'])
@login_required
def list_all_topics():
    """Список всех тематик включая неактивные (для админки)"""
    topics = Topic.query.order_by(Topic.sort_order).all()
    return jsonify({
        'success': True,
        'topics': [t.to_dict() for t in topics]
    })


@ai_bp.route('/topics', methods=['POST'])
@login_required
def create_topic():
    """Создать новую тематику"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('slug') or not data.get('name'):
            return jsonify({'success': False, 'error': 'slug and name are required'}), 400
        
        # Check uniqueness
        if Topic.query.filter_by(slug=data['slug']).first():
            return jsonify({'success': False, 'error': 'Topic with this slug already exists'}), 400
        
        topic = Topic(
            slug=data['slug'],
            name=data['name'],
            interests_prompt=data.get('interests_prompt', ''),
            schedule_prompt=data.get('schedule_prompt', ''),
            sort_order=data.get('sort_order', 0),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(topic)
        db.session.commit()
        
        return jsonify({'success': True, 'topic': topic.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create topic error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/topics/<int:topic_id>', methods=['PUT'])
@login_required
def update_topic(topic_id):
    """Обновить тематику"""
    try:
        topic = Topic.query.get_or_404(topic_id)
        data = request.get_json()
        
        if 'name' in data:
            topic.name = data['name']
        if 'interests_prompt' in data:
            topic.interests_prompt = data['interests_prompt']
        if 'schedule_prompt' in data:
            topic.schedule_prompt = data['schedule_prompt']
        if 'sort_order' in data:
            topic.sort_order = data['sort_order']
        if 'is_active' in data:
            topic.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({'success': True, 'topic': topic.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update topic error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/topics/<int:topic_id>', methods=['DELETE'])
@login_required
def delete_topic(topic_id):
    """Удалить тематику (soft delete - deactivate)"""
    try:
        topic = Topic.query.get_or_404(topic_id)
        
        # Don't delete 'general' topic
        if topic.slug == 'general':
            return jsonify({'success': False, 'error': 'Cannot delete default topic'}), 400
        
        # Soft delete
        topic.is_active = False
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete topic error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== TIERS CRUD ====================

@ai_bp.route('/tiers', methods=['GET'])
@login_required
def list_tiers():
    """Список всех тиров"""
    tiers = Tier.query.filter_by(is_active=True).order_by(Tier.sort_order).all()
    return jsonify({
        'success': True,
        'tiers': [t.to_dict() for t in tiers]
    })


@ai_bp.route('/tiers/all', methods=['GET'])
@login_required
def list_all_tiers():
    """Список всех тиров включая неактивные (для админки)"""
    tiers = Tier.query.order_by(Tier.sort_order).all()
    return jsonify({
        'success': True,
        'tiers': [t.to_dict() for t in tiers]
    })


@ai_bp.route('/tiers', methods=['POST'])
@login_required
def create_tier():
    """Создать новый тир"""
    try:
        data = request.get_json()
        
        if not data.get('slug') or not data.get('name'):
            return jsonify({'success': False, 'error': 'slug and name are required'}), 400
        
        if Tier.query.filter_by(slug=data['slug']).first():
            return jsonify({'success': False, 'error': 'Tier with this slug already exists'}), 400
        
        tier = Tier(
            slug=data['slug'],
            name=data['name'],
            description=data.get('description', ''),
            min_sessions=data.get('min_sessions', 2),
            max_sessions=data.get('max_sessions', 5),
            total_minutes_min=data.get('total_minutes_min', 15),
            total_minutes_max=data.get('total_minutes_max', 45),
            session_duration_min=data.get('session_duration_min', 2),
            session_duration_max=data.get('session_duration_max', 12),
            forbidden_hours=data.get('forbidden_hours', [0, 1, 2, 3, 4, 5, 6]),
            sort_order=data.get('sort_order', 0),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(tier)
        db.session.commit()
        
        return jsonify({'success': True, 'tier': tier.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create tier error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/tiers/<int:tier_id>', methods=['PUT'])
@login_required
def update_tier(tier_id):
    """Обновить тир"""
    try:
        tier = Tier.query.get_or_404(tier_id)
        data = request.get_json()
        
        if 'name' in data:
            tier.name = data['name']
        if 'description' in data:
            tier.description = data['description']
        if 'min_sessions' in data:
            tier.min_sessions = data['min_sessions']
        if 'max_sessions' in data:
            tier.max_sessions = data['max_sessions']
        if 'total_minutes_min' in data:
            tier.total_minutes_min = data['total_minutes_min']
        if 'total_minutes_max' in data:
            tier.total_minutes_max = data['total_minutes_max']
        if 'session_duration_min' in data:
            tier.session_duration_min = data['session_duration_min']
        if 'session_duration_max' in data:
            tier.session_duration_max = data['session_duration_max']
        if 'forbidden_hours' in data:
            tier.forbidden_hours = data['forbidden_hours']
        if 'sort_order' in data:
            tier.sort_order = data['sort_order']
        if 'is_active' in data:
            tier.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({'success': True, 'tier': tier.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update tier error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/tiers/<int:tier_id>', methods=['DELETE'])
@login_required
def delete_tier(tier_id):
    """Удалить тир (soft delete)"""
    try:
        tier = Tier.query.get_or_404(tier_id)
        
        # Don't delete tier_1
        if tier.slug == 'tier_1':
            return jsonify({'success': False, 'error': 'Cannot delete default tier'}), 400
        
        tier.is_active = False
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete tier error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== ACCOUNT TOPIC ASSIGNMENT ====================

@ai_bp.route('/account/<int:account_id>/topic', methods=['PUT'])
@login_required
def update_account_topic(account_id):
    """Обновить тематику аккаунта"""
    try:
        account = Account.query.get_or_404(account_id)
        data = request.get_json()
        
        topic_slug = data.get('topic_slug')
        if not topic_slug:
            return jsonify({'success': False, 'error': 'topic_slug is required'}), 400
        
        builder = PersonaBuilder(account)
        success = builder.update_topic(topic_slug)
        
        if success:
            return jsonify({'success': True, 'persona': account.ai_metadata})
        else:
            return jsonify({'success': False, 'error': 'Topic not found'}), 404
            
    except Exception as e:
        logger.error(f"Update account topic error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
