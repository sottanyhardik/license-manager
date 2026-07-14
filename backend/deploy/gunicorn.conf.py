"""
Gunicorn configuration for license-manager-v1 (new backend/).

Parallel-run: binds to 127.0.0.1:8001
Cutover:      change bind to "127.0.0.1:8000" after legacy is stopped.

Worker sizing: 2 workers × 4 threads = 8 concurrent requests (for 1 vCPU).
Adjust GUNICORN_WORKERS / GUNICORN_THREADS env vars or edit directly for larger instances.
"""

import os
import pathlib

# ---------------------------------------------------------------------------
# Binding
# ---------------------------------------------------------------------------
bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8001")

# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))  # for 1 vCPU: 1-2 workers
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
graceful_timeout = 90  # allow in-flight PDF requests to finish on restart

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
timeout = 120       # PDF generation can take up to 60 s; leave headroom
keepalive = 5

# ---------------------------------------------------------------------------
# Request recycling (prevents memory leaks)
# ---------------------------------------------------------------------------
max_requests = 1000
max_requests_jitter = 50

# ---------------------------------------------------------------------------
# Logging — fall back to stderr if log directory does not exist
# ---------------------------------------------------------------------------
_log_dir = pathlib.Path("/var/log/license-manager-v1")
accesslog = str(_log_dir / "gunicorn-access.log") if _log_dir.exists() else "-"
errorlog = str(_log_dir / "gunicorn-error.log") if _log_dir.exists() else "-"
loglevel = "warning"

# ---------------------------------------------------------------------------
# App loading
# ---------------------------------------------------------------------------
preload_app = True   # load Django once per master; copy-on-write for workers


def post_fork(server, worker):
    """Re-create DB connections in each worker after fork to avoid sharing."""
    from django.db import connections
    for conn in connections.all():
        conn.close()
