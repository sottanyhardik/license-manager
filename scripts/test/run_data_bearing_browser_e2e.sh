#!/usr/bin/env bash
# Local-only REAL BACKEND WORKFLOW browser harness.  It creates or reuses one
# explicitly named disposable database and never reads a production URL.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DB_NAME="${LM_E2E_DB_NAME:-test_license_manager_browser_e2e}"
DB_USER="${DB_USER:-lmanagement}"
BACKEND_PORT="${LM_E2E_BACKEND_PORT:-8000}"
FRONTEND_PORT="${LM_E2E_FRONTEND_PORT:-41731}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

[[ "$DB_NAME" =~ ^test_[A-Za-z0-9_]+$ ]] || {
  echo "Refusing non-test database name." >&2
  exit 2
}
[[ "$DB_USER" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || {
  echo "Refusing invalid database role identifier." >&2
  exit 2
}

cleanup() {
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if ! psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1; then
  createdb "$DB_NAME"
fi
psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO \"$DB_USER\"" >/dev/null

cd "$ROOT_DIR"
DB_NAME="$DB_NAME" "$PYTHON_BIN" backend/manage.py migrate --noinput
DB_NAME="$DB_NAME" "$PYTHON_BIN" backend/manage.py seed_browser_2509
DB_NAME="$DB_NAME" "$PYTHON_BIN" backend/manage.py runserver "127.0.0.1:$BACKEND_PORT" --noreload >"/tmp/license-manager-e2e-backend.log" 2>&1 &
BACKEND_PID=$!

cd "$ROOT_DIR/frontend"
VITE_API_PROXY_TARGET="http://127.0.0.1:$BACKEND_PORT" npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort >"/tmp/license-manager-e2e-frontend.log" 2>&1 &
FRONTEND_PID=$!

for _ in $(seq 1 60); do
  if curl --silent --fail "http://127.0.0.1:$FRONTEND_PORT/login" >/dev/null && \
    curl --silent --fail --request OPTIONS "http://127.0.0.1:$BACKEND_PORT/api/auth/login/" >/dev/null; then
    break
  fi
  sleep 1
done

LM_REAL_E2E=1 PLAYWRIGHT_BASE_URL="http://127.0.0.1:$FRONTEND_PORT" \
  npx playwright test e2e/data-bearing.real.spec.ts "$@"
