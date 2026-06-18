# Rule — Database (PostgreSQL + psycopg 3)

Scope: models, migrations, queries. Deep dives: `docs/05-database.md`,
`docs/architecture/MATERIALIZED_VIEWS_GUIDE.md`, `docs/architecture/REDIS_CACHING_GUIDE.md`,
`docs/operations/PURCHASE_STATUS_FK_MIGRATION.md`.

## Must

- **Migrations are mandatory and reviewed.** After model changes:
  `python manage.py makemigrations` → inspect the generated migration → `migrate`. Never edit
  applied migrations; add a new one. Keep migrations forward-only and data-safe.
- **Sub-table pattern**: extensible per-license metadata is split into one-to-one sub-tables
  (`LicenseBalance`, `LicenseFlags`, `LicenseOwnership`, `LicenseNotes` — see
  `backend/apps/license/models.py:1715`) instead of widening the main table. Follow this when
  adding a new concern to an entity.
- **Materialised fields** (balances) are updated by signals — index them; don't compute on read.
- **Indexes**: add composite indexes for common filter/order combinations (the DB-optimization
  work added several). Check existing indexes before adding duplicates.
- **Nullability** is deliberate — match the column's real semantics; don't make everything null.

## Avoid

- N+1: always `select_related` (FK) / `prefetch_related` (reverse/M2M) for list endpoints.
- Raw SQL unless the ORM genuinely can't express it; if used, parameterize (never string-format).
- Large data migrations in the request path — use a management command or Celery.

## Tools

Repo scripts for DB ops: `db-tools.sh`, `audit-db-integrity.sh`, `deploy-indexes.sh`,
`sync-masters.sh` (one-way master sync canonical → followers). Read before running.
