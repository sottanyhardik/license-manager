#!/bin/bash

# Deployment script for latest fixes
# Run this on the server to apply all recent fixes

set -e

echo "================================================================================"
echo "Deploying Latest Fixes"
echo "================================================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running on server
if [ ! -d "/home" ]; then
    echo -e "${YELLOW}Warning: This script is intended for server deployment.${NC}"
    read -p "Continue anyway? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Cancelled."
        exit 0
    fi
fi

# Step 1: Pull latest code
echo -e "${BLUE}Step 1: Pulling latest code from version-4.1...${NC}"
git fetch origin
git checkout version-4.1
git pull origin version-4.1

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to pull latest code!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Code updated${NC}"
echo ""

# Step 2: Check database schema
echo -e "${BLUE}Step 2: Checking database schema...${NC}"
python manage.py sync_database_schema

echo ""
read -p "Continue with migrations? (yes/no): " continue_migrate
if [ "$continue_migrate" != "yes" ]; then
    echo "Stopped before applying migrations."
    exit 0
fi

# Step 3: Apply migrations
echo ""
echo -e "${BLUE}Step 3: Applying database migrations...${NC}"
python manage.py migrate --verbosity 2

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to apply migrations!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Migrations applied${NC}"
echo ""

# Step 4: Collect static files (if needed)
echo -e "${BLUE}Step 4: Collecting static files...${NC}"
python manage.py collectstatic --no-input

echo -e "${GREEN}✓ Static files collected${NC}"
echo ""

# Step 5: Restart services
echo -e "${BLUE}Step 5: Restarting services...${NC}"

# Try common service names
if systemctl list-units --type=service | grep -q gunicorn; then
    sudo systemctl restart gunicorn
    echo -e "${GREEN}✓ Gunicorn restarted${NC}"
elif systemctl list-units --type=service | grep -q license-manager; then
    sudo systemctl restart license-manager
    echo -e "${GREEN}✓ License Manager service restarted${NC}"
elif command -v supervisorctl &> /dev/null; then
    sudo supervisorctl restart license-manager
    echo -e "${GREEN}✓ Supervisor service restarted${NC}"
else
    echo -e "${YELLOW}⚠ Could not detect service manager. Please restart manually:${NC}"
    echo "   sudo systemctl restart <service-name>"
    echo "   OR"
    echo "   sudo supervisorctl restart <service-name>"
fi

echo ""

# Step 6: Check for errors
echo -e "${BLUE}Step 6: Checking for errors...${NC}"
python manage.py check --deploy

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ No errors detected${NC}"
else
    echo -e "${YELLOW}⚠ Some warnings detected. Please review.${NC}"
fi

echo ""
echo "================================================================================"
echo -e "${GREEN}Deployment Complete!${NC}"
echo "================================================================================"
echo ""
echo "Fixes Applied:"
echo "  ✓ Fixed float * Decimal type errors in Item Pivot Report"
echo "  ✓ Added Edit button to Allotments"
echo "  ✓ Updated Copy action to open in edit mode"
echo "  ✓ Fixed Excel export with grouped layout for Item Report"
echo "  ✓ Added missing serial_number column to SIONImportModel"
echo "  ✓ Database schema sync tools installed"
echo ""
echo "Next Steps:"
echo "  1. Test Item Pivot Report: https://labdhi.duckdns.org/reports/item-pivot"
echo "  2. Test Item Report: https://labdhi.duckdns.org/reports/item-report"
echo "  3. Test Allotments: https://labdhi.duckdns.org/allotments"
echo "  4. Test SION Classes: https://labdhi.duckdns.org/api/masters/sion-classes/"
echo ""
echo "If issues persist:"
echo "  - Check logs: sudo journalctl -u gunicorn -f"
echo "  - Run schema check: python manage.py sync_database_schema"
echo "  - Check migrations: python manage.py showmigrations"
echo ""
