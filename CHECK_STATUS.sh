#!/bin/bash

echo "================================"
echo "   TELEGRAM SYSTEM STATUS"
echo "================================"
echo ""

# Flask
echo "📱 Flask Application:"
if ps aux | grep -q "[p]ython3.*flask"; then
    echo "   ✅ Running on port 8080"
    PORT_CHECK=$(netstat -tulpn | grep :8080)
    echo "   $PORT_CHECK"
else
    echo "   ❌ Not running"
fi
echo ""

# Redis
echo "💾 Redis:"
if redis-cli ping > /dev/null 2>&1; then
    echo "   ✅ Running"
else
    echo "   ❌ Not running"
fi
echo ""

# Celery Workers
echo "⚙️  Celery Workers:"
WORKER_COUNT=$(ps aux | grep "celery.*worker" | grep -v grep | wc -l)
if [ $WORKER_COUNT -gt 0 ]; then
    echo "   ✅ $WORKER_COUNT worker(s) running"
else
    echo "   ❌ No workers running"
fi
echo ""

# Celery Beat
echo "⏰ Celery Beat (Scheduler):"
if ps aux | grep -q "celery.*beat"; then
    echo "   ✅ Running"
else
    echo "   ❌ Not running"
fi
echo ""

# Database
echo "🗄️  Database:"
if [ -f "/root/mrktguru/instance/telegram_system.db" ]; then
    SIZE=$(du -h /root/mrktguru/instance/telegram_system.db | cut -f1)
    echo "   ✅ SQLite database exists ($SIZE)"
else
    echo "   ❌ Database not found"
fi
echo ""

# Logs
echo "📝 Recent Logs:"
if [ -f "/root/mrktguru/flask.log" ]; then
    echo "   Flask: $(tail -1 /root/mrktguru/flask.log)"
fi
if [ -f "/root/mrktguru/logs/celery_worker.log" ]; then
    echo "   Worker: $(tail -1 /root/mrktguru/logs/celery_worker.log 2>/dev/null || echo No logs yet)"
fi
echo ""

echo "================================"
echo "Access: http://38.244.194.181:8080"
echo "Login: gommeux / Person12!"
echo "================================"
