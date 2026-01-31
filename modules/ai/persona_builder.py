"""
Persona Builder - генерация и управление "цифровой личностью" аккаунта
"""
import random
import logging
import requests
from datetime import datetime
from typing import Dict, Any, Optional

from database import db
from models.topic import Topic

logger = logging.getLogger(__name__)


# Маппинг регионов прокси на timezone
REGION_TIMEZONE_MAP = {
    # США
    'california': 'America/Los_Angeles',
    'los angeles': 'America/Los_Angeles',
    'new york': 'America/New_York',
    'texas': 'America/Chicago',
    'chicago': 'America/Chicago',
    'florida': 'America/New_York',
    'seattle': 'America/Los_Angeles',
    
    # Европа
    'germany': 'Europe/Berlin',
    'berlin': 'Europe/Berlin',
    'london': 'Europe/London',
    'uk': 'Europe/London',
    'france': 'Europe/Paris',
    'paris': 'Europe/Paris',
    'netherlands': 'Europe/Amsterdam',
    'amsterdam': 'Europe/Amsterdam',
    
    # СНГ
    'russia': 'Europe/Moscow',
    'moscow': 'Europe/Moscow',
    'ukraine': 'Europe/Kiev',
    'kiev': 'Europe/Kiev',
    'kazakhstan': 'Asia/Almaty',
    
    # Азия
    'singapore': 'Asia/Singapore',
    'japan': 'Asia/Tokyo',
    'china': 'Asia/Shanghai',
    'india': 'Asia/Kolkata',
}

# UTC offsets для основных timezones (numeric hours from UTC)
TIMEZONE_UTC_OFFSETS = {
    'America/Los_Angeles': ('UTC-8', -8),
    'America/New_York': ('UTC-5', -5),
    'America/Chicago': ('UTC-6', -6),
    'Europe/London': ('UTC+0', 0),
    'Europe/Berlin': ('UTC+1', 1),
    'Europe/Paris': ('UTC+1', 1),
    'Europe/Amsterdam': ('UTC+1', 1),
    'Europe/Moscow': ('UTC+3', 3),
    'Europe/Kiev': ('UTC+2', 2),
    'Europe/Helsinki': ('UTC+2', 2),
    'Asia/Almaty': ('UTC+6', 6),
    'Asia/Singapore': ('UTC+8', 8),
    'Asia/Tokyo': ('UTC+9', 9),
    'Asia/Shanghai': ('UTC+8', 8),
    'Asia/Kolkata': ('UTC+5:30', 5.5),
}

# Server timezone (Helsinki)
SERVER_TIMEZONE_OFFSET = 2  # UTC+2


class PersonaBuilder:
    """
    Генератор "цифровой личности" аккаунта.
    Использует Lazy Generation - данные генерируются один раз и сохраняются навсегда.
    """
    
    def __init__(self, account):
        """
        Args:
            account: Account model instance
        """
        self.account = account
    
    def get_or_create_persona(self) -> Dict[str, Any]:
        """
        Возвращает существующую персону или генерирует новую.
        
        Ленивая генерация:
        - Если ai_metadata уже заполнена - возвращаем её
        - Если пустая - генерируем, сохраняем в БД, возвращаем
        
        Returns:
            dict: Данные персоны (name, gender, age, timezone, interests, ...)
        """
        # Проверяем существующие данные
        if self.account.ai_metadata and self.account.ai_metadata.get('is_generated'):
            logger.debug(f"📋 Using existing persona for account {self.account.id}")
            return self.account.ai_metadata
        
        # Генерируем новую персону
        logger.info(f"🎭 Generating new persona for account {self.account.id}")
        
        # 1. Имя (из Telegram или fallback)
        name = self._extract_name()
        
        # 2. Пол (эвристика по имени)
        gender = self._guess_gender(name)
        
        # 3. Возраст (рандом 25-45)
        age = random.randint(25, 45)
        
        # 4. Timezone (из региона прокси)
        timezone, timezone_offset, timezone_offset_hours = self._get_timezone_from_proxy()
        
        # 5. Topic (из настроек аккаунта или default)
        topic = self._get_topic()
        
        # Собираем персону
        persona_data = {
            "name": name,
            "gender": gender,
            "age": age,
            "timezone": timezone,
            "timezone_offset": timezone_offset,
            "timezone_offset_hours": timezone_offset_hours,
            "topic_slug": topic.slug if topic else "general",
            "topic_name": topic.name if topic else "Универсальный",
            "interests": topic.interests_prompt if topic else "",
            "schedule_description": topic.schedule_prompt if topic else "",
            "is_generated": True,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        # Сохраняем в БД
        self.account.ai_metadata = persona_data
        db.session.commit()
        
        logger.info(f"✅ Persona generated: {name}, {age}y, {gender}, {timezone}")
        
        return persona_data
    
    def _extract_name(self) -> str:
        """Извлекает имя из данных аккаунта"""
        # Приоритет: first_name из Account > tdata_metadata > username > fallback
        
        if self.account.first_name:
            return self.account.first_name
        
        if self.account.tdata_metadata:
            # tdata_metadata может хранить имя в raw_metadata
            raw = self.account.tdata_metadata.raw_metadata or {}
            if raw.get('first_name'):
                return raw['first_name']
        
        if self.account.username:
            # Очищаем username от цифр и специальных символов
            clean_name = ''.join(c for c in self.account.username if c.isalpha())
            if len(clean_name) >= 3:
                return clean_name.capitalize()
        
        # Fallback
        return "User"
    
    def _guess_gender(self, name: str) -> str:
        """
        Определяет пол по окончанию имени (русская эвристика).
        Не идеально, но работает для большинства славянских имен.
        """
        if not name or len(name) < 2:
            return "male"
        
        name_lower = name.lower()
        
        # Женские окончания (русские имена)
        female_endings = ['а', 'я', 'ия', 'ья', 'ea', 'ia', 'ya', 'na', 'la']
        
        # Исключения (мужские имена на -а/-я)
        male_exceptions = ['никита', 'илья', 'кузьма', 'фома', 'лука', 'саша', 'миша', 'nikita', 'ilya']
        
        if name_lower in male_exceptions:
            return "male"
        
        for ending in female_endings:
            if name_lower.endswith(ending):
                return "female"
        
        return "male"
    
    def _get_timezone_from_proxy(self) -> tuple:
        """
        Определяет timezone на основе региона прокси.
        
        Returns:
            tuple: (timezone_name, utc_offset_str, utc_offset_hours)
        """
        default_tz = ("Europe/Moscow", "UTC+3", 3)
        
        try:
            # Ищем регион в названии ProxyNetwork
            if self.account.proxy_network:
                network_name = (self.account.proxy_network.name or "").lower()
                
                for region, tz in REGION_TIMEZONE_MAP.items():
                    if region in network_name:
                        offset_data = TIMEZONE_UTC_OFFSETS.get(tz, ("UTC", 0))
                        offset_str, offset_hours = offset_data
                        logger.debug(f"📍 Timezone from proxy network: {tz} ({offset_str})")
                        return (tz, offset_str, offset_hours)
            
            # Fallback: статический прокси
            if self.account.proxy:
                # Можно попробовать определить по хосту, но это ненадежно
                pass
            
        except Exception as e:
            logger.warning(f"⚠️ Error detecting timezone: {e}")
        
        return default_tz
    
    def _get_topic(self) -> Optional[Topic]:
        """Получает Topic из БД"""
        # Если topic уже привязан
        if self.account.persona_topic:
            return self.account.persona_topic
        
        # Если есть persona_topic_id
        if self.account.persona_topic_id:
            topic = Topic.query.get(self.account.persona_topic_id)
            if topic:
                return topic
        
        # Default: general
        return Topic.query.filter_by(slug='general').first()
    
    def build_system_prompt_context(self) -> str:
        """
        Формирует текстовый блок КОНТЕКСТА для отправки в LLM.
        
        Returns:
            str: Текст для включения в system prompt
        """
        data = self.get_or_create_persona()
        
        gender_ru = "мужчина" if data['gender'] == 'male' else "женщина"
        
        context = f"""КОНТЕКСТ АККАУНТА:
- Имя: {data['name']}
- Пол: {gender_ru}
- Возраст: {data['age']} лет
- Психотип/Тематика: {data['topic_name']}
- Интересы: {data['interests']}
- Жизненный график: {data['schedule_description']}
- Часовой пояс: {data['timezone_offset']} ({data['timezone']})
"""
        return context
    
    def regenerate_persona(self) -> Dict[str, Any]:
        """
        Принудительно регенерирует персону (сбрасывает is_generated).
        Используется если нужно обновить данные.
        """
        logger.info(f"🔄 Regenerating persona for account {self.account.id}")
        
        # Сбрасываем флаг
        self.account.ai_metadata = {}
        db.session.commit()
        
        # Генерируем заново
        return self.get_or_create_persona()
    
    def update_topic(self, topic_slug: str) -> bool:
        """
        Обновляет тему аккаунта и регенерирует связанные поля персоны.
        
        Args:
            topic_slug: slug новой темы
            
        Returns:
            bool: Успех операции
        """
        topic = Topic.query.filter_by(slug=topic_slug).first()
        if not topic:
            logger.error(f"❌ Topic not found: {topic_slug}")
            return False
        
        # Обновляем тему
        self.account.persona_topic_id = topic.id
        
        # Обновляем только topic-related поля в ai_metadata
        if self.account.ai_metadata:
            self.account.ai_metadata['topic_slug'] = topic.slug
            self.account.ai_metadata['topic_name'] = topic.name
            self.account.ai_metadata['interests'] = topic.interests_prompt
            self.account.ai_metadata['schedule_description'] = topic.schedule_prompt
        
        db.session.commit()
        
        logger.info(f"✅ Topic updated to: {topic.name}")
        return True
