# Telegram System - Installation & Startup Guide

## 🚀 QUICK START

### 1. Configure Telegram API
```bash
nano /root/mrktguru/.env
```

Add your Telegram API credentials:
```
TG_API_ID=12345678
TG_API_HASH=your_api_hash_here
```

Get them from: https://my.telegram.org/apps

### 2. Start Services

**Start Flask:**
```bash
cd /root/mrktguru
pkill -f flask
nohup python3 -m flask run --host=0.0.0.0 --port=8080 > flask.log 2>&1 &
```

**Start Celery Workers:**
```bash
cd /root/mrktguru
./START_WORKERS.sh
```

### 3. Access System
Open in browser: http://38.244.194.181:8080

Login:
- Username: `gommeux`
- Password: `Person12!`

---

## 📋 FULL INSTALLATION

### Prerequisites
- Python 3.10+
- PostgreSQL or SQLite
- Redis

### Step 1: Install Dependencies
```bash
cd /root/mrktguru
pip install -r requirements.txt
```

### Step 2: Configure Environment
```bash
cp .env.example .env
nano .env
```

Required variables:
```
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:////root/mrktguru/instance/telegram_system.db
REDIS_URL=redis://localhost:6379/0
TG_API_ID=your_api_id
TG_API_HASH=your_api_hash
```

### Step 3: Initialize Database
```bash
cd /root/mrktguru
python3 << EOF
from app import create_app
from database import db

app = create_app()
with app.app_context():
    db.create_all()
    print("✅ Database created")
