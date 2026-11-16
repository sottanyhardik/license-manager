---
name: django-backend
description: Project router for Django 6 / DRF / Celery work in the License Manager backend — applies the project's backend rules and points to the matching ECC skills (django-patterns, django-security, django-tdd, django-celery, django-verification, api-design) instead of duplicating them. Use when implementing or reviewing backend code in an ERP task.
metadata:
  origin: project
---

# django-backend

1. **Purpose** — one entry point that binds ECC Django knowledge to this repo's conventions.
2. **Invocation criteria** — edits in `backend/**`, `master-data-service/**`, `mds-client/**`.
3. **Required context** — `.claude/rules/backend.md` (conventions + gates), `.claude/rules/business-rules.md`
   for domain apps, index greps for blast radius, the task's decision refs.
4. **Workflow** — load the ECC skill matching the work: models/ORM/DRF → `django-patterns`;
   auth/permissions/settings → `django-security`; tests → `django-tdd` + `python-testing`;
   tasks/beat → `django-celery`; endpoints → `api-design` (contracts are frozen unless approved, OD-07 is
   additive `/api/v1/`); pre-hand-off → `django-verification` (targeted subset). Python 3.14, Decimal for money.
5. **Restrictions** — no new dependencies (OD-09 governs); no response-shape/permission changes without
   approval; migrations go through `safe-migrations`; local DB only.
6. **Acceptance criteria** — targeted tests pass with the task's `TEST_DB_NAME`; `ruff`/`python manage.py check`
   clean on touched files; dependents of changed symbols updated.
7. **Verification commands** — `cd backend && python manage.py check`;
   `TEST_DB_NAME=<db> python -m pytest <paths> -q`; `sh scripts/dev/quality-gate.sh backend` (integrator only).
8. **Documentation references** — `.claude/rules/backend.md`, `.claude/skills/django-*/SKILL.md`,
   `.claude/skills/api-design/SKILL.md`, `docs/04-api.md`, `docs/05-database.md`.
