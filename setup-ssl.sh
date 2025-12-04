#!/bin/bash

# SSL Setup Script for License Manager
# Server: 143.110.252.201
# Domain: license-manager.duckdns.org

set -e

echo "========================================="
echo "SSL Setup for License Manager"
echo "========================================="
echo "Started at: $(date)"
echo ""

# Step 1: Backup current nginx config
echo "[1/6] Backing up current nginx configuration..."
sudo cp /etc/nginx/sites-available/license-manager /etc/nginx/sites-available/license-manager.backup.$(date +%Y%m%d_%H%M%S)

# Step 2: Create temporary HTTP-only config
echo "[2/6] Creating temporary HTTP-only nginx config..."
sudo tee /etc/nginx/sites-available/license-manager-temp > /dev/null <<'EOF'
server {
    listen 80;
    server_name 143.110.252.201 license-manager.duckdns.org;

    # Allow Let's Encrypt challenge directory
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Proxy other requests to Django
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Step 3: Enable temporary config and remove SSL config
echo "[3/6] Enabling temporary HTTP-only config..."
sudo rm -f /etc/nginx/sites-enabled/license-manager
sudo rm -f /etc/nginx/sites-enabled/lmanagement
sudo ln -sf /etc/nginx/sites-available/license-manager-temp /etc/nginx/sites-enabled/

# Test nginx config
echo "Testing nginx configuration..."
sudo nginx -t

# Start nginx
echo "Starting nginx..."
sudo systemctl start nginx
sudo systemctl enable nginx

# Step 4: Create webroot directory for Let's Encrypt
echo "[4/6] Creating webroot directory..."
sudo mkdir -p /var/www/html
sudo chown -R www-data:www-data /var/www/html

# Step 5: Obtain SSL certificate
echo "[5/6] Obtaining SSL certificate from Let's Encrypt..."
echo "This will request certificates for:"
echo "  - 143.110.252.201"
echo "  - license-manager.duckdns.org"
echo ""

sudo certbot certonly \
    --webroot \
    --webroot-path=/var/www/html \
    --email hardik@labdhimercantile.com \
    --agree-tos \
    --no-eff-email \
    -d license-manager.duckdns.org

# Step 6: Create final SSL-enabled nginx config
echo "[6/6] Creating SSL-enabled nginx configuration..."
sudo tee /etc/nginx/sites-available/license-manager > /dev/null <<'EOF'
# HTTP - Redirect to HTTPS
server {
    listen 80;
    server_name 143.110.252.201 license-manager.duckdns.org;

    # Allow Let's Encrypt renewals
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all other HTTP traffic to HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS - Main configuration
server {
    listen 443 ssl http2;
    server_name 143.110.252.201 license-manager.duckdns.org;

    # SSL Certificate
    ssl_certificate /etc/letsencrypt/live/license-manager.duckdns.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/license-manager.duckdns.org/privkey.pem;

    # SSL Configuration (Mozilla Intermediate)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # SSL Session
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;

    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    ssl_trusted_certificate /etc/letsencrypt/live/license-manager.duckdns.org/chain.pem;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;

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
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
}
EOF

# Enable SSL config
echo "Enabling SSL configuration..."
sudo rm -f /etc/nginx/sites-enabled/license-manager-temp
sudo ln -sf /etc/nginx/sites-available/license-manager /etc/nginx/sites-enabled/

# Test nginx config
echo "Testing nginx configuration..."
sudo nginx -t

# Reload nginx
echo "Reloading nginx..."
sudo systemctl reload nginx

echo ""
echo "========================================="
echo "✅ SSL Setup Complete!"
echo "========================================="
echo "Certificates installed for:"
echo "  - 143.110.252.201"
echo "  - license-manager.duckdns.org"
echo ""
echo "Certificate location:"
echo "  /etc/letsencrypt/live/license-manager.duckdns.org/"
echo ""
echo "Auto-renewal:"
echo "  Certbot will automatically renew certificates"
echo "  Test renewal: sudo certbot renew --dry-run"
echo ""
echo "Your site should now be accessible via HTTPS:"
echo "  - https://143.110.252.201"
echo "  - https://license-manager.duckdns.org"
echo ""
