#!/bin/bash

echo "Starting Telegram System Workers..."

# Kill existing workers
pkill -f "celery.*worker"
pkill -f "celery.*beat"

# Wait a bit
sleep 2

# Start Celery worker
echo "Starting Celery worker..."
cd /root/mrktguru
nohup celery -A celery_app worker --loglevel=info --concurrency=4 > logs/celery_worker.log 2>&1 &

# Start Celery beat (scheduler)
echo "Starting Celery beat..."
nohup celery -A celery_app beat --loglevel=info > logs/celery_beat.log 2>&1 &

sleep 2

# Check status
echo ""
echo "Worker processes:"
ps aux | grep celery | grep -v grep

echo ""
echo "✅ Workers started!"
echo "View logs:"
echo "  - Worker: tail -f logs/celery_worker.log"
echo "  - Beat: tail -f logs/celery_beat.log"
