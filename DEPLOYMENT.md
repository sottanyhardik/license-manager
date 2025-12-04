# License Manager - Deployment Guide

## 🚀 Deployment Steps

### Quick Reference - Common Commands

```bash
# Restart application
sudo systemctl restart license-manager

# Restart Nginx
sudo systemctl restart nginx

# View application logs
sudo journalctl -u license-manager -f

# View Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Check service status
sudo systemctl status license-manager
sudo systemctl status nginx
sudo systemctl status redis-server

# Update application
cd /var/www/license-manager && git pull
source venv/bin/activate && cd backend && pip install -r requirements.txt
python manage.py migrate && python manage.py collectstatic --noinput
sudo systemctl restart license-manager
```

---

### Prerequisites
- Ubuntu/Debian server with root access
- Python 3.10+
- PostgreSQL 12+
- Nginx
- SSL certificate (Let's Encrypt recommended)

---

## 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3-pip python3-venv postgresql postgresql-contrib nginx certbot python3-certbot-nginx git redis-server libreoffice

# Install Node.js (for building frontend)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

---

## 2. Database Setup

```bash
# Login to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE lmanagement;
CREATE USER lmanagement WITH PASSWORD 'your_secure_password';
ALTER ROLE lmanagement SET client_encoding TO 'utf8';
ALTER ROLE lmanagement SET default_transaction_isolation TO 'read committed';
ALTER ROLE lmanagement SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE lmanagement TO lmanagement;
\q
```

---

## 3. Application Deployment

```bash
# Create app directory
sudo mkdir -p /var/www/license-manager
sudo chown $USER:$USER /var/www/license-manager
cd /var/www/license-manager

# Clone or copy your project
# Option 1: Clone from Git
git clone <your-repo-url> .

# Option 2: Copy from local
# scp -r /path/to/local/project/* user@server:/var/www/license-manager/

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
cd backend
pip install -r requirements.txt
```

---

## 4. Environment Configuration

Create `.env` file in `/var/www/license-manager/backend/`:

```bash
# Django Settings
DJANGO_SECRET_KEY=your-secret-key-here-generate-a-strong-one
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,YOUR_SERVER_IP

# Database
DB_NAME=lmanagement
DB_USER=lmanagement
DB_PASS=your_secure_password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://127.0.0.1:6379/0

# Security (SSL)
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Static/Media Files
STATIC_ROOT=/var/www/license-manager/staticfiles
MEDIA_ROOT=/var/www/license-manager/media
```

**Important:** After creating the `.env` file, you may also need to update the following in `backend/lmanagement/settings.py`:

1. **ALLOWED_HOSTS** - Add your domain and IP:
   ```python
   ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "yourdomain.com,www.yourdomain.com,YOUR_SERVER_IP").split(",")
   ```

2. **CORS_ALLOWED_ORIGINS** - Add your production domain:
   ```python
   CORS_ALLOWED_ORIGINS = [
       "https://yourdomain.com",
       # ... other origins
   ]
   ```

3. **CSRF_TRUSTED_ORIGINS** - Add your production domain:
   ```python
   CSRF_TRUSTED_ORIGINS = [
       "https://yourdomain.com",
       # ... other origins
   ]
   ```

---

## 5. Run Migrations and Collect Static

```bash
cd /var/www/license-manager/backend
source ../venv/bin/activate

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Create required directories
mkdir -p /var/www/license-manager/staticfiles
mkdir -p /var/www/license-manager/media

# Set proper permissions for media directory (for PDF generation)
sudo chown -R www-data:www-data /var/www/license-manager/media
sudo chmod -R 775 /var/www/license-manager/media
```

---

## 6. Build Frontend

```bash
cd /var/www/license-manager/frontend

# Install dependencies
npm install

# Build for production
npm run build

# The build output will be in /var/www/license-manager/frontend/dist
```

---

## 7. Configure Gunicorn (WSGI Server)

```bash
# Install gunicorn
source /var/www/license-manager/venv/bin/activate
pip install gunicorn

# Test gunicorn
cd /var/www/license-manager/backend
gunicorn lmanagement.wsgi:application --bind 0.0.0.0:8000
```

Create systemd service file:

```bash
sudo nano /etc/systemd/system/license-manager.service
```

Paste this content:

```ini
[Unit]
Description=License Manager Django Application
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/license-manager/backend
Environment="PATH=/var/www/license-manager/venv/bin"
ExecStart=/var/www/license-manager/venv/bin/gunicorn \
          --workers 3 \
          --bind unix:/var/www/license-manager/license-manager.sock \
          lmanagement.wsgi:application

[Install]
WantedBy=multi-user.target
```

Start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl start license-manager
sudo systemctl enable license-manager
sudo systemctl status license-manager
```

---

## 8. Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/license-manager
```

Paste this configuration:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Frontend (React/Vite build)
    root /var/www/license-manager/frontend/dist;
    index index.html;

    # Static files
    location /static/ {
        alias /var/www/license-manager/staticfiles/;
    }

    # Media files
    location /media/ {
        alias /var/www/license-manager/media/;
    }

    # API endpoints
    location /api/ {
        include proxy_params;
        proxy_pass http://unix:/var/www/license-manager/license-manager.sock;
    }

    location /admin/ {
        include proxy_params;
        proxy_pass http://unix:/var/www/license-manager/license-manager.sock;
    }

    # Frontend routing (SPA)
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Increase max upload size for file uploads
    client_max_body_size 100M;
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/license-manager /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 9. SSL Certificate (Let's Encrypt)

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Follow the prompts. Certbot will automatically configure SSL for you.

---

## 10. Set Permissions

```bash
sudo chown -R www-data:www-data /var/www/license-manager
sudo chmod -R 755 /var/www/license-manager
```

---

## 11. Firewall Configuration

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable
```

---

## 12. Start Redis Server

```bash
# Enable and start Redis
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl status redis-server
```

---

## 13. Optional: Setup Celery Worker (for background tasks)

If your application uses Celery for background tasks:

```bash
sudo nano /etc/systemd/system/celery.service
```

Paste this content:

```ini
[Unit]
Description=Celery Worker
After=network.target redis-server.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/var/www/license-manager/backend
Environment="PATH=/var/www/license-manager/venv/bin"
ExecStart=/var/www/license-manager/venv/bin/celery -A lmanagement worker --detach --loglevel=info

[Install]
WantedBy=multi-user.target
```

Start Celery:

```bash
sudo systemctl daemon-reload
sudo systemctl start celery
sudo systemctl enable celery
sudo systemctl status celery
```

---

## 🔄 Updates and Maintenance

### To Update the Application:

```bash
cd /var/www/license-manager

# Pull latest changes (if using Git)
git pull origin main

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
sudo systemctl restart license-manager
sudo systemctl restart nginx
```

### View Logs:

```bash
# Django application logs
sudo journalctl -u license-manager -f

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

---

## 🔐 Security Checklist

- ✅ Set strong SECRET_KEY in Django
- ✅ Set DEBUG=False in production
- ✅ Configure ALLOWED_HOSTS correctly
- ✅ Use strong database passwords
- ✅ Enable SSL/HTTPS
- ✅ Set up firewall (ufw)
- ✅ Regular backups of database
- ✅ Keep system packages updated
- ✅ Restrict file permissions

---

## 📊 Database Backup

```bash
# Create backup
sudo -u postgres pg_dump lmanagement > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
sudo -u postgres psql lmanagement < backup_file.sql
```

---

## 🐛 Troubleshooting

### Service won't start:
```bash
sudo journalctl -u license-manager -n 50
```

### 502 Bad Gateway:
- Check if gunicorn service is running: `sudo systemctl status license-manager`
- Check socket file exists: `ls -la /var/www/license-manager/license-manager.sock`

### Static files not loading:
```bash
cd /var/www/license-manager/backend
source ../venv/bin/activate
python manage.py collectstatic --noinput
```

### Database connection issues:
- Check PostgreSQL is running: `sudo systemctl status postgresql`
- Verify database credentials in `.env`
- Check PostgreSQL allows connections: `sudo nano /etc/postgresql/*/main/pg_hba.conf`

### PDF/DOCX conversion issues:
- Check LibreOffice is installed: `libreoffice --version`
- Ensure www-data user has HOME directory access
- Check media directory permissions: `ls -la /var/www/license-manager/media`
- View application logs for LibreOffice errors: `sudo journalctl -u license-manager -n 100`

### Redis connection issues:
- Check Redis is running: `sudo systemctl status redis-server`
- Test Redis connection: `redis-cli ping` (should return PONG)
- Verify REDIS_URL in `.env` matches your Redis configuration

---

## 📞 Support

For issues or questions, check the application logs and nginx logs first.
