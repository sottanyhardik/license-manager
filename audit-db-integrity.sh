#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python3}"

if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

cd "$ROOT_DIR/backend"
exec "$PYTHON_BIN" manage.py audit_database_integrity "$@"
