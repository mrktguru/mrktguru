from datetime import datetime
from database import db


class Topic(db.Model):
    """AI Persona Topics - тематики для генерации персоны аккаунта"""
    __tablename__ = 'topics'
    
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)  # 'sport', 'finance'
    name = db.Column(db.String(100), nullable=False)  # 'Спорт', 'Финансы'
    
    # Промпт для ИИ: Что именно интересует эту категорию людей
    interests_prompt = db.Column(db.Text, nullable=False)
    
    # Промпт для ИИ: Режим дня (Работа + Дом)
    schedule_prompt = db.Column(db.Text, nullable=False)
    
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Topic {self.slug}>'
    
    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "interests_prompt": self.interests_prompt,
            "schedule_prompt": self.schedule_prompt,
            "sort_order": self.sort_order,
            "is_active": self.is_active
        }
