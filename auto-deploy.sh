#!/bin/bash

# Automated Deployment Script for License Manager
# Deploys to django@143.110.252.201:/home/django/license-manager
# Usage: bash auto-deploy.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVER_USER="django"
SERVER_IP="143.110.252.201"
SERVER_PATH="/home/django/license-manager"
BRANCH="feature/V4.0"

echo -e "${BLUE}🚀 Starting automated deployment to ${SERVER_USER}@${SERVER_IP}${NC}"
echo -e "${BLUE}================================================${NC}"

# Deploy via SSH
ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}📂 Navigating to project directory...${NC}"
cd /home/django/license-manager

echo -e "${BLUE}📥 Pulling latest code from feature/V4.0...${NC}"
git pull origin feature/V4.0

echo -e "${BLUE}📦 Installing frontend dependencies...${NC}"
cd frontend
npm install

echo -e "${BLUE}🏗️  Building frontend...${NC}"
npm run build

echo -e "${GREEN}✅ Frontend build completed${NC}"
echo -e "${BLUE}📋 Frontend dist contents:${NC}"
ls -lh dist/

echo -e "${BLUE}🐍 Activating Python virtual environment...${NC}"
cd /home/django/license-manager
source venv/bin/activate

echo -e "${BLUE}📦 Installing Python dependencies...${NC}"
cd backend
pip install -r requirements.txt --quiet

echo -e "${BLUE}🗄️  Running database migrations...${NC}"
python manage.py migrate

echo -e "${BLUE}📦 Collecting static files...${NC}"
python manage.py collectstatic --noinput

echo -e "${BLUE}🔐 Setting permissions...${NC}"
# Set permissions (should already be owned by django user)
chmod -R 775 /home/django/license-manager/backend/media 2>/dev/null || true
chmod -R 755 /home/django/license-manager/frontend/dist 2>/dev/null || true

echo -e "${BLUE}🔄 Restarting services...${NC}"

# Restart supervisor processes
echo -e "${YELLOW}  → Restarting license-manager...${NC}"
if command -v sudo &> /dev/null && sudo -n supervisorctl status &> /dev/null 2>&1; then
    sudo supervisorctl restart license-manager
else
    supervisorctl restart license-manager
fi

# Check if celery is configured
if supervisorctl status license-manager-celery &> /dev/null; then
    echo -e "${YELLOW}  → Restarting celery worker...${NC}"
    if command -v sudo &> /dev/null && sudo -n supervisorctl status &> /dev/null 2>&1; then
        sudo supervisorctl restart license-manager-celery
    else
        supervisorctl restart license-manager-celery
    fi
fi

if supervisorctl status license-manager-celery-beat &> /dev/null; then
    echo -e "${YELLOW}  → Restarting celery beat...${NC}"
    if command -v sudo &> /dev/null && sudo -n supervisorctl status &> /dev/null 2>&1; then
        sudo supervisorctl restart license-manager-celery-beat
    else
        supervisorctl restart license-manager-celery-beat
    fi
fi

# Restart nginx
echo -e "${YELLOW}  → Reloading nginx...${NC}"
if command -v sudo &> /dev/null && sudo -n systemctl status nginx &> /dev/null 2>&1; then
    sudo systemctl reload nginx
else
    echo -e "${YELLOW}    (Skipping nginx reload - requires sudo)${NC}"
fi

echo -e "${BLUE}✅ Checking service status...${NC}"
echo -e "${YELLOW}==================== Supervisor Status ====================${NC}"
if command -v sudo &> /dev/null && sudo -n supervisorctl status &> /dev/null 2>&1; then
    sudo supervisorctl status
else
    supervisorctl status
fi

echo -e "${YELLOW}==================== Nginx Status ====================${NC}"
if command -v sudo &> /dev/null && sudo -n systemctl status nginx &> /dev/null 2>&1; then
    sudo systemctl status nginx --no-pager | head -10
else
    echo -e "${YELLOW}    (Nginx status check requires sudo)${NC}"
fi

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}✨ Deployment completed successfully!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo -e "${BLUE}🌐 Application URLs:${NC}"
echo -e "   http://143.110.252.201"
echo -e "   https://license-manager.duckdns.org"
echo ""
echo -e "${BLUE}📊 Service Status:${NC}"
if command -v sudo &> /dev/null && sudo -n supervisorctl status &> /dev/null 2>&1; then
    sudo supervisorctl status | grep license-manager
else
    supervisorctl status | grep license-manager
fi

ENDSSH

# Check if SSH command was successful
if [ $? -eq 0 ]; then
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo ""
    echo -e "${BLUE}📝 Deployment Summary:${NC}"
    echo -e "   ✅ Code pulled from ${BRANCH}"
    echo -e "   ✅ Frontend built and deployed"
    echo -e "   ✅ Backend dependencies installed"
    echo -e "   ✅ Database migrations applied"
    echo -e "   ✅ Static files collected"
    echo -e "   ✅ Services restarted"
    echo ""
    echo -e "${BLUE}🔍 Test your deployment:${NC}"
    echo -e "   → http://143.110.252.201"
    echo -e "   → https://license-manager.duckdns.org"
    echo ""
    echo -e "${BLUE}📊 View logs:${NC}"
    echo -e "   → App logs: ssh ${SERVER_USER}@${SERVER_IP} 'tail -f /home/django/license-manager/logs/*.log'"
    echo -e "   → Nginx error: ssh ${SERVER_USER}@${SERVER_IP} 'sudo tail -f /var/log/nginx/error.log'"
else
    echo -e "${RED}================================================${NC}"
    echo -e "${RED}❌ Deployment failed!${NC}"
    echo -e "${RED}================================================${NC}"
    echo -e "${YELLOW}Please check the error messages above and try again.${NC}"
    exit 1
fi
