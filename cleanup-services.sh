#!/bin/bash

# Cleanup script to remove systemd services and keep only supervisorctl
# Run this on the server: django@143.110.252.201
# Usage: bash cleanup-services.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 Cleaning up systemd services for license-manager...${NC}"
echo -e "${BLUE}================================================${NC}"

# Check for license-manager systemd service
if [ -f /etc/systemd/system/license-manager.service ]; then
    echo -e "${YELLOW}Found systemd service: license-manager.service${NC}"

    # Stop the service
    echo -e "${BLUE}Stopping systemd service...${NC}"
    sudo systemctl stop license-manager.service || true

    # Disable the service
    echo -e "${BLUE}Disabling systemd service...${NC}"
    sudo systemctl disable license-manager.service || true

    # Remove the service file
    echo -e "${BLUE}Removing service file...${NC}"
    sudo rm -f /etc/systemd/system/license-manager.service

    # Reload systemd daemon
    echo -e "${BLUE}Reloading systemd daemon...${NC}"
    sudo systemctl daemon-reload
    sudo systemctl reset-failed || true

    echo -e "${GREEN}✅ Systemd service removed${NC}"
else
    echo -e "${GREEN}No systemd service found for license-manager${NC}"
fi

# Check for Celery systemd services
if [ -f /etc/systemd/system/celery.service ]; then
    echo -e "${YELLOW}Found systemd service: celery.service${NC}"

    sudo systemctl stop celery.service || true
    sudo systemctl disable celery.service || true
    sudo rm -f /etc/systemd/system/celery.service

    echo -e "${GREEN}✅ Celery systemd service removed${NC}"
fi

if [ -f /etc/systemd/system/celery-beat.service ]; then
    echo -e "${YELLOW}Found systemd service: celery-beat.service${NC}"

    sudo systemctl stop celery-beat.service || true
    sudo systemctl disable celery-beat.service || true
    sudo rm -f /etc/systemd/system/celery-beat.service

    echo -e "${GREEN}✅ Celery-beat systemd service removed${NC}"
fi

# Reload systemd daemon again
sudo systemctl daemon-reload
sudo systemctl reset-failed || true

echo ""
echo -e "${BLUE}📊 Current Supervisor Status:${NC}"
echo -e "${YELLOW}================================================${NC}"
sudo supervisorctl status

echo ""
echo -e "${GREEN}✨ Cleanup completed!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${BLUE}Services now managed by Supervisor:${NC}"
sudo supervisorctl status | grep license-manager || echo -e "${YELLOW}No license-manager services found in supervisor${NC}"
echo ""
echo -e "${BLUE}Useful Supervisor commands:${NC}"
echo -e "  - Check status: sudo supervisorctl status"
echo -e "  - Restart app: sudo supervisorctl restart license-manager"
echo -e "  - Start app: sudo supervisorctl start license-manager"
echo -e "  - Stop app: sudo supervisorctl stop license-manager"
echo -e "  - View logs: sudo supervisorctl tail -f license-manager"
