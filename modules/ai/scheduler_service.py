"""
AI Scheduler Service - генерация расписания активности через LLM
"""
import json
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

from database import db
from models.tier import Tier
from models.warmup_schedule import WarmupSchedule
from models.warmup_schedule_node import WarmupScheduleNode
from modules.ai.llm_client import get_llm_client
from modules.ai.persona_builder import PersonaBuilder

logger = logging.getLogger(__name__)


# System prompt template для генерации расписания
SYSTEM_PROMPT_TEMPLATE = """Ты — AI-планировщик активности Telegram аккаунта. Твоя задача — создать реалистичное расписание использования мессенджера, которое имитирует поведение реального человека.

{persona_context}

{tier_constraints}

ПРАВИЛА ГЕНЕРАЦИИ:
1. ВСЕ ВРЕМЕНА УКАЗЫВАЙ В ЛОКАЛЬНОМ ВРЕМЕНИ ПОЛЬЗОВАТЕЛЯ (его timezone: {user_timezone})
2. Учитывай его "жизненный график" — когда он работает, когда отдыхает  
3. Время должно быть "неровным" (14:07, 19:23), НЕ круглые значения (14:00, 19:00)
4. Сессии должны быть распределены естественно — больше вечером, меньше утром
5. Между сессиями минимум 30 минут перерыва
6. Строго соблюдай ограничения по количеству сессий и длительности из TIER
7. НЕ планируй активность до 07:00 и после 23:00 в локальном времени пользователя
{today_constraint}

ВЫБРАННЫЕ ТИПЫ АКТИВНОСТИ:
{selected_nodes}

ФОРМАТ ОТВЕТА (СТРОГО JSON):
{{
  "schedule": [
    {{
      "date": "YYYY-MM-DD",
      "sessions": [
        {{
          "time": "HH:MM",
          "node_type": "passive_activity",
          "duration_minutes": 8,
          "reasoning": "Утренняя проверка после пробуждения"
        }}
      ]
    }}
  ],
  "total_sessions": 12,
  "total_minutes": 87
}}

Сгенерируй расписание на {days} дней, начиная с {start_date}.
"""

# Описание типов нод для промпта
NODE_TYPE_DESCRIPTIONS = {
    'passive_activity': 'Пассивная активность: скроллинг ленты, чтение каналов, просмотр историй',
    'channel_search': 'Поиск каналов: поиск и просмотр тематических каналов',
    'join_channels': 'Подписка на каналы: вступление в найденные каналы',
    'read_messages': 'Чтение сообщений: просмотр личных сообщений и чатов',
    'profile_activity': 'Активность профиля: обновление bio, фото, статуса'
}


class AISchedulerService:
    """
    Сервис генерации расписания через AI.
    """
    
    def __init__(self, account):
        """
        Args:
            account: Account model instance
        """
        self.account = account
        self.persona_builder = PersonaBuilder(account)
        self.llm = None  # Lazy init
    
    def generate_schedule(
        self,
        tier_slug: str,
        days: int = 7,
        node_types: List[str] = None,
        start_date: date = None
    ) -> Dict[str, Any]:
        """
        Генерирует расписание через AI и создает WarmupScheduleNode записи.
        
        Args:
            tier_slug: Slug тира ('tier_1', 'tier_2', etc.)
            days: Количество дней для генерации
            node_types: Список типов нод для включения (default: ['passive_activity'])
            start_date: Дата начала (default: завтра)
            
        Returns:
            dict: {
                'success': bool,
                'nodes_created': int,
                'schedule_id': int,
                'error': str (if failed)
            }
        """
        try:
            # Defaults
            if node_types is None:
                node_types = ['passive_activity']
            
            # Get persona for timezone info
            persona = self.persona_builder.get_or_create_persona()
            user_timezone = persona.get('timezone_offset', 'UTC+3')
            user_tz_offset = persona.get('timezone_offset_hours', 3)  # Default Moscow
            
            # Server is in Helsinki (UTC+2)
            SERVER_TZ_OFFSET = 2
            
            # Calculate proper start_date - must be today or later
            now = datetime.now()  # Server time (Helsinki)
            today = now.date()
            
            # Convert server time to user's local time
            tz_diff = user_tz_offset - SERVER_TZ_OFFSET  # e.g., California: -8 - 2 = -10 hours
            user_local_time = now + timedelta(hours=tz_diff)
            user_local_date = user_local_time.date()
            user_local_hour = user_local_time.hour
            
            logger.info(f"🌍 Server time: {now.strftime('%H:%M')} (UTC+2), User local time: {user_local_time.strftime('%H:%M')} ({user_timezone})")
            
            if start_date is None:
                start_date = user_local_date
            else:
                # Ensure start_date is not in the past (user's local date)
                if start_date < user_local_date:
                    start_date = user_local_date
            
            # Calculate minimum hour for today in USER'S timezone (current local time + 1 hour)
            today_constraint = ""
            if start_date == user_local_date:
                min_hour = user_local_hour + 1
                if min_hour >= 7 and min_hour < 23:  # Still reasonable time left today
                    today_constraint = f"\n8. ВАЖНО: Сегодня ({start_date.isoformat()}) планируй активность ТОЛЬКО после {min_hour:02d}:00 (текущее локальное время пользователя: {user_local_time.strftime('%H:%M')})"
                elif min_hour < 7:
                    # Very early morning in user's timezone - start from 7:00
                    today_constraint = f"\n8. ВАЖНО: Сегодня ({start_date.isoformat()}) начинай с 07:00 или позже (пользователь только просыпается)"
                else:
                    # Too late today in user's timezone, start from tomorrow
                    start_date = user_local_date + timedelta(days=1)
                    logger.info(f"📅 Too late in user's timezone, starting from tomorrow: {start_date}")
            
            # 1. Получаем Tier из БД
            tier = Tier.query.filter_by(slug=tier_slug, is_active=True).first()
            if not tier:
                return {'success': False, 'error': f"Tier not found: {tier_slug}"}
            
            # 2. Получаем контекст персоны
            persona_context = self.persona_builder.build_system_prompt_context()
            
            # 3. Формируем constraints
            tier_constraints = tier.get_constraints_text()
            
            # 4. Формируем описание нод
            selected_nodes = "\n".join([
                f"- {NODE_TYPE_DESCRIPTIONS.get(nt, nt)}"
                for nt in node_types
            ])
            
            # 5. Собираем промпт
            system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
                persona_context=persona_context,
                tier_constraints=tier_constraints,
                selected_nodes=selected_nodes,
                days=days,
                start_date=start_date.isoformat(),
                user_timezone=user_timezone,
                today_constraint=today_constraint
            )
            
            # 6. Отправляем в LLM
            logger.info(f"🤖 Generating AI schedule for account {self.account.id} ({tier.name}, {days} days)")
            
            self.llm = get_llm_client()
            ai_response = self.llm.ask_json(system_prompt)
            
            # 7. Валидируем ответ
            validated = self._validate_ai_response(ai_response, tier, days)
            if not validated['valid']:
                logger.warning(f"⚠️ AI response validation failed: {validated['error']}")
                # Пробуем fallback
                ai_response = self._generate_fallback_schedule(tier, days, node_types, start_date)
            
            # 8. Создаем записи в БД (с конвертацией времени из user timezone в server timezone)
            result = self._create_schedule_nodes(ai_response, node_types, start_date, user_tz_offset)
            
            logger.info(f"✅ AI schedule generated: {result['nodes_created']} nodes")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ AI schedule generation failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _validate_ai_response(self, response: Dict, tier: Tier, days: int) -> Dict[str, Any]:
        """
        Валидирует ответ от AI на соответствие constraints.
        """
        try:
            schedule = response.get('schedule', [])
            
            if not schedule:
                return {'valid': False, 'error': 'Empty schedule'}
            
            total_sessions = 0
            total_minutes = 0
            
            for day_data in schedule:
                sessions = day_data.get('sessions', [])
                day_sessions = len(sessions)
                
                # Проверяем количество сессий
                if day_sessions < tier.min_sessions or day_sessions > tier.max_sessions:
                    return {
                        'valid': False, 
                        'error': f"Sessions count {day_sessions} out of range [{tier.min_sessions}-{tier.max_sessions}]"
                    }
                
                total_sessions += day_sessions
                
                for session in sessions:
                    duration = session.get('duration_minutes', 0)
                    total_minutes += duration
                    
                    # Проверяем длительность сессии
                    if duration < tier.session_duration_min or duration > tier.session_duration_max:
                        return {
                            'valid': False,
                            'error': f"Session duration {duration} out of range [{tier.session_duration_min}-{tier.session_duration_max}]"
                        }
                    
                    # Проверяем запрещенные часы
                    time_str = session.get('time', '12:00')
                    hour = int(time_str.split(':')[0])
                    if hour in (tier.forbidden_hours or []):
                        return {
                            'valid': False,
                            'error': f"Session at {hour}:00 is in forbidden hours"
                        }
            
            # Проверяем общее время за день (приблизительно)
            avg_daily_minutes = total_minutes / days
            if avg_daily_minutes < tier.total_minutes_min or avg_daily_minutes > tier.total_minutes_max:
                logger.warning(f"⚠️ Average daily minutes {avg_daily_minutes:.0f} slightly off target")
                # Не фейлим, просто предупреждаем
            
            return {'valid': True}
            
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    def _generate_fallback_schedule(
        self,
        tier: Tier,
        days: int,
        node_types: List[str],
        start_date: date
    ) -> Dict[str, Any]:
        """
        Генерирует fallback расписание без AI (на случай ошибки).
        """
        import random
        
        logger.info("📋 Generating fallback schedule (AI unavailable)")
        
        schedule = []
        forbidden = set(tier.forbidden_hours or [])
        
        # Доступные часы
        available_hours = [h for h in range(7, 24) if h not in forbidden]
        
        for day_offset in range(days):
            current_date = start_date + timedelta(days=day_offset)
            
            # Рандомное количество сессий
            num_sessions = random.randint(tier.min_sessions, tier.max_sessions)
            
            # Выбираем случайные часы
            selected_hours = sorted(random.sample(available_hours, min(num_sessions, len(available_hours))))
            
            sessions = []
            for hour in selected_hours:
                # "Кривое" время
                minute = random.randint(1, 59)
                
                # Длительность
                duration = random.randint(tier.session_duration_min, tier.session_duration_max)
                
                # Тип ноды
                node_type = random.choice(node_types)
                
                sessions.append({
                    'time': f"{hour:02d}:{minute:02d}",
                    'node_type': node_type,
                    'duration_minutes': duration,
                    'reasoning': 'Fallback schedule'
                })
            
            schedule.append({
                'date': current_date.isoformat(),
                'sessions': sessions
            })
        
        return {'schedule': schedule}
    
    def _create_schedule_nodes(
        self,
        ai_response: Dict,
        node_types: List[str],
        start_date: date,
        user_tz_offset: float = 3
    ) -> Dict[str, Any]:
        """
        Создает WarmupScheduleNode записи из AI ответа.
        Конвертирует время из локального времени пользователя в серверное (Helsinki UTC+2).
        
        Args:
            ai_response: Ответ от AI
            node_types: Типы нод
            start_date: Дата начала (в локальном времени пользователя)
            user_tz_offset: Offset пользователя от UTC (e.g., -8 for California)
        """
        SERVER_TZ_OFFSET = 2  # Helsinki UTC+2
        tz_diff = SERVER_TZ_OFFSET - user_tz_offset  # How many hours to add to convert user time to server time
        
        # Получаем или создаем WarmupSchedule
        schedule = self.account.active_schedule
        
        if not schedule:
            schedule = WarmupSchedule(
                account_id=self.account.id,
                name=f'AI Schedule {datetime.now().strftime("%Y-%m-%d")}',
                status='active',
                start_date=start_date
            )
            db.session.add(schedule)
            db.session.flush()  # Получаем ID
        
        nodes_created = 0
        
        for day_data in ai_response.get('schedule', []):
            date_str = day_data.get('date')
            user_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            for session in day_data.get('sessions', []):
                node_type = session.get('node_type', 'passive_activity')
                duration = session.get('duration_minutes', 5)
                user_time_str = session.get('time', '12:00')
                
                # Parse user's local time and convert to server time
                hour, minute = map(int, user_time_str.split(':'))
                user_datetime = datetime.combine(user_date, datetime.min.time().replace(hour=hour, minute=minute))
                
                # Convert to server time
                server_datetime = user_datetime + timedelta(hours=tz_diff)
                server_date = server_datetime.date()
                server_time = server_datetime.strftime('%H:%M')
                
                # Вычисляем day_number относительно account creation
                if self.account.created_at:
                    account_start = self.account.created_at.date()
                    day_number = (server_date - account_start).days + 1
                else:
                    day_number = (server_date - start_date).days + 1
                
                # Build config based on node type
                config = {
                    'ai_generated': True,
                    'ai_reasoning': session.get('reasoning', ''),
                    'duration_minutes': duration,
                    'intensity': 'normal',
                    'user_local_time': user_time_str,  # Original time in user's timezone
                    'user_timezone_offset': user_tz_offset
                }
                
                # For passive_activity nodes, enable scrolling by default
                if node_type == 'passive_activity':
                    config['enable_scroll'] = True
                    config['scroll_count_min'] = 3
                    config['scroll_count_max'] = 6
                    config['scroll_duration_min'] = 30
                    config['scroll_duration_max'] = 120
                
                logger.debug(f"📅 Node: {user_time_str} ({user_date}) user → {server_time} ({server_date}) server")
                
                # Создаем ноду
                node = WarmupScheduleNode(
                    schedule_id=schedule.id,
                    sequence_id=WarmupScheduleNode.get_next_sequence_id(schedule.id),
                    node_type=node_type,
                    day_number=day_number,
                    execution_date=server_date,
                    execution_time=server_time,
                    is_random_time=False,
                    config=config,
                    status='pending'
                )
                
                db.session.add(node)
                nodes_created += 1
        
        # Обновляем end_date
        if ai_response.get('schedule'):
            last_date_str = ai_response['schedule'][-1].get('date')
            schedule.end_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
        
        db.session.commit()
        
        return {
            'success': True,
            'nodes_created': nodes_created,
            'schedule_id': schedule.id,
            'start_date': start_date.isoformat(),
            'end_date': schedule.end_date.isoformat() if schedule.end_date else None
        }
    
    def preview_schedule(
        self,
        tier_slug: str,
        days: int = 7,
        node_types: List[str] = None,
        start_date: date = None
    ) -> Dict[str, Any]:
        """
        Генерирует preview расписания БЕЗ сохранения в БД.
        Для показа пользователю перед подтверждением.
        """
        try:
            if node_types is None:
                node_types = ['passive_activity']
            if start_date is None:
                start_date = date.today() + timedelta(days=1)
            
            tier = Tier.query.filter_by(slug=tier_slug, is_active=True).first()
            if not tier:
                return {'success': False, 'error': f"Tier not found: {tier_slug}"}
            
            persona_context = self.persona_builder.build_system_prompt_context()
            tier_constraints = tier.get_constraints_text()
            
            selected_nodes = "\n".join([
                f"- {NODE_TYPE_DESCRIPTIONS.get(nt, nt)}"
                for nt in node_types
            ])
            
            system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
                persona_context=persona_context,
                tier_constraints=tier_constraints,
                selected_nodes=selected_nodes,
                days=days,
                start_date=start_date.isoformat()
            )
            
            self.llm = get_llm_client()
            ai_response = self.llm.ask_json(system_prompt)
            
            # Добавляем мета-информацию
            ai_response['tier'] = tier.to_dict()
            ai_response['persona'] = self.persona_builder.get_or_create_persona()
            ai_response['preview_only'] = True
            
            return {'success': True, 'data': ai_response}
            
        except Exception as e:
            logger.error(f"❌ Preview generation failed: {e}")
            return {'success': False, 'error': str(e)}
