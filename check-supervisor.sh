#!/bin/bash

# Check supervisor installation and configuration
# Run this on the server: django@143.110.252.201

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 Checking Supervisor installation...${NC}"
echo -e "${BLUE}================================================${NC}"

# Check if supervisor is installed
if command -v supervisorctl &> /dev/null; then
    echo -e "${GREEN}✅ Supervisor is installed${NC}"
    echo -e "${BLUE}Version:${NC} $(supervisorctl version)"
else
    echo -e "${RED}❌ Supervisor is NOT installed${NC}"
    echo -e "${YELLOW}Installing supervisor...${NC}"
    sudo apt update
    sudo apt install -y supervisor
    sudo systemctl enable supervisor
    sudo systemctl start supervisor
    echo -e "${GREEN}✅ Supervisor installed and started${NC}"
fi

echo ""
echo -e "${BLUE}📊 Supervisor Status:${NC}"
sudo systemctl status supervisor --no-pager | head -15

echo ""
echo -e "${BLUE}📋 Supervisor Configuration Files:${NC}"
echo -e "${YELLOW}Main config:${NC} /etc/supervisor/supervisord.conf"
echo -e "${YELLOW}Program configs:${NC} /etc/supervisor/conf.d/"
ls -lh /etc/supervisor/conf.d/ 2>/dev/null || echo -e "${YELLOW}No config files found${NC}"

echo ""
echo -e "${BLUE}🔧 Current Supervisor Programs:${NC}"
sudo supervisorctl status || echo -e "${YELLOW}No programs configured${NC}"

echo ""
echo -e "${BLUE}📝 License Manager Supervisor Config:${NC}"
if [ -f /etc/supervisor/conf.d/license-manager.conf ]; then
    echo -e "${GREEN}✅ Found: /etc/supervisor/conf.d/license-manager.conf${NC}"
    cat /etc/supervisor/conf.d/license-manager.conf
else
    echo -e "${RED}❌ Not found: /etc/supervisor/conf.d/license-manager.conf${NC}"
    echo -e "${YELLOW}You need to create a supervisor configuration for license-manager${NC}"
fi

echo ""
echo -e "${BLUE}🔍 Checking for systemd services:${NC}"
if systemctl list-units --full --all | grep -q "license-manager.service"; then
    echo -e "${YELLOW}⚠️  Found systemd service: license-manager.service${NC}"
    sudo systemctl status license-manager.service --no-pager | head -10
else
    echo -e "${GREEN}✅ No conflicting systemd service found${NC}"
fi

echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}✨ Check completed!${NC}"
