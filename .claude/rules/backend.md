# Rule — Backend (Django 6 + DRF)

Scope: `backend/apps/**`. Settings: `lmanagement.settings`. Deep dive: `docs/02-architecture.md`,
`docs/04-api.md`, `docs/guides/FILTER_BACKENDS_GUIDE.md`, `docs/guides/API_PAGINATION_GUIDE.md`.

## App boundaries

`accounts core license bill_of_entry allotment trade tasks`. Feature code lives in the owning
app's `models.py / serializers / views / urls.py`. **Shared base classes live in `apps/core/`.**
Apps may depend on `core`; `core` must not depend on feature apps.

## Must

- **Extend `MasterViewSet`** (`apps/core/views/master_view.py:69`) for CRUD endpoints — you get
  filtering/search/ordering, inline PATCH on single fields, bulk CSV/Excel export, structured
  paginated responses, and `AuditModel` auto-population. Don't reimplement these on a bare
  `ModelViewSet`.
- **Inherit `AuditModel`** (`apps/core/models.py:40`) on new models so `created_on/modified_on/
  created_by/modified_by` populate from the thread-local user.
- **Validate in serializers**, not views. Raise DRF exceptions for error paths.
- **Permissions** are explicit per ViewSet (role-based). Never ship an endpoint with no
  permission class. See `.claude/rules/security.md`.
- **Materialised balances**: license/allotment/BOE balances are maintained by signals, not
  computed on read. When you change anything that affects a balance, update via the existing
  signal/recalc path — don't hand-edit a balance field.
- **`frozen` BOE rows** are locked after ledger upload — respect the flag; never mutate frozen rows.
- **Heavy work → Celery** (`lmanagement` app). Ledger uploads return task IDs the client polls.

## Avoid

- N+1 queries — use `select_related` / `prefetch_related` (see `.claude/rules/database.md`).
- Business logic in views when it belongs on the model/service.
- Bypassing `ActivityLogMiddleware` or the auth/permission stack.

Template: `.claude/templates/viewset.md`. Example: `.claude/examples/README.md`.
