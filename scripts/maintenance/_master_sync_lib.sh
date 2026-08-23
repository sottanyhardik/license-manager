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

# Hosts are intentionally supplied by the calling environment.  Maintenance
# commands must never silently select a production peer.
: "${MASTER_SYNC_USER:=${SYNC_REMOTE_USER:?MASTER_SYNC_USER or SYNC_REMOTE_USER is required}}"
: "${MASTER_SYNC_WINNER_IP:=${SYNC_SOURCE_IP:?MASTER_SYNC_WINNER_IP or SYNC_SOURCE_IP is required}}"
: "${MASTER_SYNC_LABDHI_IP:=${SYNC_FOLLOWER1:?MASTER_SYNC_LABDHI_IP or SYNC_FOLLOWER1 is required}}"
: "${MASTER_SYNC_TRACTOR_IP:=${SYNC_FOLLOWER2:?MASTER_SYNC_TRACTOR_IP or SYNC_FOLLOWER2 is required}}"
SERVER_USER="$MASTER_SYNC_USER"
# Password authentication is intentionally opt-in.  A historical fallback
# credential made maintenance commands unsafe to run from an arbitrary shell.
PASSWORD="${MASTER_SYNC_PASSWORD:-${SYNC_PASSWORD:-}}"
KNOWN_HOSTS_FILE="${MASTER_SYNC_KNOWN_HOSTS:-${SYNC_KNOWN_HOSTS:-$HOME/.ssh/known_hosts}}"
REMOTE_PATH="${MASTER_SYNC_REMOTE_PATH:-${SYNC_REMOTE_PATH:-/home/django/license-manager/backend}}"
VENV_ACTIVATE="${MASTER_SYNC_VENV:-${SYNC_VENV:-/home/django/license-manager/venv/bin/activate}}"
WINNER_IP="$MASTER_SYNC_WINNER_IP"
WINNER_LABEL="${MASTER_SYNC_WINNER_LABEL:-license-manager}"

SERVERS=(
    "${WINNER_IP}:license-manager"
    "${MASTER_SYNC_LABDHI_IP}:labdhi"
    "${MASTER_SYNC_TRACTOR_IP}:tractor"
)

master_sync_setup_ssh() {
    [ -r "$KNOWN_HOSTS_FILE" ] || { err "Pinned known-hosts file is required: $KNOWN_HOSTS_FILE"; return 1; }
    if [ -n "$PASSWORD" ] && command -v sshpass &>/dev/null; then
        warn "Password SSH is enabled explicitly; prefer key-based automation."
        export SSHPASS="$PASSWORD"
        SSH_BIN="sshpass -e ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN_HOSTS_FILE -o LogLevel=ERROR"
        SCP_BIN="sshpass -e scp -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN_HOSTS_FILE -o LogLevel=ERROR"
    else
        SSH_BIN="ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN_HOSTS_FILE -o LogLevel=ERROR"
        SCP_BIN="scp -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN_HOSTS_FILE -o LogLevel=ERROR"
    fi
    SSH="$SSH_BIN"
    SCP="$SCP_BIN"
}
