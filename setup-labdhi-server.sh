#!/bin/bash

# Complete Setup Script for License Manager on 139.59.92.226
# Domain: labdhi.duckdns.org
# This script configures supervisor, nginx, and SSL

set -e

echo "========================================="
echo "License Manager Setup - Labdhi Server"
echo "========================================="
echo "Server: 139.59.92.226"
echo "Domain: labdhi.duckdns.org"
echo "Started at: $(date)"
echo ""

# Step 1: Update Supervisor Configuration
echo "[1/7] Updating supervisor configuration..."
sudo tee /etc/supervisor/conf.d/lmanagement.conf > /dev/null <<'EOF'
[program:license-manager]
command=/home/django/license-manager/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:8000 lmanagement.wsgi:application
directory=/home/django/license-manager/backend
user=django
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/lmanagement.log
environment=PATH="/home/django/license-manager/venv/bin",DB_NAME="lmanagement",DB_USER="lmanagement",DB_PASS="lmanagement",DB_HOST="localhost",DB_PORT="5432",ALLOWED_HOSTS="127.0.0.1,localhost,139.59.92.226,labdhi.duckdns.org,143.110.252.201,license-manager.duckdns.org",DEBUG="False",SECRET_KEY="django-insecure-your-secret-key-here"
EOF

echo "✅ Supervisor config updated"

# Step 2: Reload and restart supervisor services
echo "[2/7] Reloading supervisor..."
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart license-manager
sudo supervisorctl restart license-manager-celery || true
sudo supervisorctl restart license-manager-celery-beat || true

echo "✅ Supervisor services restarted"
sleep 3

# Step 3: Verify gunicorn is running
echo "[3/7] Verifying gunicorn..."
if ps aux | grep -q "[g]unicorn.*lmanagement.wsgi"; then
    echo "✅ Gunicorn is running"
    ps aux | grep gunicorn | grep -v grep | head -3
else
    echo "❌ ERROR: Gunicorn not running"
    exit 1
fi

# Step 4: Test gunicorn response
echo "[4/7] Testing gunicorn response..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 | grep -q "200\|302\|301"; then
    echo "✅ Gunicorn is responding on port 8000"
else
    echo "⚠️  WARNING: Gunicorn may not be responding correctly"
fi

# Step 5: Configure temporary HTTP-only nginx
echo "[5/7] Configuring nginx (HTTP-only for now)..."
sudo tee /etc/nginx/sites-available/license-manager > /dev/null <<'EOF'
server {
    listen 80;
    server_name 139.59.92.226 labdhi.duckdns.org;

    # Allow Let's Encrypt challenge directory
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

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

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
}
EOF

# Enable nginx site
echo "Enabling nginx site..."
sudo rm -f /etc/nginx/sites-enabled/*
sudo ln -sf /etc/nginx/sites-available/license-manager /etc/nginx/sites-enabled/

# Test nginx config
echo "Testing nginx configuration..."
sudo nginx -t

# Step 6: Start nginx
echo "[6/7] Starting nginx..."
sudo mkdir -p /var/www/html
sudo chown -R www-data:www-data /var/www/html
sudo systemctl start nginx
sudo systemctl enable nginx

if sudo systemctl is-active --quiet nginx; then
    echo "✅ Nginx is running"
else
    echo "❌ ERROR: Nginx failed to start"
    exit 1
fi

# Step 7: Test external access
echo "[7/7] Testing HTTP access..."
sleep 2
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://139.59.92.226 || echo "000")
if [ "$HTTP_CODE" == "200" ] || [ "$HTTP_CODE" == "301" ] || [ "$HTTP_CODE" == "302" ]; then
    echo "✅ Server is accessible via HTTP"
else
    echo "⚠️  HTTP returned: $HTTP_CODE"
fi

echo ""
echo "========================================="
echo "✅ Basic Setup Complete!"
echo "========================================="
echo ""
echo "Service Status:"
echo "---------------"
sudo supervisorctl status | grep license-manager
echo ""
echo "Nginx: $(sudo systemctl is-active nginx)"
echo ""
echo "Your server is now accessible at:"
echo "  - http://139.59.92.226"
echo "  - http://labdhi.duckdns.org"
echo ""
echo "Next Steps:"
echo "  1. Verify HTTP access works"
echo "  2. Run SSL setup: sudo bash setup-ssl-labdhi.sh"
echo ""
