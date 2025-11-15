# FILE: scripts/start_celery_worker.sh
# Make executable: chmod +x scripts/start_celery_worker.sh
# Usage: ./scripts/start_celery_worker.sh [concurrency] [queue]
# Example: ./scripts/start_celery_worker.sh 4 default

#!/usr/bin/env bash
set -euo pipefail

# Optional: path to virtualenv activation (edit if you use venv)
# source /path/to/venv/bin/activate

CONCURRENCY="${1:-4}"
QUEUE="${2:-default}"
LOGLEVEL="${CELERY_LOGLEVEL:-info}"
APP_MODULE="${APP_MODULE:-lmanagement}"

exec celery -A "${APP_MODULE}" worker \
  --loglevel="${LOGLEVEL}" \
  --concurrency="${CONCURRENCY}" \
  --queues="${QUEUE}" \
  --max-tasks-per-child=100 \
  --without-gossip --without-mingle --without-heartbeat
