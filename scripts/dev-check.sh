#!/usr/bin/env bash
# Local environment acceptance checks (read-only; local DB only).
# Usage: scripts/dev-check.sh [--gates [area...]]
#   --gates   also run scripts/dev/quality-gate.sh (CI-equivalent) with the local
#             credentials, e.g. --gates all | --gates backend mds
# Exit: 0 all checks passed · 1 something failed
set -uo pipefail
source "$(dirname "$0")/dev/lib.sh"

FAILED=0
pass() { ok "$*"; }
fail() { err "$*"; FAILED=1; }
check() { local label=$1; shift; if out=$("$@" 2>&1); then pass "$label${out:+ — ${out##*$'\n'}}"; else fail "$label — ${out##*$'\n'}"; fi; }

echo "== Toolchain"
for t in "python3.14:$LM_VENV/bin/python --version" "node:node --version" "npm:npm --version" \
         "uv:uv --version" "ruff:ruff --version" "docker:docker --version" "compose:docker compose version --short" \
         "git:git --version" "gh:gh --version" "psql:psql --version" "redis-cli:redis-cli --version" "brew:brew --version"; do
  name=${t%%:*}; cmd=${t#*:}
  if v=$($cmd 2>/dev/null | head -1); then info "$(printf '%-10s %s' "$name" "$v")"; else warn "$(printf '%-10s not installed' "$name")"; fi
done
arch=$(file -b "$(readlink -f "$LM_VENV/bin/python")" 2>/dev/null); [[ $arch == *arm64* ]] && pass "backend venv is arm64-native" || warn "backend venv arch: $arch"

echo "== Environment files"
require_env_files && pass "env files present" || FAILED=1
for f in .env.local backend/.env master-data-service/.env frontend/.env.local; do
  [ -e "$LM_ROOT/$f" ] || continue
  git -C "$LM_ROOT" check-ignore -q "$f" && pass "$f is git-ignored" || fail "$f is NOT git-ignored"
done
assert_local_db || FAILED=1

echo "== Services"
if docker_ready; then
  check "PostgreSQL responds" docker exec lm-postgres pg_isready -U lmanagement -d lmanagement
  check "Redis responds (PING)" docker exec lm-redis redis-cli ping
else
  FAILED=1
fi

echo "== Django"
PY="$LM_VENV/bin/python"
cd "$LM_BACKEND" || exit 1
check "manage.py check" "$PY" manage.py check
check "Django → PostgreSQL" "$PY" manage.py shell -v 0 -c "from django.db import connection as c; c.ensure_connection(); print('server_version', c.pg_version)"
check "Django → Redis cache" "$PY" manage.py shell -v 0 -c "from django.core.cache import cache; cache.set('lm-dev-check','ok',10); assert cache.get('lm-dev-check')=='ok'; cache.delete('lm-dev-check'); print('cache round-trip ok')"
check "Celery → Redis broker" "$PY" -c "import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','lmanagement.settings'); django.setup(); from lmanagement.celery import app; c=app.connection(); c.ensure_connection(max_retries=1); print('broker', c.as_uri()); c.release()"
if managed_pid worker >/dev/null; then
  check "Celery worker answers ping" "$LM_VENV/bin/celery" -A lmanagement inspect ping -t 5
else
  info "Celery worker not running (scripts/dev-start.sh) — ping skipped"
fi
pending=$("$PY" manage.py showmigrations --plan 2>/dev/null | grep -c '^\[ \]'); [ "${pending:-0}" -eq 0 ] && pass "no unapplied migrations" || warn "$pending unapplied migration(s) (scripts/dev-start.sh --migrate)"

echo "== HTTP (only if dev-start.sh is running)"
for u in http://127.0.0.1:8000/admin/login/ http://127.0.0.1:5173/; do
  code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$u" 2>/dev/null); code=${code:-000}
  case $code in 200|302) pass "$u → $code";; 000) info "$u not running";; *) fail "$u → $code";; esac
done

if [ "${1:-}" = "--gates" ]; then
  shift
  echo "== CI quality gates (scripts/dev/quality-gate.sh ${*:-all})"
  # Export ONLY connection settings (not DEBUG etc.) so tests see CI-like config.
  for k in DB_NAME DB_USER DB_PASS DB_HOST DB_PORT REDIS_URL; do export "$k=$(env_get "$LM_BACKEND/.env" "$k")"; done
  for k in MDS_DB_NAME MDS_DB_USER MDS_DB_PASS MDS_DB_HOST MDS_DB_PORT; do export "$k=$(env_get "$LM_MDS/.env" "$k")"; done
  PYTHON="$LM_VENV/bin/python" MDS_PYTHON="$LM_MDS_VENV/bin/python" sh "$LM_ROOT/scripts/dev/quality-gate.sh" "${@:-all}" || FAILED=1
fi

echo
[ $FAILED -eq 0 ] && ok "ALL CHECKS PASSED" || err "SOME CHECKS FAILED (see above)"
exit $FAILED
