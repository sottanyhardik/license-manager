#!/bin/sh
# Local quality gates — mirrors .github/workflows/ci.yml (the authoritative spec).
# Usage: scripts/dev/quality-gate.sh [frontend|backend|mds|mds-client|all] ...
# Exit code: 0 = every gate ran and passed; 1 = a gate failed; 3 = nothing failed but a gate could not run.
# Env: PYTHON (default: .venv-3.14/bin/python, then .venv/bin/python, then python3)
#      DB_* / MDS_DB_* override the CI defaults — must point at a LOCAL database.
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT" || exit 1
export PATH="$HOME/.local/bin:$HOME/.local/node/bin:/opt/homebrew/bin:/opt/homebrew/opt/postgresql@16/bin:$PATH"
[ $# -eq 0 ] && set -- all
FAIL=0; SKIP=0; REPORT=""
note() { REPORT="$REPORT
$1"; echo "$1"; }
run() { # name, dir, cmd...
  name=$1; dir=$2; shift 2
  printf '\n=== %s  (cd %s && %s)\n' "$name" "$dir" "$*"
  if (cd "$ROOT/$dir" && "$@"); then note "PASS     $name"; else note "FAIL     $name"; FAIL=1; fi
}
skip() { note "NOT RUN  $1 — $2"; SKIP=1; }

pick_python() {
  for p in "${PYTHON:-}" "$ROOT/.venv-3.14/bin/python" "$ROOT/.venv/bin/python" python3; do
    [ -n "$p" ] && command -v "$p" >/dev/null 2>&1 && { echo "$p"; return; }
  done
}
PY=$(pick_python)
py_ok() { "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,14) else 1)' 2>/dev/null; }
port_open() { "$PY" -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(s.connect_ex(('$1',$2)))" 2>/dev/null; }
is_local() { case "$1" in localhost|127.0.0.1|::1) return 0;; *) return 1;; esac; }

gate_frontend() {
  command -v npm >/dev/null 2>&1 || { skip "frontend (lint/typecheck/test/build)" "npm not installed (run scripts/dev/bootstrap-macos.sh)"; return; }
  [ -d frontend/node_modules ] || run "frontend: npm ci" frontend npm ci
  run "frontend: lint"       frontend npm run lint
  run "frontend: typecheck"  frontend npm run typecheck
  run "frontend: unit tests" frontend npm test
  run "frontend: build"      frontend npm run build
}
gate_backend() {
  py_ok || { skip "backend (check/migrations/pytest)" "Python >= 3.14 required (found: $("$PY" --version 2>&1)); see docs/claude/INSTALLATION.md"; return; }
  export DJANGO_SETTINGS_MODULE=lmanagement.settings TESTING=true
  export SECRET_KEY="${SECRET_KEY_TEST:-ci-not-a-secret-key-for-tests-only}"
  export DB_NAME="${DB_NAME:-lmanagement}" DB_USER="${DB_USER:-lmanagement}" DB_PASS="${DB_PASS:-lmanagement}"
  export DB_HOST="${DB_HOST:-localhost}" DB_PORT="${DB_PORT:-5432}" REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
  is_local "$DB_HOST" || { skip "backend" "DB host is not local — refusing to run against it"; return; }
  port_open "$DB_HOST" "$DB_PORT" || { skip "backend (check/migrations/pytest)" "Postgres not reachable on $DB_HOST:$DB_PORT (scripts/dev/services.sh start)"; return; }
  run "backend: manage.py check"  backend "$PY" manage.py check
  run "backend: migrations check" backend "$PY" manage.py makemigrations --check --dry-run
  run "backend: pytest tests/"    backend "$PY" -m pytest tests/ -p no:cacheprovider
  run "backend: app-level tests"  backend "$PY" -m pytest apps/license/tests apps/core/tests --import-mode=importlib -p no:cacheprovider
}
gate_mds() {
  py_ok || { skip "mds (migrations/pytest)" "Python >= 3.14 required"; return; }
  export DJANGO_SETTINGS_MODULE=mds.settings
  export SECRET_KEY="${SECRET_KEY_TEST:-ci-not-a-secret-key-for-tests-only}"
  export MDS_DB_NAME="${MDS_DB_NAME:-master_data}" MDS_DB_USER="${MDS_DB_USER:-master_data}" MDS_DB_PASS="${MDS_DB_PASS:-master_data}"
  export MDS_DB_HOST="${MDS_DB_HOST:-localhost}" MDS_DB_PORT="${MDS_DB_PORT:-5432}"
  is_local "$MDS_DB_HOST" || { skip "mds" "MDS DB host is not local — refusing"; return; }
  port_open "$MDS_DB_HOST" "$MDS_DB_PORT" || { skip "mds (migrations/pytest)" "Postgres not reachable on $MDS_DB_HOST:$MDS_DB_PORT"; return; }
  run "mds: migrations check" master-data-service "$PY" manage.py makemigrations --check --dry-run
  run "mds: pytest"           master-data-service "$PY" -m pytest -p no:cacheprovider
}
gate_mds_client() {
  py_ok || { skip "mds-client (runtests)" "Python >= 3.14 required"; return; }
  run "mds-client: runtests" mds-client "$PY" runtests.py
}
for area in "$@"; do
  case $area in
    frontend) gate_frontend;; backend) gate_backend;; mds) gate_mds;; mds-client) gate_mds_client;;
    all) gate_frontend; gate_backend; gate_mds; gate_mds_client;;
    *) echo "unknown area: $area (frontend|backend|mds|mds-client|all)"; exit 64;;
  esac
done
printf '\n=== QUALITY GATE SUMMARY (python: %s)%s\n' "$PY" "$REPORT"
[ $FAIL -ne 0 ] && exit 1
[ $SKIP -ne 0 ] && exit 3
exit 0
