# Phase 2 — Target Architecture Design

**Status:** Design only. No code changes in this phase.
**Prerequisite:** `PHASE_1_REVIEW.md` reviewed.
**Audience:** Implementers of Phases 3 + 4.

---

## 0. Design Principles

Every decision below follows these rules. When in doubt, choose the option that scores higher on more rules.

1. **Correctness first** — no silent changes in behaviour. If a refactor moves business logic, the old call site and the new one must be provably equivalent.
2. **Migration over rewrite** — the codebase is large and live. Move and rename in place, don't re-author.
3. **Preserve `app_label`** — never change Django app labels. Migrations + string FK refs + `AUTH_USER_MODEL` all key off it.
4. **One way to do each thing** — pick the canonical pattern (one fetch hook, one service layer, one view-file style) and move toward it.
5. **Make the safe path the easy path** — services with explicit transactions, query hooks with caching, signals that defer to Celery.
6. **Standardise the boundaries, not the internals** — every app gets the same outer shape (models/, services/, views/, serializers/) but the contents stay app-specific.
7. **No premature abstraction** — don't introduce a base class until two concrete implementations exist. The 6 PDF generators in `license/views/ledger.py` qualify; the single `tasks` viewset does not.

---

## 1. Target Backend Layout

### Top-level

```
backend/
├── lmanagement/
│   ├── settings/                  # split for clarity
│   │   ├── __init__.py            # re-exports from base + env-driven override
│   │   ├── base.py                # everything common
│   │   ├── dev.py                 # DEBUG, local DB, no SSL
│   │   ├── prod.py                # locked-down: secure cookies, ALLOWED_HOSTS
│   │   └── test.py                # in-memory DB, signal disabled by default
│   ├── urls.py                    # namespaced includes, see §4
│   ├── wsgi.py
│   ├── asgi.py
│   └── celery.py                  # extracted from current scattered config
├── apps/                          # all Django apps under one parent (preserves app_label)
│   ├── __init__.py
│   ├── accounts/
│   ├── core/
│   ├── license/
│   ├── allotment/
│   ├── bill_of_entry/
│   ├── trade/
│   └── tasks/
├── shared/                        # cross-cutting, NOT a Django app, no models
│   ├── __init__.py
│   ├── pdf/                       # PDFStyleBuilder, num_to_words_indian, page templates
│   │   ├── __init__.py
│   │   ├── builders.py
│   │   ├── styles.py
│   │   └── number_to_words.py
│   ├── decimal_utils.py
│   ├── date_utils.py
│   └── validation.py
├── tests/                         # ALL tests live here, mirroring apps/
│   ├── __init__.py
│   ├── conftest.py
│   ├── accounts/
│   ├── core/
│   ├── license/
│   │   ├── test_balance_calculator.py
│   │   └── test_signals.py
│   ├── allotment/
│   ├── bill_of_entry/
│   ├── trade/
│   ├── tasks/
│   └── integration/               # cross-app API tests
├── async_tasks/                   # Celery task modules (avoid name clash with apps/tasks)
│   ├── __init__.py
│   ├── pdf_generation.py
│   ├── balance_recompute.py
│   └── ledger_parse.py
├── scripts/                       # ad-hoc Python tools (NOT management commands)
│   ├── parse_ledger.py            # existing
│   ├── veg_oil_allocator.py       # existing
│   ├── test_balance_calc.py       # moved from root in Phase 0
│   └── test_crud_balance_updates.py
├── deploy/                        # existing — supervisord, deploy artifacts
├── media/                         # existing
├── staticfiles/                   # existing
├── manage.py
├── requirements.txt
└── pytest.ini
```

**Files that move out of `backend/` root:**

| Current | Target |
|---|---|
| `backend/data_script/fetch_ownership.py` | `backend/apps/license/services/dgft_ownership.py` |
| `backend/data_script/__init__.py` | (deleted) |
| `backend/setup/` | `backend/deploy/setup/` |
| `backend/DFIA_COPY/` | out of repo — to object storage |

### Per-app standard shape

Every app gets the same outer shape. Inside an app, files split when they exceed ~400 LOC.

```
apps/license/
├── __init__.py
├── apps.py                        # AppConfig with explicit label = "license"
├── admin.py
├── urls.py
├── permissions.py
├── signals.py                     # thin — dispatches Celery tasks, no business logic
├── models/                        # split: license.py, transfer.py, purchase.py, incentive.py, document.py
│   ├── __init__.py                # re-exports for backward compat
│   ├── license.py
│   ├── items.py
│   ├── transfer.py
│   ├── purchase.py
│   ├── incentive.py
│   ├── document.py
│   └── base.py                    # any shared mixins/managers
├── serializers/                   # one file per resource
│   ├── __init__.py
│   ├── license.py
│   ├── items.py
│   ├── transfer.py
│   ├── purchase.py
│   └── mixins.py                  # FormDataNestedMixin, SafeDateField
├── views/                         # one file per resource
│   ├── __init__.py
│   ├── license.py                 # CRUD
│   ├── ledger.py                  # ledger views (still big — split internally)
│   ├── reports/                   # 5 report endpoints
│   │   ├── __init__.py
│   │   ├── inventory_balance.py
│   │   ├── expiring.py
│   │   ├── active.py
│   │   ├── item_pivot.py
│   │   └── item_report.py
│   ├── actions.py
│   ├── transfer.py
│   ├── purchase.py
│   └── incentive.py
├── services/                      # business logic — required, not optional
│   ├── __init__.py
│   ├── balance_calculator.py      # existing
│   ├── condition_pool.py          # existing
│   ├── e5_plan.py                 # existing
│   ├── report_service.py          # existing
│   ├── validation_service.py      # existing
│   ├── dgft_ownership.py          # moved from data_script/
│   ├── dgft_sync.py               # extracted from update_license_ownership.py
│   └── ledger_pdf.py              # 6 PDF generators consolidated
├── selectors/                     # OPTIONAL — read-only queries (kept simple — only when worth it)
│   └── __init__.py
├── filters.py                     # existing
├── pagination.py                  # if any app-specific
├── tables.py                      # existing
├── table_columns.py               # existing
└── management/commands/
    ├── sync_licenses.py
    ├── update_balance_cif.py
    ├── update_license_ownership.py   # refactored to call service directly
    ├── update_license_expiry.py
    ├── parse_existing_license_copies.py
    ├── upload_dfia_copies.py
    ├── populate_license_items.py
    ├── delete_licenses_by_exporter.py
    └── update_dgft_descriptions.py   # MOVED from core (domain-specific)
```

The other apps follow the same template, scoped down (e.g. tasks needs only models.py + serializers.py + views.py — no need to split).

### Management command relocation

12 of `core/management/commands/` are domain-specific and move to their owning app:

| Current location | Target |
|---|---|
| `core/management/commands/fetch_detail_bisc.py` | `apps/license/management/commands/fetch_detail_bisc.py` |
| `core/management/commands/fetch_detail_conf.py` | `apps/license/management/commands/fetch_detail_conf.py` |
| `core/management/commands/update_dgft_descriptions.py` | `apps/license/management/commands/update_dgft_descriptions.py` |
| `core/management/commands/update_aluminium_foil_items.py` | `apps/core/management/commands/` (master data) — stays |
| `core/management/commands/update_sugar_items.py` | `apps/core/management/commands/` — stays |
| `core/management/commands/clean_duplicate_rowdetails.py` | `apps/bill_of_entry/management/commands/` |
| `core/management/commands/clean_item_names.py` | `apps/core/management/commands/` — stays |
| `core/management/commands/auto_import_masters.py` | `apps/core/management/commands/` — stays |
| `core/management/commands/diff_masters.py` | `apps/core/management/commands/` — stays |
| `core/management/commands/merge_masters.py` | `apps/core/management/commands/` — stays |
| `core/management/commands/sync_from_ge_server.py` | `apps/license/management/commands/` (GE-server is license-sync) |
| `core/management/commands/convert_license_table.py` | `apps/license/management/commands/` |
| `core/management/commands/convert_docx_to_pdf.py` | `apps/core/management/commands/` — stays (uses templates) |
| `core/management/commands/rebuild_migrations.py` | `apps/core/management/commands/` — stays (infrastructure) |
| `core/management/commands/refresh_materialized_views.py` | `apps/core/management/commands/` — stays |
| `core/management/commands/cache_stats.py` | `apps/core/management/commands/` — stays |
| `core/management/commands/clearcache.py` | `apps/core/management/commands/` — stays |
| `core/management/commands/check_db_structure.py` | `apps/core/management/commands/` — stays |
| `core/management/commands/sync_database_schema.py` | `apps/core/management/commands/` — stays |
| `core/management/commands/validate_db_fields.py` | `apps/core/management/commands/` — stays |
| `core/management/commands/audit_masters.py` | `apps/core/management/commands/` — stays |
| `core/management/commands/report_fetch.py` | `apps/license/management/commands/` (report = license report) |
| `core/management/commands/fetch_exchange_rates.py` | `apps/core/management/commands/` — stays (master data) |
| `core/management/commands/rqworker.py` | DELETE — Celery is used, not RQ (verify first) |

After move: core has 14 infra/master commands; license has 14 domain commands. Cleaner ownership.

### Critical preservation rule: `app_label`

When apps move to `apps/<name>/`, the Python module path changes (`license` → `apps.license`), but the **Django app_label must NOT change**. This is enforced via `apps.py`:

```python
# apps/license/apps.py
from django.apps import AppConfig

class LicenseConfig(AppConfig):
    name = "apps.license"
    label = "license"               # MUST equal the existing app_label
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals  # noqa: F401
```

This preserves:

- All migrations under `apps/license/migrations/` (they reference `app_label = "license"`)
- All string FK targets like `"license.LicenseDetailsModel"`
- `AUTH_USER_MODEL = "accounts.User"` (in settings)
- Content types in the DB
- ALL signal sender strings like `"allotment.AllotmentItems"`

`INSTALLED_APPS` updates from `"license"` to `"apps.license.apps.LicenseConfig"`.

**This is the entire safety story for the move.** Get this wrong and migrations break.

---

## 2. Target Frontend Layout

```
frontend/src/
├── app/
│   ├── App.jsx                    # tiny — just providers + router
│   ├── main.jsx
│   ├── routes.jsx                 # extracted from current App.jsx (340 LOC)
│   └── providers.jsx              # QueryClientProvider + AuthProvider + ToastProvider
├── shared/
│   ├── api/
│   │   ├── client.js              # the existing axios instance, renamed
│   │   ├── endpoints.js           # SINGLE source of URL truth
│   │   └── queryClient.js         # TanStack Query setup
│   ├── auth/
│   │   ├── AuthContext.jsx        # moved from context/
│   │   ├── ProtectedRoute.jsx     # moved from routes/
│   │   ├── roleConstants.js       # SINGLE place — moved from utils/, removed from App.jsx
│   │   └── useAuth.js             # extracted from AuthContext
│   ├── ui/                        # design system primitives
│   │   ├── Button.jsx
│   │   ├── Card.jsx
│   │   ├── StatCard.jsx
│   │   ├── Badge.jsx
│   │   ├── Modal.jsx
│   │   ├── Table.jsx
│   │   ├── DataTable.jsx
│   │   └── ...                    # 14 components from current components/ui/
│   ├── hooks/                     # cross-feature ONLY
│   │   ├── useDebounce.js
│   │   ├── useModal.js
│   │   ├── useConfirmDialog.js
│   │   ├── useFileUpload.js
│   │   ├── usePagination.js
│   │   ├── usePageTitle.js
│   │   ├── useBackButton.js
│   │   └── index.js
│   ├── utils/
│   │   ├── formatters.js          # consolidated from numberFormatter + dateFormatter
│   │   ├── formErrors.js          # existing
│   │   ├── errorUtils.js          # existing
│   │   ├── formValidation.js      # existing
│   │   ├── filterPersistence.js   # existing
│   │   ├── lazyLoad.js            # existing
│   │   ├── pdfPreview.js          # existing
│   │   ├── navigationUtils.js     # existing
│   │   └── ledgerExport.js        # existing
│   └── constants.js               # existing
├── features/
│   ├── license/
│   │   ├── api.js                 # uses shared endpoints.js, exports query keys
│   │   ├── queries.js             # useLicenseList, useLicense, useLicenseSave, useLicenseDelete (TanStack Query)
│   │   ├── pages/
│   │   │   ├── LicenseList.jsx
│   │   │   ├── LicenseForm.jsx
│   │   │   └── LicenseDetail.jsx
│   │   ├── components/
│   │   │   ├── LicenseBalance/    # split from 1082-LOC modal
│   │   │   │   ├── index.jsx                  # composition
│   │   │   │   ├── BalanceHeader.jsx
│   │   │   │   ├── BalanceTable.jsx
│   │   │   │   ├── BalanceFilters.jsx
│   │   │   │   └── BalanceActions.jsx
│   │   │   ├── LicenseFormFields.jsx
│   │   │   └── LicenseStatusBadge.jsx
│   │   ├── hooks.js               # feature-specific only
│   │   └── index.js               # public surface
│   ├── allotment/
│   │   └── ... same shape
│   ├── bill_of_entry/
│   ├── trade/
│   ├── tasks/
│   │   └── components/
│   │       └── TaskDrawer/        # split from 806-LOC drawer
│   ├── reports/                   # 9 report pages, each independent
│   ├── masters/                   # master-data CRUD
│   └── admin/                     # user mgmt, activity log
└── pages/                         # ONLY top-level shell pages
    ├── Login.jsx
    ├── Dashboard.jsx
    ├── NotFound.jsx
    ├── Forbidden.jsx
    └── Unauthorized.jsx
```

**Files that consolidate or get deleted from the frontend:**

| Action | Files |
|---|---|
| DELETE (4 fetch hooks → 1) | `hooks/useApiCall.js`, `hooks/useApiRequest.js`, `hooks/useFetch.js`, raw axios in components |
| DELETE (test infra without runner) | `src/tests/` (until vitest is wired up — see Phase 4 / 5) |
| DELETE (dead) | `hooks/useFormState.js` (not exported, superseded by `useForm`) |
| MOVE | `components/ui/*` → `shared/ui/` |
| MOVE | `context/AuthContext.jsx` → `shared/auth/AuthContext.jsx` |
| MOVE | `routes/ProtectedRoute.jsx` → `shared/auth/ProtectedRoute.jsx` |
| MOVE | `utils/roleConstants.js` → `shared/auth/roleConstants.js` (and remove inline copy in App.jsx) |
| MOVE | `services/api/*` → `features/<feature>/api.js` |
| MOVE | `services/calculators/*` → `features/<feature>/calculators.js` |
| MOVE | per-feature `pages/` and `components/` → `features/<feature>/` |

---

## 3. Signal Redesign — the highest-impact change

### Current behaviour (problem)

`backend/license/signals.py` does heavy work synchronously inside the request:

1. Trade line is saved → `post_save` fires `update_license_on_trade_line_change`
2. Receiver calls `update_license_flags()`
3. `update_license_flags()` calls `_update_all_import_items_available_value()`
4. That recomputes condition pools and `.update()`s every import item on the license
5. Worker thread blocked for tens of milliseconds per write; 50-item license + bulk insert = seconds

Same pattern for allotment changes and BOE row changes. **Three apps' write paths reach into license through this synchronous chain.**

### Target behaviour

```
Trade write
  └─ post_save signal
       └─ enqueue Celery task: recompute_license_flags.delay(license_id, source="trade")
           └─ inside the task: acquire idempotency lock by license_id
                └─ if no lock contention: run balance + flags update
                └─ if locked: drop this task (the locked one will recompute everything)
```

Key properties:

- **Sync request path stays fast.** The signal handler only enqueues.
- **Idempotency via lock.** Multiple writes to the same license coalesce into one recompute. Implemented with a Redis lock keyed on `license:flags:{id}` with a 30 s expiry.
- **Bulk writes work naturally.** The serializer's existing `suspend_license_flag_recalc()` context still applies for the in-process work; the Celery task fires once at the end.
- **Sender strings → direct imports.** `@receiver(post_save, sender="allotment.AllotmentItems")` becomes `@receiver(post_save, sender=AllotmentItems)` (with module-level import). Eliminates the silent-failure rename risk.
- **Feature-flag rollout.** Settings flag `ASYNC_LICENSE_FLAG_RECALC = False` keeps old behaviour. Set to `True` only after the Celery task is validated against a copy of prod data.

### Task contract

```python
# async_tasks/balance_recompute.py
from celery import shared_task
from django.core.cache import cache
from apps.license.services.balance_calculator import LicenseBalanceCalculator

LOCK_TIMEOUT = 30  # seconds

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=5,
)
def recompute_license_flags(self, license_id, source):
    lock_key = f"license:flags:{license_id}"
    if not cache.add(lock_key, "1", LOCK_TIMEOUT):
        # Another task is already running for this license. Drop.
        return {"license_id": license_id, "skipped": True}
    try:
        LicenseBalanceCalculator.recompute_all(license_id, source=source)
    finally:
        cache.delete(lock_key)
    return {"license_id": license_id, "skipped": False, "source": source}
```

### Migration safety

The signal change carries data-integrity risk and ships in three steps:

1. **Add task + tests, leave signals sync.** Task is callable but no signal calls it yet. Run task on a sample of 100 licenses in staging; diff before/after balance values; they must be identical.
2. **Dual-write.** Signal fires both sync recompute AND `delay()` the task. Compare results in logs. Run for 1 week.
3. **Switch flag.** `ASYNC_LICENSE_FLAG_RECALC = True`. Sync path removed in a separate commit.

Rollback at any step: revert to previous step. The dual-write step is the validation gate.

---

## 4. URL Namespacing

All app `urls.py` adopt `app_name` and `lmanagement/urls.py` namespaces every include. This makes `reverse()` calls unambiguous and stops accidental collisions when new endpoints are added.

```python
# apps/license/urls.py
app_name = "license"
urlpatterns = [ ... ]
```

```python
# lmanagement/urls.py
urlpatterns = [
    path("api/auth/",         include("apps.accounts.urls",       namespace="accounts")),
    path("api/licenses/",     include("apps.license.urls",        namespace="license")),
    path("api/allotments/",   include("apps.allotment.urls",      namespace="allotment")),
    path("api/bill-of-entries/", include("apps.bill_of_entry.urls", namespace="bill_of_entry")),
    path("api/trades/",       include("apps.trade.urls",          namespace="trade")),
    path("api/tasks/",        include("apps.tasks.urls",          namespace="tasks")),
    path("api/masters/",      include("apps.core.urls",           namespace="masters")),
    # SPA fallback unchanged
]
```

**Public URL paths do NOT change** — only the internal name resolution. Frontend URLs stay valid.

`reverse("license:license-list")` works after the change. Hardcoded URL strings in code remain valid because the paths themselves don't move.

---

## 5. API Contract — what changes and what doesn't

### Stays the same (no client work)

- Every existing public URL path: `/api/licenses/`, `/api/allotments/`, etc.
- All HTTP methods and request/response shapes.
- Auth flow (login, refresh, logout, me).
- Permission semantics.

### Changes (additive, non-breaking)

| Change | What | Why |
|---|---|---|
| New endpoint | `GET /api/health/` | Pre-deploy health check + monitoring |
| New endpoint | `GET /api/jobs/<task_id>/` | Generic async task status (consolidates ledger-task-status pattern) |
| New endpoint | `POST /api/licenses/<id>/export-pdf-async/` returns `{task_id}` | Async export path; sync stays for back-compat |
| Deprecated (still working) | `POST /api/auth/password-reset-confirm/` if unused after 1 release | Verify dead, remove next major |
| Deprecated (still working) | `POST /api/lines/`, `POST /api/payments/` | Trade form uses nested writes; standalone endpoints unused |
| Internal-only | `GET /api/throttle-health/` is now `IsAdminUser` (fixed in hotfix) | Security |

### Net change for frontend

Frontend doesn't need to change to consume the new structure. The new endpoints are opt-in (async PDF + job status). Migrating the frontend to use them is a Phase 4-or-later UX improvement, not a blocker.

---

## 6. Service Layer Template (concrete example — `trade`)

Trade is the smallest domain app — a good place to demonstrate the pattern. The same shape applies to every other app.

### Before (current)

```python
# trade/views.py
class LicenseTradeViewSet(viewsets.ModelViewSet):
    queryset = LicenseTrade.objects.all()
    serializer_class = LicenseTradeSerializer

    @action(detail=True, methods=["post"])
    def link_trade(self, request, pk=None):
        trade = self.get_object()
        partner_id = request.data.get("partner_id")
        partner = LicenseTrade.objects.get(id=partner_id)
        # business logic inline:
        trade.linked_trade = partner
        partner.linked_trade = trade
        trade.save()
        partner.save()
        # update license balance:
        for line in trade.lines.all():
            line.license.balance_cif -= line.amount  # WRONG, but illustrative
        return Response(...)
```

### After (target)

```python
# apps/trade/services/linking.py
from django.db import transaction
from apps.trade.models import LicenseTrade

class TradeLinkingError(Exception):
    pass

@transaction.atomic
def link_trades(*, primary_id, partner_id):
    primary = LicenseTrade.objects.select_for_update().get(id=primary_id)
    partner = LicenseTrade.objects.select_for_update().get(id=partner_id)
    if primary.id == partner.id:
        raise TradeLinkingError("A trade cannot be linked to itself.")
    if primary.linked_trade_id and primary.linked_trade_id != partner.id:
        raise TradeLinkingError("Primary trade is already linked.")
    primary.linked_trade = partner
    partner.linked_trade = primary
    LicenseTrade.objects.bulk_update([primary, partner], ["linked_trade"])
    return primary, partner
```

```python
# apps/trade/views/trade.py
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from apps.trade.services.linking import link_trades, TradeLinkingError
from apps.trade.serializers.trade import LicenseTradeSerializer

class LicenseTradeViewSet(viewsets.ModelViewSet):
    serializer_class = LicenseTradeSerializer

    def get_queryset(self):
        return (
            LicenseTrade.objects
            .select_related("buyer", "seller", "linked_trade")
            .prefetch_related("lines__license", "payments")
        )

    @action(detail=True, methods=["post"])
    def link_trade(self, request, pk=None):
        try:
            primary, _ = link_trades(primary_id=pk, partner_id=request.data["partner_id"])
        except TradeLinkingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(LicenseTradeSerializer(primary).data)
```

```python
# apps/trade/tests/test_link_trade.py — service tested in isolation
@pytest.mark.django_db
def test_link_trade_sets_both_sides():
    a = TradeFactory()
    b = TradeFactory()
    link_trades(primary_id=a.id, partner_id=b.id)
    a.refresh_from_db(); b.refresh_from_db()
    assert a.linked_trade_id == b.id
    assert b.linked_trade_id == a.id

@pytest.mark.django_db
def test_link_trade_rejects_self():
    a = TradeFactory()
    with pytest.raises(TradeLinkingError):
        link_trades(primary_id=a.id, partner_id=a.id)
```

**Rules embedded in this template:**

- View never does ORM writes directly; calls a service function.
- Service is a free function (or class with static methods) — no Django DRF dependency.
- Service raises domain exceptions; view translates to HTTP.
- Transaction at the service boundary, not in the view.
- `select_for_update()` on writes when concurrency matters.
- `get_queryset()` has explicit `select_related/prefetch_related` (kills the N+1s from Phase 1 risk register).
- Service is unit-testable without DRF.

The same shape applies to license, allotment, BOE, tasks. Bigger services (e.g. balance calculator) become classes; small ones stay as free functions.

---

## 7. Frontend Data-Fetching Redesign

### Single API client

```js
// shared/api/client.js  (renamed from api/axios.js)
import axios from "axios";

export const apiClient = axios.create({ baseURL: "/api/", withCredentials: false });

// existing interceptors stay: token refresh queue, 401 retry, dedup, exponential backoff
```

### Endpoint registry

```js
// shared/api/endpoints.js
const E = {
  auth: {
    login:   "auth/login/",
    logout:  "auth/logout/",
    refresh: "auth/refresh/",
    me:      "auth/me/",
    users:   "auth/users/",
    user:    (id) => `auth/users/${id}/`,
    availableRoles: "auth/users/available-roles/",
  },
  licenses: {
    list:    "licenses/",
    detail:  (id) => `licenses/${id}/`,
    items:   (id) => `licenses/${id}/items/`,
    parsePdf: "licenses/parse-pdf/",
    inventoryBalance: "reports/inventory-balance/",
    expiring: "reports/expiring-licenses/",
    active:   "reports/active-licenses/",
    itemPivot: "reports/item-pivot/",
    itemReport: "reports/item-report/",
  },
  allotments: { list: "allotments/", detail: (id) => `allotments/${id}/`, copy: (id) => `allotments/${id}/copy/` },
  bills:      { list: "bill-of-entries/", detail: (id) => `bill-of-entries/${id}/`, parsePdf: "bill-of-entries/parse-pdf/" },
  trades:     { list: "trades/", detail: (id) => `trades/${id}/`, link: (id) => `trades/${id}/link-trade/` },
  tasks:      { list: "tasks/", detail: (id) => `tasks/${id}/`, complete: (id) => `tasks/${id}/complete/`, reject: (id) => `tasks/${id}/reject/`, reopen: (id) => `tasks/${id}/reopen/` },
  masters:    { /* one entry per master */ },
};
export default E;
```

Every component imports `E` instead of building URL strings.

### Query layer

```js
// shared/api/queryClient.js
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,       // 5 min default
      gcTime: 30 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
```

### Feature query hooks

```js
// features/license/queries.js
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import E from "@/shared/api/endpoints";

const licenseKey = {
  all: ["licenses"],
  list: (params) => ["licenses", "list", params],
  detail: (id) => ["licenses", "detail", id],
};

export function useLicenseList(params) {
  return useQuery({
    queryKey: licenseKey.list(params),
    queryFn: () => apiClient.get(E.licenses.list, { params }).then((r) => r.data),
  });
}

export function useLicense(id) {
  return useQuery({
    queryKey: licenseKey.detail(id),
    queryFn: () => apiClient.get(E.licenses.detail(id)).then((r) => r.data),
    enabled: !!id,
  });
}

export function useLicenseSave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => {
      const url = data.id ? E.licenses.detail(data.id) : E.licenses.list;
      const method = data.id ? "patch" : "post";
      return apiClient[method](url, data).then((r) => r.data);
    },
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: licenseKey.all });
      qc.setQueryData(licenseKey.detail(saved.id), saved);
    },
  });
}
```

**Rules embedded:**

- Query keys live next to query hooks, not in components.
- All URLs come from `endpoints.js`.
- Mutations invalidate related lists + seed the detail cache.
- 5-minute stale time eliminates the "every page refetches" anti-pattern.

The four legacy fetch hooks (`useApiCall`, `useApiRequest`, `useFetch`, raw axios in components) are deleted as their callers migrate.

---

## 8. Database Safety Analysis

Listed by structural change, with risk assessment.

| Change | DB impact | Risk | Mitigation |
|---|---|---|---|
| Move `license/` to `apps/license/` | None — `app_label` preserved via `AppConfig.label = "license"` | Low | Verify `python manage.py makemigrations --check --dry-run` produces no migrations |
| Split `license/models.py` into `models/` package | None — same model classes, same `app_label`, same `db_table` | Low | Re-export from `models/__init__.py` for back-compat. Verify no auto-generated migrations |
| Move 12 mgmt commands to license app | None — commands are not in DB | None | n/a |
| Move `data_script/fetch_ownership.py` into license | None — no models | None | Update single import in `update_license_ownership.py` |
| Move `core/scripts/calculation.py` | None — pure functions | None | Update import in `license/models.py:564` |
| Signal sender strings → direct imports | None — runtime change, no schema | Low | Tests verify handlers are wired |
| Signal → Celery task | None — same SQL, just deferred | **Medium** | Dual-write validation step (see §3) |
| URL namespacing | None | None | `reverse()` calls re-point automatically |
| Settings split | None | None | `manage.py check` passes |

**Migrations created during this entire modernization: zero, if done correctly.** Any unexpected migration produced by `makemigrations --check` is a bug in our refactor, not desired schema change.

Recommended preflight before any structural change:

```bash
cd backend
python manage.py makemigrations --check --dry-run
# If output is non-empty: STOP. Investigate. Do not commit.
```

This check goes in CI in Phase 5.

---

## 9. Caching Strategy

### Backend

- **Existing Redis layer kept.** No replacement.
- **`core/cache_utils.py:40-64` cache-key collision risk** fixed by sorting kwargs deterministically:
  ```python
  def cache_key(prefix, *args, **kwargs):
      parts = [prefix, *map(repr, args)]
      for k in sorted(kwargs):
          parts.append(f"{k}={kwargs[k]!r}")
      return hashlib.md5("|".join(parts).encode()).hexdigest()
  ```
- **Materialized views** — keep 15-min beat refresh. Add on-write invalidation for the dashboard view only:
  ```python
  # apps/license/signals.py — after license save
  recompute_license_flags.delay(license_id, source=source)
  # mark dashboard view as stale (next read refreshes)
  cache.delete("dashboard:summary:fresh")
  ```
- **Stale-while-revalidate** for the dashboard summary (eliminates thundering herd):
  ```python
  data = cache.get("dashboard:summary")
  if data and cache.get("dashboard:summary:fresh"):
      return data
  if data:
      # serve stale, refresh async
      refresh_dashboard.delay()
      return data
  return refresh_dashboard_sync()
  ```

### Frontend

- **TanStack Query** with 5-minute default `staleTime`. Most resources fall here.
- **`refetchOnWindowFocus: false`** — the app is an internal tool; aggressive refetch on focus is noisy.
- **Mutations invalidate then optimistic-update** where the result is computed (license balance after a trade).

---

## 10. Build, Lint, and CI

Out of scope for Phase 2 design but committed-to in Phase 5:

- **Backend:** `ruff` for lint + format; `mypy` for the new service modules; pre-commit hook running both.
- **Frontend:** existing ESLint + add `eslint-plugin-no-console`, `eslint-plugin-import` for unused-imports. Strip console.log in production via Vite plugin.
- **CI** (GitHub Actions or equivalent):
  - Backend: `pytest`, `python manage.py makemigrations --check --dry-run`, `ruff check`.
  - Frontend: `npm run build`, `npm run lint`, `vitest run` (once tests exist).
  - Block merge on failure.
- **Deploy:** `scripts/deployment/auto-deploy.sh` adds a `/api/health/` check after restart on each server before continuing to next.

---

## 11. What This Design Explicitly Does NOT Do

- **Rewrite anything that's not broken.** `core/AuditModel`, the JWT auth flow, the axios interceptor logic, the materialized view machinery — these are all kept as-is.
- **Add TypeScript.** Out of scope. The JS is consistent and Zod handles validation. TypeScript migration is a separate decision.
- **Replace Bootstrap with another UI library.** No reason to.
- **Introduce Redux or Zustand.** TanStack Query + Context is sufficient for the data shape.
- **Add GraphQL or a new API style.** REST + DRF is fine.
- **Touch the database schema.** Zero migrations expected.
- **Move `DFIA_COPY/` to object storage.** Recommended but separate project — depends on choice of S3/Spaces/GCS and bucket setup.

These are deliberately out of scope so this modernization has a finish line.

---

## 12. Expected Outcomes (measurable)

After Phases 3 + 4 complete:

| Metric | Before | After (target) |
|---|---|---|
| Backend LOC (excluding migrations) | 60,889 | ~55,000 (cleanup of dupes + collapsed PDF generators) |
| Files > 800 LOC (backend) | 5 | 0 |
| Backend `print()` statements | 176 | 0 |
| Frontend `console.log` statements | 50 | 0 |
| Frontend fetch hooks | 4 (+ raw axios) | 1 (TanStack Query) |
| Markdown files at root | 26 (post-Phase 0) | 6 (consolidated guides + 1 docs index) |
| Synchronous PDF/Excel endpoints | 6 | 1 (legacy compat), 5 async |
| Public unauthenticated endpoints | 0 (hotfix) | 0 |
| Cross-app signal sender strings | 6 | 0 (direct imports) |
| Sync balance-recompute on hot path | yes | no (Celery) |
| Migrations produced by refactor | n/a | 0 |

These are the success criteria. A phase that misses them ships with a known regression.
