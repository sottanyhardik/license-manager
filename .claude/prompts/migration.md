# Prompt — Database Migration / Schema Change

Copy, fill the blanks, and run. Read `.claude/rules/database.md` + `.claude/context/database.md` first.

---

**Change**: <new field / table / FK / index / data backfill>
**Models affected**: <app.Model>
**Reason**: <why — link issue/decision>

Process:
1. Decide placement: new per-entity metadata → **sub-table** (one-to-one), not a wider table.
2. Edit the model; inherit `AuditModel` for new models.
3. `python manage.py makemigrations` → **inspect the generated file** (operations, defaults,
   nullability, reversibility). Never edit an already-applied migration; add a new one.
4. Data migration? Keep it out of the request path — management command or Celery. Make it
   idempotent and reversible where possible.
5. Index any new column used in filters/ordering or any materialised balance field.
6. `migrate` locally; add/adjust tests (`@pytest.mark.database`).

Domain guards:
- Don't change how materialised balances are computed without updating the signal/recalc path.
- Master-data tables sync one-way from the canonical server — coordinate before altering them
  (`docs/operations/PURCHASE_STATUS_FK_MIGRATION.md` is a worked example).

Definition of done:
- [ ] Migration is forward-safe and reviewed; reversible or documented if not.
- [ ] `pytest` green incl. a test exercising the change.
- [ ] `docs/05-database.md` / `backend/schema.*` updated if schema shape changed.
- [ ] `.claude/checklists/{pr,security}.md` passed.
