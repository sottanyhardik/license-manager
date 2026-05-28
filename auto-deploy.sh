#!/bin/bash
# ============================================================
#  Auto-Deploy Script — License Manager
#  Deploys to all production servers, handles SSL certs and
#  nginx config automatically.
#
#  Usage:
#    ./auto-deploy.sh [BRANCH]          — deploy to all servers
#    ./auto-deploy.sh [BRANCH] <IP>     — deploy to one server only
#
#  Requires:
#    sshpass  →  sudo apt install sshpass   (or brew install sshpass)
#    DuckDNS token stored on each server at ~/duckdns.env:
#      DUCKDNS_TOKEN=your_token_here
# ============================================================

set -e

# ── Colors ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

print_header()  { echo -e "\n${BLUE}================================================${NC}"; echo -e "${BLUE}$1${NC}"; echo -e "${BLUE}================================================${NC}\n"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_error()   { echo -e "${RED}❌ $1${NC}"; }
print_warn()    { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_info()    { echo -e "${BLUE}→ $1${NC}"; }

# ── Configuration ───────────────────────────────────────────
SERVER_USER="django"
ALL_SERVERS=("143.110.252.201" "139.59.92.226" "165.232.185.220")
SERVER_PATH="/home/django/license-manager"
BRANCH="${1:-feature/Version5}"
PASSWORD="admin"

# Target: single server or all
if [ -n "$2" ]; then
    SERVERS=("$2")
else
    SERVERS=("${ALL_SERVERS[@]}")
fi

# ── Per-server metadata ──────────────────────────────────────
get_server_meta() {
    local ip=$1
    case "$ip" in
        "143.110.252.201")
            SERVER_DOMAIN="license-manager.duckdns.org"
            NGINX_CONF_HTTP="nginx-http-only.conf"      # used before cert exists
            NGINX_CONF_HTTPS="nginx-license-manager.conf" # used after cert
            NGINX_SITE_NAME="license-manager"
            DUCKDNS_SUBDOMAIN="license-manager"
            DB_NAME="license_manager_db"
            DB_USER="django"
            ;;
        "139.59.92.226")
            SERVER_DOMAIN="labdhi.duckdns.org"
            NGINX_CONF_HTTP="nginx-http-only.conf"
            NGINX_CONF_HTTPS="nginx-labdhi.conf"
            NGINX_SITE_NAME="labdhi"
            DUCKDNS_SUBDOMAIN="labdhi"
            DB_NAME="lmanagement"
            DB_USER="lmanagement"
            ;;
        "165.232.185.220")
            SERVER_DOMAIN="license-tractor.duckdns.org"
            NGINX_CONF_HTTP="nginx-http-only-tractor.conf"
            NGINX_CONF_HTTPS="nginx-license-tractor.conf"
            NGINX_SITE_NAME="license-tractor"
            DUCKDNS_SUBDOMAIN="license-tractor"
            DB_NAME="lmanagement"
            DB_USER="lmanagement"
            ;;
        *)
            print_error "Unknown server: $ip"; exit 1 ;;
    esac
}

# ── SSH helper ───────────────────────────────────────────────
ssh_cmd() {
    if command -v sshpass &>/dev/null; then
        sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" "$@"
    else
        ssh "$SERVER_USER@$SERVER_IP" "$@"
    fi
}

# ── Main deploy function ─────────────────────────────────────
deploy_to_server() {
    local SERVER_IP=$1
    get_server_meta "$SERVER_IP"

    print_header "🚀 Deploying to $SERVER_IP ($SERVER_DOMAIN)"

    ssh_cmd bash << ENDSSH
set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
echo_ok()   { echo -e "\${GREEN}  ✅ \$1\${NC}"; }
echo_info() { echo -e "\${BLUE}  → \$1\${NC}"; }
echo_warn() { echo -e "\${YELLOW}  ⚠️  \$1\${NC}"; }
echo_err()  { echo -e "\${RED}  ❌ \$1\${NC}"; }

# ── 0. DuckDNS: keep domain pointing to this server ─────────
echo_info "Updating DuckDNS IP for ${DUCKDNS_SUBDOMAIN}..."
if [ -f ~/duckdns.env ]; then
    source ~/duckdns.env
    RESULT=\$(curl -s "https://www.duckdns.org/update?domains=${DUCKDNS_SUBDOMAIN}&token=\$DUCKDNS_TOKEN&ip=")
    if [ "\$RESULT" = "OK" ]; then
        echo_ok "DuckDNS updated for ${DUCKDNS_SUBDOMAIN}.duckdns.org"
    else
        echo_warn "DuckDNS update returned: \$RESULT (token may be missing in ~/duckdns.env)"
    fi
else
    echo_warn "~/duckdns.env not found — skipping DuckDNS update"
    echo_warn "Create ~/duckdns.env with: DUCKDNS_TOKEN=your_token"
fi

# ── 1. Pull latest code ──────────────────────────────────────
echo_info "Pulling latest code from ${BRANCH}..."
cd $SERVER_PATH
git stash
git clean -fd
git fetch --all --prune
git checkout $BRANCH || git checkout -b $BRANCH origin/$BRANCH
git pull origin $BRANCH
echo_ok "Code updated to latest $BRANCH"

# ── 2. Backend: dependencies + migrations ───────────────────
echo_info "Installing Python dependencies..."
source $SERVER_PATH/venv/bin/activate
cd $SERVER_PATH/backend
pip install --upgrade pip --quiet
pip install --upgrade -r requirements.txt --quiet
echo_ok "Python dependencies installed"

echo_info "Running database migrations..."
python manage.py makemigrations --no-input 2>&1 | grep -E "No changes|Created|Apply" || true
if ! python manage.py migrate --no-input 2>&1 | tee /tmp/migration.log; then
    if grep -q "InsufficientPrivilege\|must be owner" /tmp/migration.log; then
        echo_warn "Permission issue — attempting fix..."
        echo '$PASSWORD' | sudo -S -u postgres psql -d ${DB_NAME} \
            -c "REASSIGN OWNED BY postgres TO ${DB_USER};" 2>/dev/null || true
        python manage.py migrate --no-input
    else
        echo_err "Migration failed"; cat /tmp/migration.log | tail -20; exit 1
    fi
fi
rm -f /tmp/migration.log
echo_ok "Migrations applied"

# ── 3. Static files ─────────────────────────────────────────
python manage.py collectstatic --no-input -v 0
echo_ok "Static files collected"

# ── 4. Frontend build ────────────────────────────────────────
echo_info "Building frontend..."
cd $SERVER_PATH/frontend
npm install --silent
npm run build
echo_ok "Frontend built"

# ── 5. Nginx config — HTTP phase (needed for cert verify) ────
echo_info "Installing HTTP nginx config..."
echo '$PASSWORD' | sudo -S cp $SERVER_PATH/${NGINX_CONF_HTTP} /etc/nginx/sites-available/${NGINX_SITE_NAME}-http

# Remove wrong/default sites
for WRONG in default license-manager labdhi license-tractor nginx-http-only; do
    [ "\$WRONG" = "${NGINX_SITE_NAME}-http" ] && continue
    [ "\$WRONG" = "${NGINX_SITE_NAME}" ] && continue
    echo '$PASSWORD' | sudo -S rm -f "/etc/nginx/sites-enabled/\$WRONG" 2>/dev/null || true
done

echo '$PASSWORD' | sudo -S ln -sf \
    /etc/nginx/sites-available/${NGINX_SITE_NAME}-http \
    /etc/nginx/sites-enabled/${NGINX_SITE_NAME}-http

echo '$PASSWORD' | sudo -S nginx -t
echo '$PASSWORD' | sudo -S systemctl reload nginx
echo_ok "HTTP nginx config active"

# ── 6. SSL certificate (get or renew) ───────────────────────
echo_info "Checking SSL certificate for ${SERVER_DOMAIN}..."
CERT_EXISTS=0
if echo '$PASSWORD' | sudo -S test -f "/etc/letsencrypt/live/${SERVER_DOMAIN}/fullchain.pem" 2>/dev/null; then
    CERT_EXISTS=1
fi

if [ \$CERT_EXISTS -eq 1 ]; then
    echo_info "Certificate found — renewing if needed..."
    echo '$PASSWORD' | sudo -S certbot renew --quiet --no-random-sleep-on-renew 2>&1 | \
        grep -E "renewed|no action|Congratulations" || true
    echo_ok "Certificate renewal checked"
else
    echo_info "No certificate found — requesting new one for ${SERVER_DOMAIN}..."
    # Read email from duckdns.env or use fallback
    ADMIN_EMAIL="admin@${SERVER_DOMAIN}"
    [ -f ~/duckdns.env ] && source ~/duckdns.env && [ -n "\$ADMIN_EMAIL" ] && ADMIN_EMAIL=\$ADMIN_EMAIL

    echo '$PASSWORD' | sudo -S certbot certonly --webroot \
        -w /var/www/html \
        -d ${SERVER_DOMAIN} \
        --non-interactive \
        --agree-tos \
        -m "\$ADMIN_EMAIL" \
        --deploy-hook "sudo systemctl reload nginx" 2>&1 | \
        grep -E "Congratulations|Certificate|Error|failed" || true

    # Verify cert was obtained
    if echo '$PASSWORD' | sudo -S test -f "/etc/letsencrypt/live/${SERVER_DOMAIN}/fullchain.pem" 2>/dev/null; then
        echo_ok "SSL certificate obtained for ${SERVER_DOMAIN}"
    else
        echo_warn "SSL cert could not be obtained — HTTPS will not work until DNS resolves correctly"
        echo_warn "Run manually: sudo certbot --nginx -d ${SERVER_DOMAIN}"
    fi
fi

# ── 7. Switch to HTTPS nginx config (if cert exists) ─────────
if echo '$PASSWORD' | sudo -S test -f "/etc/letsencrypt/live/${SERVER_DOMAIN}/fullchain.pem" 2>/dev/null; then
    echo_info "Installing HTTPS nginx config..."
    echo '$PASSWORD' | sudo -S cp $SERVER_PATH/${NGINX_CONF_HTTPS} /etc/nginx/sites-available/${NGINX_SITE_NAME}

    # Remove HTTP-only variant, enable HTTPS variant
    echo '$PASSWORD' | sudo -S rm -f /etc/nginx/sites-enabled/${NGINX_SITE_NAME}-http
    echo '$PASSWORD' | sudo -S ln -sf \
        /etc/nginx/sites-available/${NGINX_SITE_NAME} \
        /etc/nginx/sites-enabled/${NGINX_SITE_NAME}

    if echo '$PASSWORD' | sudo -S nginx -t 2>/dev/null; then
        echo '$PASSWORD' | sudo -S systemctl reload nginx
        echo_ok "HTTPS nginx config active for https://${SERVER_DOMAIN}"
    else
        echo_err "HTTPS nginx config invalid — keeping HTTP config"
        echo '$PASSWORD' | sudo -S ln -sf \
            /etc/nginx/sites-available/${NGINX_SITE_NAME}-http \
            /etc/nginx/sites-enabled/${NGINX_SITE_NAME}-http
        echo '$PASSWORD' | sudo -S systemctl reload nginx
    fi
else
    echo_warn "Running HTTP only — HTTPS requires a valid DNS record first"
fi

# ── 8. Services: materialized views, cache, gunicorn ────────
echo_info "Refreshing materialized views..."
cd $SERVER_PATH/backend
source $SERVER_PATH/venv/bin/activate
python manage.py shell -c "
from core.materialized_views import create_all_materialized_views
try: create_all_materialized_views(); print('Views OK')
except Exception as e: print(f'Views: {e}')
" 2>&1 | grep -E "OK|Views" || true

python manage.py refresh_materialized_views --all 2>&1 | tail -3 || true

echo_info "Warming caches..."
python manage.py shell -c "
from django.core.cache import cache
from core.models import CompanyModel
import json
try:
    companies = list(CompanyModel.objects.values('id','name'))
    cache.set('active_companies_list', json.dumps(companies), 3600)
    print(f'Cached {len(companies)} companies')
except Exception as e: print(f'Cache: {e}')
" 2>&1 | grep -E "Cached|Cache" || true
echo_ok "Cache warmed"

echo_info "Setting file permissions..."
echo '$PASSWORD' | sudo -S chown -R django:django $SERVER_PATH/backend/media 2>/dev/null || true
echo '$PASSWORD' | sudo -S chmod -R 775 $SERVER_PATH/backend/media 2>/dev/null || true
echo '$PASSWORD' | sudo -S chmod -R 755 $SERVER_PATH/frontend/dist 2>/dev/null || true

echo_info "Restarting application services..."
echo '$PASSWORD' | sudo -S supervisorctl restart license-manager

echo_info "Restarting Celery..."
echo '$PASSWORD' | sudo -S supervisorctl stop license-manager-celery 2>/dev/null || true
echo '$PASSWORD' | sudo -S pkill -9 -f "celery" 2>/dev/null || true
sleep 2
cd $SERVER_PATH/backend && source $SERVER_PATH/venv/bin/activate
celery -A lmanagement purge -f 2>/dev/null || true
echo '$PASSWORD' | sudo -S supervisorctl start license-manager-celery

# ── 9. Summary ───────────────────────────────────────────────
echo ""
echo -e "\${GREEN}================================================\${NC}"
echo -e "\${GREEN}🎉 Deployment complete — $SERVER_IP\${NC}"
echo -e "\${GREEN}================================================\${NC}"
echo_info "URL: https://${SERVER_DOMAIN}"
echo '$PASSWORD' | sudo -S supervisorctl status | grep license-manager
ENDSSH
}

# ── Run deployment ───────────────────────────────────────────
print_header "🚀 Auto-Deploy to ${#SERVERS[@]} server(s): ${SERVERS[*]}"
print_info  "Branch: $BRANCH"

FAILED=()
SUCCESS=0

for IP in "${SERVERS[@]}"; do
    if deploy_to_server "$IP"; then
        ((SUCCESS++))
        get_server_meta "$IP"
        print_success "Deployed: $IP → https://$SERVER_DOMAIN"
    else
        FAILED+=("$IP")
        print_error "Failed: $IP"
    fi
    echo ""
done

# ── Final summary ────────────────────────────────────────────
print_header "📊 Deployment Summary"
print_success "Success: $SUCCESS/${#SERVERS[@]} servers"

if [ ${#FAILED[@]} -gt 0 ]; then
    print_error "Failed: ${FAILED[*]}"
    exit 1
else
    print_success "All servers deployed successfully!"
    print_info "https://license-manager.duckdns.org  (143.110.252.201)"
    print_info "https://labdhi.duckdns.org            (139.59.92.226)"
    print_info "https://license-tractor.duckdns.org  (165.232.185.220)"
fi