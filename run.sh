#!/bin/bash

# Start script for Telegram System

echo "Starting Telegram System..."

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start Flask app in background
echo "Starting Flask app on port 8081..."
PORT=8081 python3 app.py &
FLASK_PID=$!

# Start Celery worker
# Start Celery worker
echo "Starting Celery worker..."
python3 -m celery -A celery_app worker --loglevel=info &
WORKER_PID=$!

# Start Celery beat
echo "Starting Celery beat..."
python3 -m celery -A celery_app beat --loglevel=info &
BEAT_PID=$!

echo "All services started!"
echo "Flask PID: $FLASK_PID"
echo "Worker PID: $WORKER_PID"
echo "Beat PID: $BEAT_PID"
echo ""
echo "Access the app at: http://localhost:8081"
echo ""
echo "To stop all services, run: kill $FLASK_PID $WORKER_PID $BEAT_PID"

# Wait for any process to exit
wait $FLASK_PID

# Exit with status of process that exited first
exit $?
