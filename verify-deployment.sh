#!/bin/bash

# Comprehensive deployment verification script
# Run this on the server: django@143.110.252.201

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 Comprehensive Deployment Verification${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# 1. Check Project Directory
echo -e "${BLUE}📂 1. Project Directory Structure${NC}"
echo -e "${YELLOW}================================================${NC}"
if [ -d /home/django/license-manager ]; then
    echo -e "${GREEN}✅ Project directory exists: /home/django/license-manager${NC}"
    echo -e "${BLUE}Contents:${NC}"
    ls -lh /home/django/license-manager/
else
    echo -e "${RED}❌ Project directory not found!${NC}"
fi
echo ""

# 2. Check Virtual Environment
echo -e "${BLUE}🐍 2. Python Virtual Environment${NC}"
echo -e "${YELLOW}================================================${NC}"
if [ -d /home/django/license-manager/venv ]; then
    echo -e "${GREEN}✅ Virtual environment exists${NC}"
    echo -e "${BLUE}Python version:${NC}"
    /home/django/license-manager/venv/bin/python --version
    echo -e "${BLUE}Gunicorn location:${NC}"
    ls -lh /home/django/license-manager/venv/bin/gunicorn 2>/dev/null || echo -e "${RED}❌ Gunicorn not found${NC}"
else
    echo -e "${RED}❌ Virtual environment not found!${NC}"
fi
echo ""

# 3. Check Backend
echo -e "${BLUE}📦 3. Backend (Django)${NC}"
echo -e "${YELLOW}================================================${NC}"
if [ -d /home/django/license-manager/backend ]; then
    echo -e "${GREEN}✅ Backend directory exists${NC}"

    # Check manage.py
    if [ -f /home/django/license-manager/backend/manage.py ]; then
        echo -e "${GREEN}✅ manage.py found${NC}"
    else
        echo -e "${RED}❌ manage.py not found${NC}"
    fi

    # Check settings.py
    if [ -f /home/django/license-manager/backend/lmanagement/settings.py ]; then
        echo -e "${GREEN}✅ settings.py found${NC}"
    else
        echo -e "${RED}❌ settings.py not found${NC}"
    fi

    # Check wsgi.py
    if [ -f /home/django/license-manager/backend/lmanagement/wsgi.py ]; then
        echo -e "${GREEN}✅ wsgi.py found${NC}"
    else
        echo -e "${RED}❌ wsgi.py not found${NC}"
    fi

    # Check requirements.txt
    if [ -f /home/django/license-manager/backend/requirements.txt ]; then
        echo -e "${GREEN}✅ requirements.txt found${NC}"
    else
        echo -e "${RED}❌ requirements.txt not found${NC}"
    fi
else
    echo -e "${RED}❌ Backend directory not found!${NC}"
fi
echo ""

# 4. Check Frontend
echo -e "${BLUE}⚛️  4. Frontend (React/Vite)${NC}"
echo -e "${YELLOW}================================================${NC}"
if [ -d /home/django/license-manager/frontend ]; then
    echo -e "${GREEN}✅ Frontend directory exists${NC}"

    # Check dist folder
    if [ -d /home/django/license-manager/frontend/dist ]; then
        echo -e "${GREEN}✅ dist folder exists (frontend built)${NC}"
        echo -e "${BLUE}Dist contents:${NC}"
        ls -lh /home/django/license-manager/frontend/dist/

        # Check index.html
        if [ -f /home/django/license-manager/frontend/dist/index.html ]; then
            echo -e "${GREEN}✅ index.html found in dist${NC}"
        else
            echo -e "${RED}❌ index.html not found in dist${NC}"
        fi

        # Check assets folder
        if [ -d /home/django/license-manager/frontend/dist/assets ]; then
            echo -e "${GREEN}✅ assets folder exists${NC}"
            echo -e "${BLUE}Asset files:${NC}"
            ls -lh /home/django/license-manager/frontend/dist/assets/ | head -10
        else
            echo -e "${RED}❌ assets folder not found${NC}"
        fi
    else
        echo -e "${RED}❌ dist folder not found - frontend not built!${NC}"
        echo -e "${YELLOW}Run: cd /home/django/license-manager/frontend && npm install && npm run build${NC}"
    fi
else
    echo -e "${RED}❌ Frontend directory not found!${NC}"
fi
echo ""

# 5. Check Static Files
echo -e "${BLUE}📦 5. Static Files${NC}"
echo -e "${YELLOW}================================================${NC}"
if [ -d /home/django/license-manager/backend/staticfiles ]; then
    echo -e "${GREEN}✅ staticfiles directory exists${NC}"
    echo -e "${BLUE}Size: $(du -sh /home/django/license-manager/backend/staticfiles | cut -f1)${NC}"
else
    echo -e "${RED}❌ staticfiles not collected!${NC}"
    echo -e "${YELLOW}Run: cd /home/django/license-manager/backend && python manage.py collectstatic --noinput${NC}"
fi
echo ""

# 6. Check Media Files
echo -e "${BLUE}🖼️  6. Media Files${NC}"
echo -e "${YELLOW}================================================${NC}"
if [ -d /home/django/license-manager/backend/media ]; then
    echo -e "${GREEN}✅ media directory exists${NC}"
    echo -e "${BLUE}Permissions:${NC}"
    ls -ld /home/django/license-manager/backend/media
    echo -e "${BLUE}Size: $(du -sh /home/django/license-manager/backend/media 2>/dev/null | cut -f1)${NC}"
else
    echo -e "${YELLOW}⚠️  media directory not found - will be created on first upload${NC}"
fi
echo ""

# 7. Check Logs Directory
echo -e "${BLUE}📋 7. Logs Directory${NC}"
echo -e "${YELLOW}================================================${NC}"
if [ -d /home/django/license-manager/logs ]; then
    echo -e "${GREEN}✅ logs directory exists${NC}"
    echo -e "${BLUE}Log files:${NC}"
    ls -lh /home/django/license-manager/logs/ 2>/dev/null || echo -e "${YELLOW}No log files yet${NC}"
else
    echo -e "${YELLOW}⚠️  logs directory not found - creating...${NC}"
    mkdir -p /home/django/license-manager/logs
    echo -e "${GREEN}✅ logs directory created${NC}"
fi
echo ""

# 8. Check Supervisor
echo -e "${BLUE}⚙️  8. Supervisor Configuration${NC}"
echo -e "${YELLOW}================================================${NC}"
if command -v supervisorctl &> /dev/null; then
    echo -e "${GREEN}✅ Supervisor is installed${NC}"

    # Check config file
    if [ -f /etc/supervisor/conf.d/license-manager.conf ]; then
        echo -e "${GREEN}✅ Supervisor config exists${NC}"
        echo -e "${BLUE}Config file:${NC}"
        cat /etc/supervisor/conf.d/license-manager.conf
    else
        echo -e "${RED}❌ Supervisor config not found!${NC}"
        echo -e "${YELLOW}Run: bash /home/django/license-manager/setup-supervisor.sh${NC}"
    fi

    echo ""
    echo -e "${BLUE}Supervisor processes:${NC}"
    sudo supervisorctl status || echo -e "${YELLOW}No processes running${NC}"
else
    echo -e "${RED}❌ Supervisor not installed!${NC}"
    echo -e "${YELLOW}Run: sudo apt install supervisor${NC}"
fi
echo ""

# 9. Check Nginx
echo -e "${BLUE}🌐 9. Nginx Configuration${NC}"
echo -e "${YELLOW}================================================${NC}"
if command -v nginx &> /dev/null; then
    echo -e "${GREEN}✅ Nginx is installed${NC}"

    # Check config file
    if [ -f /etc/nginx/sites-available/license-manager ]; then
        echo -e "${GREEN}✅ Nginx config exists${NC}"
        echo -e "${BLUE}Config file preview:${NC}"
        head -30 /etc/nginx/sites-available/license-manager
    else
        echo -e "${RED}❌ Nginx config not found!${NC}"
    fi

    # Check if enabled
    if [ -L /etc/nginx/sites-enabled/license-manager ]; then
        echo -e "${GREEN}✅ Nginx site is enabled${NC}"
    else
        echo -e "${RED}❌ Nginx site not enabled!${NC}"
    fi

    echo ""
    echo -e "${BLUE}Nginx status:${NC}"
    sudo systemctl status nginx --no-pager | head -10
else
    echo -e "${RED}❌ Nginx not installed!${NC}"
fi
echo ""

# 10. Check Database Connection
echo -e "${BLUE}🗄️  10. Database${NC}"
echo -e "${YELLOW}================================================${NC}"
if command -v psql &> /dev/null; then
    echo -e "${GREEN}✅ PostgreSQL client is installed${NC}"

    # Try to connect (will prompt for password if needed)
    if psql -U lmanagement -d lmanagement -c "SELECT version();" &> /dev/null; then
        echo -e "${GREEN}✅ Database connection successful${NC}"
    else
        echo -e "${YELLOW}⚠️  Database connection check skipped (may need credentials)${NC}"
    fi
else
    echo -e "${RED}❌ PostgreSQL client not installed!${NC}"
fi
echo ""

# 11. Check Redis
echo -e "${BLUE}🔴 11. Redis${NC}"
echo -e "${YELLOW}================================================${NC}"
if command -v redis-cli &> /dev/null; then
    echo -e "${GREEN}✅ Redis is installed${NC}"

    if redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✅ Redis is running and responsive${NC}"
    else
        echo -e "${RED}❌ Redis is not running!${NC}"
    fi
else
    echo -e "${RED}❌ Redis not installed!${NC}"
fi
echo ""

# 12. Check Environment File
echo -e "${BLUE}🔐 12. Environment Configuration${NC}"
echo -e "${YELLOW}================================================${NC}"
if [ -f /home/django/license-manager/backend/.env ]; then
    echo -e "${GREEN}✅ .env file exists${NC}"
    echo -e "${BLUE}Environment variables (without values):${NC}"
    grep "^[A-Z]" /home/django/license-manager/backend/.env | cut -d'=' -f1 | sort
else
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo -e "${YELLOW}Using default settings from settings.py${NC}"
fi
echo ""

# 13. Test Application
echo -e "${BLUE}🧪 13. Application Test${NC}"
echo -e "${YELLOW}================================================${NC}"
echo -e "${BLUE}Testing local connection to Django (port 8000):${NC}"
if curl -s http://127.0.0.1:8000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Django application is responding on port 8000${NC}"
else
    echo -e "${RED}❌ Django application not responding on port 8000${NC}"
fi

echo ""
echo -e "${BLUE}Testing Nginx (port 80):${NC}"
if curl -s http://127.0.0.1 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Nginx is responding on port 80${NC}"
else
    echo -e "${RED}❌ Nginx not responding on port 80${NC}"
fi
echo ""

# Summary
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}✨ Verification Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo -e "${BLUE}📝 Next Steps (if any issues found):${NC}"
echo -e "  1. Fix missing directories/files"
echo -e "  2. Run: ${YELLOW}bash setup-supervisor.sh${NC}"
echo -e "  3. Run: ${YELLOW}bash fix-nginx.sh${NC}"
echo -e "  4. Build frontend: ${YELLOW}cd frontend && npm run build${NC}"
echo -e "  5. Collect static: ${YELLOW}cd backend && python manage.py collectstatic${NC}"
echo ""
echo -e "${BLUE}🌐 Test URLs:${NC}"
echo -e "  → http://143.110.252.201"
echo -e "  → https://license-manager.duckdns.org"
