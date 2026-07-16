#!/bin/bash
# Shared maintenance helpers for legacy master-data sync scripts.

if [ -n "${_MASTER_SYNC_LIB_SOURCED:-}" ]; then
    return 0 2>/dev/null || true
fi
_MASTER_SYNC_LIB_SOURCED=1

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}→${NC} $*"; }
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; }

SERVER_USER="${MASTER_SYNC_USER:-${SYNC_REMOTE_USER:-django}}"
PASSWORD="${MASTER_SYNC_PASSWORD:-${SYNC_PASSWORD:-admin}}"
REMOTE_PATH="${MASTER_SYNC_REMOTE_PATH:-${SYNC_REMOTE_PATH:-/home/django/license-manager/backend}}"
VENV_ACTIVATE="${MASTER_SYNC_VENV:-${SYNC_VENV:-/home/django/license-manager/venv/bin/activate}}"
WINNER_IP="${MASTER_SYNC_WINNER_IP:-${SYNC_SOURCE_IP:-143.110.252.201}}"
WINNER_LABEL="${MASTER_SYNC_WINNER_LABEL:-license-manager}"

SERVERS=(
    "${WINNER_IP}:license-manager"
    "${MASTER_SYNC_LABDHI_IP:-${SYNC_FOLLOWER1:-139.59.92.226}}:labdhi"
    "${MASTER_SYNC_TRACTOR_IP:-${SYNC_FOLLOWER2:-165.232.185.220}}:tractor"
)

master_sync_setup_ssh() {
    if command -v sshpass &>/dev/null; then
        SSH_BIN="sshpass -p $PASSWORD ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
        SCP_BIN="sshpass -p $PASSWORD scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
    else
        warn "sshpass not installed — will prompt for password each connection"
        SSH_BIN="ssh"
        SCP_BIN="scp"
    fi
    SSH="$SSH_BIN"
    SCP="$SCP_BIN"
}
