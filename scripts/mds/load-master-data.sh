#!/usr/bin/env bash
# ============================================================================
#  scripts/mds/load-master-data.sh — back up MDS, load an export, verify counts
#
#  Steps (idempotent):
#    1. pg_dump the MDS Postgres DB to a timestamped backup  (ALWAYS, even dry-run
#       does a dump so you have a restore point before you re-run with --confirm).
#    2. (only with --confirm) run `load_masters --in <json>` in the MDS project
#       — a topological, natural-key/uid upsert. Re-running converges (idempotent).
#    3. Verify per-master counts: source JSON row count vs MDS DB row count.
#       Exit non-zero on ANY mismatch (after accounting for legitimately skipped
#       rows — dangling-FK rows the loader intentionally drops).
#
#  This script writes ONLY to the MDS database (never to any source DB) and only
#  under --confirm. Without --confirm it dumps a backup and prints what it WOULD
#  load (dry-run).
#
#  Usage:
#    scripts/mds/load-master-data.sh --in ./exports/golden.json                 # dry-run + backup
#    scripts/mds/load-master-data.sh --in ./exports/golden.json --confirm       # backup + load + verify
#
#  Env (MDS project):
#    MDS_DIR         path to the master-data-service checkout (default: ../../master-data-service)
#    MDS_PY          python to use (default: python)
#    MDS_DB_NAME/USER/PASS/HOST/PORT   Postgres coords (same names MDS settings read)
#    MDS_BACKUP_DIR  where pg_dump files land (default: ./backups/mds)
#  Secrets (MDS_DB_PASS) via env only — never hardcoded, never logged.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/mds/_lib.sh
source "$SCRIPT_DIR/_lib.sh"

INFILE=""
CONFIRM=0

usage() {
    grep '^#' "$0" | sed 's/^# \{0,1\}//' | sed '/^!/d'
    exit "${1:-0}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --in)      INFILE="${2:-}"; shift 2 ;;
        --confirm) CONFIRM=1;        shift ;;
        -h|--help) usage 0 ;;
        *) die "Unknown argument: $1 (see --help)" ;;
    esac
done

[ -n "$INFILE" ] || die "--in <export.json> is required"
[ -s "$INFILE" ] || die "Export file missing or empty: $INFILE"

MDS_DIR="${MDS_DIR:-$SCRIPT_DIR/../../master-data-service}"
PY="${MDS_PY:-python}"
[ -f "$MDS_DIR/manage.py" ] || die "MDS project not found at $MDS_DIR (set MDS_DIR)"

DB_NAME="${MDS_DB_NAME:-master_data}"
DB_USER="${MDS_DB_USER:-master_data}"
DB_HOST="${MDS_DB_HOST:-localhost}"
DB_PORT="${MDS_DB_PORT:-5432}"
BACKUP_DIR="${MDS_BACKUP_DIR:-$SCRIPT_DIR/../../backups/mds}"

mds_require_cmd "$PY"
mds_require_cmd pg_dump
mkdir -p "$BACKUP_DIR"

log "MDS load — target DB '${DB_NAME}' @ ${DB_HOST}:${DB_PORT}"
log "Export file : $INFILE"
if mds_confirm_or_dry "$CONFIRM"; then
    log "Mode        : CONFIRM (will back up, load, and verify)"
else
    warn "Mode        : DRY-RUN (will back up + show plan; NO load). Re-run with --confirm to load."
fi

# ── Step 1: ALWAYS back up the MDS DB before touching it ────────────────────
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/mds-${DB_NAME}-${TS}.sql.gz"
log "[1/3] Backing up MDS DB -> $BACKUP_FILE"
# PGPASSWORD from env (never echoed). Custom-plain SQL, gzipped, idempotent name.
if PGPASSWORD="${MDS_DB_PASS:-}" pg_dump \
        --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" \
        --no-password --format=plain "$DB_NAME" 2>>"${MDS_LOG_FILE:-/dev/stderr}" \
        | gzip -c > "$BACKUP_FILE"; then
    if [ -s "$BACKUP_FILE" ]; then
        ok "Backup written ($(du -h "$BACKUP_FILE" | cut -f1)) — restore with: gunzip -c '$BACKUP_FILE' | psql ..."
    else
        rm -f "$BACKUP_FILE"
        die "pg_dump produced an empty backup — refusing to proceed. Check MDS_DB_* env."
    fi
else
    rm -f "$BACKUP_FILE"
    die "pg_dump failed — refusing to proceed without a restore point. Check MDS_DB_* env / connectivity."
fi

# ── Source-of-truth counts from the export JSON ─────────────────────────────
SRC_COUNTS_JSON="$(mds_counts_json "$INFILE")"
log "Source (export) row counts:"
mds_print_counts "$INFILE" "export"

# ── Step 2: load (only with --confirm) ──────────────────────────────────────
if ! mds_confirm_or_dry "$CONFIRM"; then
    dry "Would run: (cd '$MDS_DIR' && $PY manage.py load_masters --in '$INFILE')"
    dry "Would then verify per-master counts (export JSON vs MDS DB) and fail on mismatch."
    ok "Dry-run complete. Backup taken at $BACKUP_FILE. Re-run with --confirm to apply."
    exit 0
fi

log "[2/3] Loading into MDS (topological upsert, idempotent)"
ABS_IN="$(cd "$(dirname "$INFILE")" && pwd)/$(basename "$INFILE")"
if ! ( cd "$MDS_DIR" && "$PY" manage.py load_masters --in "$ABS_IN" ); then
    err "load_masters failed. MDS DB may be partially loaded (per-model transactions)."
    err "Restore point: gunzip -c '$BACKUP_FILE' | PGPASSWORD=... psql -h $DB_HOST -U $DB_USER $DB_NAME"
    exit 1
fi
ok "load_masters completed"

# ── Step 3: verify per-master counts (export JSON vs MDS DB) ────────────────
log "[3/3] Verifying per-master counts (export vs MDS DB)"

# Map export-JSON table names -> MDS model class names (masters.models).
# The export uses the MDS model names already (Company, Port, HSCode, ...), so
# the mapping is identity; we emit MDS live counts keyed by the same names.
MDS_COUNTS_JSON="$(
    cd "$MDS_DIR" && "$PY" manage.py shell -c '
import json
from masters.models import (
    Company, Port, ItemGroup, ItemHead, ItemName, HSCode, HeadSIONNorm,
    SIONNormClass, SIONExport, SIONImport, SIONNormNote, SIONNormCondition,
    ProductDescription, UnitPrice, SchemeCode, NotificationNumber, ExchangeRate,
)
counts = {
    "Company": Company.objects.count(),
    "Port": Port.objects.count(),
    "ItemGroup": ItemGroup.objects.count(),
    "ItemHead": ItemHead.objects.count(),
    "ItemName": ItemName.objects.count(),
    "HSCode": HSCode.objects.count(),
    "HeadSIONNorm": HeadSIONNorm.objects.count(),
    "SIONNormClass": SIONNormClass.objects.count(),
    "SIONExport": SIONExport.objects.count(),
    "SIONImport": SIONImport.objects.count(),
    "SIONNormNote": SIONNormNote.objects.count(),
    "SIONNormCondition": SIONNormCondition.objects.count(),
    "ProductDescription": ProductDescription.objects.count(),
    "UnitPrice": UnitPrice.objects.count(),
    "SchemeCode": SchemeCode.objects.count(),
    "NotificationNumber": NotificationNumber.objects.count(),
    "ExchangeRate": ExchangeRate.objects.count(),
}
print(json.dumps(counts, sort_keys=True))
' | tail -1
)"

# Compare. A MDS count LOWER than the export is only acceptable if it equals the
# export minus rows the loader legitimately skipped (dangling FK). We cannot know
# skips per-model without parsing loader output, so the rule is:
#   - MDS >= export-for-that-master  -> OK (idempotent re-runs, pre-existing rows)
#   - MDS <  export                  -> MISMATCH (rows failed to load) -> FAIL
# This catches the real failure mode (rows silently not landing) while tolerating
# a DB that already had equal-or-more rows from a prior load.
MISMATCH=$(
    python3 - "$SRC_COUNTS_JSON" "$MDS_COUNTS_JSON" <<'PY'
import json, sys
src = json.loads(sys.argv[1])
mds = json.loads(sys.argv[2])
bad = 0
print("  %-22s%9s%9s%9s" % ("master", "export", "mds", "delta"))
print("  " + "-"*49)
for k in sorted(set(src) | set(mds)):
    s = src.get(k, 0); m = mds.get(k, 0); d = m - s
    flag = "" if m >= s else "  <-- MISMATCH (rows missing)"
    if m < s:
        bad += 1
    print("  %-22s%9d%9d%9d%s" % (k, s, m, d, flag))
print("  " + "-"*49)
print("  MISMATCH_COUNT=%d" % bad)
PY
)
echo "$MISMATCH" | while IFS= read -r line; do log "$line"; done

BAD=$(printf '%s\n' "$MISMATCH" | sed -n 's/.*MISMATCH_COUNT=\([0-9]*\).*/\1/p')
if [ "${BAD:-1}" != "0" ]; then
    err "Count verification FAILED: ${BAD} master(s) have fewer rows in MDS than the export."
    err "Investigate load_masters SKIP warnings (dangling FKs) and re-run. Restore point: $BACKUP_FILE"
    exit 1
fi

ok "Count verification passed (every master: MDS rows >= export rows)."
ok "Load complete. Backup: $BACKUP_FILE"
