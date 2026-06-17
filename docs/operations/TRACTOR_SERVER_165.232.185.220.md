# License Tractor Server Setup - 165.232.185.220

## Server Information
- **IP Address:** 165.232.185.220
- **Domain:** license-tractor.duckdns.org
- **User:** django
- **Hostname:** license-tractor
- **SSH:** `ssh django@165.232.185.220`

## Configuration Updates ✅

### 1. Django Settings Updated
- Added `165.232.185.220` to `ALLOWED_HOSTS`
- Added `license-tractor.duckdns.org` to `ALLOWED_HOSTS`
- Added to `CORS_ALLOWED_ORIGINS`
- Added to `CSRF_TRUSTED_ORIGINS`

### 2. Nginx Configuration Created
- File: `nginx-tractor-http.conf`
- HTTP only (no SSL)
- Configured for both IP and domain

### 3. Auto-Deploy Script Updated
- Added `165.232.185.220` to SERVERS array
- Will automatically deploy to this server

## Quick Deployment

### Option 1: Use Auto-Deploy Script (Recommended)

```bash
# Deploy to all servers including new one
./auto-deploy.sh
```

### Option 2: Manual Deployment

```bash
# SSH to server
ssh django@165.232.185.220

# Upload nginx config
scp nginx-tractor-http.conf django@165.232.185.220:/tmp/

# On server, configure nginx
ssh django@165.232.185.220 << 'EOF'
echo 'admin' | sudo -S mv /tmp/nginx-tractor-http.conf /etc/nginx/sites-available/license-manager
echo 'admin' | sudo -S ln -sf /etc/nginx/sites-available/license-manager /etc/nginx/sites-enabled/
echo 'admin' | sudo -S rm -f /etc/nginx/sites-enabled/default
echo 'admin' | sudo -S nginx -t
echo 'admin' | sudo -S systemctl reload nginx
EOF

# Run regular deployment
./auto-deploy.sh
```

## Nginx Configuration Details

The configuration includes:
- **Server Names:** `165.232.185.220`, `license-tractor.duckdns.org`
- **Protocol:** HTTP only (port 80)
- **Root:** `/home/django/license-manager/frontend/dist`
- **Static Files:** `/home/django/license-manager/backend/staticfiles/`
- **Media Files:** `/home/django/license-manager/backend/media/`
- **API Proxy:** Forwards to Django on `127.0.0.1:8000`
- **File Upload Limit:** 100MB
- **Timeouts:** 300s for all operations

## Access URLs

After deployment:
- **HTTP:** http://165.232.185.220
- **Domain:** http://license-tractor.duckdns.org
- **API:** http://165.232.185.220/api/
- **Admin:** http://165.232.185.220/admin/

## Verification Steps

### 1. Test SSH Access
```bash
ssh django@165.232.185.220 "echo 'SSH working'; hostname"
```

### 2. Check if Application Exists
```bash
ssh django@165.232.185.220 "ls -la /home/django/license-manager"
```

### 3. Deploy Application
```bash
./auto-deploy.sh
```

### 4. Test API
```bash
curl http://165.232.185.220/api/licenses/?page_size=1
```

### 5. Test Domain (if DNS configured)
```bash
curl http://license-tractor.duckdns.org/api/licenses/?page_size=1
```

## DNS Configuration

To use the domain `license-tractor.duckdns.org`:

1. **Login to DuckDNS:** https://www.duckdns.org/
2. **Update license-tractor subdomain:**
   - Point to: `165.232.185.220`
3. **Verify DNS:**
   ```bash
   nslookup license-tractor.duckdns.org
   dig license-tractor.duckdns.org
   ```

## SSL/HTTPS Setup (Optional - Future)

If you want to add SSL later:

```bash
ssh django@165.232.185.220

# Install certbot
echo 'admin' | sudo -S apt install -y certbot python3-certbot-nginx

# Obtain certificate
echo 'admin' | sudo -S certbot --nginx \
    -d license-tractor.duckdns.org \
    --email info@labdhimercantile.com \
    --agree-tos \
    --non-interactive

# Update Django settings to enable HTTPS
# Edit .env:
# SECURE_SSL_REDIRECT=True
# SESSION_COOKIE_SECURE=True
# CSRF_COOKIE_SECURE=True

# Restart services
echo 'admin' | sudo -S supervisorctl restart license-manager
echo 'admin' | sudo -S systemctl reload nginx
```

## Troubleshooting

### Nginx Not Working
```bash
ssh django@165.232.185.220
echo 'admin' | sudo -S nginx -t
echo 'admin' | sudo -S systemctl status nginx
echo 'admin' | sudo -S tail -f /var/log/nginx/error.log
```

### Application Not Starting
```bash
ssh django@165.232.185.220
echo 'admin' | sudo -S supervisorctl status
echo 'admin' | sudo -S supervisorctl tail -f license-manager
tail -f /home/django/license-manager/logs/*.log
```

### Check Services
```bash
ssh django@165.232.185.220 << 'EOF'
echo "=== Supervisor ==="
echo 'admin' | sudo -S supervisorctl status

echo "=== Nginx ==="
echo 'admin' | sudo -S systemctl status nginx --no-pager | head -10

echo "=== PostgreSQL ==="
echo 'admin' | sudo -S systemctl status postgresql --no-pager | head -10

echo "=== Redis ==="
echo 'admin' | sudo -S systemctl status redis --no-pager | head -10
EOF
```

## Files Modified

1. **backend/lmanagement/settings.py**
   - Line 23: Added `165.232.185.220` to `ALLOWED_HOSTS`
   - Line 23: `license-tractor.duckdns.org` already present
   - Line 233: Added to `CORS_ALLOWED_ORIGINS`
   - Line 280: Added to `CSRF_TRUSTED_ORIGINS`

2. **auto-deploy.sh**
   - Line 24: Updated `SERVERS` array

3. **nginx-tractor-http.conf** (NEW)
   - Complete HTTP-only nginx configuration

## Summary

✅ Django settings updated with new IP and domain
✅ Nginx configuration created (HTTP only)
✅ Auto-deploy script updated
✅ SSH access verified
✅ Ready for deployment

Run `./auto-deploy.sh` to deploy to all servers including this new one!
