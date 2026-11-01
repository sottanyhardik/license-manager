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
# Defaults avoid 8000 (a developer's shared backend) and 41731 (Playwright's own
# webServer). Override both only with free ports.
BACKEND_PORT="${LM_E2E_BACKEND_PORT:-8011}"
FRONTEND_PORT="${LM_E2E_FRONTEND_PORT:-41732}"
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
  [[ -n "${WORKER_PID:-}" ]] && kill "$WORKER_PID" 2>/dev/null || true
  [[ -n "${WORKER_PID:-}" ]] && wait "$WORKER_PID" 2>/dev/null || true
  # The Redis index was verified empty before this run, so everything in it was created
  # by this run. Clear it so queued test jobs cannot leak into a later run.
  [[ -n "${E2E_REDIS_URL:-}" && "${CREATED_DATABASE:-0}" == "1" ]] && redis-cli -n "$E2E_REDIS_DB" flushdb >/dev/null 2>&1 || true
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

# Background jobs (ledger packages, replans) are queued in Redis and must be run by a
# worker that this harness starts against the SAME disposable database.  Use a dedicated
# Redis database index.  Index 0 is the developer's broker and is refused, and the index
# must be empty so nothing outside this run can be consumed or cleaned up by mistake.
E2E_REDIS_DB="${LM_E2E_REDIS_DB:-7}"
[[ "$E2E_REDIS_DB" =~ ^[1-9][0-9]?$ ]] || { echo "Refusing Redis index '$E2E_REDIS_DB' (must be 1-99, never the developer's 0)." >&2; exit 2; }
command -v redis-cli >/dev/null || { echo "redis-cli is required for the isolated broker check." >&2; exit 2; }
if [[ "$(redis-cli -n "$E2E_REDIS_DB" dbsize)" != "0" ]]; then
  echo "Refusing to use Redis index $E2E_REDIS_DB: it already contains keys." >&2
  exit 2
fi
E2E_REDIS_URL="redis://127.0.0.1:6379/$E2E_REDIS_DB"

# The readiness probe below accepts any server answering on these ports.  If a
# process we did not start already listens here (for example a developer's
# shared backend on 8000), the browser suite would run against that server and
# its database.  Refuse instead of trusting the probe.
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if (echo >"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    echo "Refusing to start: port $port is already in use by another process." >&2
    echo "Set LM_E2E_BACKEND_PORT / LM_E2E_FRONTEND_PORT to free ports." >&2
    exit 2
  fi
done

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
DB_NAME="$DB_NAME" REDIS_URL="$E2E_REDIS_URL" "$PYTHON_BIN" backend/manage.py runserver "127.0.0.1:$BACKEND_PORT" --noreload >"/tmp/license-manager-e2e-backend.log" 2>&1 &
BACKEND_PID=$!

# Worker for the disposable database and the isolated broker only.  Solo pool keeps
# Django database connections in one process; concurrency 1 keeps job order deterministic.
# No subshell: WORKER_PID must be the Celery process itself, or cleanup cannot stop it.
PYTHONPATH="$ROOT_DIR/backend" DB_NAME="$DB_NAME" REDIS_URL="$E2E_REDIS_URL" "$PYTHON_BIN" -m celery -A lmanagement worker \
  -Q celery --pool=solo --concurrency=1 --without-heartbeat --without-gossip --without-mingle \
  --loglevel=INFO --hostname="lm-e2e-$RUN_TOKEN@%h" >"/tmp/license-manager-e2e-worker.log" 2>&1 &
WORKER_PID=$!
for _ in $(seq 1 60); do
  grep -q "ready\." /tmp/license-manager-e2e-worker.log 2>/dev/null && break
  kill -0 "$WORKER_PID" 2>/dev/null || break
  sleep 1
done
grep -q "ready\." /tmp/license-manager-e2e-worker.log 2>/dev/null || { echo "E2E Celery worker did not become ready." >&2; tail -n 40 /tmp/license-manager-e2e-worker.log >&2; exit 1; }

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
  # Stop waiting as soon as the backend this run started has exited.
  kill -0 "$BACKEND_PID" 2>/dev/null || break
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
  npx playwright test "$@"
