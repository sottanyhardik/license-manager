#!/usr/bin/env bash
# ============================================================================
#  scripts/mds/migrate-all-servers.sh — orchestrate the consolidation into MDS
#
#  Full-migration driver (ADR-001 Phase 0 -> Phase 2 load). It:
#    1. READ-ONLY exports from all three servers, twice, into a work dir:
#         a) `audit_masters`      snapshots  -> feed reconcile_masters
#         b) `export_masters_mds` id-free JSON -> the loadable golden candidate
#       Sources are touched with SELECT-only commands ONLY.
#    2. Runs `reconcile_masters` across the three audit snapshots to produce the
#       conflict / golden report. Prints the summary.
#    3. GATE: if reconcile reports unresolved conflicts (or keyless / manual
#       sign-off items), REFUSE to load unless --accept-conflicts is given.
#    4. (only with --confirm) hands the chosen golden export to
#       load-master-data.sh, which backs up MDS then loads + verifies.
#
#  Default golden source = the .201 source-of-truth export (its DB is the
#  canonical source per ADR-001). Override with --golden <path> to load a
#  human-curated golden export instead (e.g. after resolving conflicts).
#
#  DRY-RUN by default: exports + reconcile always run (read-only, safe); the
#  LOAD step runs only with --confirm.
#
#  Usage:
#    scripts/mds/migrate-all-servers.sh                         # export + reconcile, no load
#    scripts/mds/migrate-all-servers.sh --confirm               # ... + load .201 golden into MDS
#    scripts/mds/migrate-all-servers.sh --confirm --golden ./work/golden-curated.json
#    scripts/mds/migrate-all-servers.sh --confirm --accept-conflicts   # load despite conflicts (explicit)
#    scripts/mds/migrate-all-servers.sh --servers source,labdhi        # subset (default all three)
#
#  Env: SYNC_* (SSH/host — see _lib.sh), MDS_DB_* (load target), MDS_DIR.
#       MDS_WORK_DIR (default ./work/mds-migrate-<ts>) for exports + report + log.
#  Secrets via env only.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/mds/_lib.sh
source "$SCRIPT_DIR/_lib.sh"

CONFIRM=0
ACCEPT_CONFLICTS=0
GOLDEN=""
SERVERS="source,labdhi,tractor"

usage() {
    grep '^#' "$0" | sed 's/^# \{0,1\}//' | sed '/^!/d'
    exit "${1:-0}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --confirm)          CONFIRM=1;            shift ;;
        --accept-conflicts) ACCEPT_CONFLICTS=1;   shift ;;
        --golden)           GOLDEN="${2:-}";      shift 2 ;;
        --servers)          SERVERS="${2:-}";     shift 2 ;;
        -h|--help)          usage 0 ;;
        *) die "Unknown argument: $1 (see --help)" ;;
    esac
done

# ── Work dir + log ──────────────────────────────────────────────────────────
TS="$(date +%Y%m%d-%H%M%S)"
WORK_DIR="${MDS_WORK_DIR:-$SCRIPT_DIR/../../work/mds-migrate-$TS}"
mkdir -p "$WORK_DIR"
export MDS_LOG_FILE="${MDS_LOG_FILE:-$WORK_DIR/migrate.log}"
: > "$MDS_LOG_FILE"

REMOTE_PATH="$(mds_remote_path)"
VENV="$(mds_remote_venv)"
BACKEND_DIR="${LOCAL_BACKEND_DIR:-$SCRIPT_DIR/../../backend}"

log "=================================================================="
log " MDS consolidation run  [$TS]"
log " Work dir : $WORK_DIR"
log " Servers  : $SERVERS"
log " Mode     : $( mds_confirm_or_dry "$CONFIRM" && echo 'CONFIRM (will load MDS)' || echo 'DRY-RUN (export + reconcile only)')"
log "=================================================================="

# ── Map a server token -> its resolved IP + audit label ─────────────────────
resolve_server() {
    # $1 = token (source|labdhi|tractor). Echoes "<ip> <label>".
    case "$1" in
        source)  echo "$(mds_source_ip) license-manager" ;;
        labdhi)  echo "$(mds_follower_ip labdhi) labdhi" ;;
        tractor) echo "$(mds_follower_ip tractor) tractor" ;;
        *) return 1 ;;
    esac
}

mds_check_ssh_tools

# ── Step 1: READ-ONLY exports from each server ──────────────────────────────
# We collect, per server:
#   $WORK_DIR/audit-<label>.json    (from audit_masters, for reconcile)
#   $WORK_DIR/export-<label>.json   (from export_masters_mds, loadable)
declare -a RECONCILE_INPUTS=()
IFS=',' read -r -a SERVER_TOKENS <<< "$SERVERS"

for tok in "${SERVER_TOKENS[@]}"; do
    tok="$(echo "$tok" | tr -d '[:space:]')"
    [ -n "$tok" ] || continue
    read -r IP LABEL <<< "$(resolve_server "$tok")" || die "Unknown server token: $tok"

    AUDIT_OUT="$WORK_DIR/audit-$LABEL.json"
    EXPORT_OUT="$WORK_DIR/export-$LABEL.json"

    log "── Server: $LABEL ($IP) — READ-ONLY export ──"

    if [ "$tok" = "source" ] && [ "${MIGRATE_SOURCE_LOCAL:-0}" = "1" ]; then
        # Optional: run the source export locally (this checkout points at .201 DB).
        log "  audit_masters (local) -> $AUDIT_OUT"
        ( cd "$BACKEND_DIR" && python manage.py audit_masters --server-name "$LABEL" --out "$AUDIT_OUT" ) \
            || die "audit_masters failed locally for $LABEL"
        log "  export_masters_mds (local) -> $EXPORT_OUT"
        ( cd "$BACKEND_DIR" && python manage.py export_masters_mds --out "$EXPORT_OUT" ) \
            || die "export_masters_mds failed locally for $LABEL"
    else
        REMOTE_AUDIT="/tmp/mds-audit-$$-$LABEL.json"
        REMOTE_EXPORT="/tmp/mds-export-$$-$LABEL.json"

        log "  audit_masters (remote SELECT-only) on $IP"
        mds_ssh "$IP" "cd '$REMOTE_PATH' && source '$VENV' && python manage.py audit_masters --server-name '$LABEL' --out '$REMOTE_AUDIT'" \
            || die "audit_masters failed on $LABEL ($IP)"
        mds_scp_from "$IP" "$REMOTE_AUDIT" "$AUDIT_OUT" || die "could not pull audit from $LABEL"

        log "  export_masters_mds (remote SELECT-only) on $IP"
        mds_ssh "$IP" "cd '$REMOTE_PATH' && source '$VENV' && python manage.py export_masters_mds --out '$REMOTE_EXPORT'" \
            || die "export_masters_mds failed on $LABEL ($IP)"
        mds_scp_from "$IP" "$REMOTE_EXPORT" "$EXPORT_OUT" || die "could not pull export from $LABEL"

        mds_ssh "$IP" "rm -f '$REMOTE_AUDIT' '$REMOTE_EXPORT'" 2>/dev/null || warn "could not clean remote temps on $LABEL"
    fi

    [ -s "$AUDIT_OUT" ]  || die "audit snapshot empty for $LABEL: $AUDIT_OUT"
    [ -s "$EXPORT_OUT" ] || die "export empty for $LABEL: $EXPORT_OUT"
    ok "  $LABEL export complete"
    mds_print_counts "$EXPORT_OUT" "$LABEL"

    RECONCILE_INPUTS+=(--input "$LABEL=$AUDIT_OUT")
done

[ "${#RECONCILE_INPUTS[@]}" -ge 2 ] || warn "Fewer than 2 servers — reconciliation will report everything as 'unique'."

# ── Step 2: reconcile ───────────────────────────────────────────────────────
REPORT="$WORK_DIR/reconciliation-report.json"
log "── Reconciling all servers -> $REPORT ──"
RECON_OUT="$(
    cd "$BACKEND_DIR" && python manage.py reconcile_masters "${RECONCILE_INPUTS[@]}" --out "$REPORT" 2>&1
)" || { printf '%s\n' "$RECON_OUT"; die "reconcile_masters failed"; }
printf '%s\n' "$RECON_OUT" | while IFS= read -r line; do log "$line"; done
[ -s "$REPORT" ] || die "reconciliation report not written: $REPORT"

# ── Step 3: conflict gate ───────────────────────────────────────────────────
GATE=$(
    python3 - "$REPORT" <<'PY'
import json, sys
with open(sys.argv[1]) as fh:
    rep = json.load(fh)
t = rep.get("totals", {})
c = t.get("conflicts", 0)
k = t.get("keyless", 0)
m = t.get("needs_manual_signoff", 0)
blocking = c + m   # keyless is expected (handled via synthetic uid) — informational only
print(f"conflicts={c} keyless={k} needs_manual_signoff={m} blocking={blocking}")
PY
)
log "Reconcile gate: $GATE"
BLOCKING=$(printf '%s\n' "$GATE" | sed -n 's/.*blocking=\([0-9]*\).*/\1/p')

if [ "${BLOCKING:-1}" != "0" ]; then
    if [ "$ACCEPT_CONFLICTS" = "1" ]; then
        warn "Reconcile reports unresolved conflicts/sign-off items, but --accept-conflicts was given. Proceeding."
    else
        err "Reconcile reports unresolved conflicts / manual-sign-off items ($GATE)."
        err "Review $REPORT, resolve, and provide a curated --golden export, OR re-run with --accept-conflicts to override (explicit)."
        exit 3
    fi
else
    ok "Reconcile clean — no unresolved conflicts, no manual sign-off pending."
fi

# ── Step 4: load the golden set into MDS (only with --confirm) ──────────────
if [ -z "$GOLDEN" ]; then
    # Default golden = the .201 source-of-truth export (canonical per ADR-001).
    GOLDEN="$WORK_DIR/export-license-manager.json"
    if [ ! -s "$GOLDEN" ]; then
        # source not in the selected set — fall back to the first export we made.
        GOLDEN="$(ls "$WORK_DIR"/export-*.json 2>/dev/null | head -1 || true)"
    fi
fi
[ -s "$GOLDEN" ] || die "No golden export available to load (looked for $GOLDEN). Pass --golden <path>."
log "Golden export selected: $GOLDEN"

if ! mds_confirm_or_dry "$CONFIRM"; then
    dry "Would load golden into MDS via: scripts/mds/load-master-data.sh --in '$GOLDEN' --confirm"
    ok  "DRY-RUN complete. Exports + reconcile report are in $WORK_DIR. Re-run with --confirm to load."
    exit 0
fi

log "── Loading golden set into MDS (backs up MDS first, then verifies) ──"
if ! MDS_LOG_FILE="$MDS_LOG_FILE" "$SCRIPT_DIR/load-master-data.sh" --in "$GOLDEN" --confirm; then
    die "MDS load failed — see load output above and $MDS_LOG_FILE. MDS backup was taken by load-master-data.sh."
fi

ok "Consolidation complete. Golden set loaded + verified into MDS."
ok "Artifacts: $WORK_DIR (exports, reconciliation-report.json, migrate.log)"
