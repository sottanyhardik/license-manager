#!/bin/zsh
# Persistent macOS worker for asynchronous ledger uploads.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
CELERY_BIN="$ROOT_DIR/.venv/bin/celery"

if [[ ! -x "$CELERY_BIN" ]]; then
  print -u2 "License Manager worker: Celery executable not found at $CELERY_BIN"
  exit 1
fi

# launchd has no Homebrew shell environment. Psycopg needs libpq available
# before Django initialises database settings.
export PATH="/opt/homebrew/opt/libpq/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ -x /opt/homebrew/bin/brew ]]; then
  LIBPQ_PREFIX="$(/opt/homebrew/bin/brew --prefix libpq 2>/dev/null || true)"
elif [[ -x /usr/local/bin/brew ]]; then
  LIBPQ_PREFIX="$(/usr/local/bin/brew --prefix libpq 2>/dev/null || true)"
else
  LIBPQ_PREFIX=""
fi
if [[ -n "$LIBPQ_PREFIX" && -d "$LIBPQ_PREFIX/lib" ]]; then
  export DYLD_FALLBACK_LIBRARY_PATH="$LIBPQ_PREFIX/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
fi

cd "$ROOT_DIR/backend"
export PYTHONUNBUFFERED=1
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# Threads avoid macOS's Python 3.14 prefork crashes while allowing independent
# ledger licences to run concurrently. Override for constrained machines.
exec "$CELERY_BIN" -A lmanagement worker --pool=threads --concurrency="${CELERY_LOCAL_CONCURRENCY:-4}" -Q celery --loglevel=info
