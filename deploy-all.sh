#!/bin/bash
# ============================================================
#  deploy-all.sh — Deploy to all 3 servers (or a specific one)
#
#  Usage:
#    bash deploy-all.sh                  # deploy to all 3
#    bash deploy-all.sh license-manager  # only license-manager
#    bash deploy-all.sh labdhi           # only labdhi
#    bash deploy-all.sh tractor          # only tractor
#
#  Prerequisites:
#    - SSH key auth configured for django@<server-ip>
#      (or sshpass installed and DEPLOY_PASSWORD env var set)
#    - server-envs/<name>.env files present locally
#    - git push done (or code pushed to the branch being deployed)
# ============================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
log()   { echo -e "${BLUE}▶${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*"; }
err()   { echo -e "${RED}✗${NC} $*"; }
header(){ echo -e "\n${BOLD}══ $* ══${NC}"; }

# ── Server registry ──────────────────────────────────────────
declare -A SERVER_IP=(
  [license-manager]="143.110.252.201"
  [labdhi]="139.59.92.226"
  [tractor]="165.232.185.220"
)

REPO_DIR="/home/django/license-manager"
VENV="$REPO_DIR/.venv"
USER="django"
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# ── SSH helper ────────────────────────────────────────────────
ssh_cmd() {
  local server="$1"; shift
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$server" "$@"
}
scp_cmd() {
  scp -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$@"
}

# ── Determine targets ─────────────────────────────────────────
TARGETS=("license-manager" "labdhi" "tractor")
if [[ -n "${1:-}" ]]; then
  if [[ -z "${SERVER_IP[$1]+_}" ]]; then
    err "Unknown server: $1. Valid: license-manager | labdhi | tractor"
    exit 1
  fi
  TARGETS=("$1")
fi

# ── Push code first ───────────────────────────────────────────
header "Pushing branch '$BRANCH' to origin"
git push origin HEAD
ok "Code pushed"

# ── Deploy each server ────────────────────────────────────────
FAILED=()

for NAME in "${TARGETS[@]}"; do
  IP="${SERVER_IP[$NAME]}"
  SERVER="$USER@$IP"
  ENV_FILE="$(dirname "$0")/server-envs/${NAME}.env"

  header "Deploying → $NAME ($IP)"

  # 1. Verify env file exists
  if [[ ! -f "$ENV_FILE" ]]; then
    err "Missing env file: $ENV_FILE — skipping $NAME"
    FAILED+=("$NAME")
    continue
  fi

  # 2. SCP the env file to the server
  log "Uploading .env to $SERVER:$REPO_DIR/backend/.env"
  scp_cmd "$ENV_FILE" "$SERVER:$REPO_DIR/backend/.env"
  ok ".env uploaded"

  # 3. Pull code
  log "Pulling latest code on $NAME"
  ssh_cmd "$SERVER" "cd $REPO_DIR && git fetch origin && git checkout $BRANCH && git pull origin $BRANCH"
  ok "Code updated"

  # 4. Python dependencies
  log "Installing Python dependencies"
  ssh_cmd "$SERVER" "$VENV/bin/pip install -r $REPO_DIR/backend/requirements.txt -q"
  ok "Python deps installed"

  # 5. Django: migrate + collectstatic
  log "Running migrations + collectstatic"
  ssh_cmd "$SERVER" "cd $REPO_DIR/backend && $VENV/bin/python manage.py migrate --no-input && $VENV/bin/python manage.py collectstatic --no-input -v 0"
  ok "Migrations + static files done"

  # 6. Frontend build
  log "Building frontend"
  ssh_cmd "$SERVER" "cd $REPO_DIR/frontend && npm ci --silent && npm run build"
  ok "Frontend built"

  # 7. Restart services
  log "Restarting gunicorn + celery"
  ssh_cmd "$SERVER" bash << REMOTE
    sudo systemctl restart gunicorn 2>/dev/null || \
    sudo systemctl restart license-manager-gunicorn 2>/dev/null || \
    sudo systemctl restart lmanagement 2>/dev/null || \
    { echo "No gunicorn service found — restart manually"; }

    sudo systemctl restart celery 2>/dev/null || \
    sudo systemctl restart lmanagement-celery 2>/dev/null || true

    echo "Services restarted"
REMOTE
  ok "Services restarted on $NAME"

  echo ""
  ok "${BOLD}$NAME deployed successfully${NC} — https://${NAME}.duckdns.org  (or check your domain)"
done

# ── Summary ───────────────────────────────────────────────────
echo ""
header "Deploy Summary"
for NAME in "${TARGETS[@]}"; do
  if [[ " ${FAILED[*]} " =~ " $NAME " ]]; then
    err "$NAME — FAILED"
  else
    ok "$NAME — OK"
  fi
done

if [[ ${#FAILED[@]} -gt 0 ]]; then
  err "One or more servers failed — check output above"
  exit 1
fi
