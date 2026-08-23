#!/usr/bin/env bash
# Local-only REAL BACKEND WORKFLOW browser harness.  It creates or reuses one
# explicitly named disposable database and never reads a production URL.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# A browser gate must never share a database with another local process.  The
# generated default is intentionally unique; callers may provide a name only
# when it is a new disposable ``test_*`` database.
RUN_TOKEN="$(date +%s)_$$"
DB_NAME="${LM_E2E_DB_NAME:-test_license_manager_browser_e2e_${RUN_TOKEN}}"
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
  [[ -n "${BACKEND_PID:-}" ]] && wait "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && wait "$FRONTEND_PID" 2>/dev/null || true

  # Never drop a database supplied by, or pre-existing for, another process.
  # This harness creates exactly one fresh, name-validated database per run.
  if [[ "${CREATED_DATABASE:-0}" == "1" && "${LM_E2E_KEEP_DB:-0}" != "1" ]]; then
    psql -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid()" >/dev/null 2>&1 || true
    dropdb "$DB_NAME" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

if psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1; then
  echo "Refusing to reuse an existing database: $DB_NAME" >&2
  exit 2
fi
createdb "$DB_NAME"
CREATED_DATABASE=1
psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO \"$DB_USER\"" >/dev/null

cd "$ROOT_DIR"
DB_NAME="$DB_NAME" "$PYTHON_BIN" backend/manage.py migrate --noinput
DB_NAME="$DB_NAME" "$PYTHON_BIN" backend/manage.py seed_browser_2509
DB_NAME="$DB_NAME" "$PYTHON_BIN" backend/manage.py runserver "127.0.0.1:$BACKEND_PORT" --noreload >"/tmp/license-manager-e2e-backend.log" 2>&1 &
BACKEND_PID=$!

cd "$ROOT_DIR/frontend"
# Force Vite's dependency optimizer for a deterministic browser process; a
# stale optimized dependency can otherwise produce a 504 during lazy loading.
# ``frontend/.env`` may point normal development at localhost:8000.  Clear
# that direct URL for this process so every browser API call is forced through
# the isolated Vite proxy above.
VITE_API_URL= VITE_API_PROXY_TARGET="http://127.0.0.1:$BACKEND_PORT" npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort --force >"/tmp/license-manager-e2e-frontend.log" 2>&1 &
FRONTEND_PID=$!

ready=0
for _ in $(seq 1 60); do
  if curl --silent --fail "http://127.0.0.1:$FRONTEND_PORT/login" >/dev/null && \
    curl --silent --fail --request OPTIONS "http://127.0.0.1:$BACKEND_PORT/api/auth/login/" >/dev/null; then
    ready=1
    break
  fi
  sleep 1
done

if [[ "$ready" != "1" ]]; then
  echo "E2E services did not become ready within 60 seconds." >&2
  tail -n 80 /tmp/license-manager-e2e-backend.log >&2 || true
  tail -n 80 /tmp/license-manager-e2e-frontend.log >&2 || true
  exit 1
fi

LM_REAL_E2E=1 PLAYWRIGHT_BASE_URL="http://127.0.0.1:$FRONTEND_PORT" \
  npx playwright test e2e/data-bearing.real.spec.ts "$@"
