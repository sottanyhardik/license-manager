# Infrastructure & Configuration

> **Source of truth** — generated from implementation.  
> Last updated: 2026-07-15 (feature/V1).

---

## 1. Django Settings Hierarchy

```
config/settings/
├── base.py     — all common settings (INSTALLED_APPS, REST_FRAMEWORK, Celery, Redis, CORS)
├── dev.py      — base + DEBUG=True, ALLOWED_HOSTS=["*"], EMAIL=console
├── prod.py     — base + security headers, SECURE_PROXY_SSL_HEADER, no DEBUG
├── test.py     — base + in-memory-compatible, CELERY_TASK_ALWAYS_EAGER=True
└── local.py    — dev + SQLite + managed=False patch for local development without PostgreSQL
```

**Selection**: `DJANGO_SETTINGS_MODULE` env var. Default in `celery.py`: `config.settings.dev` (set explicitly in production via systemd/supervisor).

---

## 2. Redis DB Isolation

```
Redis /1 → Django cache (CACHES["default"])
Redis /2 → Celery broker (CELERY_BROKER_URL)
Redis /3 → Celery result backend (CELERY_RESULT_BACKEND)
```

**Why isolation matters**: A `cache.clear()` or Redis FLUSHDB in one layer must not affect another. Before this fix, all three shared `/2` — a cache flush could evict in-flight Celery task messages.

**Base URL**: `REDIS_URL` env var (default: `redis://localhost:6379`). Any trailing `/N` suffix is stripped and the DB number appended explicitly.

---

## 3. Celery Configuration

| Setting | Value | Reason |
|---|---|---|
| `CELERY_BROKER_URL` | `{REDIS_URL}/2` | Isolated from cache |
| `CELERY_RESULT_BACKEND` | `{REDIS_URL}/3` | Isolated from broker |
| `CELERY_ACCEPT_CONTENT` | `["json"]` | Prevents pickle deserialization attacks |
| `CELERY_TASK_SERIALIZER` | `"json"` | Serialization standard |
| `CELERY_RESULT_SERIALIZER` | `"json"` | Serialization standard |
| `CELERY_TIMEZONE` | `TIME_ZONE` (Asia/Kolkata) | Consistent scheduling |

**Task reliability pattern**: All financial tasks use `acks_late=True, reject_on_worker_lost=True`. This means:
- The broker message is ACKed only **after** the task completes (not when picked up)
- If the worker crashes, the message is re-queued automatically

---

## 4. REST Framework & Pagination

**Default pagination class**: `shared.pagination.StandardPagination`  
**Page size**: 25 items

**Paginated response envelope**:
```json
{
  "success": true,
  "data": [...],
  "pagination": {
    "count": 100,
    "next": "http://...?page=2",
    "previous": null,
    "page": 1,
    "page_size": 25,
    "total_pages": 4
  }
}
```

**Non-paginated success envelope**:
```json
{"success": true, "data": {...}, "message": null}
```

**Error envelope**:
```json
{
  "success": false,
  "data": null,
  "errors": [{"field": "username", "message": "This field is required."}],
  "message": "Validation failed"
}
```

---

## 5. Global Exception Handler

**File**: `backend/shared/exceptions.py`  
**Setting**: `REST_FRAMEWORK["EXCEPTION_HANDLER"] = "shared.exceptions.custom_exception_handler"`

| HTTP Status | Trigger |
|---|---|
| 400 Bad Request | ValidationError, ParseError |
| 401 Unauthorized | AuthenticationFailed, NotAuthenticated |
| 403 Forbidden | PermissionDenied |
| 404 Not Found | NotFound, Http404 |
| 405 Method Not Allowed | MethodNotAllowed |
| 500 Internal Server Error | Unhandled exception |

All responses use the standard envelope format.

---

## 6. CORS

- `CORS_ALLOWED_ORIGINS`: comma-separated list from env var
- Dev: typically `http://localhost:5173,http://127.0.0.1:5173`
- Production: `https://{domain}` configured per server

---

## 7. Media Files — Protected Download Pattern

**Nginx config** (all 3 servers):
```nginx
location /protected-media/ {
    internal;
    alias /home/django/license-manager/legacy/backend/media/;
}
```

Django views set `X-Accel-Redirect: /protected-media/{path}` header. Nginx intercepts this and serves the file directly without Django involvement. The `internal` directive prevents direct browser access to `/protected-media/`.

---

## 8. API Endpoints Map

| Prefix | Backend | Port |
|---|---|---|
| `/api/v1/*` | New Django app (`backend/`) | 8001 |
| `/api/*` | Legacy Django app (`legacy/backend/`) | 8000 |
| `/admin/*` | Legacy Django admin | 8000 |
| `/` | React SPA (new frontend or legacy) | Static files |

### System endpoints (new backend)

| Method | URL | Description |
|---|---|---|
| GET | `/api/health/` | `{"status": "ok", "version": "1.0.0"}` |
| GET | `/api/schema/` | OpenAPI 3 schema (YAML) |
| GET | `/api/docs/` | Swagger UI (drf-spectacular) |
| GET/POST/... | `/admin/` | Django admin (proxied to port 8000) |

---

## 9. Nginx Configuration

All 3 production servers (`nginx-labdhi.conf`, `nginx-license-manager.conf`, `nginx-license-tractor.conf`) follow the same pattern:

```nginx
upstream backendv1 {
    server 127.0.0.1:8001;
    keepalive 32;
}

# New backend — /api/v1/ routes first
location /api/v1/ {
    proxy_pass http://backendv1;
    proxy_set_header Host $host;
    proxy_read_timeout 120s;
    proxy_connect_timeout 10s;
}

# Legacy backend — all other /api/ routes
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**Security headers applied** (post-UX review):
```nginx
add_header Content-Security-Policy "default-src 'self'; ..." always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
```

**Slow Loris mitigation**: `client_header_timeout 30s` (reduced from dangerous 300s).

---

## 10. Docker Development Environment

**File**: `docker-compose.yml`  
**Services**:

| Service | Image | Ports | Purpose |
|---|---|---|---|
| `postgres` | postgres:16 | internal only | Database |
| `redis` | redis:7 | `127.0.0.1:6379` | Cache/broker/results |
| `backend` | custom Dockerfile.dev | `8001` | New Django app |
| `celery` | same as backend | — | Worker process |
| `frontend` | node:20 | `5173` | Vite dev server |
| `mailpit` | axllent/mailpit | `8025` | Email testing UI |

**Health checks**: postgres and redis have health checks; celery depends on both with `condition: service_healthy`.

**Resource limits**: backend `1g` memory, celery `512m` memory.

---

## 11. CI/CD — GitHub Actions

| Workflow | Triggers | Jobs |
|---|---|---|
| `backend-ci.yml` | Push/PR to main/develop/feature/** | lint (ruff), typecheck (mypy if available), test (pytest), check (manage.py check) |
| `frontend-ci.yml` | Push/PR to main/develop/feature/** | lint (eslint), typecheck (tsc --noEmit), build (vite build) |
| `ci.yml` | Same | Orchestrates both |

**Action pinning**: All `uses: actions/...` are pinned to full commit SHAs (supply chain security).

**Caching**: uv cache for Python deps, npm cache for Node deps.

---

## 12. Pre-commit Hooks

**File**: `.pre-commit-config.yaml`  
**Hooks**: ruff (lint+fix), black (format), prettier (frontend format), detect-secrets

---

## 13. gunicorn Configuration

**File**: `backend/deploy/gunicorn.conf.py`

| Setting | Value |
|---|---|
| `bind` | `0.0.0.0:8001` |
| `workers` | `multiprocessing.cpu_count() * 2 + 1` |
| `worker_class` | `sync` |
| `timeout` | 120 seconds |
| `max_requests` | 1000 (auto-restart to prevent memory leaks) |
| `max_requests_jitter` | 100 (random jitter to prevent thundering herd) |

---

## 14. Production Security Settings (`prod.py`)

```python
DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # nginx → gunicorn
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

> `SECURE_PROXY_SSL_HEADER` is required because nginx terminates SSL and proxies as HTTP internally. Without this, Django would infinitely redirect HTTP → HTTPS.
