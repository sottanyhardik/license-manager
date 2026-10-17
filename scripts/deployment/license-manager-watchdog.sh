#!/bin/bash
# ============================================================
#  license-manager-watchdog — checks this production server every 10 minutes:
#  RAM, disk, PostgreSQL, supervisor (Gunicorn + Celery), nginx, the local and
#  public health endpoints, and the login endpoint.
#
#  Remediation, in order:
#    1. restart the failing service (postgresql, supervisor programs, nginx)
#    2. re-run every check
#    3. if a blocking problem still remains, reboot the server — at most once
#       per REBOOT_COOLDOWN_SECONDS, so a broken server cannot reboot-loop.
#  Disk usage and nginx config errors are alert-only: restarts cannot fix them.
#
#  Usage (as root):
#    license-manager-watchdog.sh              check and remediate
#    license-manager-watchdog.sh --check      report only; exit 1 on any problem
#    PUBLIC_DOMAIN=<host> license-manager-watchdog.sh --install
#                                             install to /usr/local/sbin and cron
#
#  Config: /etc/license-manager-watchdog.env
#    PUBLIC_DOMAIN       required, e.g. license-manager.duckdns.org
#    MONITOR_USER        optional dedicated account for a real login test
#    MONITOR_PASSWORD    optional, paired with MONITOR_USER
# ============================================================

set -Eeuo pipefail

CONF_FILE="/etc/license-manager-watchdog.env"
if [ -f "$CONF_FILE" ]; then
    set -a
    . "$CONF_FILE"
    set +a
fi

PUBLIC_DOMAIN="${PUBLIC_DOMAIN:-}"
APP_PROGRAM="${APP_PROGRAM:-license-manager}"
CELERY_PROGRAM="${CELERY_PROGRAM:-license-manager-celery}"
APP_DB="${APP_DB:-lmanagement}"
LOCAL_APP_URL="${LOCAL_APP_URL:-http://127.0.0.1:8000}"
RAM_MIN_AVAIL_PCT="${RAM_MIN_AVAIL_PCT:-10}"
SWAP_MAX_USED_PCT="${SWAP_MAX_USED_PCT:-80}"
DISK_MAX_USED_PCT="${DISK_MAX_USED_PCT:-90}"
REBOOT_COOLDOWN_SECONDS="${REBOOT_COOLDOWN_SECONDS:-21600}"
LOG_FILE="${LOG_FILE:-/var/log/license-manager-watchdog.log}"
LOCK_FILE="/var/lock/license-manager-watchdog.lock"
STATE_DIR="/var/lib/license-manager-watchdog"
REBOOT_STAMP="$STATE_DIR/last-reboot"
INSTALL_PATH="/usr/local/sbin/license-manager-watchdog.sh"
CRON_FILE="/etc/cron.d/license-manager-watchdog"
MODE="${1:-run}"

[ "$(id -u)" -eq 0 ] || { echo "license-manager-watchdog must run as root" >&2; exit 2; }

# Each entry is "category|message". Categories decide the remediation.
PROBLEMS=()
add_problem() { PROBLEMS+=("$1|$2"); }

log() {
    local line
    line="$(date '+%Y-%m-%d %H:%M:%S') $*"
    echo "$line"
    echo "$line" >> "$LOG_FILE" 2>/dev/null || true
}

rotate_log() {
    if [ -f "$LOG_FILE" ] && [ "$(stat -c %s "$LOG_FILE")" -gt 5242880 ]; then
        mv -f "$LOG_FILE" "$LOG_FILE.1"
    fi
}

# ── Checks ──────────────────────────────────────────────────

check_disk() {
    local used_pct
    used_pct="$(df -P / | awk 'NR==2 {gsub("%", "", $5); print $5}')"
    if [ "$used_pct" -gt "$DISK_MAX_USED_PCT" ]; then
        add_problem disk "disk: / is ${used_pct}% full (alert at ${DISK_MAX_USED_PCT}%)"
    fi
}

check_ram() {
    local mem_total mem_avail swap_total swap_free avail_pct swap_used_pct
    mem_total="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
    mem_avail="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
    swap_total="$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)"
    swap_free="$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)"
    avail_pct=$((mem_avail * 100 / mem_total))
    if [ "$avail_pct" -lt "$RAM_MIN_AVAIL_PCT" ]; then
        add_problem ram "RAM: only ${avail_pct}% available (minimum ${RAM_MIN_AVAIL_PCT}%)"
    fi
    if [ "$swap_total" -gt 0 ]; then
        swap_used_pct=$(( (swap_total - swap_free) * 100 / swap_total ))
        if [ "$swap_used_pct" -gt "$SWAP_MAX_USED_PCT" ]; then
            add_problem ram "swap: ${swap_used_pct}% used (maximum ${SWAP_MAX_USED_PCT}%)"
        fi
    fi
}

check_postgres() {
    if ! runuser -u postgres -- psql -d "$APP_DB" -Atqc 'SELECT 1' >/dev/null 2>&1; then
        add_problem postgres "PostgreSQL does not answer queries on database $APP_DB"
    fi
}

check_supervisor() {
    local program state
    if ! supervisorctl version >/dev/null 2>&1; then
        add_problem supervisor "supervisord is not reachable"
        return
    fi
    for program in "$APP_PROGRAM" "$CELERY_PROGRAM"; do
        state="$(supervisorctl status "$program" 2>/dev/null || true)"
        if [[ "$state" != *RUNNING* ]]; then
            case "$program" in
                "$CELERY_PROGRAM") add_problem celery "$program is not RUNNING: ${state:-no status}" ;;
                *) add_problem app "$program is not RUNNING: ${state:-no status}" ;;
            esac
        fi
    done
}

check_nginx() {
    if ! systemctl is-active --quiet nginx; then
        add_problem nginx "nginx service is not active"
    elif ! nginx -t >/dev/null 2>&1; then
        add_problem nginxcfg "nginx configuration fails 'nginx -t' (not auto-fixed)"
    fi
}

check_local_health() {
    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
        -H "Host: $PUBLIC_DOMAIN" -H "X-Forwarded-Proto: https" \
        "$LOCAL_APP_URL/api/health/" 2>/dev/null || true)"
    if [ "$code" != "200" ]; then
        add_problem app "Gunicorn health endpoint returned HTTP ${code:-000} (expected 200)"
    fi
}

check_public_health() {
    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
        "https://$PUBLIC_DOMAIN/api/health/" 2>/dev/null || true)"
    if [ "$code" != "200" ]; then
        add_problem nginx "public health https://$PUBLIC_DOMAIN/api/health/ returned HTTP ${code:-000}"
    fi
}

check_login() {
    local code resp body
    # Bad credentials must be rejected with 401: this proves the login view and
    # its database lookup work without needing a real account.
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
        -H "Host: $PUBLIC_DOMAIN" -H "X-Forwarded-Proto: https" \
        -H 'Content-Type: application/json' \
        -d '{"username":"watchdog-probe","password":"invalid"}' \
        "$LOCAL_APP_URL/api/auth/login/" 2>/dev/null || true)"
    if [ "$code" != "401" ]; then
        add_problem app "login endpoint returned HTTP ${code:-000} for bad credentials (expected 401)"
    fi

    # A real login is verified only when a monitoring account is configured.
    if [ -n "${MONITOR_USER:-}" ] && [ -n "${MONITOR_PASSWORD:-}" ]; then
        body="$(jq -n --arg u "$MONITOR_USER" --arg p "$MONITOR_PASSWORD" '{username: $u, password: $p}')"
        resp="$(curl -s -w '\n%{http_code}' --max-time 15 \
            -H "Host: $PUBLIC_DOMAIN" -H "X-Forwarded-Proto: https" \
            -H 'Content-Type: application/json' -d "$body" \
            "$LOCAL_APP_URL/api/auth/login/" 2>/dev/null || true)"
        code="$(tail -n 1 <<< "$resp")"
        body="$(head -n -1 <<< "$resp")"
        if [ "$code" != "200" ] || ! jq -e '.access' <<< "$body" >/dev/null 2>&1; then
            add_problem app "monitoring account login failed (HTTP ${code:-000})"
        fi
    fi
}

run_checks() {
    PROBLEMS=()
    check_disk
    check_ram
    check_postgres
    check_supervisor
    check_local_health
    check_nginx
    check_public_health
    check_login
}

report_problems() {
    local entry
    for entry in "${PROBLEMS[@]}"; do
        log "PROBLEM ${entry#*|}"
    done
}

# Disk and nginx-config problems are alerts: restarting does not clear them.
blocking_problems() {
    local entry
    for entry in "${PROBLEMS[@]}"; do
        case "${entry%%|*}" in
            disk|nginxcfg) ;;
            *) return 0 ;;
        esac
    done
    return 1
}

# ── Remediation ─────────────────────────────────────────────

restart_postgres() {
    log "restarting postgresql"
    systemctl restart postgresql
}

restart_supervisor() {
    log "restarting supervisor"
    systemctl restart supervisor
}

restart_app() {
    log "restarting $APP_PROGRAM and $CELERY_PROGRAM"
    supervisorctl stop "$APP_PROGRAM" "$CELERY_PROGRAM" >/dev/null 2>&1 || true
    # A stale Gunicorn master outside supervisor keeps port 8000 busy and blocks
    # the restart, so clear only this application's Gunicorn processes first.
    pkill -9 -f '[g]unicorn.*lmanagement\.wsgi:application' 2>/dev/null || true
    sleep 2
    supervisorctl start "$APP_PROGRAM" "$CELERY_PROGRAM" || log "supervisorctl start reported an error"
}

restart_celery() {
    log "restarting $CELERY_PROGRAM"
    supervisorctl restart "$CELERY_PROGRAM" || log "supervisorctl restart reported an error"
}

restart_nginx() {
    log "restarting nginx"
    systemctl restart nginx
}

remediate() {
    local entry category
    local want_postgres=0 want_supervisor=0 want_app=0 want_celery=0 want_nginx=0
    for entry in "${PROBLEMS[@]}"; do
        category="${entry%%|*}"
        case "$category" in
            postgres) want_postgres=1 ;;
            supervisor) want_supervisor=1 ;;
            app|ram) want_app=1 ;;
            celery) want_celery=1 ;;
            nginx) want_nginx=1 ;;
        esac
    done
    [ "$want_postgres" -eq 1 ] && restart_postgres
    [ "$want_supervisor" -eq 1 ] && restart_supervisor
    if [ "$want_app" -eq 1 ]; then
        restart_app
    elif [ "$want_celery" -eq 1 ]; then
        restart_celery
    fi
    [ "$want_nginx" -eq 1 ] && restart_nginx
    return 0
}

reboot_if_allowed() {
    local now last=0
    now="$(date +%s)"
    if [ -f "$REBOOT_STAMP" ]; then
        last="$(cat "$REBOOT_STAMP")"
    fi
    if [ $((now - last)) -lt "$REBOOT_COOLDOWN_SECONDS" ]; then
        log "still failing after restart; reboot skipped (last reboot $(date -d "@$last" '+%Y-%m-%d %H:%M:%S'), cooldown ${REBOOT_COOLDOWN_SECONDS}s)"
        exit 1
    fi
    echo "$now" > "$REBOOT_STAMP"
    log "still failing after restart; rebooting server"
    systemctl reboot
}

# ── Entry points ────────────────────────────────────────────

install_watchdog() {
    [ -n "$PUBLIC_DOMAIN" ] || { echo "set PUBLIC_DOMAIN=<host> before --install" >&2; exit 2; }
    install -m 755 "$(readlink -f "$0")" "$INSTALL_PATH"
    mkdir -p "$STATE_DIR"
    if [ ! -f "$CONF_FILE" ]; then
        printf 'PUBLIC_DOMAIN=%s\n' "$PUBLIC_DOMAIN" > "$CONF_FILE"
        chmod 600 "$CONF_FILE"
    fi
    cat > "$CRON_FILE" <<EOF
# Managed by license-manager-watchdog --install. Re-run --install instead of editing.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
3-59/10 * * * * root flock -n $LOCK_FILE $INSTALL_PATH >/dev/null 2>&1
EOF
    chmod 644 "$CRON_FILE"
    echo "Installed $INSTALL_PATH and $CRON_FILE"
}

case "$MODE" in
    --install)
        install_watchdog
        exit 0
        ;;
    --check)
        run_checks
        if [ ${#PROBLEMS[@]} -eq 0 ]; then
            echo "OK: all checks passed"
            exit 0
        fi
        report_problems
        exit 1
        ;;
esac

# Serialise runs so cron and manual runs never overlap.
[ -n "$PUBLIC_DOMAIN" ] || { echo "PUBLIC_DOMAIN is not configured in $CONF_FILE" >&2; exit 2; }
exec 9>"$LOCK_FILE"
flock -n 9 || exit 0
mkdir -p "$STATE_DIR"
rotate_log

run_checks
if [ ${#PROBLEMS[@]} -eq 0 ]; then
    log "OK: all checks passed"
    exit 0
fi
report_problems

if blocking_problems; then
    log "attempting remediation"
    remediate
    run_checks
    if [ ${#PROBLEMS[@]} -eq 0 ]; then
        log "OK: recovered after restart"
        exit 0
    fi
    report_problems
fi

if blocking_problems; then
    reboot_if_allowed
fi

log "WARN: only alert-only problems remain (disk or nginx config)"
exit 0
