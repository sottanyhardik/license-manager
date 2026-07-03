#!/usr/bin/env bash
# ============================================================================
#  scripts/mds/onboard-server.sh — point a consumer server at the central MDS
#
#  Prepares a NEW (or existing) consumer to use the Master-Data Service:
#    1. Writes the per-server MDS env (MDS_ENABLED=true, MDS_BASE_URL, MDS_TOKEN)
#       into the server's env file (default: <remote_path>/../.env). The consumer
#       settings.py already reads these (backend/lmanagement/settings.py:383-396).
#    2. Runs `migrate mds_client` to create the client's local tables (sync
#       cursors / outbox). Additive migration; does not touch master rows.
#    3. Runs an initial `mds_sync` to hydrate the local read-mirror from MDS.
#
#  This changes ONLY the consumer's own config + its client tables + its local
#  mirror. It NEVER writes to the MDS DB and NEVER writes to master source rows
#  on the consumer (the mirror sync is a read-from-MDS -> upsert-local operation
#  owned by mds_client). DRY-RUN by default.
#
#  Reads (never re-enables) do not require the write cutover; onboarding only
#  turns on the sync worker + write client wiring, exactly as the ADR intends
#  (write cutover is a separate, later, flag-gated step).
#
#  Usage:
#    scripts/mds/onboard-server.sh --host tractor \
#        --mds-url https://masters.internal.example.com/api/v1/ \
#        --token   "$TRACTOR_MDS_TOKEN"                              # dry-run (prints plan)
#
#    scripts/mds/onboard-server.sh --host tractor --mds-url ... --token ... --confirm
#
#    scripts/mds/onboard-server.sh --host local --mds-url ... --token ... --confirm   # this checkout
#
#  Flags:
#    --host       local | source | labdhi | tractor | <ip/hostname>
#    --mds-url    MDS API base URL (…/api/v1/). Required.
#    --token      per-server bearer token (scoped). Required. Passed via env only.
#    --env-file   remote/local path to the env file (default: <backend>/../.env)
#    --skip-sync  onboard + migrate but skip the initial mds_sync
#    --confirm    actually apply (default: dry-run)
#
#  Env: SYNC_* (SSH/host — see _lib.sh). The TOKEN is a secret — pass it from an
#  env var (e.g. --token "$TRACTOR_MDS_TOKEN"); it is written to the env file but
#  NEVER echoed to logs (only a masked form is shown).
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/mds/_lib.sh
source "$SCRIPT_DIR/_lib.sh"

HOST=""
MDS_URL=""
TOKEN=""
ENV_FILE=""
CONFIRM=0
SKIP_SYNC=0

usage() {
    grep '^#' "$0" | sed 's/^# \{0,1\}//' | sed '/^!/d'
    exit "${1:-0}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --host)      HOST="${2:-}";     shift 2 ;;
        --mds-url)   MDS_URL="${2:-}";  shift 2 ;;
        --token)     TOKEN="${2:-}";    shift 2 ;;
        --env-file)  ENV_FILE="${2:-}"; shift 2 ;;
        --skip-sync) SKIP_SYNC=1;        shift ;;
        --confirm)   CONFIRM=1;          shift ;;
        -h|--help)   usage 0 ;;
        *) die "Unknown argument: $1 (see --help)" ;;
    esac
done

[ -n "$HOST" ]    || die "--host is required (local | source | labdhi | tractor | <ip>)"
[ -n "$MDS_URL" ] || die "--mds-url is required (e.g. https://masters.internal.example.com/api/v1/)"
[ -n "$TOKEN" ]   || die "--token is required (per-server bearer token; pass from an env var)"

# Mask token for logging: show first 4 chars + length only.
MASK="${TOKEN:0:4}…(${#TOKEN} chars)"

# Resolve host label -> ip.
RESOLVED_HOST="$HOST"
case "$HOST" in
    local)   : ;;
    source)  RESOLVED_HOST="$(mds_source_ip)" ;;
    labdhi|tractor) RESOLVED_HOST="$(mds_follower_ip "$HOST")" ;;
    *)       : ;;
esac

REMOTE_PATH="$(mds_remote_path)"
VENV="$(mds_remote_venv)"
DEFAULT_ENV_FILE="$(dirname "$REMOTE_PATH")/.env"
ENV_FILE="${ENV_FILE:-$DEFAULT_ENV_FILE}"

log "MDS onboarding — consumer '$HOST'${RESOLVED_HOST:+ ($RESOLVED_HOST)}"
log "  MDS_BASE_URL : $MDS_URL"
log "  MDS_TOKEN    : $MASK  (secret — not logged in full)"
log "  env file     : $ENV_FILE"
log "  mode         : $( mds_confirm_or_dry "$CONFIRM" && echo CONFIRM || echo DRY-RUN )"

# The three lines we manage in the env file. We replace existing MDS_* lines
# idempotently rather than appending duplicates.
render_env_block() {
    cat <<EOF
# --- Master-Data Service (managed by scripts/mds/onboard-server.sh) ---
MDS_ENABLED=true
MDS_BASE_URL=$MDS_URL
MDS_TOKEN=$TOKEN
EOF
}

# Idempotent upsert of MDS_* keys into an env file, done with awk (portable).
# Reads existing file on stdin, writes merged file on stdout.
MANAGED_MARK="# --- Master-Data Service (managed by scripts/mds/onboard-server.sh) ---"
UPSERT_AWK='
BEGIN { split("MDS_ENABLED MDS_BASE_URL MDS_TOKEN", keys, " ") }
{
    line=$0; matched=0
    # Drop any prior managed marker line so re-runs stay idempotent.
    if (line == MARK) next
    for (i in keys) { k=keys[i]; if (index(line, k"=")==1) { matched=1; break } }
    if (!matched) print line
}
END {
    print MARK
    print "MDS_ENABLED=true"
    print "MDS_BASE_URL=" URL
    print "MDS_TOKEN=" TOK
}
'

# ── local vs remote executor ────────────────────────────────────────────────
if [ "$HOST" = "local" ]; then
    BACKEND_DIR="${LOCAL_BACKEND_DIR:-$SCRIPT_DIR/../../backend}"
    PY="${LOCAL_PY:-python}"
    [ -d "$BACKEND_DIR" ] || die "LOCAL_BACKEND_DIR not found: $BACKEND_DIR"

    if ! mds_confirm_or_dry "$CONFIRM"; then
        dry "Would upsert MDS_ENABLED/MDS_BASE_URL/MDS_TOKEN into: $ENV_FILE"
        dry "Would run: (cd '$BACKEND_DIR' && $PY manage.py migrate mds_client)"
        [ "$SKIP_SYNC" = "1" ] || dry "Would run: (cd '$BACKEND_DIR' && $PY manage.py mds_sync)"
        ok "DRY-RUN complete. Re-run with --confirm to apply."
        exit 0
    fi

    log "[1/3] Writing MDS env -> $ENV_FILE"
    touch "$ENV_FILE"
    TMP_ENV="$(mktemp)"
    awk -v URL="$MDS_URL" -v TOK="$TOKEN" -v MARK="$MANAGED_MARK" "$UPSERT_AWK" "$ENV_FILE" > "$TMP_ENV"
    mv "$TMP_ENV" "$ENV_FILE"
    chmod 600 "$ENV_FILE" 2>/dev/null || true
    ok "env written (MDS_TOKEN present, not logged)"

    log "[2/3] migrate mds_client"
    ( cd "$BACKEND_DIR" && MDS_ENABLED=true MDS_BASE_URL="$MDS_URL" MDS_TOKEN="$TOKEN" "$PY" manage.py migrate mds_client ) \
        || die "migrate mds_client failed"
    ok "mds_client migrated"

    if [ "$SKIP_SYNC" = "1" ]; then
        warn "[3/3] initial mds_sync skipped (--skip-sync)"
    else
        log "[3/3] initial mds_sync (hydrate local mirror from MDS)"
        ( cd "$BACKEND_DIR" && MDS_ENABLED=true MDS_BASE_URL="$MDS_URL" MDS_TOKEN="$TOKEN" "$PY" manage.py mds_sync ) \
            || die "initial mds_sync failed (mirror not hydrated)"
        ok "initial mirror sync complete"
    fi
    ok "Onboarding complete for local consumer."
    exit 0
fi

# ── remote ──────────────────────────────────────────────────────────────────
mds_check_ssh_tools

if ! mds_confirm_or_dry "$CONFIRM"; then
    dry "Would upsert MDS env keys into ${RESOLVED_HOST}:$ENV_FILE (MDS_ENABLED, MDS_BASE_URL, MDS_TOKEN)"
    dry "Would run on ${RESOLVED_HOST}: cd $REMOTE_PATH && source venv && python manage.py migrate mds_client"
    [ "$SKIP_SYNC" = "1" ] || dry "Would run on ${RESOLVED_HOST}: python manage.py mds_sync"
    ok "DRY-RUN complete. Re-run with --confirm to apply on ${RESOLVED_HOST}."
    exit 0
fi

log "[1/3] Writing MDS env on ${RESOLVED_HOST} -> $ENV_FILE"
# Build the merged env file on the remote, idempotently, via awk over the
# existing file. The token travels over the SSH channel (TLS-equivalent), never
# via a query string, and is written with 600 perms. It is NOT echoed to logs.
REMOTE_MERGE_SCRIPT="$(cat <<EOF
set -e
touch '$ENV_FILE'
tmp="\$(mktemp)"
awk -v URL='$MDS_URL' -v TOK='$TOKEN' -v MARK='$MANAGED_MARK' '$UPSERT_AWK' '$ENV_FILE' > "\$tmp"
mv "\$tmp" '$ENV_FILE'
chmod 600 '$ENV_FILE' || true
echo "env-updated"
EOF
)"
mds_ssh "$RESOLVED_HOST" "$REMOTE_MERGE_SCRIPT" >/dev/null || die "failed to write MDS env on ${RESOLVED_HOST}"
ok "env written on ${RESOLVED_HOST} (token not logged)"

log "[2/3] migrate mds_client on ${RESOLVED_HOST}"
mds_ssh "$RESOLVED_HOST" "cd '$REMOTE_PATH' && source '$VENV' && MDS_ENABLED=true MDS_BASE_URL='$MDS_URL' MDS_TOKEN='$TOKEN' python manage.py migrate mds_client" \
    || die "migrate mds_client failed on ${RESOLVED_HOST}"
ok "mds_client migrated on ${RESOLVED_HOST}"

if [ "$SKIP_SYNC" = "1" ]; then
    warn "[3/3] initial mds_sync skipped (--skip-sync)"
else
    log "[3/3] initial mds_sync on ${RESOLVED_HOST} (hydrate mirror)"
    mds_ssh "$RESOLVED_HOST" "cd '$REMOTE_PATH' && source '$VENV' && MDS_ENABLED=true MDS_BASE_URL='$MDS_URL' MDS_TOKEN='$TOKEN' python manage.py mds_sync" \
        || die "initial mds_sync failed on ${RESOLVED_HOST}"
    ok "initial mirror sync complete on ${RESOLVED_HOST}"
fi

ok "Onboarding complete for ${HOST} (${RESOLVED_HOST})."
log "Reminder: the write cutover (routing master writes to MDS) is a separate, flag-gated step — not done here."
