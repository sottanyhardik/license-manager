#!/bin/bash

# Diagnose connection issues for license-manager.duckdns.org
# Run this on the server: django@143.110.252.201

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 Diagnosing Connection Issues${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# 1. Check Nginx Status
echo -e "${BLUE}1. Nginx Status${NC}"
echo -e "${YELLOW}------------------------------------------------${NC}"
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✅ Nginx is running${NC}"
    sudo systemctl status nginx --no-pager | head -10
else
    echo -e "${RED}❌ Nginx is NOT running${NC}"
    echo -e "${YELLOW}Starting nginx...${NC}"
    sudo systemctl start nginx
fi
echo ""

# 2. Check Nginx Configuration
echo -e "${BLUE}2. Nginx Configuration${NC}"
echo -e "${YELLOW}------------------------------------------------${NC}"
echo -e "${BLUE}Testing nginx config:${NC}"
sudo nginx -t
echo ""

if [ -f /etc/nginx/sites-available/license-manager ]; then
    echo -e "${GREEN}✅ Nginx config file exists${NC}"
    echo -e "${BLUE}Current config:${NC}"
    cat /etc/nginx/sites-available/license-manager
else
    echo -e "${RED}❌ Nginx config file NOT found${NC}"
fi
echo ""

# 3. Check if site is enabled
echo -e "${BLUE}3. Nginx Site Enabled${NC}"
echo -e "${YELLOW}------------------------------------------------${NC}"
if [ -L /etc/nginx/sites-enabled/license-manager ]; then
    echo -e "${GREEN}✅ Site is enabled${NC}"
else
    echo -e "${RED}❌ Site is NOT enabled${NC}"
    echo -e "${YELLOW}Enabling site...${NC}"
    sudo ln -s /etc/nginx/sites-available/license-manager /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx
fi
echo ""

# 4. Check Listening Ports
echo -e "${BLUE}4. Open Ports${NC}"
echo -e "${YELLOW}------------------------------------------------${NC}"
echo -e "${BLUE}Checking port 80 (HTTP):${NC}"
if sudo netstat -tlnp | grep -q ":80 "; then
    echo -e "${GREEN}✅ Port 80 is open${NC}"
    sudo netstat -tlnp | grep ":80 "
else
    echo -e "${RED}❌ Port 80 is NOT open${NC}"
fi

echo ""
echo -e "${BLUE}Checking port 443 (HTTPS):${NC}"
if sudo netstat -tlnp | grep -q ":443 "; then
    echo -e "${GREEN}✅ Port 443 is open${NC}"
    sudo netstat -tlnp | grep ":443 "
else
    echo -e "${RED}❌ Port 443 is NOT open (SSL not configured)${NC}"
fi

echo ""
echo -e "${BLUE}Checking port 8000 (Django):${NC}"
if sudo netstat -tlnp | grep -q ":8000 "; then
    echo -e "${GREEN}✅ Port 8000 is open${NC}"
    sudo netstat -tlnp | grep ":8000 "
else
    echo -e "${RED}❌ Port 8000 is NOT open (Django not running)${NC}"
fi
echo ""

# 5. Check Supervisor/Django
echo -e "${BLUE}5. Django Application${NC}"
echo -e "${YELLOW}------------------------------------------------${NC}"
if sudo supervisorctl status license-manager | grep -q "RUNNING"; then
    echo -e "${GREEN}✅ Django app is running via supervisor${NC}"
    sudo supervisorctl status license-manager
else
    echo -e "${RED}❌ Django app is NOT running${NC}"
    echo -e "${YELLOW}Starting Django app...${NC}"
    sudo supervisorctl start license-manager
fi
echo ""

# 6. Test Local Connections
echo -e "${BLUE}6. Local Connection Tests${NC}"
echo -e "${YELLOW}------------------------------------------------${NC}"
echo -e "${BLUE}Testing Django (port 8000):${NC}"
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000 | grep -q "200\|301\|302"; then
    echo -e "${GREEN}✅ Django responds on port 8000${NC}"
else
    echo -e "${RED}❌ Django not responding on port 8000${NC}"
fi

echo ""
echo -e "${BLUE}Testing Nginx (port 80):${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1)
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
    echo -e "${GREEN}✅ Nginx responds on port 80 (HTTP code: $HTTP_CODE)${NC}"
else
    echo -e "${RED}❌ Nginx not responding properly (HTTP code: $HTTP_CODE)${NC}"
fi
echo ""

# 7. Check DNS
echo -e "${BLUE}7. DNS Resolution${NC}"
echo -e "${YELLOW}------------------------------------------------${NC}"
echo -e "${BLUE}Resolving license-manager.duckdns.org:${NC}"
RESOLVED_IP=$(dig +short license-manager.duckdns.org | tail -1)
if [ -n "$RESOLVED_IP" ]; then
    echo -e "${GREEN}✅ DNS resolves to: $RESOLVED_IP${NC}"

    # Check if it matches server IP
    SERVER_IP=$(hostname -I | awk '{print $1}')
    if [ "$RESOLVED_IP" = "143.110.252.201" ]; then
        echo -e "${GREEN}✅ DNS points to correct server${NC}"
    else
        echo -e "${YELLOW}⚠️  DNS points to $RESOLVED_IP but server is $SERVER_IP${NC}"
        echo -e "${YELLOW}Expected: 143.110.252.201${NC}"
    fi
else
    echo -e "${RED}❌ DNS does not resolve${NC}"
fi
echo ""

# 8. Check Firewall
echo -e "${BLUE}8. Firewall Status${NC}"
echo -e "${YELLOW}------------------------------------------------${NC}"
if command -v ufw &> /dev/null; then
    echo -e "${BLUE}UFW Status:${NC}"
    sudo ufw status
else
    echo -e "${YELLOW}UFW not installed${NC}"
fi
echo ""

# 9. Check SSL Certificate
echo -e "${BLUE}9. SSL Certificate${NC}"
echo -e "${YELLOW}------------------------------------------------${NC}"
if [ -d /etc/letsencrypt/live/license-manager.duckdns.org ]; then
    echo -e "${GREEN}✅ SSL certificate directory exists${NC}"
    echo -e "${BLUE}Certificate files:${NC}"
    sudo ls -lh /etc/letsencrypt/live/license-manager.duckdns.org/

    # Check expiry
    if [ -f /etc/letsencrypt/live/license-manager.duckdns.org/cert.pem ]; then
        echo -e "${BLUE}Certificate expiry:${NC}"
        sudo openssl x509 -enddate -noout -in /etc/letsencrypt/live/license-manager.duckdns.org/cert.pem
    fi
else
    echo -e "${RED}❌ SSL certificate NOT found${NC}"
    echo -e "${YELLOW}SSL is not configured. Run: bash setup-ssl.sh${NC}"
fi
echo ""

# Summary and Recommendations
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}✨ Diagnosis Complete${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo -e "${BLUE}📝 Recommendations:${NC}"
echo ""

# Check what needs fixing
NEEDS_FIX=0

if ! systemctl is-active --quiet nginx; then
    echo -e "${YELLOW}→ Start nginx: sudo systemctl start nginx${NC}"
    NEEDS_FIX=1
fi

if ! sudo supervisorctl status license-manager | grep -q "RUNNING"; then
    echo -e "${YELLOW}→ Start Django: sudo supervisorctl start license-manager${NC}"
    NEEDS_FIX=1
fi

if [ ! -d /etc/letsencrypt/live/license-manager.duckdns.org ]; then
    echo -e "${YELLOW}→ Setup SSL: bash setup-ssl.sh${NC}"
    NEEDS_FIX=1
fi

if [ ! -f /etc/nginx/sites-available/license-manager ]; then
    echo -e "${YELLOW}→ Configure nginx: bash fix-nginx.sh${NC}"
    NEEDS_FIX=1
fi

if [ $NEEDS_FIX -eq 0 ]; then
    echo -e "${GREEN}✅ Everything looks good!${NC}"
    echo ""
    echo -e "${BLUE}🌐 Access your application:${NC}"
    echo -e "  → http://143.110.252.201"
    if [ -d /etc/letsencrypt/live/license-manager.duckdns.org ]; then
        echo -e "  → https://license-manager.duckdns.org"
    fi
fi
