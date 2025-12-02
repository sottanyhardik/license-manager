#!/bin/bash

# Quick fix for nginx static files 404
# Run this on the server: django@143.110.252.201

set -e

echo "🔧 Fixing nginx configuration for static files..."

# Backup existing config
sudo cp /etc/nginx/sites-available/license-manager /etc/nginx/sites-available/license-manager.backup.$(date +%Y%m%d_%H%M%S)

# Update nginx config
sudo tee /etc/nginx/sites-available/license-manager > /dev/null <<'EOF'
server {
    listen 80;
    server_name 143.110.252.201 license-manager.duckdns.org;

    client_max_body_size 100M;

    # Frontend (React/Vite build)
    root /home/django/license-manager/frontend/dist;
    index index.html;

    # Static files (Django admin, DRF, etc.)
    location /static/ {
        alias /home/django/license-manager/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files (uploads, PDFs, etc.)
    location /media/ {
        alias /home/django/license-manager/backend/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # Django API endpoints
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Django admin
    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Frontend assets (JS, CSS from Vite build)
    location /assets/ {
        alias /home/django/license-manager/frontend/dist/assets/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Frontend routes - serve index.html for all other routes
    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

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
