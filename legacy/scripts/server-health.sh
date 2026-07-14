#!/bin/bash

# Server Health & Verification Script
# Checks all 3 production servers for full functionality
# Usage: ./server-health.sh [--fix]

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
SERVER_USER="django"
SERVER_NAMES=("Global" "Labdhi" "Server3")
SERVER_HOSTS=("143.110.252.201" "139.59.92.226" "165.232.185.220")
SERVER_DOMAINS=("license-manager.duckdns.org" "labdhi.duckdns.org" "license-tractor.duckdns.org")
APP_PATH="/home/django/license-manager"
VENV_BIN="$APP_PATH/venv/bin"
BACKEND_PATH="$APP_PATH/backend"
PASSWORD="admin"
FIX_MODE=false

if [[ "$1" == "--fix" ]]; then
    FIX_MODE=true
fi

# Counters per server
declare -A SERVER_PASS
declare -A SERVER_FAIL
declare -A SERVER_WARN

print_header() {
    echo -e "\n${BOLD}${BLUE}══════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${BLUE}  $1${NC}"
    echo -e "${BOLD}${BLUE}══════════════════════════════════════════════════${NC}"
}

print_sub() {
    echo -e "\n${CYAN}── $1 ──${NC}"
}

ok()   { echo -e "  ${GREEN}✅ $1${NC}"; }
fail() { echo -e "  ${RED}❌ $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
info() { echo -e "  ${BLUE}→  $1${NC}"; }

ssh_run() {
    local host="$1"
    local cmd="$2"
    ssh -o StrictHostKeyChecking=no \
        -o ConnectTimeout=10 \
        -o BatchMode=yes \
        "$SERVER_USER@$host" "$cmd" 2>/dev/null
}

ssh_sudo() {
    local host="$1"
    local cmd="$2"
    ssh -o StrictHostKeyChecking=no \
        -o ConnectTimeout=10 \
        -o BatchMode=yes \
        "$SERVER_USER@$host" "echo '$PASSWORD' | sudo -S $cmd" 2>/dev/null
}

check_server() {
    local idx=$1
    local name="${SERVER_NAMES[$idx]}"
    local host="${SERVER_HOSTS[$idx]}"
    local domain="${SERVER_DOMAINS[$idx]}"
    local pass=0
    local fail=0
    local warn_count=0

    print_header "[$name] $host ($domain)"

    # ── 1. SSH Connectivity ──────────────────────────────────────────
    print_sub "SSH Connectivity"
    if ssh_run "$host" "echo ok" | grep -q ok; then
        ok "SSH connection"
        ((pass++))
    else
        fail "SSH connection FAILED — skipping server"
        SERVER_PASS[$idx]=0; SERVER_FAIL[$idx]=1; SERVER_WARN[$idx]=0
        return
    fi

    # ── 2. System Info ───────────────────────────────────────────────
    print_sub "System Resources"
    UPTIME=$(ssh_run "$host" "uptime -p")
    info "Uptime: $UPTIME"

    DISK=$(ssh_run "$host" "df -h $APP_PATH | tail -1 | awk '{print \$5\" used of \"\$2\" (\"\$4\" free)\"}'")
    DISK_PCT=$(ssh_run "$host" "df $APP_PATH | tail -1 | awk '{print \$5}' | tr -d '%'")
    if [ -n "$DISK_PCT" ] && [ "$DISK_PCT" -lt 85 ]; then
        ok "Disk: $DISK"
        ((pass++))
    elif [ -n "$DISK_PCT" ] && [ "$DISK_PCT" -lt 95 ]; then
        warn "Disk usage high: $DISK"
        ((warn_count++))
    else
        fail "Disk critically full: $DISK"
        ((fail++))
    fi

    MEM=$(ssh_run "$host" "free -h | awk '/^Mem:/{print \"Used: \"\$3\" / Total: \"\$2\" (Free: \"\$4\")\"}'")
    info "Memory: $MEM"

    # ── 3. PostgreSQL ────────────────────────────────────────────────
    print_sub "PostgreSQL"
    PG_STATUS=$(ssh_run "$host" "pg_isready -h localhost -U lmanagement -d lmanagement 2>&1")
    if echo "$PG_STATUS" | grep -q "accepting connections"; then
        ok "PostgreSQL accepting connections"
        ((pass++))
    else
        fail "PostgreSQL not accepting connections: $PG_STATUS"
        ((fail++))
    fi

    PG_TABLES=$(ssh_run "$host" "PGPASSWORD=lmanagement psql -U lmanagement -d lmanagement -t -c 'SELECT count(*) FROM information_schema.tables WHERE table_schema='\''public'\'';' 2>/dev/null | tr -d ' '")
    if [ -n "$PG_TABLES" ] && [ "$PG_TABLES" -gt 0 ] 2>/dev/null; then
        ok "Database has $PG_TABLES tables"
        ((pass++))
    else
        warn "Could not count tables (DB may be empty or misconfigured)"
        ((warn_count++))
    fi

    # Check pending migrations
    PENDING=$(ssh_run "$host" "cd $BACKEND_PATH && $VENV_BIN/python manage.py showmigrations 2>/dev/null | grep '\[ \]' | wc -l | tr -d ' '")
    if [ "$PENDING" = "0" ] || [ -z "$PENDING" ]; then
        ok "No pending migrations"
        ((pass++))
    else
        warn "$PENDING pending migration(s) — run: python manage.py migrate"
        ((warn_count++))
    fi

    # ── 4. Redis ─────────────────────────────────────────────────────
    print_sub "Redis"
    REDIS_PING=$(ssh_run "$host" "redis-cli ping 2>/dev/null")
    if [ "$REDIS_PING" = "PONG" ]; then
        ok "Redis responding (PONG)"
        ((pass++))
    else
        fail "Redis not responding (got: '$REDIS_PING')"
        ((fail++))
    fi

    REDIS_MEM=$(ssh_run "$host" "redis-cli info memory 2>/dev/null | grep used_memory_human | cut -d: -f2 | tr -d '\r'")
    [ -n "$REDIS_MEM" ] && info "Redis memory: $REDIS_MEM"

    # ── 5. Supervisor / Gunicorn ─────────────────────────────────────
    print_sub "Supervisor & Gunicorn"
    SUPER_STATUS=$(ssh_sudo "$host" "supervisorctl status")

    if echo "$SUPER_STATUS" | grep -q "license-manager "; then
        GUN_LINE=$(echo "$SUPER_STATUS" | grep "license-manager " | grep -v celery)
        if echo "$GUN_LINE" | grep -q "RUNNING"; then
            ok "license-manager (gunicorn): RUNNING"
            ((pass++))
        else
            fail "license-manager (gunicorn): $(echo "$GUN_LINE" | awk '{print $2}')"
            ((fail++))
            if $FIX_MODE; then
                info "Attempting restart..."
                ssh_sudo "$host" "supervisorctl start license-manager"
            fi
        fi
    else
        fail "license-manager supervisor program not found"
        ((fail++))
    fi

    # Test Gunicorn port directly
    GUN_PORT=$(ssh_run "$host" "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/ 2>/dev/null || echo 000")
    if [[ "$GUN_PORT" =~ ^(200|301|302|400|401|403|404)$ ]]; then
        ok "Gunicorn responding on :8000 (HTTP $GUN_PORT)"
        ((pass++))
    else
        fail "Gunicorn not responding on :8000 (HTTP $GUN_PORT)"
        ((fail++))
    fi

    # ── 6. Celery ────────────────────────────────────────────────────
    print_sub "Celery Worker"
    if echo "$SUPER_STATUS" | grep -q "license-manager-celery"; then
        CEL_LINE=$(echo "$SUPER_STATUS" | grep "license-manager-celery" | grep -v beat | head -1)
        if echo "$CEL_LINE" | grep -q "RUNNING"; then
            ok "license-manager-celery: RUNNING"
            ((pass++))
        else
            fail "license-manager-celery: $(echo "$CEL_LINE" | awk '{print $2}')"
            ((fail++))
            if $FIX_MODE; then
                info "Attempting restart..."
                ssh_sudo "$host" "supervisorctl start license-manager-celery"
            fi
        fi
    else
        fail "license-manager-celery supervisor program not found"
        ((fail++))
    fi

    # Check celery beat (may be combined in same process)
    CEL_BEAT_LINE=$(echo "$SUPER_STATUS" | grep "license-manager-celery-beat")
    if [ -n "$CEL_BEAT_LINE" ]; then
        if echo "$CEL_BEAT_LINE" | grep -q "RUNNING"; then
            ok "license-manager-celery-beat: RUNNING"
            ((pass++))
        else
            warn "license-manager-celery-beat: $(echo "$CEL_BEAT_LINE" | awk '{print $2}')"
            ((warn_count++))
        fi
    else
        # Check if beat is embedded in worker
        BEAT_PROC=$(ssh_run "$host" "ps aux | grep -c '[c]elery.*--beat'")
        if [ "$BEAT_PROC" -ge 1 ] 2>/dev/null; then
            ok "Celery beat embedded in worker process"
            ((pass++))
        else
            warn "Celery beat not found as separate service (may be embedded)"
            ((warn_count++))
        fi
    fi

    # ── 7. Nginx ─────────────────────────────────────────────────────
    print_sub "Nginx"
    NGINX_STATUS=$(ssh_sudo "$host" "systemctl is-active nginx")
    if [ "$NGINX_STATUS" = "active" ]; then
        ok "Nginx is active"
        ((pass++))
    else
        fail "Nginx status: $NGINX_STATUS"
        ((fail++))
        if $FIX_MODE; then
            info "Attempting nginx start..."
            ssh_sudo "$host" "systemctl start nginx"
        fi
    fi

    # Check nginx config valid
    NGINX_TEST=$(ssh_sudo "$host" "nginx -t 2>&1")
    if echo "$NGINX_TEST" | grep -q "syntax is ok"; then
        ok "Nginx config syntax valid"
        ((pass++))
    else
        fail "Nginx config syntax error: $(echo "$NGINX_TEST" | tail -1)"
        ((fail++))
    fi

    # ── 8. SSL Certificate ───────────────────────────────────────────
    print_sub "SSL Certificate"
    SSL_EXPIRY=$(ssh_run "$host" "echo | openssl s_client -connect $domain:443 -servername $domain 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2" 2>/dev/null)
    if [ -n "$SSL_EXPIRY" ]; then
        # Calculate days remaining
        EXPIRY_EPOCH=$(date -d "$SSL_EXPIRY" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$SSL_EXPIRY" +%s 2>/dev/null || echo 0)
        NOW_EPOCH=$(date +%s)
        DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))
        if [ "$DAYS_LEFT" -gt 30 ] 2>/dev/null; then
            ok "SSL cert valid for $DAYS_LEFT days (expires: $SSL_EXPIRY)"
            ((pass++))
        elif [ "$DAYS_LEFT" -gt 7 ] 2>/dev/null; then
            warn "SSL cert expires soon: $DAYS_LEFT days (expires: $SSL_EXPIRY)"
            ((warn_count++))
        else
            fail "SSL cert expires in $DAYS_LEFT days — renew now!"
            ((fail++))
        fi
    else
        # Try checking locally
        LOCAL_SSL=$(curl -sI --connect-timeout 5 "https://$domain" 2>&1 | head -1)
        if echo "$LOCAL_SSL" | grep -q "HTTP"; then
            ok "HTTPS accessible (cert check via openssl failed)"
            ((pass++))
        else
            warn "Could not verify SSL cert for $domain"
            ((warn_count++))
        fi
    fi

    # Check certbot renewal timer
    CERTBOT_STATUS=$(ssh_sudo "$host" "systemctl is-active certbot.timer 2>/dev/null || systemctl is-active certbot-renew.timer 2>/dev/null || echo inactive")
    if [ "$CERTBOT_STATUS" = "active" ]; then
        ok "Certbot auto-renewal timer active"
        ((pass++))
    else
        warn "Certbot auto-renewal timer not active — manual renewal may be needed"
        ((warn_count++))
    fi

    # ── 9. LibreOffice / PDF Conversion ─────────────────────────────
    print_sub "LibreOffice / PDF Conversion"
    LO_VERSION=$(ssh_run "$host" "soffice --version 2>/dev/null || libreoffice --version 2>/dev/null || echo ''")
    if [ -n "$LO_VERSION" ]; then
        ok "LibreOffice installed: $LO_VERSION"
        ((pass++))
    else
        fail "LibreOffice not installed"
        ((fail++))
        if $FIX_MODE; then
            info "Installing LibreOffice..."
            ssh_sudo "$host" "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libreoffice unoconv"
        fi
    fi

    # Test actual conversion
    LO_TEST=$(ssh_run "$host" "
        tmpdir=\$(mktemp -d)
        echo '<html><body><p>Test</p></body></html>' > \$tmpdir/test.html
        soffice --headless --convert-to pdf --outdir \$tmpdir \$tmpdir/test.html > /dev/null 2>&1
        if [ -f \$tmpdir/test.pdf ]; then echo 'ok'; else echo 'fail'; fi
        rm -rf \$tmpdir
    ")
    if [ "$LO_TEST" = "ok" ]; then
        ok "LibreOffice PDF conversion working"
        ((pass++))
    else
        fail "LibreOffice PDF conversion test failed"
        ((fail++))
    fi

    # Check unoconv
    UNOCONV=$(ssh_run "$host" "which unoconv 2>/dev/null")
    if [ -n "$UNOCONV" ]; then
        ok "unoconv available: $UNOCONV"
        ((pass++))
    else
        warn "unoconv not installed (LibreOffice fallback will be used)"
        ((warn_count++))
    fi

    # ── 10. File Permissions ─────────────────────────────────────────
    print_sub "File Permissions"
    MEDIA_PERM=$(ssh_run "$host" "[ -w $BACKEND_PATH/media ] && echo writable || echo readonly")
    if [ "$MEDIA_PERM" = "writable" ]; then
        ok "media/ directory is writable"
        ((pass++))
    else
        fail "media/ directory is NOT writable by django user"
        ((fail++))
        if $FIX_MODE; then
            ssh_sudo "$host" "chown -R django:django $BACKEND_PATH/media && chmod -R 775 $BACKEND_PATH/media"
        fi
    fi

    STATIC_OK=$(ssh_run "$host" "[ -d $BACKEND_PATH/staticfiles ] && [ \"\$(ls -A $BACKEND_PATH/staticfiles 2>/dev/null)\" ] && echo ok || echo empty")
    if [ "$STATIC_OK" = "ok" ]; then
        ok "staticfiles/ directory exists and is populated"
        ((pass++))
    else
        warn "staticfiles/ empty or missing — run collectstatic"
        ((warn_count++))
    fi

    LOGS_OK=$(ssh_run "$host" "[ -d $APP_PATH/logs ] && echo ok || echo missing")
    if [ "$LOGS_OK" = "ok" ]; then
        ok "logs/ directory exists"
        ((pass++))
    else
        warn "logs/ directory missing — creating"
        ((warn_count++))
        $FIX_MODE && ssh_run "$host" "mkdir -p $APP_PATH/logs"
    fi

    # ── 11. Application API Health ───────────────────────────────────
    print_sub "Application API Health"
    # Test via nginx (external)
    HTTP_CODE=$(curl -s -m 10 -o /dev/null -w "%{http_code}" "http://$host/api/" 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" =~ ^(200|301|302|401|403)$ ]]; then
        ok "HTTP API responding (http://$host/api/ → $HTTP_CODE)"
        ((pass++))
    else
        fail "HTTP API not responding (http://$host/api/ → $HTTP_CODE)"
        ((fail++))
    fi

    # Test HTTPS
    HTTPS_CODE=$(curl -s -m 10 -o /dev/null -w "%{http_code}" "https://$domain/api/" 2>/dev/null || echo "000")
    if [[ "$HTTPS_CODE" =~ ^(200|301|302|401|403)$ ]]; then
        ok "HTTPS API responding (https://$domain/api/ → $HTTPS_CODE)"
        ((pass++))
    else
        warn "HTTPS API: $HTTPS_CODE (may need SSL or DNS check)"
        ((warn_count++))
    fi

    # License count from API
    LICENSE_COUNT=$(curl -s -m 10 "http://$host/api/licenses/?page_size=1" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('count','?'))" 2>/dev/null || echo "N/A")
    if [ "$LICENSE_COUNT" != "N/A" ] && [ "$LICENSE_COUNT" != "?" ]; then
        ok "License API returns data ($LICENSE_COUNT total licenses)"
        ((pass++))
    else
        warn "Could not fetch license count (API may require auth)"
        ((warn_count++))
    fi

    # ── 12. Python / Django Environment ─────────────────────────────
    print_sub "Python / Django Environment"
    PY_VERSION=$(ssh_run "$host" "$VENV_BIN/python --version 2>&1")
    ok "Python: $PY_VERSION"

    DJANGO_CHECK=$(ssh_run "$host" "cd $BACKEND_PATH && $VENV_BIN/python manage.py check --deploy 2>&1 | tail -3")
    if echo "$DJANGO_CHECK" | grep -q "System check identified no issues"; then
        ok "Django system check: no issues"
        ((pass++))
    elif echo "$DJANGO_CHECK" | grep -q "System check identified"; then
        ISSUES=$(echo "$DJANGO_CHECK" | grep "System check identified" | grep -o '[0-9]* issue' || echo "some issues")
        warn "Django system check: $ISSUES"
        ((warn_count++))
    else
        warn "Django system check incomplete"
        ((warn_count++))
    fi

    # Check SECRET_KEY is not insecure default
    KEY_CHECK=$(ssh_run "$host" "cd $BACKEND_PATH && $VENV_BIN/python -c \"import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','lmanagement.settings'); import django; django.setup(); from django.conf import settings; print('insecure' if 'django-insecure' in settings.SECRET_KEY else 'ok')\" 2>/dev/null")
    if [ "$KEY_CHECK" = "ok" ]; then
        ok "SECRET_KEY is not using insecure default"
        ((pass++))
    elif [ "$KEY_CHECK" = "insecure" ]; then
        warn "SECRET_KEY is using insecure default value — update supervisor config"
        ((warn_count++))
    fi

    # ── 13. Git Status ───────────────────────────────────────────────
    print_sub "Git / Code Status"
    GIT_BRANCH=$(ssh_run "$host" "cd $APP_PATH && git branch --show-current 2>/dev/null")
    GIT_COMMIT=$(ssh_run "$host" "cd $APP_PATH && git log --oneline -1 2>/dev/null")
    info "Branch: $GIT_BRANCH"
    info "Last commit: $GIT_COMMIT"

    GIT_DIRTY=$(ssh_run "$host" "cd $APP_PATH && git status --porcelain 2>/dev/null | wc -l | tr -d ' '")
    if [ "$GIT_DIRTY" = "0" ]; then
        ok "Working directory clean"
        ((pass++))
    else
        warn "$GIT_DIRTY uncommitted file(s) on server"
        ((warn_count++))
    fi

    # ── 14. Supervisor config summary ───────────────────────────────
    print_sub "All Supervisor Services"
    echo "$SUPER_STATUS" | while IFS= read -r line; do
        if echo "$line" | grep -q "RUNNING"; then
            echo -e "  ${GREEN}  $line${NC}"
        elif [ -n "$line" ]; then
            echo -e "  ${RED}  $line${NC}"
        fi
    done

    # ── Server Summary ───────────────────────────────────────────────
    SERVER_PASS[$idx]=$pass
    SERVER_FAIL[$idx]=$fail
    SERVER_WARN[$idx]=$warn_count
}

# ── Main ─────────────────────────────────────────────────────────────────
echo -e "${BOLD}${BLUE}"
echo "╔══════════════════════════════════════════════════╗"
echo "║     License Manager — Server Health Check        ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "  Checking ${#SERVER_NAMES[@]} servers at $(date)"
$FIX_MODE && echo -e "  ${YELLOW}--fix mode enabled: will attempt to fix issues${NC}"
echo ""

for i in "${!SERVER_NAMES[@]}"; do
    check_server "$i"
done

# ── Final Summary Table ──────────────────────────────────────────────────
print_header "Health Summary"
printf "\n  %-10s %-22s %-25s %6s %6s %6s\n" "Server" "IP" "Domain" "PASS" "WARN" "FAIL"
printf "  %-10s %-22s %-25s %6s %6s %6s\n" "----------" "----------------------" "-------------------------" "------" "------" "------"

TOTAL_FAIL=0
for i in "${!SERVER_NAMES[@]}"; do
    name="${SERVER_NAMES[$i]}"
    host="${SERVER_HOSTS[$i]}"
    domain="${SERVER_DOMAINS[$i]}"
    p="${SERVER_PASS[$i]:-0}"
    w="${SERVER_WARN[$i]:-0}"
    f="${SERVER_FAIL[$i]:-0}"
    TOTAL_FAIL=$((TOTAL_FAIL + f))

    if [ "$f" -gt 0 ]; then
        COLOR=$RED
    elif [ "$w" -gt 0 ]; then
        COLOR=$YELLOW
    else
        COLOR=$GREEN
    fi

    printf "  ${COLOR}%-10s %-22s %-25s %6d %6d %6d${NC}\n" "$name" "$host" "$domain" "$p" "$w" "$f"
done

echo ""
if [ "$TOTAL_FAIL" -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}All servers healthy!${NC}"
else
    echo -e "  ${RED}${BOLD}$TOTAL_FAIL failure(s) found across servers.${NC}"
    echo -e "  ${YELLOW}Run with --fix to automatically remediate common issues.${NC}"
fi
echo ""
