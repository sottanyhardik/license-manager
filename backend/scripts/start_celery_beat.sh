# FILE: scripts/start_celery_beat.sh
# Make executable: chmod +x scripts/start_celery_beat.sh
# Usage: ./scripts/start_celery_beat.sh
# Example: ./scripts/start_celery_beat.sh

#!/usr/bin/env bash
set -euo pipefail

# Optional: source your virtualenv
# source /path/to/venv/bin/activate

APP_MODULE="${APP_MODULE:-lmanagement}"
LOGLEVEL="${CELERY_LOGLEVEL:-info}"

exec celery -A "${APP_MODULE}" beat --loglevel="${LOGLEVEL}" --pidfile=""
