# mds-client

A thin, pip-installable **Django app** that lets a consuming project talk to the
central **Master-Data Service (MDS)** — the single write authority for the 17
master/reference models (see `docs/architecture/ADR-001-master-data-service.md`,
Decision 3). This is **Phase 4** of that ADR.

It gives a consumer three things:

1. **Write path** — push masters to MDS over REST (`write_master` / `bulk_upsert`).
2. **Local read-only mirror** — kept fresh by delta pulls (`updated_since` +
   ETag) and the change feed (for deletes), advancing a per-model cursor.
3. **Graceful degradation** — reads always work from the local mirror (they never
   touch MDS); writes fail **loudly** with a clear message (never silently
   dropped) when MDS is unreachable.

## Install

```bash
pip install mds-client
# optionally, for the scheduled sync task:
pip install "mds-client[celery]"
```

Requires Django >= 6 and `requests`.

## Wire it up in a consuming project

**1. Add the app and configure settings:**

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "mds_client",
]

MDS_BASE_URL = "https://masters.internal.example.com/api/v1/"
MDS_TOKEN = env("MDS_TOKEN")  # service-to-service bearer token (write- or read-scoped)

# model_label -> how to reach it on MDS + which LOCAL mirror model to upsert into.
# The complete 17-master mapping ships in the package — adopt it wholesale:
from mds_client import DEFAULT_MDS_MODELS
MDS_MODELS = DEFAULT_MDS_MODELS

# ...or define/trim your own. Each entry looks like:
#   "core.CompanyModel": {
#       "endpoint": "companies",              # MDS URL segment
#       "natural_key": "iec",                 # shared natural key
#       "mirror_model": "core.CompanyModel",  # local Django model to upsert into
#       "mds_model_label": "masters.Company", # label MDS stamps on its change feed
#   }
#
# NOTE: the 7 keyless masters (KEYLESS_MODEL_LABELS) sync on a synthetic `uid`
# UUID — their local mirror model must carry a matching `uid` column first
# (added during mirror hydration, ADR Phase 5). Sync the business-keyed masters
# until then.

# optional tuning
MDS_TIMEOUT = (3.05, 30)     # (connect, read) seconds
MDS_MAX_RETRIES = 3          # transient-failure retries for idempotent GETs
MDS_BACKOFF_FACTOR = 0.5     # exponential backoff base
```

**2. Migrate** — creates the one bookkeeping table, `MDSSyncState`:

```bash
python manage.py migrate mds_client
```

**3. Refresh the mirror.** Manually / from cron:

```bash
python manage.py mds_sync                       # all configured models
python manage.py mds_sync --model core.CompanyModel
```

Or on a schedule with Celery beat (the 5-minute polling backstop from the ADR):

```python
# celery beat schedule
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    "mds-mirror-refresh": {
        "task": "mds_client.sync_masters",
        "schedule": crontab(minute="*/5"),
    },
}
```

You can also call `mds_client.tasks.sync_masters.delay()` from the MDS webhook
nudge for near-real-time refresh.

**4. Route master writes through MDS** (admin/API save hooks call this instead
of writing the mirror directly):

```python
from mds_client.sync import write_master
from mds_client.client import MDSUnavailable

try:
    write_master("core.CompanyModel", {"iec": "1234567890", "name": "Acme", "address": "..."})
except MDSUnavailable as exc:
    # Reads still work from the mirror; surface this to the user and let them retry.
    raise ValidationError(str(exc))
```

## API surface

`mds_client.client.MDSClient`:

| Method | MDS endpoint | Returns |
|---|---|---|
| `get_meta(model)` | `GET /<ep>/_meta/` | `{max_modified, count, etag}` |
| `fetch_delta(model, since=None, etag=None)` | `GET /<ep>/?updated_since=` (+ `If-None-Match`) | one `DeltaPage` (handles 304) |
| `iter_delta(model, since, etag)` | walks cursor pages | generator of rows |
| `bulk_upsert(model, rows)` | `POST /<ep>/bulk_upsert/` | `{created, updated}` |
| `get_changes(since=None)` | `GET /changes/?since=` | list of change dicts (incl. deletes) |

`mds_client.sync`:

- `sync_model(label)` / `sync_all()` — refresh the mirror, apply deletes, advance the cursor.
- `write_master(label, row)` — write one master; raises `MDSUnavailable` on outage.

Errors: `MDSUnavailable` (connection/timeout — degrade), `MDSHTTPError`
(non-2xx from MDS), both subclasses of `MDSError`.

## Degradation contract

- **Reads** — always available from the local mirror (possibly stale up to the
  polling interval; seconds with webhook nudge). Never touch MDS.
- **Writes** — require MDS. On outage they raise `MDSUnavailable` with a clear,
  user-facing message and are **never silently dropped**. A `TODO(outbox)` hook
  in `sync.write_master` marks where an optional Celery outbox would enqueue for
  eventual-consistency retry (ADR-001 open question #2).

## Development / tests

No live MDS and no real DB server needed — the suite mocks HTTP with stdlib
`unittest.mock` and runs against in-memory SQLite:

```bash
python runtests.py            # Django test runner
# or, if pytest + pytest-django are installed:
pytest
```

Coverage: delta pagination, ETag/304 short-circuit, `bulk_upsert`, change-feed
delete application, cursor advance, and `MDSUnavailable` on connection error.
