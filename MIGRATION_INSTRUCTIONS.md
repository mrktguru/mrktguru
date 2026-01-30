# Инструкция по миграции базы данных на сервере

## Проблема
Ошибка: `no such column: accounts.last_sync_at`

## Решение (PostgreSQL)

### Шаг 1: Подключиться к серверу
```bash
ssh root@your-server
```

### Шаг 2: Перейти в директорию проекта
```bash
cd ~/mrktguru
```

### Шаг 3: Обновить код из Git
```bash
git pull origin antigravity_v02
```

### Шаг 4: Выполнить миграцию (PostgreSQL)

**Вариант A: Использовать Python-скрипт**
```bash
python3 migrate_add_last_sync_at_postgres.py
```

**Вариант B: Использовать SQL напрямую**
```bash
# Проверьте переменную DATABASE_URL
echo $DATABASE_URL

# Выполните SQL-миграцию
psql $DATABASE_URL -f migrations/add_last_sync_at_postgres.sql
```

**Вариант C: Через psql вручную**
```bash
# Подключитесь к базе
psql $DATABASE_URL

# Выполните команду
ALTER TABLE accounts ADD COLUMN last_sync_at TIMESTAMP;

# Выйдите
\q
```

### Шаг 5: Перезапустить веб-сервис
```bash
systemctl restart mrktguru-web
```

### Шаг 6: Проверить статус
```bash
systemctl status mrktguru-web
```

### Шаг 7: Проверить логи
```bash
journalctl -u mrktguru-web -n 50 --no-pager
```

## Примечание

Приложение использует **PostgreSQL**, а не SQLite. Убедитесь, что переменная окружения `DATABASE_URL` правильно настроена в файле `.env` или в systemd service файле.

