#!/usr/bin/env bash
# ============================================================================
#  scripts/mds/_lib.sh — shared helpers for the MDS ops scripts (ADR-001)
#
#  Sourced by export-master-data.sh, load-master-data.sh,
#  migrate-all-servers.sh and onboard-server.sh. Not meant to run standalone.
#
#  Conventions inherited from the repo-root sync-masters.sh:
#    - Source of truth host   : .201  (SYNC_SOURCE_IP)
#    - Followers              : labdhi 139.59.92.226, tractor 165.232.185.220
#    - Remote user            : django
#    - Remote backend path    : /home/django/license-manager/backend
#    - Remote venv activate    : /home/django/license-manager/venv/bin/activate
#    - Credentials via env only — NEVER hardcode. Prefer SSH keys; sshpass is
#      a fallback when SYNC_PASSWORD is exported (same as sync-masters.sh).
#
#  Safety contract (every MDS script):
#    - DRY-RUN by default. State-changing steps require --confirm.
#    - SOURCE databases are strictly READ-ONLY (export = SELECT only).
#    - The MDS DB is backed up (pg_dump) before any load.
#    - set -euo pipefail; non-zero exit on any failure; clear logging.
# ============================================================================

# Guard against double-sourcing.
if [ -n "${_MDS_LIB_SOURCED:-}" ]; then
    return 0 2>/dev/null || true
fi
_MDS_LIB_SOURCED=1

# ── strict mode ─────────────────────────────────────────────────────────────
set -euo pipefail

# ── colours / logging ───────────────────────────────────────────────────────
if [ -t 1 ]; then
    _C_RED='\033[0;31m'; _C_GRN='\033[0;32m'; _C_YEL='\033[1;33m'
    _C_BLU='\033[0;34m'; _C_DIM='\033[2m'; _C_NC='\033[0m'
else
    _C_RED=''; _C_GRN=''; _C_YEL=''; _C_BLU=''; _C_DIM=''; _C_NC=''
fi

# Optional log file: set MDS_LOG_FILE to tee everything to disk.
_ts() { date '+%Y-%m-%d %H:%M:%S'; }
_emit() {
    # $1 = coloured line for the terminal; also append the plain line to MDS_LOG_FILE.
    printf '%b\n' "$1"
    if [ -n "${MDS_LOG_FILE:-}" ]; then
        printf '%s\n' "$(printf '%b' "$1" | sed 's/\x1b\[[0-9;]*m//g')" >> "$MDS_LOG_FILE"
    fi
}
log()  { _emit "${_C_BLU}[$(_ts)] →${_C_NC} $*"; }
ok()   { _emit "${_C_GRN}[$(_ts)] ✓${_C_NC} $*"; }
warn() { _emit "${_C_YEL}[$(_ts)] ⚠${_C_NC} $*" >&2; }
err()  { _emit "${_C_RED}[$(_ts)] ✗${_C_NC} $*" >&2; }
dry()  { _emit "${_C_DIM}[$(_ts)] (dry-run)${_C_NC} $*"; }
die()  { err "$*"; exit 1; }

# ── host resolution (same defaults as sync-masters.sh) ──────────────────────
mds_source_ip()   { echo "${SYNC_SOURCE_IP:-143.110.252.201}"; }
mds_follower_ip() {
    # $1 = label (labdhi|tractor)
    case "$1" in
        labdhi)  echo "${SYNC_FOLLOWER1:-139.59.92.226}" ;;
        tractor) echo "${SYNC_FOLLOWER2:-165.232.185.220}" ;;
        *)       return 1 ;;
    esac
}

mds_remote_user()    { echo "${SYNC_REMOTE_USER:-django}"; }
mds_remote_path()    { echo "${SYNC_REMOTE_PATH:-/home/django/license-manager/backend}"; }
mds_remote_venv()    { echo "${SYNC_VENV:-/home/django/license-manager/venv/bin/activate}"; }

# ── SSH / SCP command builders ──────────────────────────────────────────────
# Prefer key auth (no SYNC_PASSWORD). Fall back to sshpass iff SYNC_PASSWORD is
# set — identical to sync-masters.sh. Emits the command as an array via stdout
# is awkward in bash; instead we export functions that run it.
_ssh_common_opts=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=15)

_use_sshpass() { [ -n "${SYNC_PASSWORD:-}" ]; }

mds_check_ssh_tools() {
    if _use_sshpass && ! command -v sshpass >/dev/null 2>&1; then
        die "SYNC_PASSWORD is set but 'sshpass' is not installed (brew install sshpass / apt install sshpass). Prefer SSH keys and unset SYNC_PASSWORD."
    fi
}

# Run a command on a remote host. $1=host(ip), rest=remote command string.
mds_ssh() {
    local host="$1"; shift
    local user; user="$(mds_remote_user)"
    if _use_sshpass; then
        sshpass -p "$SYNC_PASSWORD" ssh "${_ssh_common_opts[@]}" "${user}@${host}" "$@"
    else
        ssh "${_ssh_common_opts[@]}" "${user}@${host}" "$@"
    fi
}

# Copy a remote file to local. $1=host $2=remote_path $3=local_path
mds_scp_from() {
    local host="$1" remote="$2" local="$3"
    local user; user="$(mds_remote_user)"
    if _use_sshpass; then
        sshpass -p "$SYNC_PASSWORD" scp "${_ssh_common_opts[@]}" "${user}@${host}:${remote}" "$local"
    else
        scp "${_ssh_common_opts[@]}" "${user}@${host}:${remote}" "$local"
    fi
}

# Copy a local file to remote. $1=host $2=local_path $3=remote_path
mds_scp_to() {
    local host="$1" local="$2" remote="$3"
    local user; user="$(mds_remote_user)"
    if _use_sshpass; then
        sshpass -p "$SYNC_PASSWORD" scp "${_ssh_common_opts[@]}" "$local" "${user}@${host}:${remote}"
    else
        scp "${_ssh_common_opts[@]}" "$local" "${user}@${host}:${remote}"
    fi
}

# ── misc helpers ────────────────────────────────────────────────────────────
mds_require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

# Count records per master in an export_masters_mds JSON, printed as a table.
# Uses python3 (always available where Django runs). $1 = json path, $2 = label.
mds_print_counts() {
    local json="$1" label="${2:-export}"
    mds_require_cmd python3
    python3 - "$json" "$label" <<'PY'
import json, sys
path, label = sys.argv[1], sys.argv[2]
with open(path) as fh:
    snap = json.load(fh)
tables = snap.get("tables", {})
total = 0
print(f"  {'master':<22}{'rows':>9}   [{label}]")
for name in sorted(tables):
    c = tables[name].get("count", 0)
    total += c
    print(f"  {name:<22}{c:>9}")
print(f"  {'-'*33}")
print(f"  {'TOTAL':<22}{total:>9}")
PY
}

# Emit a JSON object of {master: count} for verification/diffing. $1 = json path.
mds_counts_json() {
    local json="$1"
    mds_require_cmd python3
    python3 - "$json" <<'PY'
import json, sys
with open(sys.argv[1]) as fh:
    snap = json.load(fh)
tables = snap.get("tables", {})
print(json.dumps({k: v.get("count", 0) for k, v in tables.items()}, sort_keys=True))
PY
}

# Standard confirm-gate messaging.
mds_confirm_or_dry() {
    # $1 = CONFIRM flag (0/1); returns 0 if we should perform state changes.
    [ "${1:-0}" = "1" ]
}
