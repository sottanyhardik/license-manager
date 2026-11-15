#!/usr/bin/env bash
# Show the state of the local development stack. Read-only.
set -uo pipefail
source "$(dirname "$0")/dev/lib.sh"

echo "Docker services"
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  for c in lm-postgres lm-redis; do printf '  %-12s %s\n' "$c" "$(container_health "$c")"; done
else
  echo "  docker daemon not running"
fi

echo "App processes (started by dev-start.sh)"
for p in django worker beat vite; do
  if pid=$(managed_pid "$p"); then printf '  %-12s running (pid %s)\n' "$p" "$pid"; else printf '  %-12s stopped\n' "$p"; fi
done

echo "Ports"
for port in 5432 6379 8000 5173; do
  owner=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | awk 'NR==2{print $1" (pid "$2")"}')
  printf '  %-6s %s\n' "$port" "${owner:-free}"
done

echo "HTTP"
for u in http://127.0.0.1:8000/admin/login/ http://127.0.0.1:5173/; do
  printf '  %-38s %s\n' "$u" "$(curl -s -o /dev/null -m 3 -w '%{http_code}' "$u" 2>/dev/null || echo down)"
done
