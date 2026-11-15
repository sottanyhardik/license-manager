#!/usr/bin/env bash
# Start the local development stack:
#   Docker: PostgreSQL 16 + Redis 7  →  Django runserver :8000  →  Celery worker
#   →  (optional) Celery beat  →  Vite :5173
# Never runs destructive DB operations. Migrations only with --migrate (local DB only).
#
# Usage: scripts/dev-start.sh [--with-beat] [--no-celery] [--no-frontend] [--services-only] [--migrate]
#   --with-beat   also start Celery beat. OFF by default: the beat schedule includes
#                 license.tasks.sync_all_licenses (external DGFT calls) and periodic
#                 balance jobs; enable it only when you are testing scheduled tasks.
set -euo pipefail
source "$(dirname "$0")/dev/lib.sh"

WITH_BEAT=0 CELERY=1 FRONTEND=1 APPS=1 MIGRATE=0
for a in "$@"; do
  case $a in
    --with-beat) WITH_BEAT=1 ;; --no-celery) CELERY=0 ;; --no-frontend) FRONTEND=0 ;;
    --services-only) APPS=0 ;; --migrate) MIGRATE=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) err "unknown option: $a"; exit 64 ;;
  esac
done

require_env_files
assert_local_db
mkdir -p "$LM_LOG_DIR" "$LM_ROOT/backups/db"

# 1–3. Docker services
docker_ready
info "starting postgres + redis (docker compose)"
compose up -d postgres redis
for c in lm-postgres lm-redis; do
  wait_healthy "$c" 90 && ok "$c healthy" || { err "$c not healthy — docker logs $c"; exit 1; }
done
[ $APPS -eq 1 ] || { ok "services up (Postgres 127.0.0.1:5432, Redis 127.0.0.1:6379)"; exit 0; }

# 4. Backend virtualenv
[ -x "$LM_VENV/bin/python" ] || { err "backend/.venv missing — see docs/development-environment/LOCAL-SETUP.md"; exit 1; }
"$LM_VENV/bin/python" -c 'import sys; sys.exit(sys.version_info < (3, 14))' || { err "backend/.venv is not Python 3.14"; exit 1; }
PY="$LM_VENV/bin/python"

# 5. Django configuration
(cd "$LM_BACKEND" && "$PY" manage.py check >/dev/null) && ok "manage.py check" || { err "Django system check failed: (cd backend && .venv/bin/python manage.py check)"; exit 1; }
if [ $MIGRATE -eq 1 ]; then
  (cd "$LM_BACKEND" && "$PY" manage.py migrate --noinput) && ok "migrations applied (local DB)"
else
  pending=$(cd "$LM_BACKEND" && "$PY" manage.py showmigrations --plan 2>/dev/null | grep -c '^\[ \]' || true)
  [ "${pending:-0}" -eq 0 ] && ok "no unapplied migrations" || warn "$pending unapplied migration(s) — rerun with --migrate"
fi

# 6. Django
port_in_use 8000 && ! managed_pid django >/dev/null && { err "port 8000 is in use by another process — not starting Django (lsof -nP -iTCP:8000)"; exit 1; }
start_proc django "$LM_BACKEND" "$PY" manage.py runserver 127.0.0.1:8000

# 7. Celery (solo pool: forking pools crash on macOS + Python 3.14 — see scripts/development/run-celery-dev.sh)
if [ $CELERY -eq 1 ]; then
  start_proc worker "$LM_BACKEND" "$LM_VENV/bin/celery" -A lmanagement worker --pool=solo -Q celery -l info -n "lm-dev@%h"
  if [ $WITH_BEAT -eq 1 ]; then
    start_proc beat "$LM_BACKEND" "$LM_VENV/bin/celery" -A lmanagement beat -l info
  else
    info "celery beat not started (use --with-beat)"
  fi
fi

# 8. Vite
if [ $FRONTEND -eq 1 ]; then
  [ -x "$LM_FRONTEND/node_modules/.bin/vite" ] || { info "frontend deps missing — running npm ci"; (cd "$LM_FRONTEND" && npm ci); }
  port_in_use 5173 && ! managed_pid vite >/dev/null && { err "port 5173 is in use by another process — not starting Vite"; exit 1; }
  start_proc vite "$LM_FRONTEND" "$LM_FRONTEND/node_modules/.bin/vite" --host 127.0.0.1 --port 5173 --strictPort
fi

# 9. Addresses
cat <<EOF

  Frontend (Vite)    http://localhost:5173
  Backend (Django)   http://127.0.0.1:8000      admin: /admin/
  PostgreSQL         127.0.0.1:5432  db=lmanagement user=lmanagement  (+ master_data)
  Redis              127.0.0.1:6379  (broker + result backend: db 0)
  Logs               logs/dev/*.log
  Status / stop      scripts/dev-status.sh  ·  scripts/dev-stop.sh
EOF
