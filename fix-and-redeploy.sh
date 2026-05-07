#!/bin/bash

# Fix deployment issues and redeploy
# Issues to fix:
# 1. Missing esbuild package on servers
# 2. Untracked migration files
# 3. Frontend build failures

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SERVER_USER="django"
SERVERS=("143.110.252.201" "139.59.92.226" "165.232.185.220")
SERVER_PATH="/home/django/license-manager"
PASSWORD="admin"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}🔧 Fixing Deployment Issues${NC}"
echo -e "${BLUE}================================================${NC}\n"

for SERVER_IP in "${SERVERS[@]}"; do
    echo -e "${BLUE}→ Fixing issues on $SERVER_IP...${NC}"

    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP bash << 'ENDSSH'
set -e

cd /home/django/license-manager

# Fix 1: Clean untracked migration files
echo "→ Cleaning untracked migration files..."
git clean -fd backend/license/migrations/ || true

# Fix 2: Install esbuild explicitly
echo "→ Installing esbuild..."
cd frontend
npm install esbuild --save-dev || true
npm install --silent || true

# Fix 3: Clear node_modules and reinstall if needed
if [ ! -d "node_modules/esbuild" ]; then
    echo "→ esbuild not found, clearing and reinstalling..."
    rm -rf node_modules package-lock.json
    npm install
fi

echo "✅ Fixes applied on $(hostname -I | awk '{print $1}')"
ENDSSH

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Fixes applied on $SERVER_IP${NC}\n"
    else
        echo -e "${RED}❌ Failed to apply fixes on $SERVER_IP${NC}\n"
    fi
done

echo -e "\n${BLUE}================================================${NC}"
echo -e "${BLUE}🚀 Starting Redeployment${NC}"
echo -e "${BLUE}================================================${NC}\n"

# Run deployment again
./auto-deploy.sh
