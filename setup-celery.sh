#!/bin/bash

# Setup Celery with Supervisor
# Run this on the server: django@143.110.252.201

set -e

echo "🔧 Setting up Celery with Supervisor..."

# Create logs directory if it doesn't exist
mkdir -p /home/django/license-manager/logs

# Copy supervisor config for celery
echo "📋 Installing Celery supervisor config..."
sudo cp /home/django/license-manager/supervisord-celery.conf /etc/supervisor/conf.d/license-manager-celery.conf

# Reload supervisor to read new config
echo "🔄 Reloading supervisor..."
sudo supervisorctl reread
sudo supervisorctl update

# Start celery services
echo "🚀 Starting Celery worker and beat..."
sudo supervisorctl start license-manager-celery
sudo supervisorctl start license-manager-celery-beat

# Check status
echo "✅ Checking Celery status..."
sudo supervisorctl status license-manager-celery
sudo supervisorctl status license-manager-celery-beat

echo "✨ Celery setup completed!"
echo ""
echo "Useful commands:"
echo "  - Check status: sudo supervisorctl status"
echo "  - Restart worker: sudo supervisorctl restart license-manager-celery"
echo "  - Restart beat: sudo supervisorctl restart license-manager-celery-beat"
echo "  - View logs: tail -f /home/django/license-manager/logs/celery.log"
