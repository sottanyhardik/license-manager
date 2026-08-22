#!/bin/bash
set -euo pipefail

if [[ "${1:-}" != "--confirm-local-restore" ]]; then
    echo "Refusing to replace a local database without --confirm-local-restore." >&2
    echo "All connection names and .pgpass paths must be supplied through MIGRATION_* environment variables." >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# ─── Configuration ─────────────────────────────────────────────
: "${MIGRATION_REMOTE_USER:?MIGRATION_REMOTE_USER is required}"
: "${MIGRATION_REMOTE_HOST:?MIGRATION_REMOTE_HOST is required}"
: "${MIGRATION_REMOTE_DB_NAME:?MIGRATION_REMOTE_DB_NAME is required}"
: "${MIGRATION_REMOTE_DB_USER:?MIGRATION_REMOTE_DB_USER is required}"
: "${MIGRATION_REMOTE_BACKUP_PATH:?MIGRATION_REMOTE_BACKUP_PATH is required}"
: "${MIGRATION_REMOTE_PGPASSFILE:?MIGRATION_REMOTE_PGPASSFILE is required}"
: "${MIGRATION_LOCAL_DB_NAME:?MIGRATION_LOCAL_DB_NAME is required}"
: "${MIGRATION_LOCAL_DB_USER:?MIGRATION_LOCAL_DB_USER is required}"
: "${MIGRATION_SUPERUSER:?MIGRATION_SUPERUSER is required}"
: "${MIGRATION_LOCAL_PGPASSFILE:?MIGRATION_LOCAL_PGPASSFILE is required}"
: "${MIGRATION_SUPERUSER_PGPASSFILE:?MIGRATION_SUPERUSER_PGPASSFILE is required}"
: "${MIGRATION_KNOWN_HOSTS_FILE:?MIGRATION_KNOWN_HOSTS_FILE is required}"

REMOTE_USER="$MIGRATION_REMOTE_USER"
REMOTE_HOST="$MIGRATION_REMOTE_HOST"
REMOTE_DB_NAME="$MIGRATION_REMOTE_DB_NAME"
REMOTE_DB_USER="$MIGRATION_REMOTE_DB_USER"
REMOTE_BACKUP_PATH="$MIGRATION_REMOTE_BACKUP_PATH"
REMOTE_PGPASSFILE="$MIGRATION_REMOTE_PGPASSFILE"
LOCAL_DB_NAME="$MIGRATION_LOCAL_DB_NAME"
LOCAL_DB_USER="$MIGRATION_LOCAL_DB_USER"
SUPERUSER="$MIGRATION_SUPERUSER"
LOCAL_PGPASSFILE="$MIGRATION_LOCAL_PGPASSFILE"
SUPERUSER_PGPASSFILE="$MIGRATION_SUPERUSER_PGPASSFILE"
KNOWN_HOSTS_FILE="$MIGRATION_KNOWN_HOSTS_FILE"
LOCAL_PORT="${MIGRATION_LOCAL_PORT:-5432}"

[[ -r "$KNOWN_HOSTS_FILE" ]] || { echo "MIGRATION_KNOWN_HOSTS_FILE must be readable." >&2; exit 2; }
[[ -r "$LOCAL_PGPASSFILE" && -r "$SUPERUSER_PGPASSFILE" ]] || { echo "Local .pgpass files must be readable." >&2; exit 2; }
SSH_OPTS=(-o BatchMode=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$KNOWN_HOSTS_FILE")

BACKUP_DIR="$PROJECT_ROOT/backups/server-db"
BACKUP_FILE="$BACKUP_DIR/lmanagement.backup"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="$PROJECT_ROOT/logs"
LOGFILE="$LOG_DIR/db_update_$TIMESTAMP.log"

mkdir -p "$BACKUP_DIR" "$LOG_DIR"

# ─── Step 1: Trigger pg_dump on remote ─────────────────────────
echo "🔄 Starting remote dump..." | tee -a "$LOGFILE"
ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" "PGPASSFILE=$(printf '%q' "$REMOTE_PGPASSFILE") pg_dump -U $(printf '%q' "$REMOTE_DB_USER") -h localhost -p $(printf '%q' "$LOCAL_PORT") -F c -b -v -f $(printf '%q' "$REMOTE_BACKUP_PATH") $(printf '%q' "$REMOTE_DB_NAME")" 2>&1 | tee -a "$LOGFILE"

# ─── Step 2: Copy backup file to local ─────────────────────────
echo "📥 Copying backup to local..." | tee -a "$LOGFILE"
scp "${SSH_OPTS[@]}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BACKUP_PATH}" "$BACKUP_FILE" 2>&1 | tee -a "$LOGFILE"

# ─── Step 3: Drop and recreate local database ──────────────────
echo "💣 Dropping and recreating local database..." | tee -a "$LOGFILE"
PGPASSFILE="$SUPERUSER_PGPASSFILE" dropdb -U "$SUPERUSER" -h localhost -p "$LOCAL_PORT" --if-exists "$LOCAL_DB_NAME"
PGPASSFILE="$SUPERUSER_PGPASSFILE" createdb -U "$SUPERUSER" -h localhost -p "$LOCAL_PORT" -O "$LOCAL_DB_USER" "$LOCAL_DB_NAME"

# ─── Step 4: Restore backup locally ────────────────────────────
echo "♻️ Restoring database locally..." | tee -a "$LOGFILE"
PGPASSFILE="$LOCAL_PGPASSFILE" pg_restore -U "$LOCAL_DB_USER" -h localhost -p "$LOCAL_PORT" -d "$LOCAL_DB_NAME" -v "$BACKUP_FILE" 2>&1 | tee -a "$LOGFILE"

# ─── Step 5: Delete backup file ────────────────────────────────
echo "🗑 Deleting backup file..." | tee -a "$LOGFILE"
rm -f "$BACKUP_FILE"

echo "✅ Database update complete. Log saved to $LOGFILE"
