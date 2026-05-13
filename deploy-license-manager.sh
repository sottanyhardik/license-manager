#!/bin/bash
# Deploy script for license-manager.duckdns.org (143.110.252.201)
# Run from your LOCAL machine: bash deploy-license-manager.sh
# Prerequisites: SSH key auth set up for django@143.110.252.201

set -e
SERVER="django@143.110.252.201"
REPO_DIR="/home/django/license-manager"
VENV="$REPO_DIR/.venv"

echo "=== [1/6] Pushing latest code to license-manager server ==="
git push origin HEAD  # make sure local commits are pushed

echo "=== [2/6] Pulling latest code on server ==="
ssh "$SERVER" "cd $REPO_DIR && git pull origin \$(git rev-parse --abbrev-ref HEAD)"

echo "=== [3/6] Installing Python dependencies ==="
ssh "$SERVER" "$VENV/bin/pip install -r $REPO_DIR/backend/requirements.txt -q"

echo "=== [4/6] Running Django migrations & collectstatic ==="
ssh "$SERVER" "cd $REPO_DIR/backend && $VENV/bin/python manage.py migrate --no-input && $VENV/bin/python manage.py collectstatic --no-input -v 0"

echo "=== [5/6] Building frontend ==="
ssh "$SERVER" "cd $REPO_DIR/frontend && npm ci --silent && npm run build"

echo "=== [6/6] Installing nginx config & restarting services ==="
ssh "$SERVER" bash << 'REMOTE'
  # Install nginx config for license-manager
  sudo cp /home/django/license-manager/nginx-license-manager.conf \
          /etc/nginx/sites-available/license-manager
  sudo ln -sf /etc/nginx/sites-available/license-manager \
              /etc/nginx/sites-enabled/license-manager

  # Remove labdhi config from this server if it exists (wrong config)
  sudo rm -f /etc/nginx/sites-enabled/labdhi \
             /etc/nginx/sites-enabled/nginx-http-only.conf \
             /etc/nginx/sites-enabled/default

  # Test and reload nginx
  sudo nginx -t && sudo systemctl reload nginx

  # Restart gunicorn so the latest Django code is live
  sudo systemctl restart gunicorn || sudo systemctl restart license-manager-gunicorn || true
  echo "Services reloaded."
REMOTE

echo ""
echo "=== Deploy complete ==="
echo "  Frontend: https://license-manager.duckdns.org"
echo "  Admin:    https://license-manager.duckdns.org/admin/"
echo ""
echo "  If gunicorn failed to restart, run on the server:"
echo "    sudo systemctl status gunicorn"
