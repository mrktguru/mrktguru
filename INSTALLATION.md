# Установка и настройка

Пошаговая инструкция по установке Telegram System на чистый сервер.

## Шаг 1: Установка PostgreSQL

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# Запуск PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Создание базы данных
sudo -u postgres psql
postgres=# CREATE DATABASE telegram_system;
postgres=# CREATE USER telegram_user WITH PASSWORD 'your_password';
postgres=# GRANT ALL PRIVILEGES ON DATABASE telegram_system TO telegram_user;
postgres=# \q
```

## Шаг 2: Установка Redis

```bash
# Ubuntu/Debian
sudo apt install redis-server

# Запуск Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Проверка
redis-cli ping
# Должно вернуть: PONG
```

## Шаг 3: Установка Python и зависимостей

```bash
# Установка Python 3.9+
sudo apt install python3 python3-pip python3-venv

# Клонирование репозитория
git clone <your-repo-url>
cd mrktguru

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

## Шаг 4: Получение Telegram API credentials

1. Перейти на https://my.telegram.org/apps
2. Авторизоваться с вашим Telegram аккаунтом
3. Создать новое приложение
4. Сохранить `api_id` и `api_hash`

## Шаг 5: Конфигурация

```bash
# Копировать .env файл
cp .env.example .env

# Отредактировать .env
nano .env
```

Заполнить обязательные параметры:

```env
# Секретный ключ (сгенерировать: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your_generated_secret_key

# База данных
DATABASE_URL=postgresql://telegram_user:your_password@localhost:5432/telegram_system

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram API (КРИТИЧНО!)
TG_API_ID=12345678
TG_API_HASH=your_api_hash_from_telegram

# Окружение
FLASK_ENV=production
FLASK_DEBUG=False
```

## Шаг 6: Инициализация базы данных

```bash
# Применить миграции
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# Создать администратора
python create_admin.py
```

По умолчанию:
- Username: `admin`
- Password: `admin123`

**ВАЖНО:** Смените пароль после первого входа!

## Шаг 7: Подготовка Telegram аккаунтов

### Вариант A: Использование существующих .session файлов

Если у вас уже есть `.session` файлы от Telethon:

```bash
# Скопировать в uploads/sessions/
cp /path/to/your/*.session uploads/sessions/
```

### Вариант B: Создание новых сессий

Создать скрипт `generate_session.py`:

```python
from telethon.sync import TelegramClient

API_ID = 12345678  # Ваш API ID
API_HASH = 'your_api_hash'  # Ваш API Hash
PHONE = '+1234567890'  # Номер телефона

client = TelegramClient(f'uploads/sessions/{PHONE}', API_ID, API_HASH)
client.start(phone=PHONE)
print(f"Session created: {PHONE}.session")
client.disconnect()
```

Запустить:
```bash
python generate_session.py
# Следовать инструкциям (ввести код из Telegram)
```

## Шаг 8: Настройка прокси (опционально, но рекомендуется)

Прокси критичны для избежания банов. Рекомендуется использовать мобильные прокси.

**Формат прокси:**
```
socks5://username:password@host:port
http://username:password@host:port
```

Добавить через веб-интерфейс: Proxies → Add Proxy

**Мобильные прокси с ротацией:**
Укажите `rotation_url` для автоматической смены IP.

## Шаг 9: Запуск приложения

### Вариант A: Простой запуск (для тестирования)

```bash
./run.sh
```

### Вариант B: Production с systemd

Создать файлы systemd service:

**1. Flask app (`/etc/systemd/system/telegram-flask.service`):**

```ini
[Unit]
Description=Telegram System Flask App
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/mrktguru
Environment="PATH=/path/to/mrktguru/venv/bin"
ExecStart=/path/to/mrktguru/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**2. Celery worker (`/etc/systemd/system/telegram-worker.service`):**

```ini
[Unit]
Description=Telegram System Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/mrktguru
Environment="PATH=/path/to/mrktguru/venv/bin"
ExecStart=/path/to/mrktguru/venv/bin/celery -A celery_app worker --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

**3. Celery beat (`/etc/systemd/system/telegram-beat.service`):**

```ini
[Unit]
Description=Telegram System Celery Beat
After=network.target redis.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/mrktguru
Environment="PATH=/path/to/mrktguru/venv/bin"
ExecStart=/path/to/mrktguru/venv/bin/celery -A celery_app beat --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

**Запустить сервисы:**

```bash
sudo systemctl daemon-reload
sudo systemctl start telegram-flask
sudo systemctl start telegram-worker
sudo systemctl start telegram-beat

# Включить автозапуск
sudo systemctl enable telegram-flask
sudo systemctl enable telegram-worker
sudo systemctl enable telegram-beat

# Проверить статус
sudo systemctl status telegram-flask
sudo systemctl status telegram-worker
sudo systemctl status telegram-beat
```

## Шаг 10: Настройка Nginx (опционально)

Для production рекомендуется использовать Nginx как reverse proxy.

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Шаг 11: Доступ к приложению

Открыть браузер:
```
http://your-server-ip:5000
или
http://your-domain.com (если настроен Nginx)
```

Войти с учетными данными:
- Username: `admin`
- Password: `admin123`

## Проверка работы

1. **Dashboard** - Должна отображаться статистика
2. **Accounts** - Загрузить .session файлы
3. **Proxies** - Добавить и протестировать прокси
4. **Channels** - Добавить канал
5. **Campaigns** - Создать тестовую кампанию

## Мониторинг

### Проверка логов

```bash
# Flask app
tail -f logs/app.log

# Celery worker
journalctl -u telegram-worker -f

# Celery beat
journalctl -u telegram-beat -f
```

### Проверка сервисов

```bash
# PostgreSQL
sudo systemctl status postgresql

# Redis
sudo systemctl status redis-server

# Flask
sudo systemctl status telegram-flask

# Workers
sudo systemctl status telegram-worker
sudo systemctl status telegram-beat
```

## Troubleshooting

### PostgreSQL не запускается
```bash
sudo journalctl -u postgresql
sudo pg_isready
```

### Redis не отвечает
```bash
redis-cli ping
sudo systemctl restart redis-server
```

### Celery не видит задачи
```bash
# Проверить подключение к Redis
celery -A celery_app inspect active
```

### Ошибки миграции БД
```bash
# Сбросить миграции (ОСТОРОЖНО: удалит данные!)
rm -rf migrations/
flask db init
flask db migrate
flask db upgrade
```

## Безопасность

1. **Сменить пароль admin** после первого входа
2. **Использовать сильный SECRET_KEY**
3. **Настроить firewall:**
   ```bash
   sudo ufw allow 22   # SSH
   sudo ufw allow 80   # HTTP
   sudo ufw allow 443  # HTTPS
   sudo ufw enable
   ```
4. **Регулярные бэкапы БД:**
   ```bash
   pg_dump telegram_system > backup_$(date +%Y%m%d).sql
   ```

## Обновление

```bash
cd /path/to/mrktguru
git pull
source venv/bin/activate
pip install -r requirements.txt
flask db migrate
flask db upgrade
sudo systemctl restart telegram-flask telegram-worker telegram-beat
```

---

**Готово!** Система установлена и готова к работе.
