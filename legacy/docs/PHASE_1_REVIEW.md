# Phase 1 — Codebase Review

**Scope:** Django + DRF backend (~60K LOC, 7 apps) + React/Vite frontend (~32K LOC) deployed to 3 production servers.
**Status:** Read-only analysis. No code changes made.
**Date:** 2026-05-27.

---

## 0. Executive Summary

The system is a coherent license/import-export compliance app with a clear domain core. Architecture is sound at the top level (clean app boundaries, services emerging, materialized views + Redis already in place), but **execution is inconsistent** — half-finished refactors, dead Django templates from a previous server-rendered era, signal cascades that recompute too much on every write, oversized view files (2,900+ LOC), and one immediately exploitable security exposure in the deploy script.

Three observations to anchor decisions:

1. **Most "duplication" is half-finished refactoring**, not parallel implementations. The previous engineer started consolidation (`MODULARIZATION_MASTER_PLAN.md`, `BALANCE_CALCULATION_CONSOLIDATION.md`) and stopped mid-flight. Old artifacts (`item_report.py` + `item_report_refactored.py`, `calculation.py` + `calculate_balance.py`) remain.
2. **The license app is the architectural hub**, with 82 cross-app imports + 6 cross-app signal receivers. Any restructure must protect license signals — they are the data-integrity guarantee.
3. **Frontend is in better shape than backend.** No TypeScript drift, no dead-version files, one strong axios layer. The chief frontend smell is four parallel ways to fetch (`useApiCall`/`useApiRequest`/`useFetch`/raw axios) and 50 `console.log`s.

---

## 1. Architecture Review

### Backend (Django + DRF)

- **`lmanagement/`** — project (settings, urls, wsgi). Single `settings.py`, no dev/prod split.
- **`accounts/`** — custom `User` (`accounts.User` is `AUTH_USER_MODEL`), JWT + session auth, RBAC permission classes (12 roles, documented in `RBAC_DOCUMENTATION.md`).
- **`core/`** — shared layer. `AuditModel` base, 23 master-data models, materialized views, caching, middleware, throttling, pagination, 24 management commands. **Acting as both leaf and hub.**
- **`license/`** — domain core. 14 models (~1,581 LOC), most business logic, `services/` partially adopted (5 files), 8 management commands. **Largest, most coupled, most fragile.**
- **`allotment/`**, **`bill_of_entry/`**, **`trade/`** — surrounding domain apps. Each owns its CRUD + a few cross-app integrations.
- **`tasks/`** — isolated to-do list. Coupling to `core.AuditModel` only.

**Three view-organization styles in the same project:** single `views.py` (accounts, trade, tasks), `views/` folder (bill_of_entry, core), sibling `views_*.py` files (allotment, license). Pick one — recommendation in §10.

**Settings** (`backend/lmanagement/settings.py`):
- Postgres + Redis + Celery configured
- DRF: `StandardPagination` (25/page), custom throttling (`BurstRateThrottle`, 180/min), `DjangoFilterBackend`
- JWT: 4-hour access, 7-day rotating refresh + blacklist
- Custom middleware: `DisableCSRFForAPIMiddleware`, `ActivityLogMiddleware`
- `AUTH_USER_MODEL = "accounts.User"` — locks the accounts app in place

### Frontend (React 19 + Vite)

- **`api/axios.js`** — single transport. Token refresh queue, 401 retry, in-flight GET dedup, exponential backoff on 5xx. Strong.
- **`context/AuthContext.jsx`** — auth state, idle timeout (30 min), proactive refresh 5 min before expiry. Strong.
- **`routes/ProtectedRoute.jsx`** — `requiredRole` / `requiredAnyRole` / `requireSuperuser` gating.
- **`App.jsx`** (340 LOC) — all routes inline. Should be extracted to `routes.jsx`.
- **`hooks/`** — 16 hooks. 4 of them overlap on data fetching (see §3).
- **`pages/`** + **`components/`** — flat organization. With 24 pages + 40 components, feature folders are overdue.
- **State management:** Context API only. No Redux/Zustand. No React Query / SWR — every page refetches on mount.
- **Build:** Vite with explicit `manualChunks` for vendors, reports, ledger, masters — good. Bootstrap 5 for UI (no MUI/Tailwind).
- **Forms:** Zod present; mixed `useForm` (custom) + `useFormState` (unexported) usage.

---

## 2. Dependency Map

### Cross-app import counts (Python imports only)

| Importer | Imports from | Note |
|---|---|---|
| **license** | allotment, bill_of_entry, core, accounts | 82 imports — **hub** |
| **bill_of_entry** | accounts, allotment, core, license | 18 imports |
| **allotment** | accounts, bill_of_entry, core, license | 23 imports |
| **trade** | accounts, bill_of_entry, core, license | 4 imports |
| **tasks** | core | 1 import |
| **accounts** | core | 2 imports |
| **core** | (none — proper leaf) | clean |

### String-target FKs (lazy bindings the import graph misses)

- 10 `license` → `"core.X"` ForeignKeys (Company, Port, ItemName, SionNormClass, HSCode, …) — expected, low risk.
- 1 `license` → `"bill_of_entry.BillOfEntryModel"` (`LicenseInvoice.bills_of_entry`, `license/models.py:~1534`) — **renaming bill_of_entry breaks LicenseInvoice migrations.**

### Signal coupling (THE refactor risk)

`backend/license/signals.py` registers 6 cross-app receivers (lines 332–379):

| Signal | Sender (string ref) | Receiver | Effect |
|---|---|---|---|
| post_save / post_delete | `allotment.AllotmentItems` | `update_license_on_allotment_item_change` | Recompute license balance_cif |
| post_save / post_delete | `bill_of_entry.RowDetails` | `update_license_on_boe_item_change` | Recompute license balance_cif |
| post_save / post_delete | `trade.LicenseTradeLine` | `update_license_on_trade_line_change` | Recompute license balance_cif |

**Critical risk:** Senders are referenced by *string*, so renaming a model fails silently (no ImportError; signal just stops firing). Data corruption ensues.

`allotment/signals.py` separately calls `core.scripts.calculate_balance.update_balance_values()` — a second balance-update pathway parallel to the license signals. Need to confirm they don't both run on the same write.

### `AppConfig.ready()` side effects

- `license.apps` imports `license.signals` → registers 6 cross-app receivers. **If allotment, bill_of_entry, or trade are removed/renamed, Django startup is fine but signals silently die.**
- `core.apps` imports `cache_signals`.
- `allotment.apps` imports `allotment.signals`.

### URL ownership (no conflicts — clean)

| Prefix | Owner | Endpoint count |
|---|---|---|
| `/api/auth/` | accounts | 14 |
| `/api/licenses/` + sub-paths | license | 38 |
| `/api/allotments/`, `/api/allotment-actions/` | allotment | 7 |
| `/api/bill-of-entries/` | bill_of_entry | 8 |
| `/api/trades/`, `/api/lines/`, `/api/payments/` | trade | 10 |
| `/api/tasks/` | tasks | 6 |
| `/api/masters/` | core | 17+ |

URL routes are mounted with no namespace, but DRF router prefixes prevent collisions. Adding `app_name` + `namespace=` is recommended (easy, low risk).

---

## 3. Duplication Analysis

### Confirmed dead/duplicate files (grep-verified — no Python importers)

| File | Status | Action |
|---|---|---|
| `backend/license/views/item_report.py` | Not imported in any `.py`; only referenced in templates | Verify template usage; delete if templates dead |
| `backend/license/item_report_refactored.py` | Not imported anywhere | Delete after confirming above |
| `backend/core/scripts/calculation.py` | Likely superseded by `calculate_balance.py` | Verify; delete |
| `backend/core/scripts/new_ledger.py` | Stub alongside `ledger.py` | Verify; delete |

### Half-finished consolidation

Per `BALANCE_CALCULATION_CONSOLIDATION.md`, `LicenseBalanceCalculator` is meant to be the single source of truth, but three balance paths still exist:

1. `license/services/balance_calculator.py` (the "official" one)
2. `core/scripts/calculate_balance.py` (called from `allotment/signals.py`)
3. `license/signals.py:_update_all_import_items_available_value` (direct ORM updates)

This is the highest-priority technical debt because it's also a data-integrity risk.

### Duplicate utilities

- **Frontend:** `useApiCall`, `useApiRequest`, `useFetch`, plus raw axios — 4 fetch patterns. Two of them (`useApiRequest`, `useFormState`) aren't even exported from `hooks/index.js` (comment in file says they're "available but not exported yet").
- **Frontend:** Role constants in `utils/roleConstants.js` AND inlined in `App.jsx`.
- **Backend:** `license/helper.py` standalone, while `core/utils/` is the canonical home.

### Frontend modal sizing (not duplicates, but unmaintainable)

- `LicenseBalanceModal.jsx` — 1,082 LOC
- `TaskDrawer.jsx` — 806 LOC
- `AllotmentFormModal.jsx` — 605 LOC
- `AdvancedFilter.jsx` — 549 LOC
- `TransferLetterForm.jsx` — 530 LOC

These need to be split, but each is a single feature — not duplication.

### Backend view files (similar)

- `license/views/license.py` — 2,931 LOC
- `license/views/ledger.py` — 2,918 LOC (6 separate PDF generators, ~150 LOC each, duplicated table logic)
- `license/views/item_pivot_report.py` — 1,187 LOC

Ledger.py's 6 PDF generators are the clearest internal duplication — they all build the same table differently.

---

## 4. Dead Code Analysis

### Backend

- **`backend/allotment/templates/`, `backend/bill_of_entry/templates/`, `backend/license/templates/`** — Django server-rendered templates from a pre-React era. Loaded by `app_tags.py` templatetag. **Likely never rendered in production** (React handles all UI), but Django may still try to load them.
- **`backend/allotment/templatetags/app_tags.py:3`** — broken import: `from license.models import AllotmentItems` (AllotmentItems is in `allotment.models`). Either dead templates (likely) or silently failing renders.
- **`backend/allotment/forms.py`** — Django forms (`TlForm`) used by `bill_of_entry/views/parse_pdf.py`. Likely the only live form.
- **`backend/extracted_files/`** — empty directory.
- **`backend/src/`** — orphan CSS file in a Python backend.
- **`backend/test_balance_calc.py`, `backend/test_crud_balance_updates.py`** — tests at app root, not under `tests/`. Should be moved.
- **`backend/DFIA_COPY/`** — 210 PDFs, 443MB. Belongs in object storage.
- **`backend/data_script/fetch_ownership.py`** — used by `update_license_ownership.py` mgmt command; should live under `license/` not at backend root.

### Frontend

- **`frontend/src/tests/`** — Jest config present, no jest installed. `CLEANUP_ANALYSIS.md` already documents this. Dead infra.
- **`hooks/useFormState.js`, `hooks/useApiRequest.js`** — not exported, intentionally hidden per `hooks/index.js` comment.
- **50 `console.log`** statements in src.

### Repo root (already audited)

- **16 stale markdown one-shot notes** ready to delete (`ADD_ORDERING_TO_MODELS.md`, `BUGFIX_THROTTLING.md`, all `PURCHASE_STATUS_*` except `_FK_MIGRATION`, `*_COMPLETED.md`, `*_FINAL_STATUS.md`, `SERVER_165.232.185.220_*.md`, `VERIFICATION_REPORT.md`, etc.)
- **3 obsolete nginx temp configs** (`nginx-http-only.conf`, `nginx-http-only-tractor.conf`, `nginx-http-temp.conf`).
- **2 one-off fix scripts** (`fix-and-redeploy.sh`, `quick-fix-tokens.sh`).
- **`check_user_roles.py`** at root — should be a Django management command.
- **`Command db`** (file with no extension at root) — investigate or delete.

---

## 5. Frontend ↔ Backend Coupling Analysis

### Endpoint inventory (~120 routes total)

- **License (38)** — by far the largest, due to many report exports + actions + items + ledger sub-paths.
- **Core/masters (17+)** — lookups.
- **Auth (14)**, **trade (10)**, **bill_of_entry (8)**, **allotment (7)**, **tasks (6)**.

### Frontend → backend match

- ✅ **No broken frontend calls.** Every axios call resolves to a defined backend route.
- ⚠ **Dead backend endpoints (no frontend caller):**
  - `POST /api/auth/password-reset-confirm/` — incomplete 2FA path?
  - `POST /api/lines/`, `POST /api/payments/` — Trade form sends nested, never hits these.
  - `GET /api/masters/hs-codes/`, `GET /api/masters/head-norms/` — reference-data lookups; check if backend-internal only.

### Refactor targets (multiple frontend callers of same endpoint)

| Endpoint | Callers | Recommendation |
|---|---|---|
| `/api/masters/companies/` | TransferLetterForm (×2), AllotmentFormModal, TradeForm | Build `useMasterSelect("companies")` once |
| `/api/licenses/` | Dashboard, ListLicenses, AllotmentAction, TradeForm | Centralize with query hooks + cache |
| `/api/auth/users/available-roles/` | Profile, Settings | Cache in AuthContext |
| `/api/tasks/assignable-users/` | Task modal, Sidebar widget | Memoize |

### URL drift

- **No trailing-slash drift** — Django + DRF defaults are respected throughout.
- **No centralized endpoint registry** — URLs are duplicated as string literals across ~40 files. Refactor target.

### Form submission shape

| Resource | Pattern | Risk |
|---|---|---|
| License | Single POST with nested `items: [{}]`; separate PATCH for item edits | Partial-fail risk: header saved, items fail → orphan |
| Allotment | POST + separate `allocate-items` action | Two-phase, no rollback |
| BOE | POST + N action endpoints for piecemeal updates | Diffuse |
| Trade | Single POST with nested `lines` + `payments` | Cleanest |
| Tasks | POST + state-action endpoints (`/complete`, `/reject`, `/reopen`) | Cleanest |

Recommendation: standardize on single-call nested writes inside `transaction.atomic()`. Trade is the model to follow.

### Long-running endpoints (sync today, should be async)

| Endpoint | Time | Current | Fix |
|---|---|---|---|
| `POST /api/upload-ledger/` | 5–30s+ | **Already async via Celery** (`?async=true`) | Keep |
| `GET /api/trades/<id>/generate-bill-of-supply/` | 3–5s | Sync | Celery + signed URL |
| `GET /api/trades/<id>/generate-purchase-invoice/` | 3–5s | Sync | Celery + signed URL |
| `GET /api/reports/*` (5 endpoints) | 5–15s | Sync | Celery + signed URL |
| `GET /api/allotment-actions/<id>/generate-pdf/` | 2–5s | Sync | Celery + signed URL |
| `GET /api/licenses/<id>/merged-documents/` | 3–5s | Sync | Celery + signed URL |

### Files / management commands hitting our own API

- `backend/license/management/commands/update_license_ownership.py` → `POST /api/license-actions/bulk-update-license-transfer/`. **In-process Django calling its own HTTP API is wasteful.** Refactor to call the service directly. (The "highlighted file" question from earlier — this is the takeaway.)

---

## 6. Risk Register

Severity: **H** = ship-stoppers / data-corruption / security, **M** = production scaling issues, **L** = quality of life.

| # | Sev | Category | Location | Issue | Fix |
|---|---|---|---|---|---|
| 1 | **H** | Security | `auto-deploy.sh:30–34` | Hardcoded password `"admin"` + sshpass for 3 prod servers, in git | Move to SSH keys; rotate password immediately |
| 2 | **H** | Security | `backend/core/views/throttle_status.py:217` | `ThrottleHealthView.permission_classes = []` — public, leaks throttle config | Gate to authenticated/staff |
| 3 | **H** | Data integrity | `backend/license/signals.py:42–158` | `_update_all_import_items_available_value` recomputes all items on every license touch; silent failure on `compute_condition_pools` exceptions (lines 99–100) | Wrap in `transaction.on_commit`; log failures to Sentry; defer to Celery |
| 4 | **H** | Data integrity | `backend/license/signals.py:332–379` | Cross-app signals use string sender refs; rename of any sender model = silent data corruption | Switch to direct imports; add integration test verifying handlers are wired |
| 5 | **H** | External API safety | `backend/core/management/commands/sync_from_ge_server.py:268` | `# TODO: Implement actual GE server API calls` — stub in production | Validate or remove. If keeping, add schema validation on upstream responses |
| 6 | **H** | Deployment | `auto-deploy.sh` (all) | Sequential deploy across 3 servers, no health check between, no rollback. Failed mid-way = split-state cluster | Add health check; rollback function; consider parallel deploy + CI gate |
| 7 | **M** | Data integrity | `backend/bill_of_entry/models.py:42–58` | `company`, `port` use `on_delete=CASCADE` to high-value FKs | Switch to `PROTECT` or `SET_NULL`; add soft-delete |
| 8 | **M** | Performance | `backend/license/serializers.py:157–187` | N+1 in `LicenseImportItemSerializer.get_items_detail()` — for 50 import items × 5 items each = 250 SELECTs per response | Move to view-level prefetch_related |
| 9 | **M** | Performance | `backend/license/serializers.py:617–624` | `.filter().exists()` for booleans, 2× per object in list views | Annotate booleans via `Case/When` on queryset |
| 10 | **M** | Performance | `backend/license/views/license.py:494, 1970` | Sync PDF/Excel export, 3–5s, blocks worker thread | Celery + signed-URL pattern |
| 11 | **M** | Performance | `backend/allotment/views.py`, `bill_of_entry/views/boe.py` | Dynamic viewset creation (`MasterViewSet.create_viewset`) doesn't enforce `select_related`/`prefetch_related` | Add explicit prefetch overrides |
| 12 | **M** | Auth | `backend/accounts/permissions.py:13` | `is_superuser` bypasses all role checks | Make role check explicit even for superusers |
| 13 | **M** | Maintainability | `backend/license/views/license.py` (2,931 LOC), `ledger.py` (2,918), `item_pivot_report.py` (1,187), `models.py` (1,581), `serializers.py` (1,467) | Files too large to reason about safely | Split per-resource; extract PDF builders to `core/exporters/` |
| 14 | **M** | Caching | `backend/core/cache_utils.py:40–64` | MD5 cache key combines args + kwargs in a way that can collide (`(123, cond='AU')` vs `(cond='AU', 123)`) | Switch to deterministic serialization (sorted kwargs) |
| 15 | **L** | Quality | 176 `print()` calls in backend, 50 `console.log` in frontend | Log noise in production | Replace with `logging.info`; add lint rules |
| 16 | **L** | Quality | 36 migrations in `core`, 33 in `license` | Schema churn | Squash after major versions; require docstring on every `RunPython` |
| 17 | **L** | Coupling | `backend/license/management/commands/update_license_ownership.py` | Calls own API over HTTP in-process | Refactor to call service directly |
| 18 | **L** | Dead code | `backend/allotment/templatetags/app_tags.py:3` | `from license.models import AllotmentItems` (wrong app) — only fires if template renders | Delete templatetag + Django templates if React handles UI everywhere |

---

## 7. Performance Bottlenecks (concrete)

Ranked by likely production impact:

1. **License-list serializer N+1** (`serializers.py:157-187, 590, 617–624`) — every list view of licenses fans out hundreds of queries. The materialized view + cache layer hides this for the dashboard but not for everything else.
2. **Signal cascade on bulk writes** (`license/signals.py:42–110`) — saving 1 trade with a 50-item license fires balance recalc that hits ~5 UPDATEs + 3 SUM queries; importing 100 BOE rows = 800+ queries. Bulk-import serializer uses `suspend_license_flag_recalc()` context — good — but direct `model.save()` calls outside the serializer skip the guard.
3. **PDF/Excel generation in request thread** — listed in §5. Each blocks a worker for 3–5s.
4. **Materialized view refresh on Celery beat (15 min)** — fine in steady state, but no on-write invalidation. Stale data window for the dashboard up to 15 min.
5. **Cache thundering herd** — global cache keys + many users → after TTL expiry all refetch at once. Mitigate with stale-while-revalidate or jitter.

---

## 8. Technical Debt — Quantified

| Metric | Count |
|---|---|
| Total Python LOC (excluding migrations) | ~60,889 |
| Total JS/JSX LOC | ~32,146 |
| Markdown files at repo root | 43 (19 useful, 24 stale/duplicate) |
| Shell scripts at root | 22 (≈ 18 useful, 4 obsolete) |
| Backend `print()` statements | 176 |
| Frontend `console.log` statements | 50 |
| Files > 800 LOC (backend) | 5 (license views/models/serializers) |
| Backend files at root that shouldn't be | 5 (`check_user_roles.py`, two `test_*.py`, etc.) |
| Migrations: core | 36 |
| Migrations: license | 33 |
| Half-finished refactors (e.g. `*_refactored.py`) | 2 confirmed |
| Backend mgmt commands | ~40 (24 in `core`, ~half belong in `license`) |
| Public unauthenticated endpoints | 1 (ThrottleHealthView) |
| TODO/FIXME comments | 6 (1 critical: GE server sync stub) |

---

## 9. Frontend / Backend Coupling Summary

- **API surface:** 120 backend routes, ~85 actively consumed by the React app. The remainder are reference lookups or internal admin endpoints.
- **No URL contract mismatches.** No broken frontend calls.
- **Largest contract risk:** changes to the nested License/Allotment/Trade write payloads would cascade through several form components. Backend changes to those should be versioned (`/api/v2/`) or shipped together with frontend.
- **Async story is half-done.** Ledger upload is Celery-backed; everything else (PDF/Excel) is sync. Standardizing this would yield the biggest UX win.
- **No global query cache** on the frontend. Adding TanStack Query alone would eliminate dozens of duplicate fetches per page load.

---

## 10. Recommended Target Architecture

### Backend — `apps/` layout

```
backend/
├── lmanagement/
│   ├── settings/             # base.py, dev.py, prod.py, test.py
│   ├── urls.py               # namespaced includes
│   ├── wsgi.py / asgi.py
│   └── celery.py
├── apps/
│   ├── accounts/
│   ├── core/                 # AuditModel, masters, cache, throttling, pagination
│   ├── license/              # the domain hub
│   ├── allotment/
│   ├── bill_of_entry/
│   ├── trade/
│   └── tasks/
├── shared/                   # cross-cutting, no Django models
│   ├── pdf/                  # ReportLab/Weasy builders, num_to_words_indian, styles
│   ├── decimal_utils.py
│   ├── date_utils.py
│   └── validation.py
├── tests/                    # ALL tests, mirroring apps/ structure
│   ├── conftest.py
│   ├── accounts/ license/ allotment/ ...
├── tasks/                    # Celery task modules (renamed from app to avoid clash)
├── deploy/                   # supervisord, nginx, deploy scripts
├── scripts/                  # ad-hoc Python tools (NOT management commands)
└── manage.py
```

Each app standardized to:
```
apps/<app>/
├── models/              # split if file > 400 LOC
├── serializers/
├── views/               # one file per resource (license.py, transfer.py, …)
├── services/            # required — views call services, services call ORM
├── selectors/           # read-side queries (optional but clarifies CQS)
├── permissions.py
├── signals.py
├── urls.py
├── admin.py
└── management/commands/
```

**Key rules:**
- Views never query the ORM directly; views call `services/`.
- Signals are minimal: dispatch a Celery task, don't compute in-process.
- Cross-app coupling goes through `core` or via Celery tasks, never via direct model imports where avoidable.
- 12 domain-specific management commands move from `core/` to their owning app (sync_licenses → `license/`, etc.).

### Frontend — feature-based layout

```
frontend/src/
├── app/
│   ├── App.jsx
│   ├── main.jsx
│   └── routes.jsx               # extracted from App.jsx
├── shared/
│   ├── api/                     # axios instance + queryClient
│   │   ├── client.js
│   │   ├── endpoints.js         # single source of URL truth
│   │   └── queryClient.js       # TanStack Query
│   ├── auth/                    # AuthContext, ProtectedRoute, roleConstants
│   ├── ui/                      # design system (Button, Card, Table, Modal, …)
│   ├── hooks/                   # cross-feature only (useDebounce, useModal, useFileUpload)
│   ├── utils/                   # formatters, formErrors, dateFormatter, numberFormatter
│   └── constants.js
├── features/
│   ├── license/
│   │   ├── api.js               # endpoint definitions
│   │   ├── queries.js           # useLicenseList, useLicense, useLicenseSave (TanStack Query)
│   │   ├── pages/               # LicenseList, LicenseForm, LicenseDetail
│   │   ├── components/          # LicenseBalanceModal split into 3-4 sub-components
│   │   └── index.js
│   ├── allotment/
│   ├── bill_of_entry/
│   ├── trade/
│   ├── reports/                 # 9 report pages
│   ├── masters/
│   ├── admin/
│   └── tasks/
└── pages/                       # only top-level shell pages (Login, NotFound, Dashboard)
```

**Key rules:**
- One way to fetch: TanStack Query hooks wrapping `axios.js`. Delete `useApiCall`, `useApiRequest`, `useFetch`.
- All URLs live in `shared/api/endpoints.js`. No string URLs in components.
- Role constants from `shared/auth/roleConstants.js` only — delete the App.jsx inlining.
- One feature folder per backend app (mostly).
- Modals over 500 LOC are split into composable parts within the feature folder.

### Caching / async strategy

- **Server-state cache (frontend):** TanStack Query (5-min staleTime by default; per-query tuning).
- **API response cache (backend):** existing Redis layer kept; add stale-while-revalidate to reduce thundering herd.
- **Materialized views:** keep, but add on-write invalidation for hot views in addition to 15-min beat refresh.
- **Long-running work:** every PDF/Excel endpoint → Celery + signed URL. Standardize a `JobStatus` model + `/api/jobs/<id>/` polling endpoint.

---

## 11. Phase 2 Preview (next deliverable)

Phase 2 will produce, building on this review:

1. **Concrete folder-move spec** for backend and frontend, mapping every current file to its target path.
2. **API contract diff** — endpoints to keep, deprecate, rename, version.
3. **Signal redesign** — move balance recalc out of synchronous signals into Celery tasks with idempotency keys.
4. **Service-layer template** — example refactor of one viewset (`trade`, smallest) showing the new pattern.
5. **Database safety review** — confirm every move is migration-free or migration-safe.
6. **Updated risk register** — for each change, severity + rollback.

Phase 2 is design only — still no code changes. We block on your approval before Phase 3 (migration plan) and Phase 4 (execution).

---

## 12. Critical issues that should be fixed *before* the modernization

Independent of the broader refactor, these three should be patched on the current codebase ASAP:

1. **Rotate the `"admin"` password and remove from `auto-deploy.sh`** — replace with SSH key auth.
2. **Gate `ThrottleHealthView`** to authenticated/staff users.
3. **Verify `backend/allotment/templatetags/app_tags.py:3` and the Django templates** — if dead, delete templatetag + templates folder; if live, fix the import.

These are ~30 minutes of work and reduce risk before any structural change.
