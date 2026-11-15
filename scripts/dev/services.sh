#!/bin/sh
# Start/stop/status local dev Postgres 16 + Redis (Homebrew services). Local only.
export PATH="/opt/homebrew/bin:$PATH"
command -v brew >/dev/null 2>&1 || { echo "Homebrew missing — run scripts/dev/bootstrap-macos.sh"; exit 1; }
case "${1:-status}" in
  start)  brew services start postgresql@16; brew services start redis;;
  stop)   brew services stop postgresql@16;  brew services stop redis;;
  status) brew services list | grep -E "postgresql|redis";;
  *) echo "usage: $0 start|stop|status"; exit 64;;
esac
