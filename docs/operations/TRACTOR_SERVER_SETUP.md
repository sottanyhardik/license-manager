# License Tractor Server Setup Guide

## Server Information
- **Domain**: license-tractor.duckdns.org
- **IP Address**: 178.128.58.219
- **User**: django
- **SSH**: `ssh django@178.128.58.219`

## Files Updated
1. **backend/lmanagement/settings.py** - Added 178.128.58.219 to ALLOWED_HOSTS
2. **auto-deploy.sh** - Updated server list with new IP
3. **nginx-license-tractor.conf** - New nginx configuration file
4. **setup-ssl-tractor.sh** - SSL setup script for Let's Encrypt

## Deployment Steps

### Step 1: Initial Server Setup
Connect to the server and ensure basic requirements are installed:

```bash
ssh django@178.128.58.219

# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3-pip python3-venv postgresql postgresql-contrib nginx supervisor redis-server git nodejs npm
```

### Step 2: Clone Repository
```bash
cd /home/django
git clone <your-repo-url> license-manager
cd license-manager
git checkout master
```

### Step 3: Setup Python Environment
```bash
cd /home/django/license-manager
python3 -m venv venv
source venv/bin/activate
cd backend
pip install -r requirements.txt
```

### Step 4: Configure Database
```bash
# Create PostgreSQL database and user
sudo -u postgres psql

# In PostgreSQL prompt:
CREATE DATABASE lmanagement;
CREATE USER lmanagement WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE lmanagement TO lmanagement;
ALTER DATABASE lmanagement OWNER TO lmanagement;
\q
```

### Step 5: Configure Environment Variables
Create a `.env` file in `/home/django/license-manager/backend/`:

```bash
cat > /home/django/license-manager/backend/.env << 'EOF'
DEBUG=False
DJANGO_SECRET_KEY=your-super-secret-key-here
DB_NAME=lmanagement
DB_USER=lmanagement
DB_PASS=your_secure_password
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://127.0.0.1:6379/0
ALLOWED_HOSTS=127.0.0.1,localhost,178.128.58.219,license-tractor.duckdns.org
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
EOF
```

### Step 6: Build Frontend
```bash
cd /home/django/license-manager/frontend
npm install
npm run build
```

### Step 7: Setup Django
```bash
cd /home/django/license-manager/backend
source /home/django/license-manager/venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

### Step 8: Configure Supervisor
Copy the supervisor configuration:

```bash
sudo cp /home/django/license-manager/backend/setup/supervisord.conf /etc/supervisor/conf.d/license-manager.conf

# Update the configuration if needed
sudo nano /etc/supervisor/conf.d/license-manager.conf

# Reload supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start license-manager
```

### Step 9: Configure Nginx (HTTP Only - Before SSL)
```bash
# Copy nginx configuration
sudo cp /home/django/license-manager/nginx-license-tractor.conf /etc/nginx/sites-available/license-tractor

# Create symlink
sudo ln -s /etc/nginx/sites-available/license-tractor /etc/nginx/sites-enabled/

# Remove default configuration
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

### Step 10: Setup Let's Encrypt SSL
Before running this step, ensure:
1. DNS is properly configured (license-tractor.duckdns.org points to 178.128.58.219)
2. Port 80 and 443 are open in firewall

```bash
# Make the script executable
chmod +x /home/django/license-manager/setup-ssl-tractor.sh

# Run the SSL setup script
cd /home/django/license-manager
./setup-ssl-tractor.sh
```

Alternatively, manually setup SSL:

```bash
# Install certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot certonly --nginx \
    -d license-tractor.duckdns.org \
    --email info@labdhimercantile.com \
    --agree-tos \
    --non-interactive

# Update nginx configuration (uncomment HTTPS block in nginx-license-tractor.conf)
sudo nano /etc/nginx/sites-available/license-tractor

# Test and reload nginx
sudo nginx -t
sudo systemctl reload nginx
```

### Step 11: Setup Firewall (UFW)
```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
sudo ufw status
```

### Step 12: Configure Redis
```bash
# Redis should be running already
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl status redis-server
```

### Step 13: Setup Celery Workers (If using Celery)
The supervisor configuration should already include Celery workers. Check status:

```bash
sudo supervisorctl status
```

## Automated Deployment

After initial setup, use the automated deployment script from your local machine:

```bash
# From your local machine
cd /path/to/license-manager
./auto-deploy.sh
```

This will deploy to all configured servers including the new tractor server at 178.128.58.219.

## Verification

### Test HTTP/HTTPS Access
```bash
# Test HTTP (before SSL)
curl http://178.128.58.219
curl http://license-tractor.duckdns.org

# Test HTTPS (after SSL)
curl https://license-tractor.duckdns.org
```

### Test API Endpoint
```bash
curl http://178.128.58.219/api/licenses/?page_size=1
# or
curl https://license-tractor.duckdns.org/api/licenses/?page_size=1
```

### Check Service Status
```bash
# Check Django application
sudo supervisorctl status license-manager

# Check Celery (if configured)
sudo supervisorctl status license-manager-celery
sudo supervisorctl status license-manager-celery-beat

# Check Nginx
sudo systemctl status nginx

# Check PostgreSQL
sudo systemctl status postgresql

# Check Redis
sudo systemctl status redis-server
```

### View Logs
```bash
# Django logs
tail -f /home/django/license-manager/logs/django.log

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Supervisor logs
sudo tail -f /var/log/supervisor/supervisord.log
```

## SSL Certificate Renewal

Certificates auto-renew via systemd timer. Check status:

```bash
# Check renewal timer
sudo systemctl status certbot.timer

# Test renewal (dry run)
sudo certbot renew --dry-run

# Force renewal (if needed)
sudo certbot renew --force-renewal
```

## Troubleshooting

### Django not starting
```bash
# Check supervisor logs
sudo tail -f /var/log/supervisor/license-manager-stderr*.log

# Restart service
sudo supervisorctl restart license-manager
```

### Nginx errors
```bash
# Check configuration
sudo nginx -t

# Check error logs
sudo tail -f /var/log/nginx/error.log
```

### Database connection issues
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test database connection
sudo -u postgres psql -d lmanagement -c "SELECT 1;"
```

### SSL certificate issues
```bash
# Check certificate
sudo certbot certificates

# Renew certificate
sudo certbot renew
```

## Maintenance Commands

### Update application
```bash
# SSH to server
ssh django@178.128.58.219

cd /home/django/license-manager
git pull origin master

# Update backend
source venv/bin/activate
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput

# Update frontend
cd ../frontend
npm install
npm run build

# Restart services
sudo supervisorctl restart license-manager
sudo systemctl reload nginx
```

### Backup database
```bash
# Create backup
sudo -u postgres pg_dump lmanagement > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
sudo -u postgres psql lmanagement < backup_file.sql
```

### Clear Redis cache
```bash
redis-cli FLUSHALL
```

## URLs
- HTTP: http://178.128.58.219 or http://license-tractor.duckdns.org
- HTTPS: https://license-tractor.duckdns.org
- Admin: https://license-tractor.duckdns.org/admin/
- API: https://license-tractor.duckdns.org/api/

## Notes
- Django runs on port 8000 (proxied through Nginx)
- Frontend is served by Nginx from `/home/django/license-manager/frontend/dist`
- Static files are in `/home/django/license-manager/backend/staticfiles`
- Media files are in `/home/django/license-manager/backend/media`
