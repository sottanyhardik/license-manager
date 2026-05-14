#!/bin/bash
# ============================================================
#  sync-masters.sh — One-way master sync from license-manager → labdhi + tractor
#
#  Runs the canonical audit on license-manager, then imports any new
#  master records into the follower servers.  Uses unique-key matching
#  so duplicates are silently skipped — only NEW records get added.
#
#  Designed to be safe to run repeatedly (idempotent) — perfect for cron.
#
#  Usage:
#    bash sync-masters.sh           # full run, prints summary
#    bash sync-masters.sh --quiet   # silent except errors (for cron)
#
#  Cron example (run every 15 min from your local mac):
#    */15 * * * * cd /Users/hardiksottany/PycharmProjects/license-manager && bash sync-masters.sh --quiet >> /tmp/master-sync.log 2>&1
# ============================================================

set -e

QUIET="${1:-}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { [ "$QUIET" != "--quiet" ] && echo -e "${BLUE}→${NC} $*"; return 0; }
ok()   { [ "$QUIET" != "--quiet" ] && echo -e "${GREEN}✓${NC} $*"; return 0; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; }

PASSWORD="admin"
SOURCE_IP="143.110.252.201"             # license-manager (canonical source)
FOLLOWER_IPS=("139.59.92.226:labdhi" "165.232.185.220:tractor")
REMOTE_PATH="/home/django/license-manager/backend"
VENV_ACTIVATE="/home/django/license-manager/venv/bin/activate"

if ! command -v sshpass &>/dev/null; then
    err "sshpass not installed. Install with: brew install sshpass (Mac) or apt install sshpass (Linux)"
    exit 1
fi

SSH="sshpass -p $PASSWORD ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
SCP="sshpass -p $PASSWORD scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
TMPFILE=$(mktemp /tmp/master-sync-XXXXXX.json)
trap "rm -f $TMPFILE" EXIT

# ── Step 1: Pull canonical audit from license-manager ───────
log "[$TIMESTAMP] Auditing source: license-manager ($SOURCE_IP)..."
if ! $SSH "django@$SOURCE_IP" "cd $REMOTE_PATH && source $VENV_ACTIVATE && python manage.py audit_masters --server-name license-manager --out /tmp/sync-audit.json" >/dev/null 2>&1; then
    err "Audit failed on $SOURCE_IP"
    exit 1
fi
$SCP "django@$SOURCE_IP:/tmp/sync-audit.json" "$TMPFILE"
ok "Source audit pulled"

# ── Step 2: Push + apply to each follower ───────────────────
TOTAL_IMPORTED=0
TOTAL_FAILED=0
SUMMARY=""

for entry in "${FOLLOWER_IPS[@]}"; do
    IFS=':' read -r IP LABEL <<< "$entry"
    log "Syncing → $LABEL ($IP)..."

    REMOTE_TMP="/tmp/master-sync-$$"
    $SSH "django@$IP" "mkdir -p $REMOTE_TMP"
    $SCP "$TMPFILE" "django@$IP:$REMOTE_TMP/source.json"

    OUTPUT=$($SSH "django@$IP" "cd $REMOTE_PATH && source $VENV_ACTIVATE && python manage.py auto_import_masters --sources $REMOTE_TMP/source.json --failed-out $REMOTE_TMP/failed.csv --apply 2>&1" || true)

    IMPORTED=$(echo "$OUTPUT" | grep -oE "imported= *[0-9]+" | tail -1 | grep -oE "[0-9]+" || echo "0")
    FAILED=$(echo "$OUTPUT"   | grep -oE "failed= *[0-9]+"   | tail -1 | grep -oE "[0-9]+" || echo "0")

    SUMMARY="$SUMMARY  $LABEL: imported=$IMPORTED, failed=$FAILED\n"
    TOTAL_IMPORTED=$((TOTAL_IMPORTED + IMPORTED))
    TOTAL_FAILED=$((TOTAL_FAILED + FAILED))

    if [ "$FAILED" != "0" ] && [ "$FAILED" != "" ]; then
        # Save failure CSV locally
        FAIL_OUT="/tmp/master-sync-failed-${LABEL}-${TIMESTAMP}.csv"
        $SCP "django@$IP:$REMOTE_TMP/failed.csv" "$FAIL_OUT" 2>/dev/null && warn "Failures on $LABEL → $FAIL_OUT"
    fi

    $SSH "django@$IP" "rm -rf $REMOTE_TMP"
    ok "Done $LABEL — imported=$IMPORTED, failed=$FAILED"
done

# ── Final summary ────────────────────────────────────────────
if [ "$QUIET" != "--quiet" ] || [ $TOTAL_FAILED -gt 0 ]; then
    echo ""
    echo "═══ Sync summary [$TIMESTAMP] ═══"
    echo -e "$SUMMARY"
    echo "  TOTAL: imported=$TOTAL_IMPORTED  failed=$TOTAL_FAILED"
fi

# Exit non-zero if there were failures (so cron emails get triggered)
[ $TOTAL_FAILED -gt 0 ] && exit 2 || exit 0
