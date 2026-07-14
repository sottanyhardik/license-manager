#!/bin/bash
# ============================================================
#  Auto-run master data audit + diff across all 3 servers.
#  Produces merge-plan.csv locally for manual review.
#
#  Usage:
#    bash audit-and-diff-masters.sh
#
#  Requires:
#    sshpass installed locally  (sudo apt install sshpass / brew install sshpass)
# ============================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}→${NC} $*"; }
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; }

SERVER_USER="django"
PASSWORD="admin"
REMOTE_PATH="/home/django/license-manager/backend"
VENV_ACTIVATE="/home/django/license-manager/venv/bin/activate"

# server-ip:server-label pairs
SERVERS=(
    "143.110.252.201:license-manager"
    "139.59.92.226:labdhi"
    "165.232.185.220:tractor"
)

# Output location (local)
OUT_DIR="$(pwd)/master-audit-$(date +%Y%m%d-%H%M)"
mkdir -p "$OUT_DIR"
log "Output directory: $OUT_DIR"

# Choose SSH/SCP wrapper (sshpass if installed)
if command -v sshpass &>/dev/null; then
    SSH_BIN="sshpass -p $PASSWORD ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
    SCP_BIN="sshpass -p $PASSWORD scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
else
    warn "sshpass not installed — will prompt for password each connection"
    SSH_BIN="ssh"
    SCP_BIN="scp"
fi

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

cd backend
../.venv/bin/python manage.py diff_masters \
    --winner "$WINNER" \
    --others "${OTHERS[@]}" \
    --out "$PLAN_CSV"
cd ..

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
echo "       bash apply-master-merge.sh \"$OUT_DIR\""
