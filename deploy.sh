#!/bin/bash
# Deployment script for MRKTGURU production server

set -e

echo "🚀 Starting deployment to production..."

# Pull latest changes from GitHub
echo "📥 Pulling latest code from GitHub..."
ssh mrktguru "cd ~/mrktguru && git pull origin main"

# Install/update dependencies if requirements changed
echo "📦 Checking dependencies..."
ssh mrktguru "cd ~/mrktguru && source venv/bin/activate && pip install -r requirements.txt --quiet"

# Run migrations if any
echo "🔄 Running database migrations..."
ssh mrktguru "cd ~/mrktguru && source venv/bin/activate && flask db upgrade"

# Restart services
echo "🔄 Restarting services..."
ssh mrktguru "systemctl restart mrktguru-web.service && systemctl restart mrktguru-worker.service && systemctl restart mrktguru-beat.service"

# Check services status
echo "✅ Checking services status..."
ssh mrktguru "systemctl is-active mrktguru-web.service mrktguru-worker.service mrktguru-beat.service"

echo "✨ Deployment completed successfully!"
