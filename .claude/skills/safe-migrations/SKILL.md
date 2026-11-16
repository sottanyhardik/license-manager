---
name: safe-migrations
description: Project rules for Django migrations in the License Manager — local-only, reversible, one migrating task per app, no open-decision schema changes — layered on the ECC database-migrations and postgres-patterns skills. Use whenever a task creates or edits a migration, index, constraint or data backfill.
metadata:
  origin: project
---

# safe-migrations

1. **Purpose** — schema changes that can be applied, reversed and integrated without conflicts or data loss.
2. **Invocation criteria** — any `migrations/*.py`, `Meta.indexes/constraints`, FK `on_delete`, backfill code.
3. **Required context** — ECC `database-migrations` (expand/contract, batched backfills, concurrent indexes),
   `postgres-patterns`; `.claude/state/decisions-snapshot.md` (OD-16, OD-19, OD-20 are OPEN);
   `orch.py status` (who else is migrating which app).
4. **Workflow** — (a) one migrating task per Django app per round (queue ownership of `apps/<app>/migrations/`);
   (b) `makemigrations <app> --check --dry-run`; (c) create; (d) on a local throwaway DB: migrate forward,
   back to previous, forward again; (e) large tables → `AddIndexConcurrently` with `atomic = False`,
   batched data migrations, explicit reverse functions; (f) record evidence in the hand-off.
5. **Restrictions** — local DB only (`DB_HOST` localhost/127.0.0.1; guard hook enforces); never edit an
   applied migration; no DROP/TRUNCATE/RunSQL deletes; no `flush`/`reset_db`; irreversible or data-destroying
   migrations need owner approval; never against production or a production snapshot.
6. **Acceptance criteria** — forward/backward evidence; no conflicting `00NN_` numbers at integration
   (`makemigrations --check` clean after integrating); tests for new constraints.
7. **Verification commands** — `cd backend && python manage.py makemigrations --check --dry-run`;
   `python manage.py showmigrations <app>`; `TEST_DB_NAME=<db> python -m pytest <tests> -q`.
8. **Documentation references** — `.claude/skills/database-migrations/SKILL.md`,
   `.claude/skills/postgres-patterns/SKILL.md`, `.claude/agents/erp-database.md`, `docs/05-database.md`.
