# Context — Database

Orientation only. Authoritative: `docs/05-database.md` (+ `backend/schema.json`,
`backend/schema.png`).

## Shape

- PostgreSQL via psycopg 3, Django ORM.
- Every model inherits `AuditModel` (`backend/apps/core/models.py:40`):
  `created_on / modified_on / created_by / modified_by`, auto-populated from the request user.
- **One-to-one sub-table pattern** keeps the wide `LicenseDetailsModel` lean — related concerns
  live in `LicenseBalance`, `LicenseFlags`, `LicenseOwnership`, `LicenseNotes`
  (`backend/apps/license/models.py:1715` and nearby).
- **Materialised balances**: balance columns are kept current by signals, indexed for fast
  reads, never computed on read.
- Core relationships (see ER diagram in `docs/02-architecture.md` / `docs/05-database.md`):
  License → import/export items → BOE `RowDetails` debits and `AllotmentItems` reservations;
  Allotment/BOE → Company + Port; Trade → DFIA/incentive lines + payments.

## Working with it

- Schema changes: `makemigrations` → inspect → `migrate`. Never edit applied migrations.
- Follow the sub-table pattern for new per-entity metadata; don't widen main tables.
- See `.claude/rules/database.md` for the full do/avoid list and the repo DB scripts.

## Reference snapshots in repo

`backend/schema.json` (machine-readable) and `backend/schema.png` (visual) — regenerate rather
than hand-edit if the schema changes.
