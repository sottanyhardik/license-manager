# Deploying backend/ to production

## Log directory (create once per server)

```bash
sudo mkdir -p /var/log/license-manager-v1
sudo chown django:django /var/log/license-manager-v1
```

---

## Parallel-run (current phase)

The new app runs on port 8001 alongside the legacy app on port 8000.
Only `/api/v1/` traffic is routed to the new backend; all other paths hit legacy.

```bash
# 1. Install Python dependencies
cd /home/django/license-manager/backend
/home/django/license-manager/venv/bin/pip install -r requirements/base.txt

# 2. Run migrations (review output before confirming)
DJANGO_SETTINGS_MODULE=config.settings.prod \
  /home/django/license-manager/venv/bin/python manage.py migrate --check
DJANGO_SETTINGS_MODULE=config.settings.prod \
  /home/django/license-manager/venv/bin/python manage.py migrate

# 3. Collect static files
DJANGO_SETTINGS_MODULE=config.settings.prod \
  /home/django/license-manager/venv/bin/python manage.py collectstatic --no-input

# 4. Install supervisor configs
sudo cp /home/django/license-manager/backend/deploy/supervisor.conf \
        /etc/supervisor/conf.d/license-manager-v1.conf
sudo cp /home/django/license-manager/backend/deploy/celery.conf \
        /etc/supervisor/conf.d/license-manager-v1-celery.conf

# 5. Add nginx routing snippet (see nginx-v1.conf for exact placement)
#    Then validate and reload — never blind-reload:
sudo nginx -t && sudo systemctl reload nginx

# 6. Start new supervisor programs
sudo supervisorctl reread && sudo supervisorctl update

# 7. Verify
curl -s https://<domain>/api/v1/health/
# Expected: {"status": "ok", "version": "<string>"}
sudo supervisorctl status license-manager-v1 license-manager-v1-celery
```

### Rollback (parallel-run)

```bash
# Stop the new processes
sudo supervisorctl stop license-manager-v1 license-manager-v1-celery

# Remove the /api/v1/ location block from the nginx server block, then:
sudo nginx -t && sudo systemctl reload nginx
```

---

## Final cutover (after all criteria met — see ADR-009)

```bash
# 1. Update gunicorn bind to port 8000
#    Edit backend/deploy/gunicorn.conf.py: bind = "127.0.0.1:8000"
#    (or set GUNICORN_BIND=127.0.0.1:8000 in supervisor environment)

# 2. Restart new gunicorn on port 8000
sudo supervisorctl restart license-manager-v1

# 3. Update nginx: replace the legacy location block's proxy_pass target
#    with the backendv1 upstream (or change upstream server to :8000).
#    Remove the /api/v1/ split block — all traffic now uses one location.
sudo nginx -t && sudo systemctl reload nginx

# 4. Verify the new app is serving all traffic
curl -s https://<domain>/api/v1/health/
curl -s https://<domain>/api/health/   # if legacy health endpoint proxied

# 5. Stop legacy processes
sudo supervisorctl stop license-manager license-manager-celery

# 6. Remove legacy supervisor configs (optional — keeps supervisor clean)
sudo rm /etc/supervisor/conf.d/license-manager.conf \
        /etc/supervisor/conf.d/license-manager-celery.conf
sudo supervisorctl reread && sudo supervisorctl update

# 7. Monitor error logs for 24 h
sudo tail -f /var/log/license-manager-v1/gunicorn-error.log \
             /var/log/license-manager-v1/celery-error.log \
             /var/log/license-manager-v1/django.log
```

### Rollback (cutover)

```bash
# Revert nginx to point at legacy (port 8000 / legacy upstream)
sudo nginx -t && sudo systemctl reload nginx

# Restart legacy supervisor programs
sudo supervisorctl start license-manager license-manager-celery

# Stop v1 on port 8000
sudo supervisorctl stop license-manager-v1 license-manager-v1-celery
```

---

## Log rotation

Add `/etc/logrotate.d/license-manager-v1`:

```
/var/log/license-manager-v1/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        supervisorctl signal USR1 license-manager-v1 license-manager-v1-celery 2>/dev/null || true
    endscript
}
```
