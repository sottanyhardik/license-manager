#!/bin/bash

# Setup SSL and Nginx Configuration
# Run this on the server: django@143.110.252.201

set -e

echo "🔧 Setting up SSL and Nginx..."

# Backup existing nginx config
if [ -f /etc/nginx/sites-available/license-manager ]; then
    echo "📋 Backing up existing nginx config..."
    sudo cp /etc/nginx/sites-available/license-manager /etc/nginx/sites-available/license-manager.backup.$(date +%Y%m%d_%H%M%S)
fi

# Install certbot if not already installed
if ! command -v certbot &> /dev/null; then
    echo "📦 Installing certbot..."
    sudo apt update
    sudo apt install -y certbot python3-certbot-nginx
fi

# Create temporary nginx config without SSL for certbot
echo "📝 Creating temporary nginx config for SSL setup..."
sudo tee /etc/nginx/sites-available/license-manager > /dev/null <<'EOF'
server {
    listen 80;
    server_name 143.110.252.201 license-manager.duckdns.org;

    client_max_body_size 100M;

    root /home/django/license-manager/frontend/dist;
    index index.html;

    location /static/ {
        alias /home/django/license-manager/backend/staticfiles/;
    }

    location /media/ {
        alias /home/django/license-manager/backend/media/;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /assets/ {
        alias /home/django/license-manager/frontend/dist/assets/;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

# Enable site if not already enabled
if [ ! -L /etc/nginx/sites-enabled/license-manager ]; then
    echo "🔗 Enabling nginx site..."
    sudo ln -s /etc/nginx/sites-available/license-manager /etc/nginx/sites-enabled/
fi

# Test nginx config
echo "✅ Testing nginx configuration..."
sudo nginx -t

# Reload nginx
echo "🔄 Reloading nginx..."
sudo systemctl reload nginx

# Obtain SSL certificate
echo "🔒 Obtaining SSL certificate from Let's Encrypt..."
echo "NOTE: Make sure license-manager.duckdns.org points to this server!"
sudo certbot --nginx -d license-manager.duckdns.org --non-interactive --agree-tos --email sottanyhardik@gmail.com --redirect

# Copy the full SSL config
echo "📝 Installing full nginx config with SSL..."
sudo cp /home/django/license-manager/nginx-config.conf /etc/nginx/sites-available/license-manager

# Test nginx config again
echo "✅ Testing final nginx configuration..."
sudo nginx -t

# Reload nginx
echo "🔄 Reloading nginx with SSL config..."
sudo systemctl reload nginx

# Setup auto-renewal
echo "⏰ Setting up SSL certificate auto-renewal..."
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

echo "✨ SSL and Nginx setup completed!"
echo ""
echo "🌐 Your site should now be accessible at:"
echo "   https://license-manager.duckdns.org"
echo "   https://143.110.252.201"
echo ""
echo "Certificate auto-renewal is enabled and will run automatically."
