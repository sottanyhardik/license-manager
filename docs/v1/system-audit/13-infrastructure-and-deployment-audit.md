# 13 Infrastructure and Deployment Audit (Agent E)

Date: 2026-11-01. Branch: `version-v1`. Mode: read-only.

## Scope and method

- Read only. No configuration, Docker, nginx, systemd, or deploy script was changed. No container, server, worker, load test, `npm run build`, package install, or connection to Redis, PostgreSQL, Celery, or production was made.
- Not read, by rule: `.env*` files, `auth.json`, `config.toml`, `~/.claude.json`, `.env_dgft`, `deploy-secrets.env`, the watchdog env file (`/etc/license-manager-watchdog.env`), and the database dumps in `backups/`. Environment variables are described by name and code default only. Git tracking of env-named files was checked with `git ls-files` and `git check-ignore`, which read names only.
- Labels: **MEASURED** means a read-only command was run and its output was observed. **THEORETICAL** means the risk is inferred from code or configuration and not observed at runtime. Production state that could not be observed is marked UNVERIFIED.
- Finding IDs: ISS-066 to ISS-069 only.

## 1. Summary

- **No container definitions exist.** There is no Dockerfile, compose file, Kubernetes manifest, Procfile, or Terraform in the repository (MEASURED by `find`). Deployment is a bash script (`scripts/deployment/auto-deploy.sh`) that connects over SSH to hosts running nginx, supervisor, systemd, and cron.
- **The deployment topology is partly visible.** The repository holds three nginx hostname families for this application, two HTTP-only configurations, a separate Master-Data Service (MDS), and a sample supervisor entry for an unrelated application. The live Gunicorn and supervisor definitions for this application are not in the repository.
- **Security defaults fail open.** The production guard in settings runs only when `DJANGO_ENVIRONMENT` is set to production, and the variable is not set by any deploy artefact in the repository. A development signing key is committed in code as the fallback. Env-named files are tracked by git (ISS-066).
- **nginx configuration drift and exposure.** One HTTP-only configuration still serves `backend/media` publicly. Locations with their own `add_header` do not inherit the server-level security headers (ISS-067).
- **The deploy path is unsafe by default.** It disables SSH host-key checking, runs `git reset --hard` and `git clean -fd` on the server, migrates the schema without a pre-migration dump, and contains a privileged database-ownership fallback. Gunicorn and supervisor config are not versioned (ISS-068).
- **Observability and backup controls are thin.** The repository has no logging configuration, error-tracking, metrics or tracing, log rotation, or backup retention policy. The watchdog cron is the only active monitor. A backup script pulls production dumps into an ignored local directory, which holds about 1.0 GB with no pruning (ISS-069).

Findings table: ISS-066 to ISS-069 (section 7).

## 2. Infrastructure files found

| Path | Kind | What it is | Label |
|---|---|---|---|
| `nginx-license-manager.conf` | nginx vhost | HTTP redirect plus HTTPS for `license-manager.duckdns.org`; proxies `/api/` and `/admin/` to `127.0.0.1:8000`; internal `/protected-media/`; security headers | MEASURED |
| `nginx-labdhi.conf` | nginx vhost | HTTP and HTTPS for `labdhi.duckdns.org` (port-80 block names IP `139.59.92.226`); `/protected-media/` present | MEASURED |
| `nginx-license-tractor.conf` | nginx vhost | HTTP and HTTPS for `license-tractor.duckdns.org` (IP `165.232.185.220`); `/protected-media/` present | MEASURED |
| `nginx-http-only.conf` | nginx vhost | HTTP-only for `labdhi.duckdns.org` (IP `64.227.129.26`); **public `/media/` alias** | MEASURED |
| `nginx-http-only-tractor.conf` | nginx vhost | HTTP-only tractor variant with `proxy_pass` to `127.0.0.1:8000` | MEASURED |
| `nginx-protected-media.conf` | snippet | Replacement for the public `/media/` block; internal `/protected-media/` | MEASURED |
| `master-data-service/deploy/nginx-mds.conf` | nginx vhost | MDS; placeholder host `masters.internal.example.com`; proxies to `127.0.0.1:8100` | MEASURED |
| `master-data-service/deploy/gunicorn.conf.py` | Gunicorn | MDS config; bind, workers, timeout, log paths all env-overridable (`GUNICORN_*`) | MEASURED |
| `master-data-service/deploy/mds.service`, `deploy-mds.sh` | systemd, deploy | MDS service and its deploy script (not read in full) | MEASURED (names) |
| `backend/setup/supervisord.conf` | supervisor | Program `dgftglobalexim`: Gunicorn on `0.0.0.0:8086`, 3 workers, user `django`. **Not this application.** | MEASURED |
| `backend/deploy/celery.service` | systemd | Example Celery unit: `/srv/lmanagement`, user `www-data`, `-Q celery,ledger`, no `--beat` | MEASURED |
| `scripts/deployment/license-manager-celery.conf` | supervisor | Program `license-manager-celery`: `/home/django/license-manager`, user `django`, `--beat`, `-Q celery,ledger`, logs under project `logs/` | MEASURED |
| `scripts/deployment/auto-deploy.sh` | deploy | Primary deploy (38 KB). `run-deploy.sh` and `deploy-license-manager.sh` are six-line wrappers that exec it | MEASURED |
| `scripts/deployment/deploy-indexes.sh` | deploy | Index deployment; takes `pg_dump` before changes (`:180-189`); uses `CONCURRENTLY` | MEASURED |
| `scripts/deployment/verify-deployment.sh`, `setup-ssl-tractor.sh` | ops | Verification and TLS setup helpers (not read in full) | MEASURED (names) |
| `scripts/deployment/license-manager-watchdog.sh` | cron | Self-healing check every 10 minutes; `--install` writes `/etc/cron.d/license-manager-watchdog` | MEASURED |
| `scripts/database/db-tools.sh` | ops | Remote `pg_dump` over SSH from production into local `backups/`; local `pg_restore` | MEASURED |
| `run_django.sh` | dev | Development `runserver` manager: binds `0.0.0.0`, uses `--use-threading`, kills processes listening on the port with `kill -9` | MEASURED |
| `.github/workflows/ci.yml` | CI | Frontend (lint, typecheck, test, build); backend pytest with Postgres 16 and Redis 7 service containers; MDS job. **No deploy job.** | MEASURED |
| `tests/deployment/test_auto_deploy.sh` | test | Test for the deploy script (not read in full) | MEASURED (name) |

**Not found (MEASURED by `find` or `grep`):** Dockerfile, docker-compose or compose YAML, Kubernetes manifests, Terraform (`*.tf`), Procfile, `backend/gunicorn.conf.py` (referenced by `auto-deploy.sh:380-382`), a production `[program:license-manager]` supervisor definition, a logrotate configuration, a Django `LOGGING` dictionary, an error-tracking SDK, a metrics or tracing SDK, and any backup-retention or restore-automation script.

## 3. Deployment topology as found

```mermaid
flowchart TB
  subgraph Deploy workstation
    D[auto-deploy.sh<br/>ssh, StrictHostKeyChecking=no]
    DB[db-tools.sh<br/>remote pg_dump to local backups/]
  end
  subgraph App host, per hostname family
    NG[nginx :80 and :443<br/>certbot TLS]
    GU[Gunicorn lmanagement.wsgi<br/>127.0.0.1:8000<br/>config not in repo]
    CE[Celery worker, beat in one variant<br/>-Q celery,ledger<br/>supervisor program]
    PG[(PostgreSQL<br/>localhost:5432)]
    RD[(Redis 127.0.0.1:6379<br/>db0 broker, db1 cache)]
    ST[backend/staticfiles]
    MD[backend/media<br/>internal /protected-media/]
    DIST[frontend/dist]
    WD[watchdog, cron every 10 min]
  end
  MDS[MDS gunicorn 127.0.0.1:8100<br/>separate service]
  Browser --> NG
  NG -->|/api/ and /admin/| GU
  NG --> ST
  NG -->|X-Accel-Redirect| MD
  NG --> DIST
  GU --> PG
  GU --> RD
  CE --> PG
  CE --> RD
  GU -. MDS_BASE_URL if MDS_ENABLED .-> MDS
  D -->|ssh, git reset, migrate, supervisorctl| App host
  DB -->|ssh pg_dump| PG
  WD -->|check, restart, maybe reboot| App host
```

Observations:

- Three hostname families are visible in nginx configs: `license-manager.duckdns.org`, `labdhi.duckdns.org` (two configs with different IPs), and `license-tractor.duckdns.org`. The repository does not show which of these are live.
- A sibling application (`dgftglobalexim`, port 8086, bound to all interfaces) has a supervisor sample in `backend/setup/`. Which host runs it is not established.
- The MDS service sits behind its own nginx vhost on `127.0.0.1:8100`. Its public name is a placeholder.
- Redis serves both the Celery broker (`db0`) and the Django cache (`db1`) on one instance with no password in the default URL.

## 4. Environment variable names and defaults

Names and code defaults only. Values in any env file were not read. Names marked **(secret)** are credential-bearing by name.

### 4.1 Security and core (`backend/lmanagement/settings.py`)

| Name | Code default | Line | Note |
|---|---|---:|---|
| `DJANGO_SECRET_KEY` | literal development key, via `_DEFAULT_DEV_SECRET_KEY` **(secret)** | 40-43 | Committed fallback |
| `DEBUG` | `"False"` | 45 | Safe default |
| `DJANGO_ENVIRONMENT` | `"development"` | 46-47 | Gates `IS_PRODUCTION`; the production guard is off unless set |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | 61-63 | Production guard rejects these |
| `SECURE_SSL_REDIRECT` | `"False"` | 72 | |
| `SESSION_COOKIE_SECURE` | `"False"` | 73 | |
| `CSRF_COOKIE_SECURE` | `"False"` | 74 | |
| `SECURE_HSTS_SECONDS` | `"0"` | 75 | Guard requires at least 31536000 |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `"False"` | 76 | |
| `SECURE_HSTS_PRELOAD` | `"False"` | 77 | |
| `ACCESS_TOKEN_MINUTES` | `"30"` | 334 | |
| `CORS_ALLOWED_ORIGINS` | empty | 421 | Development origins added only when not production |
| `CSRF_TRUSTED_ORIGINS` | empty | 486 | |
| `MEDIA_X_ACCEL_REDIRECT` | empty | 255 | nginx location name; the repo comment expects `/protected-media/` |
| `TEST_DB_NAME` | empty | 215-217 | |

### 4.2 Database, cache, broker

| Name | Code default | Line | Note |
|---|---|---:|---|
| `DB_NAME` | `lmanagement` | 204 | Guard requires an explicit value in production |
| `DB_USER` | `lmanagement` | 205 | Same |
| `DB_PASS` | literal default password **(secret)** | 206 | Same; guard compares to default |
| `DB_HOST` | `localhost` | 207 | Same |
| `DB_PORT` | `5432` | 208 | |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` broker; `/1` cache | 111, 346, 392 | Guard requires explicit value; no password default |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | `1` | 384 | |
| `LICENSE_REPLAN_SOFT_TIME_LIMIT`, `LICENSE_REPLAN_TIME_LIMIT` | 240, 300 | 368-369 | Celery time limits |
| `LICENSE_PACKAGE_ITEM_SOFT_TIME_LIMIT`, `LICENSE_PACKAGE_ITEM_TIME_LIMIT` | 240, 300 | 374-375 | |
| `LICENSE_PACKAGE_ARCHIVE_SOFT_TIME_LIMIT`, `LICENSE_PACKAGE_ARCHIVE_TIME_LIMIT` | 300, 360 | 380-381 | |
| `LICENSE_LEDGER_PACKAGE_RETENTION_DAYS` | not in settings; code default 7 | `ledger.py:229` | Read through `getattr(settings, ...)` |

### 4.3 Email, frontend, integrations

| Name | Code default | Line | Note |
|---|---|---:|---|
| `EMAIL_BACKEND` | set from env, default not read | 529-531 | Guard requires it to be set in production |
| `EMAIL_HOST` | `localhost` | 533 | |
| `EMAIL_PORT` | `25` | 534 | |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | empty **(secret)** | 535-536 | |
| `EMAIL_USE_TLS` | `"False"` | 537 | |
| `DEFAULT_FROM_EMAIL` | an organisation address | 539 | Guard requires explicit value |
| `FRONTEND_URL` | `http://localhost:5173` | 540 | Guard requires HTTPS in production |
| `VITE_API_PROXY_TARGET` | `http://localhost:8000` | `frontend/vite.config.js:15` | Frontend dev proxy only |
| `DGFT_OWNERSHIP_URL` | public DGFT portal URL | 53 | |
| `DGFT_SCRIP_NUMBER`, `DGFT_SCRIP_ISSUE_DATE`, `DGFT_IEC_NUMBER`, `DGFT_APP_ID` | empty | 54-57 | Loaded from `.env_dgft` by `settings.py:4-8` |
| `DGFT_SESSION_ID`, `DGFT_CSRF_TOKEN`, `DGFT_AWSALB` | empty **(secret)** | 58-60 | Session-token names; not covered by any guard |
| `MDS_ENABLED`, `MDS_BASE_URL`, `MDS_TOKEN` | `"False"`, empty, empty **(secret)** | 607-609 | |
| `SYNC_ENABLED`, `SYNC_PUSH_ON_SAVE` | `"False"` | 588-589 | |
| `SYNC_SERVER_ID` | `default` | 587 | |
| `SYNC_PEER_TOKENS` | `{}` (JSON) **(secret)** | 591 | |
| `BISCUIT_COMPANY_ID` | `567` | 575 | |
| `RECONCILIATION_CIF_TOLERANCE`, `RECONCILIATION_QTY_TOLERANCE` | `1.00`, `1.000` | 581-582 | Financial tolerances; owner-controlled |

### 4.4 Other process-level names

- MDS Gunicorn (`master-data-service/deploy/gunicorn.conf.py:22-51`): `GUNICORN_BIND` (`127.0.0.1:8100`), `GUNICORN_WORKERS`, `GUNICORN_WORKER_CLASS` (`sync`), `GUNICORN_TIMEOUT` (30), `GUNICORN_GRACEFUL_TIMEOUT` (30), `GUNICORN_MAX_REQUESTS` (1000), `GUNICORN_MAX_REQUESTS_JITTER` (100), `GUNICORN_ACCESS_LOG`, `GUNICORN_ERROR_LOG`, `GUNICORN_LOG_LEVEL` (`info`).
- Watchdog (`license-manager-watchdog.sh` header): `PUBLIC_DOMAIN` (required), `MONITOR_USER`, `MONITOR_PASSWORD` **(secret)**, `ALERT_EMAIL_TO`, `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD` **(secret)**, `SMTP_FROM`. Read from `/etc/license-manager-watchdog.env`, which was not read.
- CI (`ci.yml:76-85`) sets `DJANGO_SETTINGS_MODULE`, `TESTING`, `SECRET_KEY` (a CI-only value), and the DB and Redis variables.

### 4.5 Env-named files tracked by git

`git ls-files` lists these as tracked: `.env` (repository root), `backend/.env_dgft`, `frontend/.env`, `frontend/.env.production`, `frontend/.env.example`, `master-data-service/.env.example`, `master-data-service/.env.production.example`, `deploy-secrets.env.example`. The real `deploy-secrets.env` exists in the working tree and is gitignored (`.gitignore:24`). The contents of the tracked files were not read. Whether they hold live values is UNVERIFIED (see ISS-066).

## 5. Logging, monitoring, backup, and deployment process

### 5.1 Logging

- No Django `LOGGING` dictionary exists in the backend or MDS (MEASURED by grep). The only `logging.basicConfig` call is in a script, `backend/apps/allotment/scripts/pdf_coordinate_finder.py:95`.
- 63 backend modules call `getLogger`. Without configuration they use Django defaults: `django.request` errors propagate to the root logger, which has no handler, so output goes to stderr and into whatever file supervisor captures.
- Supervisor captures Celery output to `logs/celery.log` and `logs/celery_err.log` (`scripts/deployment/license-manager-celery.conf:8-9`). No logrotate configuration exists (MEASURED).
- The watchdog writes `/var/log/license-manager-watchdog.log` (`license-manager-watchdog.sh:48`). The auto-deploy script's log destination was not confirmed.

### 5.2 Monitoring and health

- `GET /api/health/` is public. It runs `SELECT 1` and a cache set and get, and returns `{"status":"ok"}` (200) or `{"status":"degraded"}` (503). It exposes no version or configuration (`backend/apps/core/views/health.py:1-43`). The view says it is throttled only by the anonymous rate (300/hour).
- `GET /api/throttle-health/` is admin-only (`backend/apps/core/views/throttle_status.py`, `IsAdminUser`).
- No metrics, tracing, or error-tracking SDK appears in backend, MDS, or frontend source (MEASURED by grep). One hit exists: `backend/apps/core/management/commands/rqworker.py:43-52` offers a `--sentry-dsn` flag. RQ is not installed (`rq`, `django-rq` and `RQ_QUEUES` are absent from requirements and settings), so this command is unused.
- The watchdog is the only active monitor. It runs every 10 minutes and checks RAM, disk, PostgreSQL, supervisor programs, nginx, the local and public health endpoints, and the login endpoint (`license-manager-watchdog.sh:1-12`). Remediation restarts PostgreSQL (`:214-217`), supervisor (`:219-222`), the application and Celery programs (`:224-231`), and can kill Gunicorn with `pkill -9` (`:229`). It can reboot the host, at most once per cooldown. Disk and nginx-config problems are alert-only.

### 5.3 Backup and restore

- `docs/v1/07-quality-and-operations/backup-and-recovery.md` states: "No production backup or restore evidence was observed."
- `scripts/database/db-tools.sh` runs `pg_dump` over SSH against the production server (`:198`, `:226` plain SQL; `:342` custom format, compressed at level 6) and copies each dump to a local `backups/` directory. Restore (`:395`) targets the local database only. No production restore procedure is in the repository.
- `backups/` holds 121 `remote_db_backup_*.sql` files totalling about 1.0 GB, with names dated from 2026-08-13 to 2026-10-31 (MEASURED by `du` and `ls`). The directory is gitignored (`.gitignore:52`). No pruning or retention logic exists in `db-tools.sh` (MEASURED by grep for `rm`, `find`, `retain`, `keep`).
- `db-tools.sh:432` runs `rm -rf TL_ALLOT_* TL_BOE_* TL_TRADE_*` on the remote media path over SSH. The surrounding function was not reviewed in full.
- `deploy-indexes.sh:180-189` takes a `pg_dump` before index changes. `auto-deploy.sh` does not (MEASURED: `pg_dump` appears in neither auto-deploy nor the migrate path).

### 5.4 Deployment process as found (`scripts/deployment/auto-deploy.sh`)

Ordered steps, from the script's section markers and commands:

1. Local prerequisite checks, then SSH helpers with `StrictHostKeyChecking=no` (`:255-280`).
2. Health gate function that polls `https://<domain>/api/health/` (`:89-122`).
3. Record the deployment attempt (`:292`). Stash local changes, excluding the venv backup, logs, and `backend/gunicorn.conf.py` (`:375-382`).
4. `git clean -fd` with exclusions for `frontend/dist`, `venv`, and `node_modules` (`:394`). `git fetch --all --prune` (`:405`).
5. Save local-only commits to a `backup/pre-deploy-*` branch if they are not on origin (`:426-436`). Then `git reset --hard origin/$BRANCH` (`:439`).
6. `python manage.py migrate --no-input` (`:471`). On a permission error, run `REASSIGN OWNED BY postgres TO ${DB_USER}` as the postgres user and retry (`:474-476`).
7. `collectstatic` (`:541`). Swap-file handling for the small-server RAM case is in `:545-553` (creation condition not read in full).
8. Certbot issuance with rollback of the HTTPS site on failure (`:619-674`). `nginx -t` before each reload (`:589-590`).
9. Materialized-view refresh (`:679-681`). Recursive `chmod` on media and `frontend/dist` (`:712-713`).
10. Stop `license-manager`, kill stale Gunicorn processes matching `lmanagement.wsgi:application` (`:716-735`), start it, and require at least four Gunicorn processes (`:745-765`).
11. Local health check on `http://127.0.0.1:8000/api/health/` (`:770-776`). Reread and update supervisor, restart the Celery program (`:786-793`). Verify the nginx port (`:796-803`).
12. External health gate from the deploy machine over HTTPS (`:824` onward).

Build and deploy are not separated: the frontend is built on the server, which the chunk-retention comment in `vite.config.js:35-38` and the dist exclusion at `:393-394` imply. This is inferred, not read from a build step.

## 6. Security-relevant configuration defaults

| Control | Code default | Production guard | Observation |
|---|---|---|---|
| Secret key | Literal development key | Rejects default, requires 32+ characters, only when production is declared | Default is committed; fail-open unless `DJANGO_ENVIRONMENT` is set |
| `DEBUG` | False | Requires False | Safe default |
| `ALLOWED_HOSTS` | localhost only | Rejects localhost, 127.0.0.1, `*` | Safe default; guard only when production |
| HTTPS redirect and cookies | Off | Required when production | nginx terminates TLS; Django sets `SECURE_PROXY_SSL_HEADER` (`settings.py:71`) and trusts `X-Forwarded-Proto` unconditionally |
| HSTS | 0 seconds | At least one year, subdomains, preload | nginx sets `max-age=31536000; includeSubDomains` on the HTTPS vhost only (`nginx-license-manager.conf:117`) |
| Database credentials | Literal defaults | Guard rejects defaults in production | CI uses the same literal values, which is acceptable for CI only |
| Redis | No password in default URL | Guard requires explicit `REDIS_URL` | No authentication enforced by the code |
| CORS | Not allow-all | Explicit origins only when production | Development origins are added only when not production |
| Email delivery | `localhost:25`, no TLS | Requires `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL`, HTTPS `FRONTEND_URL` | Guard is separate from the security guard |
| Token lifetimes | Access 30 minutes; refresh 7 days | Not guarded | `settings.py:334-335` |
| Public health | Anonymous `/api/health/` | Not guarded | Minimal response by design |
| Bind addresses | nginx to `127.0.0.1:8000` | Not guarded | `run_django.sh` binds `0.0.0.0`; the sample supervisor for another app binds `0.0.0.0:8086` |

## 7. Findings (ISS-066 to ISS-069)

Each finding lists severity, confidence, label, evidence, business impact, remediation, acceptance criteria, and the runtime measurement that would confirm it. Runtime measurements must be run by the owner or QA in a controlled environment. None was run here.

### ISS-066: Production configuration fails open, default signing key is committed, and env-named files are tracked by git

- **Severity:** High. Escalate to Critical if the production process is found without `DJANGO_ENVIRONMENT` and the committed key is live. **Confidence:** Medium (production environment UNVERIFIED). **Label:** MEASURED (code and tracking). Production state UNVERIFIED.
- **Evidence:**
  - `backend/lmanagement/settings.py:40-43` (development key fallback), `:46-47` (`DJANGO_ENVIRONMENT` default `development`), `:80-87` (guard runs only if `IS_PRODUCTION`), `:104-115` (database and Redis guard), `:204-206` (database defaults), `:31-33` (`.env` loaded with `override=False`, so process environment wins).
  - Grep: `DJANGO_ENVIRONMENT` is referenced only in `docs/v1/`, never in deploy scripts, systemd or supervisor files, or nginx configs.
  - `git ls-files` lists `.env`, `backend/.env_dgft`, `frontend/.env`, `frontend/.env.production` as tracked. Contents not read.
- **Business impact:** If the production process starts without the variable, the committed key signs sessions and JWTs, the guard is silently skipped, and cookie and HSTS flags stay off. Anyone with repository access could forge tokens. If any tracked env file holds live credentials, they are in git history and must be treated as exposed. The DGFT names suggest session and CSRF tokens.
- **Remediation:**
  1. Make the production guard fail closed: treat `DEBUG=False` with non-local `ALLOWED_HOSTS` as production unless development is explicitly declared. Alternatively, default to production and require an explicit development opt-in.
  2. Set `DJANGO_ENVIRONMENT` in the deploy unit or supervisor definition, versioned in the repository.
  3. Add `python manage.py check --deploy` with production-like variables to the deploy gate.
  4. Owner and security review: confirm by variable name whether the production process has `DJANGO_ENVIRONMENT`. If the committed key was ever live, rotate `DJANGO_SECRET_KEY` and invalidate sessions.
  5. Inventory the tracked env files with a secret scanner, recording file names and rule IDs only. Rotate any credential found and purge history only under an owner decision. Keep templates as `*.example`.
- **Acceptance criteria:** A test shows that starting with `DEBUG=False`, a non-local host and no `DJANGO_ENVIRONMENT` fails with a clear error. The deploy aborts if `check --deploy` fails. The scanner reports no live values in tracked env files.
- **Runtime measurement:** On the production host, read-only, without printing values: `tr '\0' '\n' < /proc/<gunicorn-pid>/environ | cut -d= -f1 | grep -c '^DJANGO_ENVIRONMENT$'` (expect 1). A secret scanner run on the repository, recording file names and rule IDs only.

### ISS-067: nginx configuration drift, a public media alias, and header inheritance

- **Severity:** High (conditional on the HTTP-only configuration being live). **Confidence:** Medium (configuration read; live configuration not observed). **Label:** MEASURED (configuration text). Header effect THEORETICAL.
- **Evidence:**
  - `nginx-http-only.conf:24-29`: public `location /media/` alias to `backend/media`, `expires 7d`, `Cache-Control: public`. The file has no `/protected-media/` location (MEASURED by grep).
  - `nginx-license-manager.conf:63-71`: media contains customs documents and PII and is served only through the authenticated view and an internal location. `nginx-protected-media.conf:1-4` describes replacing the public block.
  - Header inheritance: server-level `add_header` at `nginx-license-manager.conf:113-117` sets X-Frame-Options, nosniff, XSS protection, Referrer-Policy, and HSTS. The locations `/static/` (`:60`), `/assets/` (`:97`), and `= /index.html` (`:104`) define their own `add_header`, which replaces the inherited set in nginx. The SPA entry document and its assets would therefore lack those headers (THEORETICAL until observed).
  - Drift: `labdhi.duckdns.org` appears with IP `139.59.92.226` (`nginx-labdhi.conf:7`) and IP `64.227.129.26` (`nginx-http-only.conf:3`). The MDS vhost uses a placeholder host (`nginx-mds.conf:18,33`).
- **Business impact:** If the HTTP-only vhost is live on a public address, BOE PDFs, licence copies, and transfer letters can be downloaded without authentication by path. The missing headers weaken clickjacking and MIME-sniffing protection on the application entry document.
- **Remediation:** Retire or label the HTTP-only and placeholder configurations as non-production. Keep one template per host, with a shared snippet for security headers applied in every location with `add_header ... always;` or `more_set_headers`. Add `server_tokens off`. Add a repository check that no location aliases `backend/media`.
- **Acceptance criteria:** `nginx -T` on each live host matches the template. A request for a known media path without authentication returns 401, 403, or 404, verified by the owner with a non-sensitive test object. Security headers are present on `/`, `/index.html`, one `/assets/` file, and one `/static/` file.
- **Runtime measurement:** On each live host, `nginx -T | grep -n 'location /media/'` (expect no match). For headers, `curl -sI https://<host>/index.html` run by the owner or QA. Not run here.

### ISS-068: Deployment process is unsafe by default and not reproducible from the repository

- **Severity:** High. **Confidence:** High (static). **Label:** MEASURED (script content and repository contents). Incident impact THEORETICAL.
- **Evidence:**
  - `scripts/deployment/auto-deploy.sh:259,274` (`StrictHostKeyChecking=no` in SSH and SCP helpers).
  - `:394` (`git clean -fd`), `:439` (`git reset --hard origin/$BRANCH`). `:426-436` keeps local-only commits on a backup branch, which is the correct mitigation.
  - `:471-478` (automatic `migrate`; on a permission error, `sudo -u postgres psql … REASSIGN OWNED BY postgres TO ${DB_USER}`, then retry). No `pg_dump` in the deploy path.
  - `:380-382` refers to `backend/gunicorn.conf.py`, which does not exist in the repository. `:721-745` manages a supervisor program `license-manager` that is not defined in the repository.
  - Two Celery definitions disagree: `scripts/deployment/license-manager-celery.conf` (user `django`, `/home/django/license-manager`, `--beat`) and `backend/deploy/celery.service` (user `www-data`, `/srv/lmanagement`, no `--beat`).
  - `backend/setup/supervisord.conf` belongs to another application (`dgftglobalexim`, port 8086, bound to `0.0.0.0`).
  - `run_django.sh:75` starts `--settings=config.settings`, a module that does not exist (`backend/config` is absent; `backend/manage.py:10` defaults to `lmanagement.settings`). `run_django.sh:33` kills any listener on the port with `kill -9`.
  - `.github/workflows/ci.yml:104-111` runs `makemigrations --check` and tests. There is no deploy-check and no deploy job.
- **Business impact:** A deploy can migrate production without a restore point, discard server-side working-tree changes, and trust a spoofed host. Two Celery units with `--beat` on one host would run periodic tasks twice (THEORETICAL). Rebuilding the environment from the repository alone is not possible because the Gunicorn and supervisor definitions are not versioned.
- **Remediation:**
  1. Pin host keys in `known_hosts` and remove `StrictHostKeyChecking=no`.
  2. Take a `pg_dump -Fc` and verify it before `migrate`. Record its checksum and stop if it fails.
  3. Replace the `REASSIGN OWNED` fallback with explicit grants that the owner reviews.
  4. Version the Gunicorn configuration and the `license-manager` supervisor program in the repository.
  5. Keep one Celery unit definition. Enforce a single beat process per environment.
  6. Fix or retire `run_django.sh`.
  7. Add a CI job that runs `manage.py check --deploy` with placeholder production variables and no secrets.
- **Acceptance criteria:** The deploy aborts when a host key does not match. Every deploy produces a verified dump before `migrate` (tested on staging). A staging build from repository files alone reproduces the Gunicorn and supervisor configuration with no diff. Exactly one beat process runs per environment.
- **Runtime measurement:** On staging, read-only: `pgrep -fc 'celery.* beat'` (expect 1 per environment). Check the deploy workstation's `known_hosts` for the target host. The owner runs a dump-and-restore drill.

### ISS-069: No observability, log rotation, or backup retention; production dumps accumulate unpruned

- **Severity:** High (backup retention and recovery). **Confidence:** High (absence). **Label:** MEASURED (absence of configuration, directory size and file count). Recovery effectiveness THEORETICAL.
- **Evidence:**
  - No `LOGGING` dictionary (section 5.1). No error-tracking, metrics, or tracing SDK (section 5.2). The `rqworker` Sentry flag is dead code.
  - Watchdog: `scripts/deployment/license-manager-watchdog.sh:1-12` (10-minute check; restarts; reboot), `:214-217` (`systemctl restart postgresql`), `:229` (`pkill -9` on Gunicorn), `:53` (`/etc/cron.d` install target). Alert channel is SMTP email.
  - `scripts/database/db-tools.sh:198,226,342` (remote `pg_dump`), `:395` (local restore), `:432` (remote `rm -rf` on media, context not fully reviewed).
  - `backups/`: 121 dumps, about 1.0 GB, dated 2026-08-13 to 2026-10-31, gitignored at `.gitignore:52`. No pruning logic. `backup-and-recovery.md` records no production backup or restore evidence.
- **Business impact:** Dumps containing customs and financial data accumulate on a developer workstation with no retention rule and no evidenced encryption. Production recovery has no evidenced restore path. The only alert channel is email from the watchdog. A watchdog-initiated PostgreSQL restart or `pkill -9` can interrupt long exports and migrations.
- **Remediation:**
  1. Owner decision: retention period for dumps and where they may live. Automate pruning. Encrypt dumps at rest. Store a copy off the workstation.
  2. Run a restore drill into an isolated database from the latest dump, comparing row counts and checksums. Record the result.
  3. Add a Django `LOGGING` configuration with structured output and a redaction filter. Add logrotate for supervisor logs.
  4. Owner decision: choose one error-tracking or metrics channel. Connect it before relying on it.
  5. Remove or quarantine the unused `rqworker` command.
  6. For the watchdog: refuse to restart PostgreSQL while migrations or long jobs run, and use a graceful stop before any `kill`.
  7. Review the `db-tools.sh:432` remote `rm -rf` and restrict it to an explicit confirmation.
- **Acceptance criteria:** A restore drill into an isolated database succeeds, with recorded row-count and checksum comparison. The `backups/` directory stays within the approved budget. Logs rotate. A test exception produces an alert in the chosen channel. The watchdog does not kill a Gunicorn worker before the graceful timeout.
- **Runtime measurement:** On the workstation, read-only: `du -sh backups` and `ls backups | wc -l`. On each host: `ls -la /var/log/license-manager-watchdog.log` and the supervisor log sizes. The owner runs the restore drill in an isolated environment.

## 8. Candidate product and owner questions

These are for the final report, not for the owner directly from this agent.

1. **Data governance (backup):** How long should local production dumps be kept, and where may they be stored? Impact: 1.0 GB of customs and financial data is kept with no retention rule.
2. **Operations (live hosts):** Which nginx configurations are live for `labdhi.duckdns.org` (`139.59.92.226` or `64.227.129.26`), and is the HTTP-only public `/media/` alias serving traffic?
3. **Data governance (package files):** What retention period applies to generated ledger package files? Code defaults to 7 days (`ledger.py:229`) and no setting overrides it.
4. **Operations (export limits):** What maximum licence count and export size are acceptable for synchronous exports before they must run as background jobs?

## 9. Limits

- No runtime probe, server access, or production inspection was performed. Every deployment-state statement about production is UNVERIFIED unless labelled MEASURED from repository content.
- The Gunicorn and supervisor definitions for this application, the watchdog env file, and the backend `.env` were not available for reading and were not read.
- Env-named files tracked by git were identified by name only. Their contents, and therefore whether they hold live credentials, were not read.
- `auto-deploy.sh` (38 KB) was reviewed by targeted line ranges and grep, not read in full. Some steps are summarised from section markers.
- `docs/v1/07-quality-and-operations/*.md` and existing `performance-baseline.md` were read or referenced and were not modified.
