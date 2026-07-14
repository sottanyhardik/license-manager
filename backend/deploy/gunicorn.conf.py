"""
Gunicorn configuration for license-manager-v1 (new backend/).

Parallel-run: binds to 127.0.0.1:8001
Cutover:      change bind to "127.0.0.1:8000" after legacy is stopped.

Worker sizing: 4 workers = 2 × CPU + 1 (assumes 1–2 vCPU DigitalOcean droplet).
Adjust GUNICORN_WORKERS env var or edit directly for larger instances.
"""

import os

# ---------------------------------------------------------------------------
# Binding
# ---------------------------------------------------------------------------
bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8001")

# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------
workers = int(os.environ.get("GUNICORN_WORKERS", "4"))  # 2 × CPU + 1
worker_class = "gthread"
threads = 2

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
# Logging — rotate via logrotate, not gunicorn itself
# ---------------------------------------------------------------------------
accesslog = "/var/log/license-manager-v1/gunicorn-access.log"
errorlog = "/var/log/license-manager-v1/gunicorn-error.log"
loglevel = "warning"

# ---------------------------------------------------------------------------
# App loading
# ---------------------------------------------------------------------------
preload_app = True   # load Django once per master; copy-on-write for workers
