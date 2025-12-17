#!/bin/bash

# Start script for Telegram System

echo "Starting Telegram System..."

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start Flask app in background
echo "Starting Flask app..."
python app.py &
FLASK_PID=$!

# Start Celery worker
echo "Starting Celery worker..."
celery -A celery_app worker --loglevel=info &
WORKER_PID=$!

# Start Celery beat
echo "Starting Celery beat..."
celery -A celery_app beat --loglevel=info &
BEAT_PID=$!

echo "All services started!"
echo "Flask PID: $FLASK_PID"
echo "Worker PID: $WORKER_PID"
echo "Beat PID: $BEAT_PID"
echo ""
echo "Access the app at: http://localhost:5000"
echo ""
echo "To stop all services, run: kill $FLASK_PID $WORKER_PID $BEAT_PID"

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?
