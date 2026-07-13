"""
Gunicorn production config for the Master-Data Service (ADR-001).

Loaded via `gunicorn -c deploy/gunicorn.conf.py mds.wsgi:application`
(the systemd unit does exactly this). All values can be overridden by the
GUNICORN_* environment variables so the same file works on hosts with
different core counts without editing code.

MDS is a small internal REST peer (writes + delta pulls), not a user-facing
high-concurrency app, so a modest sync-worker pool is plenty and keeps memory
predictable. Bumping workers is a one-line env change (GUNICORN_WORKERS).
"""

import multiprocessing
import os

# --- Bind ------------------------------------------------------------------
# Default to a loopback TCP socket that nginx proxy_passes to. To use a unix
# socket instead, set GUNICORN_BIND=unix:/run/mds/mds.sock (nginx must then
# proxy_pass to that socket, and the socket dir must be writable by the
# service user — RuntimeDirectory=mds in the systemd unit handles this).
bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8100")

# --- Worker model ----------------------------------------------------------
# (2 x CPU) + 1 is the standard sync-worker rule of thumb; cap it so a big
# box does not spawn dozens of idle workers for a low-traffic internal service.
_default_workers = min((multiprocessing.cpu_count() * 2) + 1, 5)
workers = int(os.getenv("GUNICORN_WORKERS", str(_default_workers)))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "sync")
threads = int(os.getenv("GUNICORN_THREADS", "2"))

# --- Timeouts / lifecycle --------------------------------------------------
# 30s worker timeout is generous for JSON API calls; bulk_upsert of large
# masters (HSCode/ItemName) is the only slow path — raise via env if a
# consolidation load times out rather than baking a huge default in here.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Recycle workers to bound any slow memory growth; jitter avoids all workers
# restarting at once.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))

# --- Logging ---------------------------------------------------------------
# Files by default so logs survive alongside the app; set to "-" to log to
# stdout/stderr and let journald/systemd capture them instead.
_log_dir = os.getenv("GUNICORN_LOG_DIR", os.path.join(os.path.dirname(__file__), "..", "logs"))
accesslog = os.getenv("GUNICORN_ACCESS_LOG", os.path.join(_log_dir, "gunicorn-access.log"))
errorlog = os.getenv("GUNICORN_ERROR_LOG", os.path.join(_log_dir, "gunicorn-error.log"))
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Include response time (%(L)s) so slow endpoints are visible. Do NOT log the
# Authorization header — service tokens must never hit disk.
access_log_format = (
    '%(h)s %(t)s "%(r)s" %(s)s %(b)s %(L)ss "%(f)s" "%(a)s"'
)

# --- Process naming --------------------------------------------------------
proc_name = "mds-gunicorn"

# --- Preload ---------------------------------------------------------------
# preload_app shares the parent's memory (copy-on-write) across workers and
# fails fast at boot if the app cannot import — good for a systemd Type=notify
# unit. Django/DRF here have no per-worker warmup state that would forbid it.
preload_app = os.getenv("GUNICORN_PRELOAD", "true").lower() == "true"
