#!/bin/zsh
# Keep the local Django API available for the Vite application.
# This script is run by the macOS launchd agent installed below.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  print -u2 "License Manager backend: Python environment not found at $PYTHON_BIN"
  exit 1
fi

mkdir -p "$ROOT_DIR/logs/dev"
cd "$ROOT_DIR/backend"

export DEBUG="${DEBUG:-true}"
export PYTHONUNBUFFERED=1

# launchd has a deliberately minimal PATH/DYLD environment.  Psycopg's pure
# Python package needs Homebrew's libpq at runtime, so discover it before
# Django imports database settings.  Interactive shells already inherit this
# through Homebrew; the persistent launch agent does not.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
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

# launchd supplies availability and automatic restart; --noreload prevents
# Django from leaving a separate child process that launchd cannot supervise.
exec "$PYTHON_BIN" manage.py runserver 127.0.0.1:8000 --noreload
