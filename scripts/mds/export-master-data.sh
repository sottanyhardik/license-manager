#!/usr/bin/env bash
# ============================================================================
#  scripts/mds/export-master-data.sh — READ-ONLY export of all 17 masters
#
#  Runs the `export_masters_mds` management command on a target host (local or
#  remote over SSH) and pulls the id-free JSON export back to a local file.
#
#  READ-ONLY GUARANTEE: `export_masters_mds` performs SELECT-only queries and
#  writes only the JSON output file on the remote host's /tmp. It NEVER writes
#  to the source database. This wrapper adds no DB writes of its own. Because
#  the command only reads, an export is always safe and needs no --confirm;
#  the flag exists only to keep the interface uniform and is a no-op here.
#
#  Usage:
#    scripts/mds/export-master-data.sh --host local            --out ./exports/local.json
#    scripts/mds/export-master-data.sh --host 143.110.252.201  --out ./exports/201.json
#    scripts/mds/export-master-data.sh --host labdhi           --out ./exports/labdhi.json
#    scripts/mds/export-master-data.sh --host tractor          --out ./exports/tractor.json
#
#  --host local          run in the current checkout's backend/ against the
#                        local DB (uses LOCAL_MANAGE / LOCAL_BACKEND_DIR).
#  --host <ip|label>     run on a remote server over SSH (django@host), pull JSON.
#
#  Env (remote): SYNC_PASSWORD (optional; SSH keys preferred), SYNC_REMOTE_PATH,
#                SYNC_VENV, SYNC_REMOTE_USER. Secrets via env only.
#  Env (local):  LOCAL_BACKEND_DIR (default ./backend), LOCAL_PY (default python).
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/mds/_lib.sh
source "$SCRIPT_DIR/_lib.sh"

HOST=""
OUT=""
CONFIRM=0   # accepted for interface uniformity; export is read-only regardless

usage() {
    grep '^#' "$0" | sed 's/^# \{0,1\}//' | sed '/^!/d'
    exit "${1:-0}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --host)    HOST="${2:-}"; shift 2 ;;
        --out)     OUT="${2:-}";  shift 2 ;;
        --confirm) CONFIRM=1;      shift ;;
        -h|--help) usage 0 ;;
        *) die "Unknown argument: $1 (see --help)" ;;
    esac
done

[ -n "$HOST" ] || die "--host is required (local | 143.110.252.201 | labdhi | tractor)"
[ -n "$OUT" ]  || die "--out <path> is required"

mkdir -p "$(dirname "$OUT")"

# ── Resolve host label -> ip for the known followers/source ─────────────────
RESOLVED_HOST="$HOST"
case "$HOST" in
    local)   : ;;
    labdhi|tractor) RESOLVED_HOST="$(mds_follower_ip "$HOST")" ;;
    source)  RESOLVED_HOST="$(mds_source_ip)" ;;
    *)       : ;;  # assume an IP/hostname was passed directly
esac

log "MDS export — READ-ONLY (SELECT only; source DB is never written)"
log "Target host : $HOST${RESOLVED_HOST:+ ($RESOLVED_HOST)}"
log "Output file : $OUT"

# ── LOCAL export ────────────────────────────────────────────────────────────
if [ "$HOST" = "local" ]; then
    BACKEND_DIR="${LOCAL_BACKEND_DIR:-$SCRIPT_DIR/../../backend}"
    PY="${LOCAL_PY:-python}"
    [ -d "$BACKEND_DIR" ] || die "LOCAL_BACKEND_DIR not found: $BACKEND_DIR"
    log "Running export_masters_mds locally in $BACKEND_DIR"
    (
        cd "$BACKEND_DIR"
        "$PY" manage.py export_masters_mds --out "$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
    )
    ok "Local export written"
    mds_print_counts "$OUT" "$HOST"
    ok "Export complete: $OUT"
    exit 0
fi

# ── REMOTE export over SSH ──────────────────────────────────────────────────
mds_check_ssh_tools
REMOTE_PATH="$(mds_remote_path)"
VENV="$(mds_remote_venv)"
REMOTE_TMP="/tmp/mds-export-$$-$(date +%Y%m%d-%H%M%S).json"

log "Running export_masters_mds on ${RESOLVED_HOST} (path=$REMOTE_PATH)"
# The remote command is SELECT-only; it writes only the JSON to remote /tmp.
if ! mds_ssh "$RESOLVED_HOST" \
    "cd '$REMOTE_PATH' && source '$VENV' && python manage.py export_masters_mds --out '$REMOTE_TMP'"; then
    err "Remote export failed on ${RESOLVED_HOST}"
    mds_ssh "$RESOLVED_HOST" "rm -f '$REMOTE_TMP'" 2>/dev/null || true
    exit 1
fi
ok "Remote export produced $REMOTE_TMP"

log "Pulling export back to $OUT"
if ! mds_scp_from "$RESOLVED_HOST" "$REMOTE_TMP" "$OUT"; then
    err "Failed to pull export from ${RESOLVED_HOST}"
    mds_ssh "$RESOLVED_HOST" "rm -f '$REMOTE_TMP'" 2>/dev/null || true
    exit 1
fi

# Clean up the remote temp file (best-effort; no source-DB impact).
mds_ssh "$RESOLVED_HOST" "rm -f '$REMOTE_TMP'" 2>/dev/null || warn "Could not remove remote temp $REMOTE_TMP on ${RESOLVED_HOST}"

[ -s "$OUT" ] || die "Pulled export is empty: $OUT"
mds_print_counts "$OUT" "$HOST"
ok "Export complete: $OUT"
