#!/bin/bash
# ============================================================
#  One-shot master data consolidation:
#    1. Audit all 3 servers
#    2. Pull JSONs locally
#    3. Upload "other" JSONs to license-manager
#    4. Run auto-import (dry-run) on license-manager
#    5. Show summary + failures CSV
#    6. Prompt to apply
#
#  Usage:
#    bash scripts/maintenance/audit-and-merge-masters.sh
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
WINNER_IP="143.110.252.201"   # license-manager
WINNER_LABEL="license-manager"

# All servers to audit (IP:label)
SERVERS=(
    "143.110.252.201:license-manager"
    "139.59.92.226:labdhi"
    "165.232.185.220:tractor"
)

OUT_DIR="$(pwd)/master-audit-$(date +%Y%m%d-%H%M)"
mkdir -p "$OUT_DIR"
log "Output directory: $OUT_DIR"

if command -v sshpass &>/dev/null; then
    SSH="sshpass -p $PASSWORD ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
    SCP="sshpass -p $PASSWORD scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
else
    warn "sshpass not installed — will prompt for password"
    SSH="ssh"
    SCP="scp"
fi

# ── 1. Audit every server, pull JSON ─────────────────────────
FAILED=()
for entry in "${SERVERS[@]}"; do
    IFS=':' read -r IP LABEL <<< "$entry"
    log "Auditing $LABEL ($IP)..."
    REMOTE_JSON="$REMOTE_PATH/audit-${LABEL}.json"
    if $SSH "$SERVER_USER@$IP" "cd $REMOTE_PATH && source $VENV_ACTIVATE && python manage.py audit_masters --server-name $LABEL --out $REMOTE_JSON" >/dev/null 2>&1; then
        if $SCP "$SERVER_USER@$IP:$REMOTE_JSON" "$OUT_DIR/" 2>/dev/null; then
            count=$(/usr/bin/python3 -c "import json; d=json.load(open('$OUT_DIR/audit-${LABEL}.json')); print(sum(t.get('count',0) for t in d['tables'].values() if 'count' in t))")
            ok "$LABEL — $count master records"
        else
            err "Download failed: $LABEL"
            FAILED+=("$LABEL")
        fi
    else
        err "Audit failed on $IP"
        FAILED+=("$LABEL")
    fi
done

if [ ${#FAILED[@]} -gt 0 ]; then
    err "Failed servers: ${FAILED[*]}"
    exit 1
fi

# ── 2. Upload "other" JSONs to winner server ─────────────────
log "Uploading other servers' audits to $WINNER_LABEL..."
REMOTE_TMP="/tmp/master-merge-$(date +%s)"
$SSH "$SERVER_USER@$WINNER_IP" "mkdir -p $REMOTE_TMP"

OTHER_REMOTE_FILES=""
for entry in "${SERVERS[@]}"; do
    IFS=':' read -r IP LABEL <<< "$entry"
    [ "$LABEL" = "$WINNER_LABEL" ] && continue
    name="audit-${LABEL}.json"
    $SCP "$OUT_DIR/$name" "$SERVER_USER@$WINNER_IP:$REMOTE_TMP/$name"
    OTHER_REMOTE_FILES="$OTHER_REMOTE_FILES $REMOTE_TMP/$name"
done

# ── 3. Run auto-import in DRY-RUN mode ───────────────────────
echo ""
log "Running DRY-RUN auto-import on $WINNER_LABEL..."
echo "============================================================"
$SSH "$SERVER_USER@$WINNER_IP" "cd $REMOTE_PATH && source $VENV_ACTIVATE && python manage.py auto_import_masters --sources $OTHER_REMOTE_FILES --failed-out $REMOTE_TMP/failed-imports.csv"
echo "============================================================"

# ── 4. Pull failures CSV (if any) ────────────────────────────
$SCP "$SERVER_USER@$WINNER_IP:$REMOTE_TMP/failed-imports.csv" "$OUT_DIR/" 2>/dev/null || true

if [ -f "$OUT_DIR/failed-imports.csv" ]; then
    FAIL_COUNT=$(($(wc -l < "$OUT_DIR/failed-imports.csv") - 1))
    if [ $FAIL_COUNT -gt 0 ]; then
        warn "$FAIL_COUNT records failed to import. Review: $OUT_DIR/failed-imports.csv"
        echo ""
        echo "First few failures:"
        head -6 "$OUT_DIR/failed-imports.csv" | column -t -s,
    fi
fi

echo ""
read -p "$(echo -e ${YELLOW}Apply auto-import for real?${NC} [y/N] )" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    warn "Cancelled. No changes made."
    $SSH "$SERVER_USER@$WINNER_IP" "rm -rf $REMOTE_TMP"
    exit 0
fi

# ── 5. Apply for real ────────────────────────────────────────
log "Applying auto-import..."
$SSH "$SERVER_USER@$WINNER_IP" "cd $REMOTE_PATH && source $VENV_ACTIVATE && python manage.py auto_import_masters --sources $OTHER_REMOTE_FILES --failed-out $REMOTE_TMP/failed-imports.csv --apply"

# Pull final failures CSV
$SCP "$SERVER_USER@$WINNER_IP:$REMOTE_TMP/failed-imports.csv" "$OUT_DIR/" 2>/dev/null || true

# Cleanup remote temp
$SSH "$SERVER_USER@$WINNER_IP" "rm -rf $REMOTE_TMP"

ok "Merge complete on $WINNER_LABEL."
echo ""
echo "  📁 All files in: $OUT_DIR"
if [ -f "$OUT_DIR/failed-imports.csv" ]; then
    FAIL_COUNT=$(($(wc -l < "$OUT_DIR/failed-imports.csv") - 1))
    [ $FAIL_COUNT -gt 0 ] && warn "  $FAIL_COUNT records require manual review → $OUT_DIR/failed-imports.csv"
fi
