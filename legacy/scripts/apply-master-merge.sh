#!/bin/bash
# ============================================================
#  Apply a reviewed merge plan to license-manager.
#  Runs in DRY-RUN mode first, then prompts before applying.
#
#  Usage:
#    bash apply-master-merge.sh /path/to/master-audit-YYYYMMDD-HHMM
# ============================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}→${NC} $*"; }
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; }

AUDIT_DIR="${1:?Usage: $0 <audit-dir>}"
if [ ! -d "$AUDIT_DIR" ]; then
    err "Directory not found: $AUDIT_DIR"
    exit 1
fi

PLAN_CSV="$AUDIT_DIR/merge-plan.csv"
if [ ! -f "$PLAN_CSV" ]; then
    err "merge-plan.csv missing in $AUDIT_DIR"
    exit 1
fi

SERVER_USER="django"
PASSWORD="admin"
IP="143.110.252.201"   # license-manager (winner)
REMOTE_PATH="/home/django/license-manager/backend"
VENV_ACTIVATE="/home/django/license-manager/venv/bin/activate"
REMOTE_TMP="/tmp/master-merge-$(date +%s)"

if command -v sshpass &>/dev/null; then
    SSH_BIN="sshpass -p $PASSWORD ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
    SCP_BIN="sshpass -p $PASSWORD scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
else
    SSH_BIN="ssh"
    SCP_BIN="scp"
fi

# Find non-winner audit jsons in the audit dir
OTHERS=()
for f in "$AUDIT_DIR"/audit-*.json; do
    base=$(basename "$f")
    [ "$base" = "audit-license-manager.json" ] && continue
    OTHERS+=("$f")
done

if [ ${#OTHERS[@]} -eq 0 ]; then
    err "No non-winner audit JSONs found in $AUDIT_DIR"
    exit 1
fi

# Upload plan + others to remote tmp dir
log "Uploading plan + audit files to license-manager..."
$SSH_BIN "$SERVER_USER@$IP" "mkdir -p $REMOTE_TMP"
$SCP_BIN "$PLAN_CSV" "$SERVER_USER@$IP:$REMOTE_TMP/merge-plan.csv"
REMOTE_OTHERS=""
for f in "${OTHERS[@]}"; do
    name=$(basename "$f")
    $SCP_BIN "$f" "$SERVER_USER@$IP:$REMOTE_TMP/$name"
    REMOTE_OTHERS="$REMOTE_OTHERS $REMOTE_TMP/$name"
done
ok "Files uploaded to $REMOTE_TMP"

# Dry-run
echo ""
log "Running DRY-RUN merge..."
echo "============================================================"
$SSH_BIN "$SERVER_USER@$IP" "cd $REMOTE_PATH && source $VENV_ACTIVATE && python manage.py merge_masters --plan $REMOTE_TMP/merge-plan.csv --others $REMOTE_OTHERS"
echo "============================================================"
echo ""

read -p "$(echo -e ${YELLOW}Apply changes for real?${NC} [y/N] )" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    warn "Cancelled. No changes made."
    $SSH_BIN "$SERVER_USER@$IP" "rm -rf $REMOTE_TMP"
    exit 0
fi

log "Applying changes..."
$SSH_BIN "$SERVER_USER@$IP" "cd $REMOTE_PATH && source $VENV_ACTIVATE && python manage.py merge_masters --plan $REMOTE_TMP/merge-plan.csv --others $REMOTE_OTHERS --apply"

# Cleanup
$SSH_BIN "$SERVER_USER@$IP" "rm -rf $REMOTE_TMP"

ok "Merge complete on license-manager."
echo ""
echo "Next step — replicate license-manager → labdhi + tractor."
echo "Run a fresh audit to verify, then I'll set up the dump/restore."
