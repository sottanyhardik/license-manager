#!/bin/bash

# License Manager Deployment Script
# Run this script on the production server after SSH

set -e  # Exit on error

echo "🚀 Starting deployment..."

# Navigate to project directory
cd /var/www/license-manager

# Pull latest changes
echo "📥 Pulling latest code from git..."
git pull origin develop

# Backend updates
echo "🐍 Updating Python dependencies..."
source venv/bin/activate
cd backend
pip install -r requirements.txt

# Run migrations
echo "🗄️  Running database migrations..."
python manage.py migrate

# Frontend build
echo "⚛️  Building frontend..."
cd ../frontend
npm install
npm run build

# Collect static files
echo "📦 Collecting static files..."
cd ../backend
python manage.py collectstatic --noinput

# Set permissions
echo "🔐 Setting permissions..."
sudo chown -R www-data:www-data /var/www/license-manager/media
sudo chmod -R 775 /var/www/license-manager/media

# Restart services
echo "🔄 Restarting services..."
sudo systemctl restart license-manager
sudo systemctl restart nginx

# Check status
echo "✅ Checking service status..."
sudo systemctl status license-manager --no-pager
sudo systemctl status nginx --no-pager

echo "✨ Deployment completed successfully!"
echo "🌐 Application should be live at: https://license-manager.duckdns.org"
