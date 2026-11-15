#!/usr/bin/env bash
# Stop processes started by scripts/dev-start.sh (only those — verified via PID files),
# then stop the Postgres/Redis containers. Data volumes are always kept.
# Usage: scripts/dev-stop.sh [--keep-services]
set -uo pipefail
source "$(dirname "$0")/dev/lib.sh"

KEEP=0
for a in "$@"; do case $a in --keep-services) KEEP=1 ;; *) err "unknown option: $a"; exit 64 ;; esac; done

for p in vite beat worker django; do stop_proc "$p"; done

if [ $KEEP -eq 0 ] && command -v docker >/dev/null && docker info >/dev/null 2>&1 && [ -f "$LM_COMPOSE_ENV" ]; then
  compose stop postgres redis && ok "postgres + redis stopped (volumes kept)"
else
  info "docker services left as they are"
fi
