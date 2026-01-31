"""
Seed script for AI Planner: Topics and Tiers
Run: python scripts/seed_ai_config.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import db
from models.topic import Topic
from models.tier import Tier

# ============== TOPICS ==============
INITIAL_TOPICS = [
    {
        "slug": "general",
        "name": "Универсальный",
        "interests_prompt": "Новости мира, Погода, Популярные мемы, Киноновинки, Музыка, Путешествия, Лайфхаки.",
        "schedule_prompt": "Стандартный день. Активность с 08:00 до 23:00. Пики активности: утром за завтраком (08-09), в обед (12-14), и вечером после работы (19-23).",
        "sort_order": 0
    },
    {
        "slug": "sport",
        "name": "Спорт",
        "interests_prompt": "Футбол (РПЛ, Еврокубки), Хоккей (КХЛ, НХЛ), Результаты матчей, Спортивная аналитика, Интервью спортсменов, Ставки на спорт.",
        "schedule_prompt": "Фанат спорта. Активность с 09:00 до 00:00. Обязательно проверяет новости вечером (когда идут матчи 19-23) и утром (результаты 09-10). В выходные активность значительно выше.",
        "sort_order": 1
    },
    {
        "slug": "finance",
        "name": "Финансы / Крипта",
        "interests_prompt": "Курс Биткоина, Ethereum, Альткоины, Акции, Экономические новости, Forbes, Tech Insider, Инвестиции, DeFi, NFT.",
        "schedule_prompt": "Трейдер/Инвестор. Ранний подъем - проверка рынков в 07:00-08:00 (открытие Азии). Активен в рабочее время 10:00-18:00. Вечером реже, но может проверять курсы перед сном (22-23).",
        "sort_order": 2
    },
    {
        "slug": "design",
        "name": "Дизайн / Арт",
        "interests_prompt": "UI/UX тренды, Figma, Behance, Dribbble, Современное искусство, Нейросети для генерации (Midjourney, Stable Diffusion), Фриланс, Креатив.",
        "schedule_prompt": "Творческий режим (Сова). Может спать до 10-11 утра. Активность смещена на вечер и ночь (18:00-02:00). Много сидит в телефоне поздно вечером, вдохновляется перед сном.",
        "sort_order": 3
    }
]

# ============== TIERS ==============
INITIAL_TIERS = [
    {
        "slug": "tier_1",
        "name": "Warmup",
        "description": "Начальный прогрев. Минимальная активность для новых аккаунтов.",
        "min_sessions": 2,
        "max_sessions": 5,
        "total_minutes_min": 15,
        "total_minutes_max": 45,
        "session_duration_min": 2,
        "session_duration_max": 12,
        "forbidden_hours": [0, 1, 2, 3, 4, 5, 6],
        "sort_order": 0
    },
    {
        "slug": "tier_2",
        "name": "Active",
        "description": "Активный режим. Для аккаунтов после 3-5 дней прогрева.",
        "min_sessions": 4,
        "max_sessions": 8,
        "total_minutes_min": 30,
        "total_minutes_max": 90,
        "session_duration_min": 5,
        "session_duration_max": 15,
        "forbidden_hours": [0, 1, 2, 3, 4, 5],
        "sort_order": 1
    },
    {
        "slug": "tier_3",
        "name": "Trusted",
        "description": "Доверенный режим. Для аккаунтов с хорошей историей (7+ дней).",
        "min_sessions": 5,
        "max_sessions": 12,
        "total_minutes_min": 45,
        "total_minutes_max": 150,
        "session_duration_min": 5,
        "session_duration_max": 20,
        "forbidden_hours": [0, 1, 2, 3, 4],
        "sort_order": 2
    },
    {
        "slug": "tier_4",
        "name": "Veteran",
        "description": "Ветеран. Максимальная активность для проверенных аккаунтов (14+ дней).",
        "min_sessions": 6,
        "max_sessions": 15,
        "total_minutes_min": 60,
        "total_minutes_max": 240,
        "session_duration_min": 5,
        "session_duration_max": 30,
        "forbidden_hours": [0, 1, 2, 3],
        "sort_order": 3
    }
]


def seed_topics():
    """Создает или обновляет Topics"""
    print("🎯 Seeding Topics...")
    
    for item in INITIAL_TOPICS:
        existing = Topic.query.filter_by(slug=item['slug']).first()
        
        if existing:
            # Update existing
            existing.name = item['name']
            existing.interests_prompt = item['interests_prompt']
            existing.schedule_prompt = item['schedule_prompt']
            existing.sort_order = item['sort_order']
            print(f"   ✏️  Updated: {item['slug']}")
        else:
            # Create new
            topic = Topic(
                slug=item['slug'],
                name=item['name'],
                interests_prompt=item['interests_prompt'],
                schedule_prompt=item['schedule_prompt'],
                sort_order=item['sort_order'],
                is_active=True
            )
            db.session.add(topic)
            print(f"   ✅ Created: {item['slug']}")
    
    db.session.commit()
    print(f"   📊 Total topics: {Topic.query.count()}")


def seed_tiers():
    """Создает или обновляет Tiers"""
    print("📈 Seeding Tiers...")
    
    for item in INITIAL_TIERS:
        existing = Tier.query.filter_by(slug=item['slug']).first()
        
        if existing:
            # Update existing
            existing.name = item['name']
            existing.description = item['description']
            existing.min_sessions = item['min_sessions']
            existing.max_sessions = item['max_sessions']
            existing.total_minutes_min = item['total_minutes_min']
            existing.total_minutes_max = item['total_minutes_max']
            existing.session_duration_min = item['session_duration_min']
            existing.session_duration_max = item['session_duration_max']
            existing.forbidden_hours = item['forbidden_hours']
            existing.sort_order = item['sort_order']
            print(f"   ✏️  Updated: {item['slug']}")
        else:
            # Create new
            tier = Tier(
                slug=item['slug'],
                name=item['name'],
                description=item['description'],
                min_sessions=item['min_sessions'],
                max_sessions=item['max_sessions'],
                total_minutes_min=item['total_minutes_min'],
                total_minutes_max=item['total_minutes_max'],
                session_duration_min=item['session_duration_min'],
                session_duration_max=item['session_duration_max'],
                forbidden_hours=item['forbidden_hours'],
                sort_order=item['sort_order'],
                is_active=True
            )
            db.session.add(tier)
            print(f"   ✅ Created: {item['slug']}")
    
    db.session.commit()
    print(f"   📊 Total tiers: {Tier.query.count()}")


def migrate_accounts_to_general():
    """Присваивает всем существующим аккаунтам topic 'general'"""
    from models.account import Account
    
    print("👤 Migrating accounts to 'general' topic...")
    
    general_topic = Topic.query.filter_by(slug='general').first()
    if not general_topic:
        print("   ❌ Error: 'general' topic not found! Run seed_topics first.")
        return
    
    # Update accounts without topic
    count = Account.query.filter(Account.persona_topic_id.is_(None)).update(
        {Account.persona_topic_id: general_topic.id},
        synchronize_session=False
    )
    
    db.session.commit()
    print(f"   ✅ Updated {count} accounts")


def main():
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*50)
        print("🤖 AI Planner Configuration Seed")
        print("="*50 + "\n")
        
        seed_topics()
        print()
        seed_tiers()
        print()
        migrate_accounts_to_general()
        
        print("\n" + "="*50)
        print("✅ Seed completed successfully!")
        print("="*50 + "\n")


if __name__ == '__main__':
    main()
