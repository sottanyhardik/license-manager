#!/bin/bash
# ============================================================
#  run-deploy.sh — convenience wrapper around auto-deploy.sh
#
#  Sources local secrets from `deploy-secrets.env` (git-ignored) so you don't
#  have to export DEPLOY_PASSWORD / MDS_BASE_URL / MDS_TOKEN by hand each time,
#  then runs the real deploy.
#
#  Usage:
#    cp deploy-secrets.env.example deploy-secrets.env   # once, then fill it in
#    ./run-deploy.sh                 # deploy default branch (feature/Phase2), all servers
#    ./run-deploy.sh feature/Phase2 143.110.252.201     # one branch, one server
#
#  Everything after the first arg is passed straight through to auto-deploy.sh
#  (BRANCH, then optional single-server IP).
# ============================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS="$HERE/deploy-secrets.env"

if [ ! -f "$SECRETS" ]; then
    echo "❌ $SECRETS not found."
    echo "   Create it:  cp deploy-secrets.env.example deploy-secrets.env  (then fill in the values)"
    exit 1
fi

# shellcheck disable=SC1090
source "$SECRETS"

if [ -z "${DEPLOY_PASSWORD:-}" ] || [ "${DEPLOY_PASSWORD:-}" = "CHANGE_ME" ]; then
    echo "❌ DEPLOY_PASSWORD is not set (still CHANGE_ME?). Edit $SECRETS."
    exit 1
fi

case "${MDS_BASE_URL:-}" in
    ""|*"<host>"*)
        echo "⚠️  MDS_BASE_URL/MDS_TOKEN look unset or placeholder — MDS will be enabled but the"
        echo "    master-data sync will be SKIPPED (app still serves from the local mirror)."
        echo "    Fill real values in $SECRETS to run the sync."
        ;;
esac

exec "$HERE/auto-deploy.sh" "${1:-feature/Phase2}" "${2:-}"
