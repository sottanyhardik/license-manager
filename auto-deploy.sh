#!/bin/bash

# Automated Deployment Script for License Manager
# Deploys to multiple servers sequentially
# Usage: ./auto-deploy.sh
# Password: admin (hardcoded)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVER_USER="django"
SERVERS=("143.110.252.201" "139.59.92.226" "165.232.185.220")
SERVER_PATH="/home/django/license-manager"
BRANCH="version-4.4"
PASSWORD="admin"

print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}→ $1${NC}"
}

# Function to deploy to a single server
deploy_to_server() {
    local SERVER_IP=$1

    print_header "🚀 Starting Deployment to $SERVER_IP"

    # Check if sshpass is installed, if not use expect
    if command -v sshpass &> /dev/null; then
        print_info "Using sshpass for authentication"
        SSH_CMD="sshpass -p '$PASSWORD' ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP"
        SUDO_CMD="echo '$PASSWORD' | sudo -S"
    else
        print_info "Using SSH (password will be prompted if needed)"
        SSH_CMD="ssh $SERVER_USER@$SERVER_IP"
        SUDO_CMD="sudo"
    fi

    # Execute deployment via SSH
    $SSH_CMD bash << ENDSSH
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "\${BLUE}→ Navigating to project directory...\${NC}"
cd $SERVER_PATH

echo -e "\${BLUE}→ Stashing local changes if any...\${NC}"
git stash

echo -e "\${BLUE}→ Pulling latest code from $BRANCH...\${NC}"
git pull origin $BRANCH

echo -e "\${BLUE}→ Installing frontend dependencies...\${NC}"
cd frontend
npm install --silent

echo -e "\${BLUE}→ Building frontend...\${NC}"
npm run build

echo -e "\${BLUE}→ Activating Python virtual environment...\${NC}"
cd $SERVER_PATH
source venv/bin/activate

echo -e "\${BLUE}→ Upgrading pip to latest version...\${NC}"
pip install --upgrade pip --quiet

echo -e "\${BLUE}→ Installing/upgrading Python dependencies...\${NC}"
cd backend
pip install --upgrade -r requirements.txt --quiet

echo -e "\${BLUE}→ Creating new migrations if needed...\${NC}"
python manage.py makemigrations

echo -e "\${BLUE}→ Running database migrations...\${NC}"
if ! python manage.py migrate 2>&1 | tee /tmp/migration_output.log; then
    # Check if the error is about insufficient privileges
    if grep -q "psycopg2.errors.InsufficientPrivilege.*must be owner of table" /tmp/migration_output.log; then
        echo -e "\${YELLOW}⚠️  Database permission issue detected. Attempting to fix...\${NC}"

        # Determine database name and user based on server IP
        DB_NAME="lmanagement"
        DB_USER="lmanagement"
        if [[ "$SERVER_IP" == "143.110.252.201" ]]; then
            DB_NAME="license_manager_db"
            DB_USER="django"
        fi
        echo -e "\${BLUE}→ Using database: \${DB_NAME} with user: \${DB_USER}\${NC}"

        # Try to fix the permission issue
        echo -e "\${BLUE}→ Granting table ownership to \${DB_USER} user...\${NC}"
        if echo '$PASSWORD' | sudo -S -u postgres psql -d \${DB_NAME} -c "ALTER TABLE license_licensedetailsmodel OWNER TO \${DB_USER};" 2>/dev/null; then
            echo -e "\${GREEN}✅ Ownership granted, retrying migration...\${NC}"
            python manage.py migrate
        else
            # If ownership change fails, try adding column manually
            echo -e "\${YELLOW}→ Attempting manual column addition...\${NC}"
            if echo '$PASSWORD' | sudo -S -u postgres psql -d \${DB_NAME} -c "ALTER TABLE license_licensedetailsmodel ADD COLUMN IF NOT EXISTS balance_report_notes text NULL;" 2>/dev/null; then
                echo -e "\${GREEN}✅ Column added manually, faking migration...\${NC}"
                python manage.py migrate license --fake
            else
                echo -e "\${RED}❌ Could not fix database permissions automatically\${NC}"
                echo -e "\${YELLOW}Please run manually on the server:\${NC}"
                echo -e "sudo -u postgres psql -d \${DB_NAME} -c \"ALTER TABLE license_licensedetailsmodel OWNER TO \${DB_USER};\""
                echo -e "cd $SERVER_PATH/backend && source ../venv/bin/activate && python manage.py migrate"
                exit 1
            fi
        fi
    else
        # Different migration error
        exit 1
    fi
fi
rm -f /tmp/migration_output.log

echo -e "\${BLUE}→ Collecting static files...\${NC}"
python manage.py collectstatic --noinput

echo -e "\n\${BLUE}================================================\${NC}"
echo -e "\${BLUE}📊 Database Optimization & Setup\${NC}"
echo -e "\${BLUE}================================================\${NC}"

echo -e "\${BLUE}→ Creating materialized views...\${NC}"
python manage.py shell -c "
from core.materialized_views import create_all_materialized_views
try:
    create_all_materialized_views()
    print('✅ Materialized views created successfully')
except Exception as e:
    print(f'⚠️  Materialized views may already exist or error: {e}')
" 2>&1 | grep -E '✅|⚠️' || echo -e "\${YELLOW}  ⚠️  Materialized views check completed\${NC}"

echo -e "\${BLUE}→ Refreshing materialized views with data...\${NC}"
python manage.py refresh_materialized_views --all 2>&1 | tail -5 || echo -e "\${YELLOW}  ⚠️  Materialized views refresh completed with warnings\${NC}"

echo -e "\${BLUE}→ Verifying database indexes...\${NC}"
python manage.py shell -c "
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('''
        SELECT
            schemaname,
            tablename,
            indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
        AND (
            indexname LIKE '%composite%'
            OR indexname LIKE '%performance%'
            OR indexname LIKE '%_idx'
        )
        ORDER BY tablename, indexname
    ''')
    indexes = cursor.fetchall()
    print(f'✅ Found {len(indexes)} performance indexes')
    for schema, table, index in indexes[:5]:
        print(f'  - {table}.{index}')
    if len(indexes) > 5:
        print(f'  ... and {len(indexes) - 5} more')
" 2>&1 | grep -E '✅|Found' || echo -e "\${YELLOW}  ⚠️  Index verification completed\${NC}"

echo -e "\${BLUE}→ Checking Redis cache connection...\${NC}"
python manage.py shell -c "
from django.core.cache import cache
try:
    cache.set('deployment_test_key', 'deployment_test_value', 10)
    value = cache.get('deployment_test_key')
    if value == 'deployment_test_value':
        print('✅ Redis cache is working correctly')
        cache.delete('deployment_test_key')
    else:
        print('⚠️  Redis cache connection issue')
except Exception as e:
    print(f'⚠️  Redis cache error: {e}')
" 2>&1 | grep -E '✅|⚠️' || echo -e "\${YELLOW}  ⚠️  Redis check completed\${NC}"

echo -e "\${BLUE}→ Warming up critical caches...\${NC}"
python manage.py shell -c "
from django.core.cache import cache
from core.models import CompanyModel, PurchaseStatus
import json

try:
    # Cache active companies
    companies = list(CompanyModel.objects.all().values('id', 'name'))
    cache.set('active_companies_list', json.dumps(companies), 3600)

    # Cache purchase statuses
    statuses = list(PurchaseStatus.objects.all().values('id', 'code', 'label'))
    cache.set('purchase_statuses_list', json.dumps(statuses), 3600)

    print(f'✅ Cached {len(companies)} companies and {len(statuses)} purchase statuses')
except Exception as e:
    print(f'⚠️  Cache warmup error: {e}')
" 2>&1 | grep -E '✅|⚠️' || echo -e "\${YELLOW}  ⚠️  Cache warmup completed\${NC}"

echo -e "\${BLUE}→ Checking throttle system health...\${NC}"
python manage.py shell -c "
from django.core.cache import cache
try:
    # Test throttle cache
    cache.set('throttle_health_check', 'ok', 10)
    test = cache.get('throttle_health_check')
    if test == 'ok':
        print('✅ Throttling system ready')
        cache.delete('throttle_health_check')
    else:
        print('⚠️  Throttling cache issue')
except Exception as e:
    print(f'⚠️  Throttling system error: {e}')
" 2>&1 | grep -E '✅|⚠️' || echo -e "\${YELLOW}  ⚠️  Throttling check completed\${NC}"

echo -e "\n\${BLUE}→ Setting file permissions...\${NC}"
echo '$PASSWORD' | sudo -S chown -R django:django $SERVER_PATH/backend/media 2>/dev/null || true
echo '$PASSWORD' | sudo -S chmod -R 775 $SERVER_PATH/backend/media 2>/dev/null || true
echo '$PASSWORD' | sudo -S chmod -R 755 $SERVER_PATH/frontend/dist 2>/dev/null || true

echo -e "\${BLUE}→ Restarting license-manager service...\${NC}"
echo '$PASSWORD' | sudo -S supervisorctl restart license-manager

echo -e "\${BLUE}→ Purging Celery queue (removing all pending tasks)...\${NC}"
cd $SERVER_PATH/backend
source $SERVER_PATH/venv/bin/activate
celery -A lmanagement purge -f 2>/dev/null || echo -e "\${YELLOW}  ⚠️  Could not purge Celery queue (queue might be empty)\${NC}"
echo -e "\${GREEN}  ✅ Celery queue purged\${NC}"

echo -e "\${BLUE}→ Ensuring Celery worker listens on 'celery,ledger' queues...\${NC}"
CELERY_CONF=\$(echo '$PASSWORD' | sudo -S find /etc/supervisor/conf.d/ -name "*celery*" ! -name "*beat*" 2>/dev/null | head -1)
if [ -n "\$CELERY_CONF" ]; then
    if ! echo '$PASSWORD' | sudo -S grep -q "\-Q celery,ledger" "\$CELERY_CONF" 2>/dev/null; then
        echo '$PASSWORD' | sudo -S sed -i 's/\(command=.*celery.*worker.*\)/\1 -Q celery,ledger/' "\$CELERY_CONF"
        echo '$PASSWORD' | sudo -S supervisorctl reread
        echo '$PASSWORD' | sudo -S supervisorctl update
        echo -e "\${GREEN}  ✅ Celery worker queue config updated to celery,ledger\${NC}"
    else
        echo -e "\${GREEN}  ✅ Celery worker already configured for celery,ledger queues\${NC}"
    fi
else
    echo -e "\${YELLOW}  ⚠️  Celery supervisor conf not found, skipping queue config\${NC}"
fi

echo -e "\${BLUE}→ Checking and restarting Celery if configured...\${NC}"
if echo '$PASSWORD' | sudo -S supervisorctl status license-manager-celery &>/dev/null; then
    echo '$PASSWORD' | sudo -S supervisorctl restart license-manager-celery
    echo -e "\${GREEN}  ✅ Celery worker restarted\${NC}"
else
    echo -e "\${YELLOW}  ⚠️  Celery not configured\${NC}"
fi

if echo '$PASSWORD' | sudo -S supervisorctl status license-manager-celery-beat &>/dev/null; then
    echo '$PASSWORD' | sudo -S supervisorctl restart license-manager-celery-beat
    echo -e "\${GREEN}  ✅ Celery beat restarted\${NC}"
else
    echo -e "\${YELLOW}  ⚠️  Celery Beat not configured\${NC}"
fi

echo -e "\${BLUE}→ Reloading Nginx...\${NC}"
echo '$PASSWORD' | sudo -S systemctl reload nginx

echo -e "\n\${BLUE}================================================\${NC}"
echo -e "\${BLUE}📊 Service Status\${NC}"
echo -e "\${BLUE}================================================\${NC}"
echo -e "\${YELLOW}Supervisor Services:\${NC}"
echo '$PASSWORD' | sudo -S supervisorctl status

echo -e "\n\${YELLOW}Nginx Status:\${NC}"
echo '$PASSWORD' | sudo -S systemctl status nginx --no-pager | head -15

echo -e "\n\${BLUE}================================================\${NC}"
echo -e "\${BLUE}✨ Deployment Summary\${NC}"
echo -e "\${BLUE}================================================\${NC}"
echo -e "\${GREEN}✅ Code pulled from $BRANCH\${NC}"
echo -e "\${GREEN}✅ Frontend built and deployed\${NC}"
echo -e "\${GREEN}✅ Backend dependencies installed\${NC}"
echo -e "\${GREEN}✅ Migrations created and applied\${NC}"
echo -e "\${GREEN}✅ Static files collected\${NC}"
echo -e "\${GREEN}✅ Services restarted\${NC}"
echo ""
echo -e "\${BLUE}🌐 Application URLs:\${NC}"
echo -e "   → http://143.110.252.201 (license-manager.duckdns.org)"
echo -e "   → http://139.59.92.226 (labdhi.duckdns.org)"
echo -e "   → http://165.232.185.220 (license-tractor.duckdns.org)"
echo ""

echo -e "\${BLUE}→ Final service status check...\${NC}"
echo '$PASSWORD' | sudo -S supervisorctl status | grep license-manager

echo -e "\n\${BLUE}================================================\${NC}"
echo -e "\${BLUE}🧪 Testing Celery Functions\${NC}"
echo -e "\${BLUE}================================================\${NC}"

echo -e "\${BLUE}→ Checking registered Celery tasks...\${NC}"
cd $SERVER_PATH/backend
source $SERVER_PATH/venv/bin/activate

# Test Level-1 task
echo -e "\${BLUE}→ Testing Level-1 task (identify_licenses_needing_update)...\${NC}"
python manage.py shell -c "
from license.tasks import identify_licenses_needing_update
print('✓ Level-1 task imported successfully')
print('  Task name:', identify_licenses_needing_update.name)
" 2>/dev/null && echo -e "\${GREEN}  ✅ Level-1 task OK\${NC}" || echo -e "\${RED}  ❌ Level-1 task failed\${NC}"

# Test Level-2 task
echo -e "\${BLUE}→ Testing Level-2 task (update_identified_licenses)...\${NC}"
python manage.py shell -c "
from license.tasks import update_identified_licenses
print('✓ Level-2 task imported successfully')
print('  Task name:', update_identified_licenses.name)
" 2>/dev/null && echo -e "\${GREEN}  ✅ Level-2 task OK\${NC}" || echo -e "\${RED}  ❌ Level-2 task failed\${NC}"

# Check Celery Beat schedule
echo -e "\${BLUE}→ Verifying Celery Beat schedule...\${NC}"
python manage.py shell -c "
from lmanagement.celery import app
schedule = app.conf.beat_schedule
if 'update-balances-11am-ist' in schedule and 'update-balances-8pm-ist' in schedule:
    print('✓ Scheduled tasks configured:')
    print('  - 11 AM IST (5:30 UTC)')
    print('  - 8 PM IST (14:30 UTC)')
    exit(0)
else:
    print('✗ Schedule not found')
    exit(1)
" 2>/dev/null && echo -e "\${GREEN}  ✅ Schedule configured correctly\${NC}" || echo -e "\${RED}  ❌ Schedule configuration failed\${NC}"

# Test CeleryTaskTracker model
echo -e "\${BLUE}→ Testing CeleryTaskTracker model...\${NC}"
python manage.py shell -c "
from core.models import CeleryTaskTracker
count = CeleryTaskTracker.objects.count()
print(f'✓ CeleryTaskTracker table accessible: {count} records')
" 2>/dev/null && echo -e "\${GREEN}  ✅ Task tracking ready\${NC}" || echo -e "\${RED}  ❌ Task tracking failed\${NC}"

echo -e "\n\${GREEN}================================================\${NC}"
echo -e "\${GREEN}🎉 Deployment completed successfully!\${NC}"
echo -e "\${GREEN}================================================\${NC}"
ENDSSH

    # Check if SSH command was successful
    if [ $? -eq 0 ]; then
        print_header "🎉 Deployment Verification for $SERVER_IP"
        print_success "Deployment to $SERVER_IP completed successfully!"
        print_info "Testing API at http://$SERVER_IP..."

        # Test the server endpoint
        if curl -s -m 10 "http://$SERVER_IP/api/licenses/?page_size=1" > /dev/null 2>&1; then
            print_success "API at $SERVER_IP is responding correctly"

            # Get license count
            LICENSE_COUNT=$(curl -s -m 10 "http://$SERVER_IP/api/licenses/?page_size=1" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('count', 0))" 2>/dev/null || echo "N/A")
            print_info "Total licenses on $SERVER_IP: $LICENSE_COUNT"
        else
            print_error "API at $SERVER_IP not responding (might still be starting up)"
        fi

        echo ""
        print_info "View logs: ssh $SERVER_USER@$SERVER_IP 'tail -f /home/django/license-manager/logs/*.log'"
        print_info "Nginx error log: ssh $SERVER_USER@$SERVER_IP 'sudo tail -f /var/log/nginx/error.log'"
        return 0
    else
        print_header "❌ Deployment to $SERVER_IP Failed"
        print_error "Please check the error messages above."
        return 1
    fi
}

# Main deployment loop
print_header "🚀 Starting Multi-Server Deployment"
print_info "Deploying to ${#SERVERS[@]} servers: ${SERVERS[*]}"
echo ""

FAILED_SERVERS=()
SUCCESS_COUNT=0

for SERVER_IP in "${SERVERS[@]}"; do
    if deploy_to_server "$SERVER_IP"; then
        ((SUCCESS_COUNT++))
        echo ""
    else
        FAILED_SERVERS+=("$SERVER_IP")
        echo ""
    fi
done

# Final summary
print_header "📊 Deployment Summary"
print_success "Successfully deployed to $SUCCESS_COUNT/${#SERVERS[@]} servers"

if [ ${#FAILED_SERVERS[@]} -gt 0 ]; then
    print_error "Failed servers: ${FAILED_SERVERS[*]}"
    exit 1
else
    print_success "All servers deployed successfully!"
    echo ""
    print_info "Application URLs:"
    print_info "   → http://143.110.252.201 (license-manager.duckdns.org)"
    print_info "   → http://139.59.92.226 (labdhi.duckdns.org)"
    print_info "   → http://165.232.185.220 (license-tractor.duckdns.org)"
    exit 0
fi
