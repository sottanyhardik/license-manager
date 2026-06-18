# Checklist — Release / Deploy

Context: 3 servers — `license-manager` (canonical), `labdhi`, `tractor`. Master data syncs
one-way from canonical. Read the relevant script before running it; deploy/sync are
outward-facing — confirm with a human first.

## Pre-deploy

- [ ] `.claude/checklists/pr.md` passed on the merge to `develop`.
- [ ] Frontend built: `cd frontend && npm run build` → `frontend/dist/`.
- [ ] Backend migrations reviewed and forward-safe.
- [ ] DB backup taken (see `backups/` + `db-tools.sh`).

## Deploy (per server)

- [ ] `python manage.py migrate`
- [ ] `python manage.py collectstatic`
- [ ] Restart gunicorn + `celery -A lmanagement worker` (see `supervisord.conf` / `start-server.sh`).
- [ ] Indexes applied if changed: `deploy-indexes.sh`.

## Master-data sync (canonical → followers)

- [ ] `sync-masters.sh` (runs `audit_masters` + `auto_import_masters`).
- [ ] Verify followers: `audit-db-integrity.sh`, `server-health.sh`.

## Post-deploy

- [ ] Smoke test login + a read endpoint per server.
- [ ] `verify-deployment.sh`.
- [ ] Confirm `ActivityLog` is recording and Celery is processing.

Reference: `docs/operations/*` (server setup, RBAC setup). Repo deploy scripts:
`auto-deploy.sh`, `deploy-license-manager.sh`, `server-health.sh`.
