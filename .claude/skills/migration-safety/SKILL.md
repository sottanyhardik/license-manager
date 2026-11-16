---
name: migration-safety
description: Safety checklist for Django schema/data migrations on historical licence data. Use before writing, reviewing or running any migration.
metadata:
  origin: project
---
Generic: ECC `database-migrations`. Design: `database-architect`; review: `database-reviewer` + `django-reviewer`.

1. One concern per migration; `python manage.py makemigrations --check --dry-run` must be clean (CI gate).
2. Additive first: new columns nullable/defaulted → backfill (batched `RunPython`, with `reverse_code`) → enforce constraint in a later migration.
3. No drops/renames of columns/tables used by APIs, reports or ledger SQL without explicit approval (`SCHEMA CHANGE`).
4. Large-table indexes: `AddIndexConcurrently` + `atomic = False`.
5. Data migrations touching CIF/balance/allotment/BOE/invoice data → domain auditor + human approval; must be audited/reversible or explicitly flagged irreversible.
6. `migrate` requires user approval each time (settings `ask`) and only against the local dev/test DB — never a remote DB (hook-blocked).
7. Test: migrate forward and backward on a fresh local test DB; run the area tests.
