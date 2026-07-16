# Master-Data Service (MDS)

The central, authoritative service for shared master/reference data (companies,
ports, items, HS codes, SION norms, exchange rates, …). Consuming projects keep
a **local read-mirror** and talk to MDS for **writes** and **delta pulls**.

See the full design: `docs/architecture/ADR-001-master-data-service.md` (main repo).

> **Status: Phase 2 complete — all 17 masters implemented.** Company, Port,
> ItemHead, ItemGroup, ItemName, HSCode, HeadSIONNorm, SIONNormClass, SIONExport,
> SIONImport, SIONNormNote, SIONNormCondition, ProductDescription, UnitPrice,
> SchemeCode, NotificationNumber, ExchangeRate — all driven by `MASTER_REGISTRY`
> so serializers/viewsets/routes/change-feed/admin are generated from one list.
> Keyless masters use a synthetic `uid` natural key (ADR Decision 6). Media is an
> object-storage key (django-storages wired in a later phase). Lives as a
> subdirectory for now, extractable to its own repo.

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
   business key, or combine `SyntheticKeyMixin` with `MasterModel` for keyless
   child rows that need deterministic `uid` values.
2. Add the model to `MASTER_REGISTRY` with `(model, natural_key_field, endpoint)`.
3. `serializers.py`, `views.py`, `urls.py`, `signals.py`, and `admin.py` consume
   the registry, so no per-master boilerplate is required unless the new model
   needs custom behavior.
4. Run `makemigrations` and add or update contract tests in `masters/tests/`.

## Not yet wired (later phases)

- Media → shared MinIO/S3 via `django-storages` (Decision 5). Media fields are
  object-key strings for now so the service boots without external infra.
- Webhook push to consumers (polling is the backstop).
- The `mds-client` package consumers install (Phase 4).
