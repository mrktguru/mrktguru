from datetime import datetime
from database import db


class Tier(db.Model):
    """AI Scheduler Tiers - уровни интенсивности активности"""
    __tablename__ = 'tiers'
    
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)  # 'tier_1', 'tier_2'
    name = db.Column(db.String(100), nullable=False)  # 'Warmup', 'Active'
    description = db.Column(db.Text)  # Описание для UI
    
    # Constraints - ограничения для AI
    min_sessions = db.Column(db.Integer, nullable=False, default=2)  # Мин. кол-во сессий в день
    max_sessions = db.Column(db.Integer, nullable=False, default=5)  # Макс. кол-во сессий в день
    total_minutes_min = db.Column(db.Integer, nullable=False, default=15)  # Мин. общее время за день
    total_minutes_max = db.Column(db.Integer, nullable=False, default=45)  # Макс. общее время за день
    session_duration_min = db.Column(db.Integer, nullable=False, default=2)  # Мин. длительность 1 сессии (мин)
    session_duration_max = db.Column(db.Integer, nullable=False, default=12)  # Макс. длительность 1 сессии (мин)
    forbidden_hours = db.Column(db.JSON, default=[0, 1, 2, 3, 4, 5, 6])  # Запрещенные часы (ночь)
    
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Tier {self.slug}>'
    
    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "min_sessions": self.min_sessions,
            "max_sessions": self.max_sessions,
            "total_minutes_min": self.total_minutes_min,
            "total_minutes_max": self.total_minutes_max,
            "session_duration_min": self.session_duration_min,
            "session_duration_max": self.session_duration_max,
            "forbidden_hours": self.forbidden_hours,
            "sort_order": self.sort_order,
            "is_active": self.is_active
        }
    
    def get_constraints_text(self):
        """Форматирует ограничения для промпта AI"""
        forbidden = ", ".join([f"{h}:00" for h in (self.forbidden_hours or [])])
        return f"""ОГРАНИЧЕНИЯ УРОВНЯ {self.name.upper()}:
- Количество сессий в день: {self.min_sessions}-{self.max_sessions}
- Общее время активности: {self.total_minutes_min}-{self.total_minutes_max} минут
- Длительность одной сессии: {self.session_duration_min}-{self.session_duration_max} минут
- Запрещенные часы (сон): {forbidden if forbidden else 'нет'}
"""
