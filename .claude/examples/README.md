# Examples — Good Implementations to Model

Pointers to real, exemplary code in this repo. **Don't copy blindly** — read the file, then
mirror its shape. Verify line numbers (`file:line`) before relying on them; code moves.

## Frontend

| Pattern | Where | Why it's a good model |
|---|---|---|
| Single configured axios instance | `frontend/src/api/axios.js` | Request interceptor attaches JWT (`:17`); response interceptor does GET-dedup + 401 silent-refresh queue + 403/5xx handling (`:81`). Every API call should route through this — don't reimplement. |
| Resource service modules | `frontend/src/services/api/{licenseApi,allotmentApi,boeApi,masterApi}.js` | Thin, typed-ish resource wrappers over the axios instance. Model new `services/` modules on these (`.claude/templates/service.md`). |
| UI primitive reuse | `frontend/src/components/ui/*` (button, card, dialog, select…) | Radix-backed shadcn primitives. Compose these instead of hand-rolling modals/selects. |

## Backend

| Pattern | Where | Why it's a good model |
|---|---|---|
| ViewSet base class | `backend/apps/core/views/master_view.py:69` (`MasterViewSet`) | Filtering/search/ordering + inline PATCH + bulk export + audit population. Extend it; don't start from bare `ModelViewSet`. |
| ViewSet subclass in practice | `backend/apps/license/views_incentive.py` | Concrete `MasterViewSet` subclass — shows queryset/serializer/permission/filter wiring. |
| Audit base model | `backend/apps/core/models.py:40` (`AuditModel`) | All models inherit this for created/modified tracking. |
| Sub-table pattern | `backend/apps/license/models.py` — `LicenseNotes` (`:1694`), `LicenseFlags` (`:1739`), `LicenseOwnership` (`:1765`), `LicenseBalance` (`:1715`) | One-to-one extension tables keep the main model lean. Follow this for new per-entity metadata instead of widening the table. |

## How to add an example here

When you introduce a new reference-worthy pattern (`CLAUDE.md` §11): add a row above with the
`file:line`, a one-line "why," and — if it's a brand-new convention — a matching rule in
`.claude/rules/` and a template in `.claude/templates/`.
