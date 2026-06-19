# ⚙️ Backend Role

**Purpose:** Django 6 + DRF feature work that stays inside app boundaries, reuses
`apps/core/` base classes, and preserves materialised-balance integrity.

## Routing

| Concern | File |
|---|---|
| Backend do/avoid rules | `rules/backend.md` |
| Database / migrations / queries | `rules/database.md`, `context/database.md` |
| Endpoint shape / client contract | `context/api.md` |
| Permissions / auth boundary | `rules/security.md`, `graph/security.md` |
| ViewSet scaffold | `templates/viewset.md` |
| Service scaffold | `templates/service.md` |

## Mandate
- Apps: `accounts core license bill_of_entry allotment trade tasks`. Feature code lives in
  the owning app; shared bases in `apps/core/` (apps may depend on `core`, not vice versa).
- Extend `MasterViewSet` (`apps/core/views/master_view.py:69`) for CRUD — don't reimplement
  filtering/search/ordering/export/pagination on a bare `ModelViewSet`.
- Inherit `AuditModel` (`apps/core/models.py:40`) on new models.
- Validate in serializers, not views; raise DRF exceptions for error paths.
- Every endpoint declares an explicit role-based permission class.
- Balances are maintained by signals — update via the signal/recalc path, never hand-edit
  a balance field. Respect `frozen` BOE rows; never mutate them.
- Heavy work → Celery (`lmanagement`); long jobs return task IDs the client polls.

## Checklist
- [ ] Code in the owning app; shared logic in `core`
- [ ] `MasterViewSet` + `AuditModel` reused where applicable
- [ ] Permission class present and role-correct
- [ ] No N+1 — `select_related` / `prefetch_related` on list endpoints
- [ ] Model change → migration generated, inspected, applied
- [ ] Balance/frozen invariants preserved

## Exit criteria
Migrations clean; permissions enforced; `./run-tests.sh` green for touched areas
(regression test added for any bug fix — see `rules/testing.md`).
