#!/bin/bash
# ============================================================
#  Auto-run master data audit + diff across all 3 servers.
#  Produces merge-plan.csv locally for manual review.
#
#  Usage:
#    bash scripts/maintenance/audit-and-diff-masters.sh
#
#  Requires:
#    sshpass installed locally  (sudo apt install sshpass / brew install sshpass)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/maintenance/_master_sync_lib.sh
source "$SCRIPT_DIR/_master_sync_lib.sh"

# Output location (local)
OUT_DIR="$(pwd)/master-audit-$(date +%Y%m%d-%H%M)"
mkdir -p "$OUT_DIR"
log "Output directory: $OUT_DIR"

master_sync_setup_ssh

# ── Step 1: run audit on every server, pull JSON locally ────
FAILED=()
JSON_FILES=()

for entry in "${SERVERS[@]}"; do
    IFS=':' read -r IP LABEL <<< "$entry"
    log "Auditing $LABEL ($IP)..."

    REMOTE_JSON="$REMOTE_PATH/audit-${LABEL}.json"
    if $SSH_BIN "$SERVER_USER@$IP" "cd $REMOTE_PATH && source $VENV_ACTIVATE && python manage.py audit_masters --server-name $LABEL --out $REMOTE_JSON" 2>&1 | tail -2; then
        # Pull the JSON down
        if $SCP_BIN "$SERVER_USER@$IP:$REMOTE_JSON" "$OUT_DIR/" 2>/dev/null; then
            ok "Pulled audit-${LABEL}.json"
            JSON_FILES+=("$OUT_DIR/audit-${LABEL}.json")
        else
            err "Failed to download audit JSON from $IP"
            FAILED+=("$LABEL")
        fi
    else
        err "Audit command failed on $IP"
        FAILED+=("$LABEL")
    fi
done

if [ ${#FAILED[@]} -gt 0 ]; then
    err "Failed servers: ${FAILED[*]}"
    err "Aborting — fix the failed servers and re-run."
    exit 1
fi

if [ ${#JSON_FILES[@]} -lt 2 ]; then
    err "Need at least 2 successful audits to diff. Got ${#JSON_FILES[@]}."
    exit 1
fi

# ── Step 2: run diff locally ─────────────────────────────────
WINNER="$OUT_DIR/audit-license-manager.json"
OTHERS=()
for f in "${JSON_FILES[@]}"; do
    [ "$f" != "$WINNER" ] && OTHERS+=("$f")
done

if [ ! -f "$WINNER" ]; then
    err "Winner audit missing: $WINNER"
    exit 1
fi

PLAN_CSV="$OUT_DIR/merge-plan.csv"
log "Generating merge plan..."
log "  winner: $WINNER"
log "  others: ${OTHERS[*]}"

PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT/backend"
"$PROJECT_ROOT/.venv/bin/python" manage.py diff_masters \
    --winner "$WINNER" \
    --others "${OTHERS[@]}" \
    --out "$PLAN_CSV"
cd "$PROJECT_ROOT"

echo ""
ok "============================================================"
ok "Done. Files in: $OUT_DIR"
ok "============================================================"
echo ""
echo "  📋 Review the merge plan:"
echo "       open '$PLAN_CSV'"
echo ""
echo "  Files:"
ls -la "$OUT_DIR"
echo ""
echo "  Next step — for each CONFLICT row in the CSV, edit the 'action'"
echo "  column to one of: KEEP_WINNER / OVERWRITE / SKIP"
echo "  Then run:"
echo "       bash scripts/maintenance/apply-master-merge.sh \"$OUT_DIR\""
