#!/bin/bash
# ============================================================
#  Apply a reviewed merge plan to license-manager.
#  Runs in DRY-RUN mode first, then prompts before applying.
#
#  Usage:
#    bash scripts/maintenance/apply-master-merge.sh /path/to/master-audit-YYYYMMDD-HHMM
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/maintenance/_master_sync_lib.sh
source "$SCRIPT_DIR/_master_sync_lib.sh"

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

IP="$WINNER_IP"   # license-manager (winner)
REMOTE_TMP="/tmp/master-merge-$(date +%s)"

master_sync_setup_ssh

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
