#!/bin/bash

# Setup Supervisor for License Manager
# Run this on the server: django@143.110.252.201

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 Setting up Supervisor for License Manager...${NC}"
echo -e "${BLUE}================================================${NC}"

# Install supervisor if not installed
if ! command -v supervisorctl &> /dev/null; then
    echo -e "${YELLOW}📦 Installing supervisor...${NC}"
    sudo apt update
    sudo apt install -y supervisor
    sudo systemctl enable supervisor
    sudo systemctl start supervisor
    echo -e "${GREEN}✅ Supervisor installed${NC}"
else
    echo -e "${GREEN}✅ Supervisor is already installed${NC}"
fi

# Create logs directory
echo -e "${BLUE}📁 Creating logs directory...${NC}"
mkdir -p /home/django/license-manager/logs

# Stop any existing systemd service
if systemctl list-units --full --all | grep -q "license-manager.service"; then
    echo -e "${YELLOW}⚠️  Stopping existing systemd service...${NC}"
    sudo systemctl stop license-manager.service || true
    sudo systemctl disable license-manager.service || true
    sudo rm -f /etc/systemd/system/license-manager.service
    sudo systemctl daemon-reload
fi

# Copy supervisor config
echo -e "${BLUE}📋 Installing supervisor configuration...${NC}"
sudo cp /home/django/license-manager/supervisor-license-manager.conf /etc/supervisor/conf.d/license-manager.conf

# Copy celery config if exists
if [ -f /home/django/license-manager/supervisord-celery.conf ]; then
    echo -e "${BLUE}📋 Installing celery supervisor configuration...${NC}"
    sudo cp /home/django/license-manager/supervisord-celery.conf /etc/supervisor/conf.d/license-manager-celery.conf
fi

# Reload supervisor
echo -e "${BLUE}🔄 Reloading supervisor configuration...${NC}"
sudo supervisorctl reread
sudo supervisorctl update

# Start services
echo -e "${BLUE}🚀 Starting license-manager...${NC}"
sudo supervisorctl start license-manager

# Start celery if configured
if sudo supervisorctl status license-manager-celery &> /dev/null 2>&1; then
    echo -e "${BLUE}🚀 Starting celery services...${NC}"
    sudo supervisorctl start license-manager-celery || true
    sudo supervisorctl start license-manager-celery-beat || true
fi

# Check status
echo -e "${BLUE}✅ Checking service status...${NC}"
echo -e "${YELLOW}================================================${NC}"
sudo supervisorctl status

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}✨ Supervisor setup completed!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo -e "${BLUE}📊 Service Status:${NC}"
sudo supervisorctl status license-manager

echo ""
echo -e "${BLUE}📝 Useful Commands:${NC}"
echo -e "  - Check status: ${YELLOW}sudo supervisorctl status${NC}"
echo -e "  - Restart app: ${YELLOW}sudo supervisorctl restart license-manager${NC}"
echo -e "  - View logs: ${YELLOW}sudo supervisorctl tail -f license-manager${NC}"
echo -e "  - Stop app: ${YELLOW}sudo supervisorctl stop license-manager${NC}"
echo -e "  - Start app: ${YELLOW}sudo supervisorctl start license-manager${NC}"
echo ""
echo -e "${BLUE}🌐 Test your application:${NC}"
echo -e "  → http://143.110.252.201"
