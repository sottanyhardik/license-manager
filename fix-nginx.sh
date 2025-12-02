#!/bin/bash

# Quick fix for nginx static files 404
# Run this on the server: django@143.110.252.201

set -e

echo "🔧 Fixing nginx configuration for static files..."

# Backup existing config if exists
if [ -f /etc/nginx/sites-available/license-manager ]; then
    sudo cp /etc/nginx/sites-available/license-manager /etc/nginx/sites-available/license-manager.backup.$(date +%Y%m%d_%H%M%S)
fi

# Use the HTTP-only config file
sudo cp /home/django/license-manager/nginx-http-only.conf /etc/nginx/sites-available/license-manager

# Enable site if not already enabled
if [ ! -L /etc/nginx/sites-enabled/license-manager ]; then
    echo "🔗 Enabling site..."
    sudo ln -s /etc/nginx/sites-available/license-manager /etc/nginx/sites-enabled/
fi

# Test nginx config
echo "✅ Testing nginx configuration..."
sudo nginx -t

# Reload nginx
echo "🔄 Reloading nginx..."
sudo systemctl reload nginx

echo "✨ Nginx configuration fixed!"
echo "🌐 Try accessing: http://143.110.252.201"
echo ""
echo "⚠️  Note: You're still using HTTP. Run 'bash setup-ssl.sh' to enable HTTPS."
