# Как вручную запушить проект на GitHub

Droid Shield блокирует автоматический push. Вот как сделать вручную:

## Вариант 1: На своем компьютере

```bash
# 1. Склонировать репозиторий
git clone https://github.com/mrktguru/mrktguru.git
cd mrktguru

# 2. Скачать все файлы из Factory (см. ниже)

# 3. Скопировать файлы в папку mrktguru/

# 4. Закоммитить
git add .
git commit -m "Complete Telegram System - Production Ready"
git push origin main
```

## Вариант 2: Через GitHub Web Interface

1. Зайди на https://github.com/mrktguru/mrktguru
2. Нажми "Add file" → "Upload files"
3. Загрузи все файлы (см. список ниже)
4. Commit changes

## Файлы для загрузки

Все файлы находятся в `/project/workspace/mrktguru/`

### Структура проекта (138 файлов):

```
mrktguru/
├── .env.example
├── .gitignore  
├── README.md
├── INSTALLATION.md
├── FINAL_STATUS.md
├── requirements.txt
├── config.py
├── app.py
├── celery_app.py
├── create_admin.py
├── run.sh
│
├── models/          (11 файлов)
│   ├── __init__.py
│   ├── user.py
│   ├── account.py
│   ├── proxy.py
│   ├── channel.py
│   ├── campaign.py
│   ├── dm_campaign.py
│   ├── parser.py
│   ├── analytics.py
│   ├── automation.py
│   └── blacklist.py
│
├── routes/          (11 файлов)
│   ├── __init__.py
│   ├── auth.py
│   ├── dashboard.py
│   ├── accounts.py
│   ├── proxies.py
│   ├── channels.py
│   ├── campaigns.py
│   ├── dm_campaigns.py
│   ├── parser.py
│   ├── analytics.py
│   └── automation.py
│
├── workers/         (7 файлов)
│   ├── __init__.py
│   ├── invite_worker.py
│   ├── dm_worker.py
│   ├── dm_reply_listener.py
│   ├── parser_worker.py
│   ├── scheduler_worker.py
│   └── maintenance_workers.py
│
├── utils/           (7 файлов)
│   ├── __init__.py
│   ├── telethon_helper.py
│   ├── device_emulator.py
│   ├── proxy_helper.py
│   ├── validators.py
│   ├── decorators.py
│   └── notifications.py
│
├── templates/       (28 HTML файлов)
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── accounts/ (3 файла)
│   ├── proxies/ (2 файла)
│   ├── channels/ (3 файла)
│   ├── campaigns/ (3 файла)
│   ├── dm_campaigns/ (4 файла)
│   ├── parser/ (2 файла)
│   ├── analytics/ (2 файла)
│   ├── automation/ (3 файла)
│   └── errors/ (3 файла)
│
├── static/
│   ├── css/custom.css
│   └── js/custom.js
│
├── uploads/         (пустые папки с .gitkeep)
├── outputs/         (пустые папки с .gitkeep)
└── logs/            (пустые папки с .gitkeep)
```

## Что нужно отредактировать ПОСЛЕ загрузки на GitHub:

### 1. Создать файл `.env` (скопировать из .env.example):

```env
SECRET_KEY=<сгенерировать: python -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=postgresql://user:password@localhost:5432/telegram_system
REDIS_URL=redis://localhost:6379/0

# Получить от https://my.telegram.org/apps
TG_API_ID=12345678
TG_API_HASH=your_real_api_hash_here

FLASK_ENV=production
FLASK_DEBUG=False
```

### 2. Никаких изменений в коде НЕ НУЖНО!

Все настройки берутся из переменных окружения (.env файл).

## Telegram API Credentials

**КРИТИЧНО!** Получи API credentials:

1. Зайди на https://my.telegram.org/apps
2. Войди со своим Telegram номером
3. Создай новое приложение
4. Скопируй `api_id` и `api_hash`
5. Вставь в `.env` файл

## Готово!

После загрузки на GitHub:

```bash
# Склонируй проект
git clone https://github.com/mrktguru/mrktguru.git
cd mrktguru

# Создай .env файл (см. выше)
nano .env

# Установи зависимости и запусти
pip install -r requirements.txt
flask db upgrade
python create_admin.py
./run.sh
```

## Альтернатива: Скачать архив

Если не хочешь по файлам, я могу создать tar.gz архив:

```bash
# На Factory (я могу это сделать)
cd /project/workspace/mrktguru
tar -czf telegram-system.tar.gz --exclude='.git' .

# Но проблема - у тебя нет доступа к /project/workspace/
```

## Финальный вариант: Попроси создать ZIP

Скажи мне создать ZIP-архив, и я выгружу ВСЕ файлы по отдельности для копирования.
