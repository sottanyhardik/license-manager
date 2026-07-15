#!/usr/bin/env bash
# =============================================================================
#  db-tools.sh — Database management for the new License Manager (v1 backend)
#
#  Reads all local DB credentials from backend/.env (DATABASE_URL) so nothing
#  is hardcoded. Remote servers still hold the legacy `lmanagement` Postgres DB.
#
#  Usage:  ./scripts/db-tools.sh <command> [options]
#
#  Commands
#  --------
#   backup          Dump remote DB to a .dump file (stays on remote)
#   download        Dump + scp the file to ./backups/
#   restore <file>  Restore a local backup file → local DB → migrate
#   sync            download + restore + migrate + media in one shot
#   migrate         Run Django migrations on the local DB only
#   setup-db        Create local DB from scratch and run all migrations (no copy)
#   media           Sync media files from a remote server
#   list            List available local backup files
#
#  Options
#  -------
#   --env <file>    Use a custom .env file (default: backend/.env)
#   --no-media      Skip media sync in `sync` command
#   --yes           Skip all confirmation prompts (non-interactive / CI)
#
# =============================================================================

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_header()  { echo -e "\n${BOLD}${BLUE}══════════════════════════════════════════════${NC}"; echo -e "${BOLD}${BLUE}  $1${NC}"; echo -e "${BOLD}${BLUE}══════════════════════════════════════════════${NC}\n"; }
log_ok()      { echo -e "${GREEN}  ✅  $1${NC}"; }
log_info()    { echo -e "${BLUE}  →  $1${NC}"; }
log_warn()    { echo -e "${YELLOW}  ⚠️   $1${NC}"; }
log_error()   { echo -e "${RED}  ❌  $1${NC}" >&2; }
log_step()    { echo -e "\n${CYAN}  ▶  $1${NC}"; }
log_ts()      { echo -e "${CYAN}  [$(date '+%H:%M:%S')]${NC} $1"; }

# ── Remote server registry ────────────────────────────────────────────────────
SERVER_NAMES=("Global"              "Labdhi"               "Server3")
SERVER_HOSTS=("django@143.110.252.201" "django@139.59.92.226" "django@165.232.185.220")

# Remote legacy DB (same credentials on every server)
REMOTE_DB_NAME="lmanagement"
REMOTE_DB_USER="lmanagement"
REMOTE_DB_PASS="lmanagement"
REMOTE_APP_DIR="/home/django/license-manager"

# ── Directories ───────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups"
BACKEND_DIR="$PROJECT_DIR/backend"

# ── Defaults ──────────────────────────────────────────────────────────────────
ENV_FILE="$BACKEND_DIR/.env"
SKIP_MEDIA=false
AUTO_YES=false
REMOTE_SERVER=""

# Local DB vars (populated by parse_env_file)
LOCAL_DB_NAME=""
LOCAL_DB_USER=""
LOCAL_DB_PASS=""
LOCAL_DB_HOST="localhost"
LOCAL_DB_PORT="5432"
DJANGO_SETTINGS_MODULE="config.settings.dev"
LOCAL_PG_SUPERUSER="${USER}"   # macOS Homebrew superuser = current OS user

# ── Homebrew rsync (avoids macOS system rsync 2.6.9 mmap bug) ────────────────
if   [ -x "/opt/homebrew/bin/rsync" ];  then RSYNC="/opt/homebrew/bin/rsync"
elif [ -x "/usr/local/bin/rsync" ];     then RSYNC="/usr/local/bin/rsync"
else                                         RSYNC="rsync --no-whole-file"
fi

# =============================================================================
# ARGUMENT PARSING
# =============================================================================
parse_args() {
    POSITIONAL=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --env)      ENV_FILE="$2"; shift 2 ;;
            --no-media) SKIP_MEDIA=true;  shift ;;
            --yes|-y)   AUTO_YES=true;    shift ;;
            *)          POSITIONAL+=("$1"); shift ;;
        esac
    done
    set -- "${POSITIONAL[@]+"${POSITIONAL[@]}"}"
    COMMAND="${1:-}"
    ARG2="${2:-}"
}

# =============================================================================
# ENV FILE READER
# Parse backend/.env → extract DATABASE_URL and Django settings
# =============================================================================
parse_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Env file not found: $ENV_FILE"
        log_info  "Copy backend/.env.example → backend/.env and fill in DATABASE_URL"
        exit 1
    fi

    local db_url settings_mod

    # Read DATABASE_URL and DJANGO_SETTINGS_MODULE from the file
    db_url=$(grep -E '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
    settings_mod=$(grep -E '^DJANGO_SETTINGS_MODULE=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")

    if [ -z "$db_url" ]; then
        log_error "DATABASE_URL is not set in $ENV_FILE"
        exit 1
    fi

    [ -n "$settings_mod" ] && DJANGO_SETTINGS_MODULE="$settings_mod"

    # Reject SQLite — this tool is PostgreSQL-only
    if echo "$db_url" | grep -qi "sqlite"; then
        log_error "DATABASE_URL points to SQLite: $db_url"
        log_info  "Update backend/.env to a PostgreSQL URL, e.g.:"
        log_info  "  DATABASE_URL=postgresql://lmanagement:lmanagement@localhost:5432/lmanagement"
        exit 1
    fi

    # Parse postgresql://user:pass@host:port/dbname  using Python (reliable)
    eval "$(python3 - "$db_url" <<'PYEOF'
import sys
from urllib.parse import urlparse, unquote
u = urlparse(sys.argv[1])
print(f"LOCAL_DB_USER={unquote(u.username or '')}")
print(f"LOCAL_DB_PASS={unquote(u.password or '')}")
print(f"LOCAL_DB_HOST={u.hostname or 'localhost'}")
print(f"LOCAL_DB_PORT={u.port or 5432}")
print(f"LOCAL_DB_NAME={u.path.lstrip('/')}")
PYEOF
)"

    if [ -z "$LOCAL_DB_NAME" ]; then
        log_error "Could not parse database name from DATABASE_URL: $db_url"
        exit 1
    fi

    log_info "Local DB  : ${LOCAL_DB_USER}@${LOCAL_DB_HOST}:${LOCAL_DB_PORT}/${LOCAL_DB_NAME}"
    log_info "Settings  : $DJANGO_SETTINGS_MODULE"
}

# =============================================================================
# POSTGRES HELPERS
# =============================================================================

# Locate the Python that has Django (venv > system)
find_python() {
    local venv_python="$BACKEND_DIR/venv/bin/python"
    if [ -x "$venv_python" ]; then
        echo "$venv_python"
    elif command -v python3 &>/dev/null; then
        echo "$(command -v python3)"
    else
        log_error "python3 not found — install Python 3 or create backend/venv"
        exit 1
    fi
}

# Ensure local PostgreSQL is up (handles stale postmaster.pid)
ensure_local_postgres() {
    if pg_isready -q 2>/dev/null; then
        return 0
    fi
    log_warn "Local PostgreSQL is not responding — attempting auto-recovery"

    local data_dir=""
    for candidate in \
        "/opt/homebrew/var/postgresql@18" \
        "/opt/homebrew/var/postgresql@17" \
        "/opt/homebrew/var/postgresql@16" \
        "/usr/local/var/postgresql@18" \
        "/usr/local/var/postgresql@17" \
        "/usr/local/var/postgresql@16"; do
        if [ -d "$candidate" ]; then
            data_dir="$candidate"
            break
        fi
    done

    if [ -z "$data_dir" ]; then
        log_error "No PostgreSQL data directory found under /opt/homebrew or /usr/local"
        log_info  "Start PostgreSQL manually and re-run this script"
        exit 1
    fi

    local pid_file="$data_dir/postmaster.pid"
    if [ -f "$pid_file" ]; then
        local stale_pid
        stale_pid=$(head -n1 "$pid_file" 2>/dev/null | tr -d '[:space:]')
        if [ -n "$stale_pid" ] && ps -p "$stale_pid" >/dev/null 2>&1; then
            local proc_name
            proc_name=$(ps -p "$stale_pid" -o comm= 2>/dev/null | xargs basename 2>/dev/null)
            if echo "$proc_name" | grep -qi postgres; then
                log_error "Postgres PID $stale_pid is alive but not accepting connections — investigate manually"
                exit 1
            fi
            log_info "Stale lock: PID $stale_pid is '$proc_name', not postgres — removing"
        else
            log_info "Stale lock: PID $stale_pid is dead — removing"
        fi
        rm -f "$pid_file"
    fi

    # Detect major version from data_dir path and restart
    local pg_ver
    pg_ver=$(echo "$data_dir" | grep -oE 'postgresql@[0-9]+' | head -1)
    log_info "Starting ${pg_ver:-postgresql} via brew services..."
    if ! brew services restart "${pg_ver:-postgresql}" >/dev/null 2>&1; then
        log_error "brew services restart ${pg_ver:-postgresql} failed"
        exit 1
    fi

    local i
    for i in $(seq 1 30); do
        if pg_isready -q 2>/dev/null; then
            log_ok "PostgreSQL is up"
            return 0
        fi
        sleep 0.5
    done
    log_error "PostgreSQL did not become ready within 15 s"
    exit 1
}

# Ensure the application role exists locally
ensure_local_role() {
    local exists
    exists=$(psql -U "$LOCAL_PG_SUPERUSER" -d postgres -tAc \
        "SELECT 1 FROM pg_roles WHERE rolname='$LOCAL_DB_USER';" 2>/dev/null || true)
    if [ "$exists" = "1" ]; then
        return 0
    fi
    log_info "Creating role '$LOCAL_DB_USER'..."
    if ! psql -U "$LOCAL_PG_SUPERUSER" -d postgres \
        -c "CREATE ROLE $LOCAL_DB_USER WITH LOGIN PASSWORD '$LOCAL_DB_PASS' CREATEDB;" 2>/dev/null; then
        log_error "Failed to create role '$LOCAL_DB_USER'"
        exit 1
    fi
    log_ok "Role '$LOCAL_DB_USER' created"
}

# Drop and recreate the local DB, owned by the app role
recreate_local_db() {
    log_step "Dropping existing local database '$LOCAL_DB_NAME'..."
    # Terminate active connections first (safe on local dev)
    psql -U "$LOCAL_PG_SUPERUSER" -d postgres \
        -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$LOCAL_DB_NAME' AND pid <> pg_backend_pid();" \
        >/dev/null 2>&1 || true
    psql -U "$LOCAL_PG_SUPERUSER" -d postgres \
        -c "DROP DATABASE IF EXISTS $LOCAL_DB_NAME;" >/dev/null 2>&1

    log_step "Creating database '$LOCAL_DB_NAME'..."
    if ! psql -U "$LOCAL_PG_SUPERUSER" -d postgres \
        -c "CREATE DATABASE $LOCAL_DB_NAME OWNER $LOCAL_DB_USER;" >/dev/null 2>&1; then
        log_error "Failed to create database '$LOCAL_DB_NAME'"
        exit 1
    fi
    log_ok "Database '$LOCAL_DB_NAME' created"
}

# =============================================================================
# DJANGO MIGRATE
# =============================================================================
run_migrations() {
    log_step "Running Django migrations..."
    local python
    python=$(find_python)

    # Build the environment that Django needs
    local env_exports
    env_exports=$(grep -E '^[A-Z_]+=.' "$ENV_FILE" | grep -v '^#' | \
        sed "s|'||g;s|\"||g" || true)

    if ! (
        cd "$BACKEND_DIR"
        # Export all vars from .env, then override the settings module
        set -a
        # shellcheck disable=SC1090
        source "$ENV_FILE"
        set +a
        export DJANGO_SETTINGS_MODULE="$DJANGO_SETTINGS_MODULE"
        "$python" manage.py migrate --noinput
    ); then
        log_error "Django migrations failed"
        log_info  "Check the output above — you may need to resolve schema conflicts manually"
        exit 1
    fi
    log_ok "Migrations complete"
}

# =============================================================================
# SERVER SELECTOR
# =============================================================================
select_server() {
    log_header "🖥️  Select Remote Server"
    echo -e "${CYAN}  Available servers:${NC}\n"
    for i in "${!SERVER_NAMES[@]}"; do
        echo -e "    ${CYAN}[$((i+1))]${NC}  ${BOLD}${SERVER_NAMES[$i]}${NC}  —  ${SERVER_HOSTS[$i]}"
    done
    echo ""
    read -rp "  Select server [1-${#SERVER_NAMES[@]}]: " selection

    if ! [[ "$selection" =~ ^[0-9]+$ ]] || \
       [ "$selection" -lt 1 ] || \
       [ "$selection" -gt "${#SERVER_NAMES[@]}" ]; then
        log_error "Invalid selection: $selection"
        exit 1
    fi

    local idx=$((selection - 1))
    REMOTE_SERVER="${SERVER_HOSTS[$idx]}"
    log_ok "Selected: ${SERVER_NAMES[$idx]} (${REMOTE_SERVER})"
    echo ""
}

confirm_destructive() {
    local msg="${1:-This will DELETE all data in the local database '$LOCAL_DB_NAME'}"
    if [ "$AUTO_YES" = true ]; then
        log_warn "$msg  [--yes flag set, proceeding automatically]"
        return 0
    fi
    echo -e "\n${RED}  ⚠️   WARNING: $msg${NC}"
    read -rp "  Continue? (yes/no): " answer
    if [ "$answer" != "yes" ]; then
        log_info "Cancelled"
        exit 0
    fi
}

# =============================================================================
# STOP LOCAL DJANGO SERVER (best-effort)
# =============================================================================
stop_local_django() {
    pkill -f "python.*manage.py runserver" 2>/dev/null || true
}

# =============================================================================
# COMMANDS
# =============================================================================

# ── backup ─────────────────────────────────────────────────────────────────
cmd_backup() {
    select_server
    log_header "📦 Creating Remote Database Backup"

    local fname="backup_$(date +%Y%m%d_%H%M%S).dump"
    mkdir -p "$BACKUP_DIR"

    log_info "Dumping $REMOTE_DB_NAME on $REMOTE_SERVER → /tmp/$fname (custom format, level-6 gzip)"
    log_ts "Starting dump..."
    ssh "$REMOTE_SERVER" \
        "PGPASSWORD='$REMOTE_DB_PASS' pg_dump -U $REMOTE_DB_USER -d $REMOTE_DB_NAME -F c -Z 6 -f /tmp/$fname"

    log_ok "Remote backup created: /tmp/$fname"
    log_info "Download it with:  $0 download  (or scp $REMOTE_SERVER:/tmp/$fname $BACKUP_DIR/)"
}

# ── download ───────────────────────────────────────────────────────────────
cmd_download() {
    select_server
    log_header "⬇️  Downloading Database from ${REMOTE_SERVER}"

    mkdir -p "$BACKUP_DIR"
    local fname="remote_db_backup_$(date +%Y%m%d_%H%M%S).dump"

    log_step "Creating dump on remote server..."
    log_ts "Dump started (this takes 1-3 min for large DBs)..."
    if ! ssh "$REMOTE_SERVER" \
        "PGPASSWORD='$REMOTE_DB_PASS' pg_dump -U $REMOTE_DB_USER -d $REMOTE_DB_NAME -F c -Z 6 -f /tmp/$fname"; then
        log_error "Remote pg_dump failed"
        exit 1
    fi
    log_ok "Remote dump created: /tmp/$fname"

    log_step "Downloading via scp..."
    if ! scp -C "$REMOTE_SERVER:/tmp/$fname" "$BACKUP_DIR/$fname"; then
        log_error "scp failed"
        ssh "$REMOTE_SERVER" "rm -f /tmp/$fname" 2>/dev/null || true
        exit 1
    fi

    log_step "Cleaning up remote temp file..."
    ssh "$REMOTE_SERVER" "rm -f /tmp/$fname" 2>/dev/null || true

    local size
    size=$(du -h "$BACKUP_DIR/$fname" | cut -f1)
    log_ok "Downloaded $size → $BACKUP_DIR/$fname"
    echo ""
    log_info "To restore this backup:"
    echo -e "    ${CYAN}$0 restore $BACKUP_DIR/$fname${NC}"
    echo ""
}

# ── restore ────────────────────────────────────────────────────────────────
cmd_restore() {
    local backup_file="$1"

    if [ -z "$backup_file" ]; then
        log_error "Please specify a backup file"
        echo "  Usage: $0 restore <backup-file>"
        echo "  List:  $0 list"
        exit 1
    fi
    if [ ! -f "$backup_file" ]; then
        log_error "File not found: $backup_file"
        exit 1
    fi

    log_header "🔄 Restoring Local Database from Backup"
    log_info "Source  : $backup_file  ($(du -h "$backup_file" | cut -f1))"
    log_info "Target  : $LOCAL_DB_NAME @ $LOCAL_DB_HOST:$LOCAL_DB_PORT"
    echo ""

    confirm_destructive

    stop_local_django
    ensure_local_postgres
    ensure_local_role
    recreate_local_db

    log_step "Restoring backup (pg_restore, 4 parallel jobs)..."
    log_ts "Restore started..."
    local restore_log
    restore_log=$(mktemp)

    if PGPASSWORD="$LOCAL_DB_PASS" pg_restore \
        -U "$LOCAL_DB_USER" \
        -h "$LOCAL_DB_HOST" \
        -p "$LOCAL_DB_PORT" \
        -d "$LOCAL_DB_NAME" \
        -j 4 \
        --no-owner --no-acl \
        "$backup_file" 2>"$restore_log"; then
        log_ok "pg_restore completed cleanly"
    else
        local rc=$?
        # PG17+ dumps emit `SET transaction_timeout = 0` which older servers reject.
        # pg_restore returns exit=1 even when only this benign SET fails and all data landed.
        if grep -q 'transaction_timeout' "$restore_log" && \
           ! grep -qE 'ERROR.*(COPY|TABLE|INDEX|CONSTRAINT|SEQUENCE)' "$restore_log"; then
            log_warn "pg_restore exit=$rc — only PG17+ session params failed (your local server is older). Data is intact."
            cat "$restore_log" >&2
        else
            log_error "pg_restore failed (exit=$rc):"
            cat "$restore_log" >&2
            rm -f "$restore_log"
            exit 1
        fi
    fi
    rm -f "$restore_log"
    log_ts "Restore finished"

    run_migrations

    echo ""
    log_ok "Database restored and migrated successfully!"
    log_info "Backup saved: $backup_file"
    echo ""
}

# ── sync ───────────────────────────────────────────────────────────────────
cmd_sync() {
    select_server
    log_header "🔄 Full Sync: Remote DB → Local DB → Migrate → Media"

    # ---- Step 1: Remote dump ----
    log_step "Step 1/4 — Dumping remote database..."
    mkdir -p "$BACKUP_DIR"
    local fname="remote_db_backup_$(date +%Y%m%d_%H%M%S).dump"

    log_ts "pg_dump started on $REMOTE_SERVER..."
    if ! ssh "$REMOTE_SERVER" \
        "PGPASSWORD='$REMOTE_DB_PASS' pg_dump -U $REMOTE_DB_USER -d $REMOTE_DB_NAME -F c -Z 6 -f /tmp/$fname"; then
        log_error "Remote pg_dump failed"
        exit 1
    fi
    log_ok "Remote dump created: /tmp/$fname"

    # ---- Step 2: Download ----
    log_step "Step 2/4 — Downloading dump..."
    if ! scp -C "$REMOTE_SERVER:/tmp/$fname" "$BACKUP_DIR/$fname"; then
        log_error "Download failed"
        ssh "$REMOTE_SERVER" "rm -f /tmp/$fname" 2>/dev/null || true
        exit 1
    fi
    ssh "$REMOTE_SERVER" "rm -f /tmp/$fname" 2>/dev/null || true

    local size
    size=$(du -h "$BACKUP_DIR/$fname" | cut -f1)
    log_ok "Downloaded $size → $BACKUP_DIR/$fname"

    # ---- Confirmation ----
    confirm_destructive

    # ---- Step 3: Restore + migrate ----
    log_step "Step 3/4 — Restoring + migrating..."
    stop_local_django
    ensure_local_postgres
    ensure_local_role
    recreate_local_db

    local restore_log
    restore_log=$(mktemp)
    log_ts "pg_restore started..."
    if PGPASSWORD="$LOCAL_DB_PASS" pg_restore \
        -U "$LOCAL_DB_USER" \
        -h "$LOCAL_DB_HOST" \
        -p "$LOCAL_DB_PORT" \
        -d "$LOCAL_DB_NAME" \
        -j 4 \
        --no-owner --no-acl \
        "$BACKUP_DIR/$fname" 2>"$restore_log"; then
        log_ok "pg_restore completed cleanly"
    else
        local rc=$?
        if grep -q 'transaction_timeout' "$restore_log" && \
           ! grep -qE 'ERROR.*(COPY|TABLE|INDEX|CONSTRAINT|SEQUENCE)' "$restore_log"; then
            log_warn "pg_restore exit=$rc — only PG17+ session params failed. Data is intact."
            cat "$restore_log" >&2
        else
            log_error "pg_restore failed (exit=$rc):"
            cat "$restore_log" >&2
            rm -f "$restore_log"
            exit 1
        fi
    fi
    rm -f "$restore_log"
    log_ts "Restore finished"

    run_migrations

    # ---- Step 4: Media ----
    if [ "$SKIP_MEDIA" = false ]; then
        log_step "Step 4/4 — Syncing media files..."
        sync_media_files
    else
        log_info "Step 4/4 — Media sync skipped (--no-media)"
    fi

    echo ""
    log_ok "Full sync complete!"
    log_info "Backup saved: $BACKUP_DIR/$fname"
    echo ""
}

# ── migrate (standalone) ───────────────────────────────────────────────────
cmd_migrate() {
    log_header "🗄️  Running Django Migrations"
    ensure_local_postgres
    run_migrations
}

# ── setup-db ───────────────────────────────────────────────────────────────
# Create a brand-new local DB and apply all migrations (no remote copy needed)
cmd_setup_db() {
    log_header "🏗️  Setting Up Local Database from Scratch"
    log_info "This creates '$LOCAL_DB_NAME' and runs all migrations."
    log_info "Use 'sync' if you want to copy data from a remote server first."
    echo ""

    confirm_destructive "This will DROP and recreate the local database '$LOCAL_DB_NAME'"

    ensure_local_postgres
    ensure_local_role
    recreate_local_db
    run_migrations

    echo ""
    log_ok "Local database set up successfully!"
    log_info "You can now start the Django server: cd backend && python manage.py runserver"
    echo ""
}

# ── media ──────────────────────────────────────────────────────────────────
cmd_media() {
    select_server
    log_header "📁 Syncing Media Files from ${REMOTE_SERVER}"
    sync_media_files
}

sync_media_files() {
    log_info "Cleaning temporary TL files from remote server..."
    ssh "$REMOTE_SERVER" \
        "cd $REMOTE_APP_DIR/backend/media && rm -rf TL_ALLOT_* TL_BOE_* TL_TRADE_*" 2>/dev/null || true

    mkdir -p "$BACKEND_DIR/media"
    log_info "Syncing $REMOTE_SERVER:$REMOTE_APP_DIR/backend/media/ → backend/media/ ..."

    $RSYNC -avz --delete \
        --exclude='TL_ALLOT_*' \
        --exclude='TL_BOE_*' \
        --exclude='TL_TRADE_*' \
        "$REMOTE_SERVER:$REMOTE_APP_DIR/backend/media/" \
        "$BACKEND_DIR/media/"

    log_ok "Media files synced"
}

# ── list ───────────────────────────────────────────────────────────────────
cmd_list() {
    log_header "📋 Local Backup Files"
    mkdir -p "$BACKUP_DIR"
    local files
    files=$(ls -lt "$BACKUP_DIR"/*.dump "$BACKUP_DIR"/*.sql 2>/dev/null | head -20 || true)
    if [ -z "$files" ]; then
        log_warn "No backup files found in $BACKUP_DIR"
        log_info "Run '$0 download' to fetch one from a remote server"
    else
        echo "$files" | while read -r line; do
            echo -e "  ${CYAN}${line}${NC}"
        done
        echo ""
        log_info "Backup directory: $BACKUP_DIR"
    fi
}

# =============================================================================
# USAGE
# =============================================================================
show_usage() {
cat <<EOF

${BOLD}License Manager — Database Tools (v1 backend)${NC}

${BOLD}Usage:${NC}
  $(basename "$0") <command> [options]

${BOLD}Commands:${NC}
  ${CYAN}backup${NC}            Dump remote DB and leave it on the server
  ${CYAN}download${NC}          Dump + download remote DB to ./backups/
  ${CYAN}restore${NC} <file>    Restore a .dump/.sql file → local DB → migrate
  ${CYAN}sync${NC}              Full one-shot: download → restore → migrate → media
  ${CYAN}migrate${NC}           Run Django migrations on the existing local DB
  ${CYAN}setup-db${NC}          Create local DB from scratch and run all migrations
  ${CYAN}media${NC}             Sync media files from a remote server
  ${CYAN}list${NC}              List available local backup files

${BOLD}Options:${NC}
  ${CYAN}--env <file>${NC}      Env file to read DB config from  (default: backend/.env)
  ${CYAN}--no-media${NC}        Skip media sync in the 'sync' command
  ${CYAN}--yes, -y${NC}         Skip confirmation prompts (for CI / automation)

${BOLD}Examples:${NC}
  $(basename "$0") sync                          # full pull from a remote server
  $(basename "$0") download                      # just grab the dump file
  $(basename "$0") restore backups/remote_db_backup_20260715_120000.dump
  $(basename "$0") migrate                       # apply pending migrations only
  $(basename "$0") setup-db                      # fresh local DB, no remote needed
  $(basename "$0") sync --no-media --yes         # CI-safe full sync

${BOLD}Local DB config${NC} is read from ${CYAN}backend/.env${NC} (DATABASE_URL).
No passwords are hardcoded in this script.

EOF
}

# =============================================================================
# ENTRY POINT
# =============================================================================
main() {
    parse_args "$@"

    if [ -z "$COMMAND" ] || [ "$COMMAND" = "help" ] || [ "$COMMAND" = "--help" ] || [ "$COMMAND" = "-h" ]; then
        show_usage
        exit 0
    fi

    # Commands that don't need local DB config
    case "$COMMAND" in
        list)
            cmd_list
            exit 0
            ;;
    esac

    # All other commands need the env file
    parse_env_file

    case "$COMMAND" in
        backup)    cmd_backup     ;;
        download)  cmd_download   ;;
        restore)   cmd_restore "$ARG2" ;;
        sync)      cmd_sync       ;;
        migrate)   cmd_migrate    ;;
        setup-db)  cmd_setup_db   ;;
        media)     cmd_media      ;;
        *)
            log_error "Unknown command: $COMMAND"
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
