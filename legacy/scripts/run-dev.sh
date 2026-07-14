#!/bin/bash
#
# run-dev.sh — Local development runner for License Manager
#
# Starts all services needed for local development in one terminal:
#   1. Redis            (broker/cache — started via brew if not already up)
#   2. Django           runserver  → http://localhost:8000
#   3. Celery worker    (background tasks)
#   4. Celery beat      (periodic task scheduler)
#   5. Vite / React     dev server → http://localhost:5173  (proxies /api → :8000)
#
# Press Ctrl-C once to stop everything cleanly.
#
# Logs are written to ./logs/dev/<service>.log
#
# Flags:
#   --no-frontend   skip the Vite dev server
#   --no-celery     skip the Celery worker + beat
#
set -euo pipefail

# ── Paths ────────────────────────────────────────────────────────────
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_PY="$ROOT_DIR/.venv/bin/python"
VENV_CELERY="$ROOT_DIR/.venv/bin/celery"
LOG_DIR="$ROOT_DIR/logs/dev"

# ── Options ──────────────────────────────────────────────────────────
RUN_FRONTEND=1
RUN_CELERY=1
for arg in "$@"; do
    case "$arg" in
        --no-frontend) RUN_FRONTEND=0 ;;
        --no-celery)   RUN_CELERY=0 ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

# ── Colours ──────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[dev]${NC} $*"; }
ok()    { echo -e "${GREEN}[dev]${NC} $*"; }
warn()  { echo -e "${YELLOW}[dev]${NC} $*"; }
err()   { echo -e "${RED}[dev]${NC} $*"; }

mkdir -p "$LOG_DIR"

# ── Pre-flight checks ────────────────────────────────────────────────
[ -x "$VENV_PY" ] || { err "venv python not found at $VENV_PY — create it and pip install -r backend/requirements.txt"; exit 1; }

# Redis
if ! redis-cli ping >/dev/null 2>&1; then
    warn "Redis not responding — attempting: brew services start redis"
    brew services start redis >/dev/null 2>&1 || true
    for _ in $(seq 1 20); do redis-cli ping >/dev/null 2>&1 && break; sleep 0.5; done
    redis-cli ping >/dev/null 2>&1 && ok "Redis is up" || { err "Redis failed to start"; exit 1; }
else
    ok "Redis is up"
fi

# Postgres
if ! pg_isready -q 2>/dev/null; then
    warn "PostgreSQL not responding — attempting: brew services start postgresql@18"
    brew services start postgresql@18 >/dev/null 2>&1 || true
    for _ in $(seq 1 30); do pg_isready -q 2>/dev/null && break; sleep 0.5; done
fi
pg_isready -q 2>/dev/null && ok "PostgreSQL is up" || { err "PostgreSQL is not running"; exit 1; }

# ── Process tracking + cleanup ───────────────────────────────────────
PIDS=()
# Recursively collect a PID and all its descendants (children first is fine;
# we signal the whole set). Works without job-control/process-group tricks.
collect_tree() {
    local pid="$1" child
    for child in $(pgrep -P "$pid" 2>/dev/null); do
        collect_tree "$child"
    done
    echo "$pid"
}

cleanup() {
    trap '' INT TERM   # ignore further signals while we tear down
    echo ""
    warn "Shutting down..."
    local all=()
    for pid in "${PIDS[@]}"; do
        while read -r p; do all+=("$p"); done < <(collect_tree "$pid")
    done
    # SIGTERM the whole forest (children + leaders).
    for p in "${all[@]}"; do kill -TERM "$p" 2>/dev/null || true; done
    # Give them a moment, then SIGKILL any survivors.
    sleep 2
    for p in "${all[@]}"; do kill -KILL "$p" 2>/dev/null || true; done
    ok "All services stopped."
    exit 0
}
trap cleanup INT TERM

start() {
    local name="$1"; shift
    local dir="$1"; shift
    local log="$LOG_DIR/$name.log"
    info "Starting ${name}  (logs: logs/dev/${name}.log)"
    ( cd "$dir" && exec "$@" ) >"$log" 2>&1 &
    PIDS+=("$!")
}

# ── Launch services ──────────────────────────────────────────────────
start "django" "$BACKEND_DIR" "$VENV_PY" manage.py runserver 0.0.0.0:8000

if [ "$RUN_CELERY" -eq 1 ]; then
    start "celery-worker" "$BACKEND_DIR" "$VENV_CELERY" -A lmanagement worker --loglevel=info
    start "celery-beat"   "$BACKEND_DIR" "$VENV_CELERY" -A lmanagement beat   --loglevel=info
else
    warn "Skipping Celery (--no-celery)"
fi

if [ "$RUN_FRONTEND" -eq 1 ]; then
    if [ -d "$FRONTEND_DIR/node_modules" ]; then
        start "vite" "$FRONTEND_DIR" npm run dev
    else
        warn "frontend/node_modules missing — run 'npm install' in frontend/. Skipping Vite."
    fi
else
    warn "Skipping frontend (--no-frontend)"
fi

sleep 2
echo ""
ok "Services launched:"
echo -e "   ${GREEN}Django API${NC}   →  http://localhost:8000"
[ "$RUN_FRONTEND" -eq 1 ] && echo -e "   ${GREEN}React (Vite)${NC} →  http://localhost:5173"
[ "$RUN_CELERY" -eq 1 ]   && echo -e "   ${GREEN}Celery${NC}       →  worker + beat (Redis broker)"
echo ""
info "Tailing logs. Press Ctrl-C to stop all services."
echo ""

# Stream all logs; when any service dies the tail keeps running, so we just wait.
tail -n +1 -F "$LOG_DIR"/*.log &
PIDS+=("$!")

# Keep the script alive until Ctrl-C. We poll with `sleep` instead of a bare
# `wait`: bash defers a trapped signal until the current builtin returns, and a
# bare `wait` blocks forever — so the cleanup trap would never fire. A short
# foreground `sleep` returns every second, letting the pending trap run promptly.
while true; do
    sleep 1
    # If the primary service (Django, first PID) has died, tear the rest down too.
    kill -0 "${PIDS[0]}" 2>/dev/null || { warn "Django exited — shutting down remaining services."; cleanup; }
done
