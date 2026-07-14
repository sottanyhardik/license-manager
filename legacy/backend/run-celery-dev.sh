#!/bin/sh
# Local dev Celery worker (macOS-safe).
#
# The default prefork pool forks worker processes; on macOS + Python 3.14 those
# forked children can crash with SIGSEGV (signal 11) / WorkerLostError the moment
# they run a task. `--pool=solo` runs tasks in a single process with NO fork,
# which avoids the crash entirely — ideal for local development.
#
# Production (Linux, via supervisor) keeps the normal prefork pool and is not
# affected; do NOT use this script there.
#
# Usage (from backend/, with the venv active):
#   ./run-celery-dev.sh                 # solo pool, info logs
#   ./run-celery-dev.sh -l debug        # extra args passed through to celery
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
cd "$(dirname "$0")" || exit 1
exec celery -A lmanagement worker --pool=solo -l info "$@"
