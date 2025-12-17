# Telegram Invite & DM System

Автоматизированная система для роста Telegram каналов/групп через invite-кампании и DM-рассылки с встроенной антибан-защитой.

## Возможности

- **Invite Campaigns** - Автоматические инвайты в каналы/группы
- **DM Campaigns** - Массовые direct message рассылки
- **Account Management** - Управление множеством аккаунтов
- **Proxy Support** - Поддержка мобильных прокси с ротацией
- **Anti-ban System** - Эмуляция устройств, human-like поведение, warm-up
- **Parser** - Парсинг пользователей из каналов
- **Analytics** - Детальная аналитика и отчеты
- **Automation** - Планирование задач и авто-действия

## Технологии

- Backend: Flask, PostgreSQL, Celery, Redis
- Telegram: Telethon
- Frontend: Bootstrap 5, jQuery

## Установка

### 1. Требования

- Python 3.9+
- PostgreSQL 14+
- Redis

### 2. Установка зависимостей

```bash
# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установить пакеты
pip install -r requirements.txt
```

### 3. Настройка базы данных

```bash
# Создать базу данных
createdb telegram_system

# Применить миграции
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 4. Конфигурация

Скопировать `.env.example` в `.env` и заполнить:

```bash
cp .env.example .env
```

Обязательные параметры:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `TG_API_ID` - Telegram API ID (с https://my.telegram.org/apps)
- `TG_API_HASH` - Telegram API Hash
- `SECRET_KEY` - Секретный ключ Flask

### 5. Создание администратора

```bash
python create_admin.py
```

Default credentials: `admin` / `admin123`

### 6. Запуск

**Терминал 1 - Flask app:**
```bash
python app.py
```

**Терминал 2 - Celery worker:**
```bash
celery -A celery_app worker --loglevel=info
```

**Терминал 3 - Celery beat (планировщик):**
```bash
celery -A celery_app beat --loglevel=info
```

### 7. Доступ

Открыть браузер: http://localhost:5000

Login: `admin`  
Password: `admin123`

## Быстрый старт

1. **Добавить прокси** - Proxies → Add Proxy
2. **Загрузить аккаунты** - Accounts → Upload Sessions
3. **Добавить канал** - Channels → Add Channel
4. **Создать кампанию** - Campaigns → New Campaign
5. **Импорт юзеров** - В кампании → Import Users
6. **Запустить** - Start Campaign

## Структура проекта

```
mrktguru/
├── app.py              # Flask приложение
├── celery_app.py       # Celery конфигурация
├── config.py           # Настройки
├── models/             # Database models
├── routes/             # Flask routes (endpoints)
├── services/           # Business logic
├── workers/            # Celery workers
├── utils/              # Утилиты
├── templates/          # HTML шаблоны
├── static/             # CSS, JS, images
├── uploads/            # Загруженные файлы
└── logs/               # Логи
```

## Антибан меры

- Эмуляция реальных устройств (iPhone, Samsung, Xiaomi и т.д.)
- Задержки между действиями (45-90 сек)
- Лимиты на инвайты в час (5-10)
- Паузы после серий действий
- Рабочие часы (09:00-22:00)
- Warm-up период для новых аккаунтов
- Ротация мобильных прокси
- Мониторинг здоровья аккаунтов

## Стратегии

**Safe** (безопасная):
- 60-120 сек задержка
- 3-5 инвайтов/час
- Максимальная безопасность

**Normal** (обычная):
- 45-90 сек задержка
- 5-10 инвайтов/час
- Баланс скорости и безопасности

**Aggressive** (агрессивная):
- 30-60 сек задержка
- 8-15 инвайтов/час
- Быстрый рост, повышенный риск

## Troubleshooting

### FloodWait ошибка
- Аккаунт автоматически помещается в cooldown
- Снизить частоту действий
- Использовать больше аккаунтов

### Сессии не валидны
- Проверить .session файлы
- Убедиться в правильности API_ID и API_HASH
- Пройти авторизацию заново

### База данных не подключается
- Проверить DATABASE_URL
- Убедиться, что PostgreSQL запущен
- Применить миграции: `flask db upgrade`

## Лицензия

Proprietary

## Контакты

Support: [your-email]
