#!/bin/bash

# SSL Setup Script for license-tractor.duckdns.org
# Server: django@178.128.58.219
# This script sets up Let's Encrypt SSL certificate

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOMAIN="license-tractor.duckdns.org"
SERVER_IP="178.128.58.219"
EMAIL="info@labdhimercantile.com"  # Update with your email

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}SSL Setup for $DOMAIN${NC}"
echo -e "${BLUE}================================================${NC}\n"

# Step 1: Update DNS
echo -e "${YELLOW}Step 1: Verify DNS Configuration${NC}"
echo -e "Please ensure that $DOMAIN points to $SERVER_IP"
echo -e "You can check with: ${GREEN}nslookup $DOMAIN${NC}"
read -p "Press Enter once DNS is configured correctly..."

# Step 2: Install Certbot
echo -e "\n${YELLOW}Step 2: Installing Certbot${NC}"
sudo apt update
sudo apt install -y certbot python3-certbot-nginx

# Step 3: Copy nginx configuration
echo -e "\n${YELLOW}Step 3: Setting up Nginx configuration${NC}"
sudo cp /home/django/license-manager/nginx-license-tractor.conf /etc/nginx/sites-available/license-tractor
sudo ln -sf /etc/nginx/sites-available/license-tractor /etc/nginx/sites-enabled/

# Remove default nginx config if exists
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
echo -e "${BLUE}Testing Nginx configuration...${NC}"
sudo nginx -t

# Reload nginx
echo -e "${BLUE}Reloading Nginx...${NC}"
sudo systemctl reload nginx

# Step 4: Obtain SSL Certificate
echo -e "\n${YELLOW}Step 4: Obtaining SSL Certificate from Let's Encrypt${NC}"
sudo certbot certonly --nginx \
    -d $DOMAIN \
    --email $EMAIL \
    --agree-tos \
    --non-interactive \
    --redirect

# Step 5: Update Nginx configuration to use SSL
echo -e "\n${YELLOW}Step 5: Updating Nginx configuration for HTTPS${NC}"

# Create the HTTPS-enabled configuration
cat > /tmp/nginx-license-tractor-ssl.conf << 'NGINX_CONFIG'
# Nginx configuration for license-tractor.duckdns.org with SSL
server {
    listen 80;
    server_name 178.128.58.219 license-tractor.duckdns.org;

    # Allow Let's Encrypt challenge directory
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all HTTP traffic to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name license-tractor.duckdns.org 178.128.58.219;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/license-tractor.duckdns.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/license-tractor.duckdns.org/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/license-tractor.duckdns.org/chain.pem;

    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;

    client_max_body_size 100M;
    client_body_timeout 300s;
    client_header_timeout 300s;
    send_timeout 300s;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;

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
        proxy_set_header X-Forwarded-Proto https;
        proxy_redirect off;
    }

    # Django admin
    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
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
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
}
NGINX_CONFIG

sudo mv /tmp/nginx-license-tractor-ssl.conf /etc/nginx/sites-available/license-tractor

# Test nginx configuration
echo -e "${BLUE}Testing Nginx configuration...${NC}"
sudo nginx -t

# Reload nginx
echo -e "${BLUE}Reloading Nginx...${NC}"
sudo systemctl reload nginx

# Step 6: Set up auto-renewal
echo -e "\n${YELLOW}Step 6: Setting up automatic certificate renewal${NC}"
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

echo -e "\n${GREEN}================================================${NC}"
echo -e "${GREEN}SSL Setup Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo -e "\n${BLUE}Your site is now available at:${NC}"
echo -e "  ${GREEN}https://$DOMAIN${NC}\n"

echo -e "${BLUE}Certificate will auto-renew. Check renewal timer with:${NC}"
echo -e "  ${GREEN}sudo systemctl status certbot.timer${NC}\n"

echo -e "${BLUE}Test certificate renewal with:${NC}"
echo -e "  ${GREEN}sudo certbot renew --dry-run${NC}\n"
