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
#
#  Master-Data Service (ADR-001): when a server's backend/.env sets
#  MDS_ENABLED=true (+ MDS_BASE_URL / MDS_TOKEN), this deploy also installs the
#  mds-client package, applies its migration, and syncs master data from the
#  central MDS into the server's local mirror (best-effort — reads always come
#  from the local mirror, so a sync hiccup never blocks the deploy). The MDS
#  *service* itself is deployed separately: master-data-service/deploy/deploy-mds.sh
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

# ── Health gate ──────────────────────────────────────────────
# Polls /api/health/ on the deploy target from this machine.
# Called after each server's SSH block so we validate network
# reachability, nginx, and the Django app together.
wait_for_health() {
    local host="${1:-localhost}"
    local max_attempts=5
    local status
    for i in $(seq 1 $max_attempts); do
        status=$(curl -s -o /dev/null -w "%{http_code}" "http://${host}/api/health/" 2>/dev/null || echo "000")
        if [ "$status" = "200" ]; then
            print_success "Health check passed (HTTP 200)"
            return 0
        fi
        print_warn "Health check attempt $i/$max_attempts failed (HTTP $status), retrying in 3s..."
        sleep 3
    done
    print_error "Deploy failed: /api/health/ not 200 after $max_attempts attempts"
    return 1
}

# ── Configuration ───────────────────────────────────────────
SERVER_USER="django"
ALL_SERVERS=("143.110.252.201" "139.59.92.226" "165.232.185.220")
SERVER_PATH="/home/django/license-manager"
BRANCH="${1:-feature/Phase2}"
PASSWORD="${DEPLOY_PASSWORD:-}"          # set: export DEPLOY_PASSWORD=admin

if [ -z "$PASSWORD" ]; then
    print_error "DEPLOY_PASSWORD is not set. Run: export DEPLOY_PASSWORD=yourpassword"
    exit 1
fi

# ── Master-Data Service (ADR-001) ────────────────────────────
# MDS_ENABLED=true makes this deploy write MDS_ENABLED into each server's
# backend/.env, install mds-client, migrate it, and sync master data from the
# central MDS into the local mirror. Defaults to true (the goal state).
#
# For the SYNC to actually run, the MDS service must be deployed + reachable and
# a token supplied — pass them via env (never hardcode a token in this script):
#   export MDS_BASE_URL="https://masters.<host>/api/v1/"
#   export MDS_TOKEN="<this server's write-scoped token>"
# Without them, MDS is enabled but the sync step is skipped with a warning; the
# app still works fully (reads come from the local mirror tables).
# MDS is DISABLED by default: master writes stay local-only (the pre-MDS,
# byte-for-byte behavior). Set MDS_ENABLED=true explicitly to turn the cutover
# back on. When false, the deploy actively writes MDS_ENABLED=false into each
# server's backend/.env so a previously-enabled server is turned off.
MDS_ENABLED="${MDS_ENABLED:-false}"
MDS_BASE_URL="${MDS_BASE_URL:-}"
MDS_TOKEN="${MDS_TOKEN:-}"

# ── Secure media (opt-in) ────────────────────────────────────
# SECURE_MEDIA=true closes the public /media/ exposure: uploads are served only
# via the authenticated /api/media/<path> view + nginx X-Accel-Redirect. It writes
# MEDIA_X_ACCEL_REDIRECT=/protected-media/ into each server's backend/.env.
# PREREQS (do them in the SAME window — see docs/media-security-cutover.md):
#   1. nginx has the internal `location /protected-media/` block
#      (nginx-protected-media.conf) and the public `location /media/` removed;
#   2. the frontend no longer links /media/ directly or uses ?access_token=.
# Defaults to false = current public /media/ behavior (byte-for-byte unchanged).
SECURE_MEDIA="${SECURE_MEDIA:-false}"

# Map server IP → short name (used to pick the right .env file)
get_server_name() {
    case "$1" in
        "143.110.252.201") echo "license-manager" ;;
        "139.59.92.226")   echo "labdhi" ;;
        "165.232.185.220") echo "tractor" ;;
        *) echo "unknown" ;;
    esac
}

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
            DB_NAME="lmanagement"
            DB_USER="lmanagement"
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

# ── SSH / SCP helpers ────────────────────────────────────────
ssh_cmd() {
    if command -v sshpass &>/dev/null; then
        sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no -o LogLevel=ERROR "$SERVER_USER@$SERVER_IP" "$@"
    else
        ssh -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" "$@"
    fi
}
scp_cmd() {
    local src="$1" dest="$2"
    if command -v sshpass &>/dev/null; then
        sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no -o LogLevel=ERROR "$src" "$SERVER_USER@$SERVER_IP:$dest"
    else
        scp -o StrictHostKeyChecking=no "$src" "$SERVER_USER@$SERVER_IP:$dest"
    fi
}

# ── Main deploy function ─────────────────────────────────────
deploy_to_server() {
    local SERVER_IP=$1
    get_server_meta "$SERVER_IP"

    print_header "🚀 Deploying to $SERVER_IP ($SERVER_DOMAIN)"

    # ── Upload server-specific .env ──────────────────────────
    local ENV_NAME
    ENV_NAME=$(get_server_name "$SERVER_IP")
    local ENV_FILE
    ENV_FILE="$(dirname "$(realpath "$0")")/server-envs/${ENV_NAME}.env"
    if [ -f "$ENV_FILE" ]; then
        print_info "Uploading .env for $ENV_NAME..."
        scp_cmd "$ENV_FILE" "$SERVER_PATH/backend/.env"
        print_success ".env uploaded to $SERVER_PATH/backend/.env"
    else
        print_warn "No env file found at $ENV_FILE — server will use existing .env or process env"
    fi

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
# Note: do NOT run makemigrations on production — migrations must be committed
# to git and pulled. Running makemigrations here risks creating divergent
# auto-generated migration files across servers.
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

# ── 2a. Seed E132 planning-item masters (idempotent) ────────────────
# The data migration already seeds these on migrate; this is a belt-and-suspenders
# re-run so the six E132 planning-item masters always exist and are active.
echo_info "Seeding E132 planning-item masters..."
python manage.py seed_e132_plan_items || echo_warn "seed_e132_plan_items failed (non-fatal)"
echo_ok "E132 planning-item masters seeded"

# ── 2b. Secure media (opt-in) ────────────────────────────────
# Activate authenticated media serving only when SECURE_MEDIA=true AND the nginx
# internal block + frontend cutover are in place (docs/media-security-cutover.md).
if [ "$SECURE_MEDIA" = "true" ]; then
    echo_info "Enabling secure media (MEDIA_X_ACCEL_REDIRECT) in backend/.env..."
    touch .env
    sed -i '/^MEDIA_X_ACCEL_REDIRECT=/d' .env
    echo 'MEDIA_X_ACCEL_REDIRECT=/protected-media/' >> .env
    echo_ok "MEDIA_X_ACCEL_REDIRECT=/protected-media/ written to .env"
    echo_warn "Verify nginx has the internal 'location /protected-media/' block and the public /media/ block is removed — otherwise document downloads will 404."
else
    echo_info "Secure media OFF (public /media/). Set SECURE_MEDIA=true after the nginx + frontend cutover (docs/media-security-cutover.md)."
fi

# ── 2b. Master-Data Service: enable + client + mirror sync ───────────────
# When MDS_ENABLED=true (script config), write MDS_ENABLED/URL/TOKEN into this
# server's backend/.env, install mds-client, apply its migration, and pull master
# data from the central MDS into the local mirror. Best-effort — reads always come
# from the local mirror, so a sync hiccup never blocks the deploy. The MDS service
# itself deploys via master-data-service/deploy/deploy-mds.sh.
if [ "$MDS_ENABLED" = "true" ]; then
    echo_info "Enabling MDS in backend/.env..."
    cd $SERVER_PATH/backend
    touch .env
    sed -i '/^MDS_ENABLED=/d' .env; echo 'MDS_ENABLED=true' >> .env
    if [ -n '$MDS_BASE_URL' ]; then sed -i '/^MDS_BASE_URL=/d' .env; echo 'MDS_BASE_URL=$MDS_BASE_URL' >> .env; fi
    if [ -n '$MDS_TOKEN' ]; then sed -i '/^MDS_TOKEN=/d' .env; echo 'MDS_TOKEN=$MDS_TOKEN' >> .env; fi
    export MDS_ENABLED=true MDS_BASE_URL='$MDS_BASE_URL' MDS_TOKEN='$MDS_TOKEN'
    echo_ok "MDS_ENABLED=true written to .env"

    echo_info "Installing mds-client + applying its migration..."
    pip install -e $SERVER_PATH/mds-client --quiet || echo_warn "mds-client install failed"
    python manage.py migrate mds_client --no-input || echo_warn "mds_client migrate failed"

    if [ -n '$MDS_BASE_URL' ] && [ -n '$MDS_TOKEN' ]; then
        echo_info "Syncing master data from central MDS..."
        if python manage.py mds_sync 2>&1 | tail -8; then
            echo_ok "Master data synced from central MDS"
        else
            echo_warn "mds_sync failed — local mirror still serving reads; check MDS URL/token/reachability"
        fi
    else
        echo_warn "MDS enabled but MDS_BASE_URL/MDS_TOKEN not provided — skipping sync."
        echo_warn "  Set them: export MDS_BASE_URL=... MDS_TOKEN=...  (needs the MDS service deployed)"
    fi
else
    # MDS removed/disabled: force it OFF in this server's .env so master writes
    # go local-only. Reads already come from the local mirror tables, so nothing
    # else changes. This actively turns off a server that was previously enabled.
    echo_info "Disabling MDS in backend/.env (master writes local-only)..."
    cd $SERVER_PATH/backend
    touch .env
    sed -i '/^MDS_ENABLED=/d' .env; echo 'MDS_ENABLED=false' >> .env
    echo_ok "MDS_ENABLED=false written to .env — master edits no longer route through MDS"
fi

# ── 3. Static files ─────────────────────────────────────────
python manage.py collectstatic --no-input -v 0
echo_ok "Static files collected"

# ── 4. Frontend build ────────────────────────────────────────
echo_info "Building frontend..."
cd $SERVER_PATH/frontend
npm install --silent
npm run build
echo_ok "Frontend built"

# ── 5. Nginx config — HTTP phase (needed only when cert doesn't exist) ──
# Skip HTTP-only swap when a cert already exists — keeping the current HTTPS
# config avoids a transient "conflicting server name" warning when both the
# new -http symlink and the old HTTPS symlink overlap on port 80.
if echo '$PASSWORD' | sudo -S test -f "/etc/letsencrypt/live/${SERVER_DOMAIN}/fullchain.pem" 2>/dev/null; then
    echo_info "SSL cert exists — skipping HTTP-only nginx phase"
else
    echo_info "No SSL cert yet — installing HTTP-only nginx config to let certbot bootstrap..."
    echo '$PASSWORD' | sudo -S cp $SERVER_PATH/${NGINX_CONF_HTTP} /etc/nginx/sites-available/${NGINX_SITE_NAME}-http

    # Remove wrong/default sites that could shadow our port-80 server block
    for WRONG in default license-manager labdhi license-tractor nginx-http-only; do
        [ "\$WRONG" = "${NGINX_SITE_NAME}-http" ] && continue
        [ "\$WRONG" = "${NGINX_SITE_NAME}" ] && continue
        echo '$PASSWORD' | sudo -S rm -f "/etc/nginx/sites-enabled/\$WRONG" 2>/dev/null || true
    done

    # Remove any existing HTTPS-variant symlink during bootstrap to avoid
    # two port-80 server blocks declaring the same server_name.
    echo '$PASSWORD' | sudo -S rm -f /etc/nginx/sites-enabled/${NGINX_SITE_NAME} 2>/dev/null || true

    echo '$PASSWORD' | sudo -S ln -sf \
        /etc/nginx/sites-available/${NGINX_SITE_NAME}-http \
        /etc/nginx/sites-enabled/${NGINX_SITE_NAME}-http

    echo '$PASSWORD' | sudo -S nginx -t
    echo '$PASSWORD' | sudo -S systemctl reload nginx
    echo_ok "HTTP nginx config active (bootstrap)"
fi

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
# Migration core/0003_create_materialized_views.py creates the MVs on first
# migrate (idempotent via CREATE ... IF NOT EXISTS). This extra step refreshes
# their data and is harmless if the views already exist.
echo_info "Ensuring materialized views exist + refreshing..."
cd $SERVER_PATH/backend
source $SERVER_PATH/venv/bin/activate
python manage.py shell -c "
from apps.core.materialized_views import create_materialized_views, refresh_all_materialized_views
try:
    create_materialized_views()
    refresh_all_materialized_views(concurrently=False)
    print('Views OK')
except Exception as e:
    print(f'Views error: {e}')
" 2>&1 | grep -E "Views" || true

echo_info "Warming caches..."
python manage.py shell -c "
from django.core.cache import cache
from apps.core.models import CompanyModel
import json
try:
    companies = list(CompanyModel.objects.values('id','name'))
    cache.set('active_companies_list', json.dumps(companies), 3600)
    print(f'Cached {len(companies)} companies')
except Exception as e:
    print(f'Cache error: {e}')
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

    # ── Health gate (runs from deploy machine against server IP) ─
    print_info "Running post-deploy health check against http://${SERVER_IP}/api/health/ ..."
    wait_for_health "$SERVER_IP"
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