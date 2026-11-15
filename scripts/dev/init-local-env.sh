#!/bin/sh
# Create the git-ignored LOCAL DEVELOPMENT env files with freshly generated,
# development-only credentials. Idempotent: an existing file is never
# overwritten (delete it yourself first if you really want a new one).
# Secrets are generated here and never echoed.
#
#   .env.local                 docker compose (Postgres/Redis containers)
#   backend/.env               Django (auto-loaded by lmanagement/settings.py)
#   master-data-service/.env   MDS (exported by scripts/dev-*.sh)
#   frontend/.env.local        Vite (no secrets — VITE_* is public)
#
# Usage: scripts/dev/init-local-env.sh
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
umask 077

rand() { openssl rand -hex "$1"; }
today=$(date +%F)

# Reuse the DB passwords from .env.local when it already exists, so the
# backend/MDS files stay consistent with the running containers.
getkv() { [ -f "$1" ] && sed -n "s/^$2=//p" "$1" | tail -1 || true; }
DBP=$(getkv .env.local LM_DB_PASSWORD); [ -n "$DBP" ] || DBP=$(rand 24)
MDSP=$(getkv .env.local MDS_DB_PASSWORD); [ -n "$MDSP" ] || MDSP=$(rand 24)

created=""; kept=""
write_if_missing() { # path  (content on stdin)
  if [ -e "$1" ]; then kept="$kept $1"; cat >/dev/null; else cat >"$1"; created="$created $1"; fi
}

write_if_missing .env.local <<EOF
# LOCAL DEVELOPMENT ONLY — generated $today by scripts/dev/init-local-env.sh. Git-ignored.
# Read by docker compose via scripts/dev-*.sh (--env-file .env.local).
COMPOSE_PROJECT_NAME=license-manager
LM_PG_PORT=5432
LM_REDIS_PORT=6379
LM_DB_NAME=lmanagement
LM_DB_USER=lmanagement
LM_DB_PASSWORD=$DBP
MDS_DB_NAME=master_data
MDS_DB_USER=master_data
MDS_DB_PASSWORD=$MDSP
EOF

write_if_missing backend/.env <<EOF
# LOCAL DEVELOPMENT ONLY — generated $today by scripts/dev/init-local-env.sh. Git-ignored.
# Loaded by lmanagement/settings.py (python-dotenv, override=False: real env vars win).
# Never put production values here. Template: backend/.env.example
DJANGO_ENVIRONMENT=development
DEBUG=true
DJANGO_SECRET_KEY=$(rand 32)
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=lmanagement
DB_USER=lmanagement
DB_PASS=$DBP
DB_HOST=127.0.0.1
DB_PORT=5432
REDIS_URL=redis://127.0.0.1:6379/0
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
FRONTEND_URL=http://localhost:5173
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
SYNC_ENABLED=False
MDS_ENABLED=False
EOF

write_if_missing master-data-service/.env <<EOF
# LOCAL DEVELOPMENT ONLY — generated $today by scripts/dev/init-local-env.sh. Git-ignored.
# mds/settings.py reads the process environment; scripts/dev-*.sh export this file.
DJANGO_SETTINGS_MODULE=mds.settings
SECRET_KEY=$(rand 32)
DEBUG=true
ALLOWED_HOSTS=localhost,127.0.0.1
MDS_DB_NAME=master_data
MDS_DB_USER=master_data
MDS_DB_PASS=$MDSP
MDS_DB_HOST=127.0.0.1
MDS_DB_PORT=5432
EOF

umask 022
write_if_missing frontend/.env.local <<EOF
# LOCAL DEVELOPMENT ONLY. Git-ignored (frontend/.gitignore: *.local).
# No secrets here — every VITE_* value is compiled into the browser bundle.
# Target of the Vite dev-server /api proxy (vite.config.js).
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
EOF

for f in .env.local backend/.env master-data-service/.env frontend/.env.local; do
  git check-ignore -q "$f" || { echo "ERROR: $f is NOT git-ignored — fix .gitignore before continuing" >&2; exit 1; }
done
echo "created:${created:- (none)}"
echo "kept (already existed):${kept:- (none)}"
echo "All local env files are git-ignored. Secrets were not printed."
