# Master-Data Service (MDS) sync — enabling & status

This backend can consume the central **Master-Data Service** (ADR-001) as a
centralized master DB. It keeps a **local read-only mirror** of the 17 master
models fresh over REST, so existing ForeignKeys, `select_related`, joins, and
reports keep working unchanged. See
`docs/architecture/ADR-001-master-data-service.md` for the full design.

Everything below is **additive and OFF by default**. With MDS disabled, or with
the optional `mds_client` package not installed, the backend boots and behaves
exactly as before.

## Enabling

MDS is controlled by environment variables read in `lmanagement/settings.py`:

| Env var        | Default | Meaning                                            |
|----------------|---------|----------------------------------------------------|
| `MDS_ENABLED`  | `False` | Master switch. Must be `true` to activate anything.|
| `MDS_BASE_URL` | `""`    | Base URL of the MDS API (e.g. `https://masters.internal`). |
| `MDS_TOKEN`    | `""`    | Service-to-service bearer token for MDS.           |

When `MDS_ENABLED=true` **and** `mds_client` is importable, settings registers
the `mds_client` app and adopts `DEFAULT_MDS_MODELS` (the full 17-master map) as
`MDS_MODELS`. If the package is missing, settings self-disables (`MDS_ENABLED`
falls back to `False`) rather than crashing.

Install the client (in the environment that runs the app + Celery worker/beat):

```bash
pip install -e ../mds-client   # module: mds_client
python manage.py migrate        # creates mds_client_mdssyncstate
```

## Periodic sync (Celery beat)

`lmanagement/celery.py` registers a beat entry **only when `MDS_ENABLED`**:

```
mds-sync-masters-every-5-min → task "mds_client.sync_masters", crontab(minute="*/5")
```

This is the ADR-001 "polling backstop" — every 5 minutes it pulls deltas
(ETag / `updated_since`) for each configured master and upserts them into the
local mirror by natural key. Nothing is scheduled when MDS is disabled.

Requires a running Celery **beat** scheduler and **worker**, e.g.:

```bash
celery -A lmanagement worker -l info
celery -A lmanagement beat   -l info
```

### No Celery beat? Cron-friendly wrapper

The same work is exposed as a management command, safe to run from cron:

```bash
# every 5 minutes, only meaningful when MDS_ENABLED=true
*/5 * * * * cd /path/to/backend && ../.venv/bin/python manage.py mds_sync
```

`mds_client.sync_masters` (the Celery task) simply calls `mds_client.sync.sync_all()`,
which is exactly what `manage.py mds_sync` runs — so beat and cron are
interchangeable. Both degrade gracefully if the client isn't installed.

## Status endpoint

```
GET /api/mds/status/
```

Read-only. Permission: `UserManagementPermission` (admin `USER_MANAGER` role;
superusers always allowed) — it exposes operational/config detail, so it is not
open to general users.

Response contract:

```json
{
  "enabled": true,
  "base_url": "https://masters.internal",
  "models": [
    {"model_label": "core.CompanyModel", "last_synced_at": "2026-07-03T10:15:00+00:00", "count": 1234}
  ],
  "healthy": true
}
```

- `enabled` — `settings.MDS_ENABLED`.
- `base_url` — `settings.MDS_BASE_URL` (empty string if unset).
- `models` — one row per configured master:
  - `model_label` — key into `settings.MDS_MODELS`.
  - `last_synced_at` — from `MDSSyncState.last_synced_at` (ISO-8601, or `null` if never synced).
  - `count` — live row count of the local mirror model.
- `healthy` — `true` only when MDS is enabled, at least one model is configured,
  and **every** configured model synced within ~15 minutes; `false` when disabled.

When MDS is disabled or `mds_client` is not installed, the endpoint returns
`{"enabled": false, "base_url": "", "models": [], "healthy": false}`.
