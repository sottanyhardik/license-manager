# Master-Data Service (MDS)

The central, authoritative service for shared master/reference data (companies,
ports, items, HS codes, SION norms, exchange rates, …). Consuming projects keep
a **local read-mirror** and talk to MDS for **writes** and **delta pulls**.

See the full design: `docs/architecture/ADR-001-master-data-service.md` (main repo).

> **Status: Phase 2 skeleton.** A working vertical slice — `Company`, `Port`,
> `ExchangeRate` — proving the whole API pattern. The remaining 14 masters are
> added mechanically (see "Adding a master" below). It lives as a subdirectory
> for now and is extractable to its own repo.

## What the API gives every master

Base URL `/api/v1/`. Auth: `Authorization: Bearer <token>` (tokens + scopes in
`MDS_TOKENS`; `write` may mutate, `read` is read-only).

| Endpoint | Purpose |
|---|---|
| `GET /companies/` | list (cursor-paginated) |
| `GET /companies/?updated_since=<iso8601>` | **delta pull** (the sync driver) |
| `GET /companies/` + `If-None-Match` | `304` when nothing changed (ETag) |
| `GET /companies/_meta/` | `{max_modified, count, etag}` high-water mark |
| `POST /companies/bulk_upsert/` | upsert a list by natural key (hydration/consolidation) |
| `GET /changes/?since=<iso8601>` | change feed incl. **deletes** |
| `GET /healthz` | liveness probe |

## Run locally

```bash
cd master-data-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-test.txt
cp .env.example .env          # set MDS_DB_* + MDS_TOKENS
createdb master_data          # + a 'master_data' role
python manage.py migrate
python manage.py runserver 8100
pytest                        # contract tests (needs Postgres)
```

## Adding a master (the pattern)

1. `models.py` — subclass `MasterModel`, set `NATURAL_KEY_FIELD` to its unique
   business key.
2. `serializers.py` — a `ModelSerializer`.
3. `views.py` — subclass `MasterViewSet` (set `queryset`, `serializer_class`,
   `natural_key_field`).
4. `urls.py` — `router.register(...)`.
5. `signals.py` — add the model to `TRACKED_MODELS` (change-feed).
6. `admin.py` — register (optional).
7. `makemigrations` + a test in `masters/tests/`.

## Not yet wired (later phases)

- Media → shared MinIO/S3 via `django-storages` (Decision 5). Media fields are
  object-key strings for now so the service boots without external infra.
- Webhook push to consumers (polling is the backstop).
- The `mds-client` package consumers install (Phase 4).
