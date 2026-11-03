# Dashboard — V1 Revamp

Route: `/dashboard` (`frontend/src/routes/AppRoutes.tsx`, lazy `pages/Dashboard`).
API: `GET /api/dashboard/` (`backend/apps/license/urls.py`, view `DashboardDataView`).
Method: ECC — **EXPLORE → CRITIQUE → CREATE → VERIFY → FREEZE**.
Status: see [V1_MASTER_TRACKER.md](../V1_MASTER_TRACKER.md#dashboard).

---

## 1. EXPLORE — current architecture

### 1.1 Components

| Layer | File | Role |
|---|---|---|
| Route | `frontend/src/routes/AppRoutes.tsx:96` | `/dashboard` behind `ProtectedRoute` |
| Page | `frontend/src/pages/Dashboard.tsx` (886 lines, single component) | Header, alert cards, stat cards, C969 table, expiring table, BOE and allotment tables |
| Shared UI | `components/PageHeader`, `AlertCard`, `StatCard`, `EmptyState`, `ui/card`, `ui/badge`, `ui/skeleton` | Reused as-is |
| Contract | `frontend/src/pages/dashboardContract.ts`, `Dashboard.contract.test.tsx` | Frozen v2 shape |
| Date util | `frontend/src/utils/dashboardDate.ts` | UTC-default date formatting |
| Auth | `context/AuthContext` (`hasAnyRole`, `isSuperAdmin`) | Client-side role checks |
| Shell | `components/TopNav.tsx` | Global search (⌘K command palette) and profile/sign-out menu already exist |

### 1.2 Backend

| Piece | File | Notes |
|---|---|---|
| View | `backend/apps/license/views/dashboard.py` | Single endpoint, role-gated sections, cache key `view:dashboard:v2:{roles}` (TTL 300 s) |
| Live balance | `backend/apps/license/services/balance_calculator.py` | `LicenseBalanceCalculator.calculate_financial_balance_for_licenses` (canonical "Financial Available Balance") and its `_for_licenses` components |
| Balance property | `backend/apps/license/models/core.py:330` | `LicenseDetailsModel.get_balance_cif` → financial balance |
| C969 review | `backend/apps/license/services/c969_link_review.py` | Read-only, isolated failure |
| Materialised stats | `backend/apps/core/materialized_views.py:468`, `tasks_materialized_views.py:59`, `cache_utils.py:386` | **Not referenced by the dashboard endpoint** (dead path for this page; see F-16) |
| Cache invalidation | `backend/apps/core/cache_utils.py:293` | `invalidate_cache('view:dashboard:*')` |

### 1.3 Endpoint sections today (v2)

| Section | Roles that receive it | Source |
|---|---|---|
| `license_stats` | LICENSE_MANAGER, LICENSE_VIEWER, REPORT_VIEWER | Flag counts + live balance for "expiring soon" |
| `expiring_licenses` | same | Top 5 active licences expiring within 30 days with live balance ≥ $100 |
| `c969_link_review` | same | `c969_link_mismatches()` |
| `allotment_stats` | ALLOTMENT_MANAGER, ALLOTMENT_VIEWER, REPORT_VIEWER | `AllotmentModel` counts and 5 most recent |
| `boe_stats` | BOE_MANAGER, BOE_VIEWER, ACCOUNT_ACCESS, REPORT_VIEWER | `BillOfEntryModel` counts and 5 most recent |
| `boe_monthly_trend` | same as `boe_stats` | 6-month BOE count (returned but **not rendered** by the UI) |

### 1.4 Trace of every displayed figure to its source (v2)

| Figure on screen | Computed at | Source | Verdict |
|---|---|---|---|
| "Active" | `_get_license_stats` | `flags.is_expired=False AND flags.is_null=False` | Excludes null-DFIA licences; ignores the `is_active` flag (changed in V1, DD-14) |
| "Expired" | same | `flags.is_expired=True, flags.is_null=False` | Stored flag only (see F-03) |
| "Missing DGFT" alert | `null_dfia` | `flags.is_null=True` (balance < $500 rule, `signals.py`) | Mislabelled (F-02) |
| "Expiring soon" alert (<7 d) | Frontend filter over `expiringLicenses` | Top-5 list only | **Under-counts** (F-01) |
| "Pending invoices" alert | `boe_stats.pending_invoices` | `BillOfEntryModel.invoice_no` blank | Not the invoice engine (F-06) |
| "Allotments" stat | `allotment_stats.total` | `AllotmentModel` where `bill_of_entry` is null | Label/predicate mismatch (F-05) |
| "BOE" stat | `boe_stats.total` | `BillOfEntryModel.count()` | Correct, but unscoped by date/company |
| Expiring table "Balance" | `_get_expiring_licenses` | Live financial balance | Correct engine; float JSON (F-08) |
| Recent BOE / Recent allotments | `_get_boe_stats` / `_get_allotment_stats` | Latest 5 | Correct source; no filters |

### 1.5 Canonical balance engine (what the dashboard must consume)

Financial Available Balance per licence (`_calculate_financial_balance`, `calculate_financial_balance_for_licenses`):

```
Available = max(0,  Opening + Purchase − Sale − BOE debit − Outstanding allotments)
Opening   = Credit − hidden BOE − purchase      (hidden BOEs present)
          = 0                                   (purchase present, no hidden BOEs)
          = Credit                              (otherwise)
```

Components (all batched, `*_for_licenses`): `calculate_credit`, `calculate_purchase_credit`, `calculate_opening_balance`, `calculate_trade` (SALE), `calculate_debit` (allocation-aware), `calculate_allotment` (allocation-aware).

**Open business question:** ISS-016 (Critical) and DEC-010 — the codebase has five CIF-balance functions that disagree, and the business has not yet defined which one is "available" for allotments and reporting. This dashboard uses the **Financial Available Balance** because it is the figure every dashboard card already shows and the one `get_balance_cif` returns. It labels the figure explicitly and does not resolve DEC-010.

---

## 2. CRITIQUE — finding register

Severity: **H** high (wrong number or dead navigation), **M** medium (misleading or unclear), **L** low.

| ID | Sev | Finding | Evidence | Resolution in V1 |
|---|---|---|---|---|
| F-01 | H | "Expiring soon (< 7 days)" alert counts only the **top 5** rows of the expiry list. Under-reports whenever more than five licences expire in 30 days. | `Dashboard.tsx` alert `count` filters `expiringLicenses`; backend slices `[:5]` (`views/dashboard.py:263`) | Counts come from backend over **all** candidates |
| F-02 | H | "Missing DGFT" is the stored `is_null` flag, which means **balance < $500** ("Null DFIA"). No DGFT field exists on the licence model. | `signals.py` "BUSINESS RULE: Null DFIA = balance < $500"; `models/core.py` has no DGFT field | Keep the flag (it is what the licence list's `is_null` filter reads, so the link matches). Label it "Null DFIA / missing DGFT: balance < $500" with a tooltip. Business to confirm the label |
| F-03 | H | Expiry and expired counts use the stored `flags.is_expired`, refreshed only on licence save (`signals.py:303`). No scheduled recompute found. A licence that crosses its expiry date without a save stays "active". | `signals.py:303`, no beat task | Expired and expiry buckets are computed from `license_expiry_date` vs as-of date. Stale flags are reported as an attention item (`stale_expiry_flags`) |
| F-04 | M | Timezone: `date.today()` (server local) in the view, `timezone.now().date()` (UTC) in the signal, and `toISOString()` (UTC) in the "View all" link. `settings.TIME_ZONE = "UTC"`. | `views/dashboard.py:125`; `signals.py:303`; `Dashboard.tsx:273` | One as-of date: `timezone.localdate()`. Returned as `meta.as_of`; shown in the header. Business timezone (IST) is a global decision, recorded in §5 |
| F-05 | M | "Allotments" total counts only allotments **without** a BOE link (`bill_of_entry__isnull=True`), but the link opens all allotments. Recent list uses another predicate (`is_boe=False OR bill_of_entry null`). | `views/dashboard.py:156,159` | Total = all allotments in scope. Engine-based status per allotment |
| F-06 | M | "Pending invoices" counts BOEs with blank `invoice_no`. The invoice engine is `LicenseTrade` (`invoice_number`, `due_amount`, `paid_or_received`). | `views/dashboard.py:190`; `trade/models.py:351-363` | Invoice section uses trades. BOE blank-invoice count is kept as a separate, honestly labelled attention item |
| F-07 | H | No authorised, utilised, reserved or available CIF is shown anywhere. The canonical engine is used only for the expiring list. | `Dashboard.tsx` (no financial cards) | Financial section driven by a backend bridge (§4.3) |
| F-08 | L | Money is sent as JSON floats (`balance_cif: float(...)`) and formatted with `toLocaleString`. | `views/dashboard.py:282` | Money is decimal strings in v3 |
| F-09 | H | Role mismatch: frontend shows licence cards to TRADE_MANAGER/TRADE_VIEWER and BOE cards to TL_GENERATE, but the backend sends no section to those roles. The UI then renders **zeros** ("Active 0", "BOE 0") — a false empty state. | `Dashboard.tsx` `canSeeLicenses`/`canSeeBOE` vs `views/dashboard.py:66,79` | Frontend role gates mirror the backend exactly. Users without a section see no card, rather than a zero |
| F-10 | H | **Refresh does not refresh.** The GET reads the 300 s cache first, so the Refresh button returns the cached payload until expiry. | `views/dashboard.py:59-61`; `cache_utils.py:429` | `refresh=1` bypasses the read (still writes the cache) |
| F-11 | M | One failing section fails the whole endpoint (HTTP 500, "Failed to load dashboard data"). Only the C969 review is isolated. | `views/dashboard.py:85-89` | Each section is isolated and returns `{ "error": ... }` on failure |
| F-12 | M | Errors are shown as one banner; the page keeps the previous data without saying which section is stale. | `Dashboard.tsx:243-249,349` | Per-card error state; header shows the last successful refresh time |
| F-13 | M | Navigation filters not reproducible: the expiring link uses `license_expiry_date__gte/__lte`, which the licence filterset does not declare (it declares `license_expiry_date_from/to`). The link silently shows unfiltered licences. | `Dashboard.tsx:279-281`; `core/filtersets.py:115-116` | V1 links use only declared filter names: `license_expiry_date_from`, `license_expiry_date_to`, `is_active`, `is_expired`, `is_null`, `status`, `company_id`. Verified in the link test |
| F-14 | M | Expiring alert link goes to `/licenses?search=<licence>` per row (`rowNav`), but the licence list's search parameter name must be verified before use. | `Dashboard.tsx:654` | Row links use `/licenses/:id/edit` by licence id |
| F-15 | M | `boe_monthly_trend` is returned but never rendered; the frozen contract lists `label` and `value` keys that the backend does not send. Contract drift. | `dashboardContract.ts` vs `views/dashboard.py:312-318` | Trend removed from the V1 UI. Key kept in payload for compatibility, documented as unused |
| F-16 | L | `materialized_views.get_dashboard_stats` and `warm_dashboard_cache` exist but nothing calls them for this page. Dead path. | `grep` results | Not used. Recorded in cleanup register for a later decision (not deleted in V1) |
| F-17 | M | Recent-table rows are `div`-based pseudo-buttons inside `<table>` rows (`role="button"` on `tr`). Keyboard works, but a screen reader announces them as buttons inside a grid, not as links. | `rowNav` helper | Rows use real links for navigation |
| F-18 | M | No company or date scope. Every number is system-wide and all-time. | `views/dashboard.py` (no parameters) | `company_id`, `date_from`, `date_to` added (§4.1) |
| F-19 | M | Balance engine is not single-source (ISS-016, DEC-010). The same licence can show different "balances" on different screens. | `V1_ISSUE_REGISTER.md` ISS-016 | Dashboard labels its figure "Financial available balance". DEC-010 stays open; no formula changed |
| F-20 | M | Allotment reservation remainder is dropped by the engine when partly used (ISS-008). Reserved CIF on the dashboard inherits this. | `V1_ISSUE_REGISTER.md` ISS-008 | Reserved CIF shows the engine's figure with a disclosure. Blocked on DEC-010 Q2 |
| F-21 | L | Stat cards have no tooltip, context line, or unit. | `StatCard` usage | Every KPI carries label, unit, context, tooltip and click target |

### 2.1 Performance (static analysis; measured in VERIFY)

- Endpoint issues about 15–25 queries per uncached request. No N+1 found in `_get_expiring_licenses` (prefetch present) or `_get_boe_stats` (`select_related('company')`).
- The expiry candidate context and the financial balance batch run once per uncached response (shared between KPI and list).
- The financial engine adds one batched pass over **all** licences in scope. Expected cost is linear in licence count. Measured in VERIFY against the local dataset (222 licences, per ISS-016) and recorded below.
- Caching: 300 s TTL keyed by role set **and** scope (company, date range). `refresh=1` bypasses the read. Invalidation stays on `view:dashboard:*`.

---

## 3. DECISIONS (dashboard-scope)

| ID | Decision | Reason | Status |
|---|---|---|---|
| DD-01 | Endpoint stays `GET /api/dashboard/`; v3 adds optional query parameters and replaces the v2 payload. Frontend and backend ship together. | Single endpoint keeps one round trip; only one consumer | DECIDED |
| DD-02 | Financial numbers come only from `LicenseBalanceCalculator`. A new engine method returns the per-licence component breakdown; `calculate_financial_balance_for_licenses` is rewritten to read from it, with no change to its output (test asserts equality). | Brief §4.C: no formula in React or a second engine (DEC-007) | DECIDED |
| DD-03 | Available CIF = canonical Financial Available Balance. DEC-010 stays BLOCKED; the label says so. | ISS-016 / DEC-010 | DECIDED |
| DD-04 | Utilisation % = (Utilised + Reserved) ÷ Authorised, shown as "committed". `null` when Authorised is 0. | Authorised has no defined cap in the engine; the bridge shows the rest | DECIDED |
| DD-05 | Date windows count **all active** licences by expiry date (no balance threshold). The "usable balance ≥ $100" rule stays for the existing expiring drill-down and its attention item only. Each KPI's link reproduces its count exactly with declared filters. | Links must match counts (brief §4.C); the balance rule can't be expressed in the filterset (its `balance_cif_min` reads the stale cache) | DECIDED (business to confirm) |
| DD-06 | Global date range filters **activity** only (BOEs by `bill_of_entry_date`, allotments by `created_on`, invoices by `invoice_date`). Balances, licence counts and expiry are as-of today and labelled so. | Balances are point-in-time; filtering them by date would change their meaning | DECIDED |
| DD-07 | "Null DFIA / missing DGFT" keeps the stored `is_null` flag. | The licence list's filter reads the same flag | DECIDED (label to confirm, F-02) |
| DD-08 | Attention centre and workflow centre are **merged** into one section. Every row is a verified count with a single action. | Avoids two lists with the same counts | DECIDED |
| DD-09 | Unsupported items (Draft/Posted/Confirmed invoice states, reconciliation issues, duplicate-debit findings) are shown as explicit "not tracked" notes, never as alerts. | Brief: no invented values; "do not show an alert unless verified" | DECIDED |
| DD-10 | Notification centre = the verified attention items (same source). No notification model exists. | Avoids inventing a notification system | DECIDED |
| DD-11 | Global search filters the dashboard's own tables (client-side) and the global ⌘K palette in TopNav is unchanged. | The palette already exists; the page search covers the page's rows | DECIDED |
| DD-12 | Materialised-view path (F-16) is not used or deleted in V1. | Cleanup needs its own decision (DEC-004) | DECIDED |
| DD-13 | Role sections keep today's access rules. No record-level data is newly exposed to any role. **Exception:** the invoice section is new for TRADE_MANAGER and TRADE_VIEWER, who already open the `/trades` list (`AppRoutes.tsx:182`). It shows aggregates over that list. Flagged for security review. | Access control must not widen in a UI revamp | DECIDED (exception flagged) |
| DD-14 | "Active" = `is_active` AND not expired (date or flag). Licences with null DFIA are now counted as active, matching the licence list's `status=active`. | v2 excluded null-DFIA licences from "Active", so the number disagreed with the link | DECIDED |
| DD-15 | "Total allotments" = all allotments in scope and date range (`created_on`). v2 counted only allotments with no BOE link. | F-05: the number disagreed with the link target | DECIDED |
| DD-16 | Expiry band "inactive" is added for licences with `is_active = false` that are not expired. Bands always partition the licence set. | Needed so bands sum to the total | DECIDED |

---

## 4. CREATE — design and API contract (v3, frozen at §4.4)

### 4.1 Request

`GET /api/dashboard/` with optional query parameters:

| Param | Type | Meaning |
|---|---|---|
| `company_id` | int | Scope: licences with `exporter_id`, BOEs with `company_id`, allotments with `company_id`, invoices where `from_company_id` or `to_company_id` equals it. Unknown id → 400 |
| `date_from` | `YYYY-MM-DD` | Activity lower bound (inclusive) |
| `date_to` | `YYYY-MM-DD` | Activity upper bound (inclusive). `date_from > date_to` → 400 |
| `refresh` | `1` | Bypass the cached read. Response is still written to cache |

No other parameters. Unknown parameters are ignored.

### 4.2 Response (v3)

```jsonc
{
  "meta": {
    "generated_at": "2026-11-02T10:15:00Z",        // ISO-8601 UTC instant
    "as_of": "2026-11-02",                         // business date used for expiry (timezone.localdate())
    "as_of_timezone": "UTC",                       // settings.TIME_ZONE
    "cached": false,
    "scope": { "company_id": null, "company_name": null, "date_from": null, "date_to": null },
    "units": { "cif": "FC", "invoice": "INR" }     // CIF is foreign currency (USD for most rows); invoices are INR
  },

  // Roles: LICENSE_MANAGER, LICENSE_VIEWER, REPORT_VIEWER (or superuser)
  "licence_portfolio": {
    "total": 0, "active": 0, "expired": 0,
    "missing_dgft": 0,                             // flags.is_null = true, all licences in scope
    "expiring_usable_30d": 0,                      // legacy rule: active, expiry 0..30 d, live balance >= 100
    "stale_expiry_flags": 0,                       // flags.is_expired disagrees with expiry date
    "bands": [                                     // non-overlapping; every licence in exactly one band; sums to total
      { "key": "expired",   "count": 0 },           // expiry < as_of (date) OR flag says expired
      { "key": "d0_7",      "count": 0 },
      { "key": "d8_15",     "count": 0 },
      { "key": "d16_30",    "count": 0 },
      { "key": "d31_60",    "count": 0 },
      { "key": "over_60",   "count": 0 },
      { "key": "inactive",  "count": 0 },           // is_active = false and not expired
      { "key": "no_expiry", "count": 0 }            // active, no expiry date
    ],
    "within": { "7": 0, "15": 0, "30": 0, "60": 0 } // active, 0 <= days_to_expiry <= N
  },

  // Roles: LICENSE_MANAGER, LICENSE_VIEWER, REPORT_VIEWER
  "financial": {
    "engine": "financial_available_balance",       // canonical; see DEC-010
    "authorized_cif": "0.00",                      // sum of export CIF (credit)
    "utilized_cif": "0.00",                        // boe_utilisation + sale_utilisation
    "reserved_cif": "0.00",                        // engine outstanding allotments
    "available_cif": "0.00",                       // canonical, floored per licence
    "expired_available_cif": "0.00",               // available held by expired licences (context for expired_with_balance)
    "committed_pct": null,                         // (utilized + reserved) / authorized * 100, 2 dp; null when authorized = 0
    "licences_in_scope": 0,
    "over_utilised_licences": 0,                   // raw available < 0 (floored; ISS-009)
    "bridge": {
      "authorized": "0.00",
      "previous_owner_utilisation": "0.00",        // credit - opening
      "purchased_cif": "0.00",
      "sale_utilisation": "0.00",
      "boe_utilisation": "0.00",
      "reserved": "0.00",
      "rounding": "0.00",                          // per-licence quantisation of raw; closes the bridge exactly
      "raw_available": "0.00",                     // = authorized - previous_owner + purchased - sale - boe - reserved + rounding
      "over_utilisation_floor": "0.00",            // = available - raw_available (>= 0)
      "available": "0.00"                          // = canonical available_cif
    }
  },

  // Roles: LICENSE_MANAGER, LICENSE_VIEWER, REPORT_VIEWER
  "expiring_licences": [                           // usable-balance drill-down, cap 25, soonest first
    { "id": 1, "license_number": "X", "license_expiry_date": "2026-11-10", "days_to_expiry": 8,
      "balance_cif": "0.00", "sion_norms": ["..."] }
  ],

  // Roles: LICENSE_MANAGER, LICENSE_VIEWER, REPORT_VIEWER
  "c969_link_review": { "count": 0, "rows": [] },  // unchanged

  // Roles: ALLOTMENT_MANAGER, ALLOTMENT_VIEWER, REPORT_VIEWER
  "allotment_activity": {
    "total": 0,                                    // all allotments in scope
    "counts": { "open": 0, "partly_consumed": 0, "consumed": 0, "boe_linked": 0 },
    "recent": [                                    // cap 10, most recent first, date-range applied on created_on
      { "id": 1, "item_name": "x", "company_name": "x", "created_on": "2026-11-01T00:00:00Z",
        "allotted_cif": "0.00", "consumed_cif": "0.00", "reserved_cif": "0.00",
        "remaining_quantity": "0.00", "status": "open" }
    ]
  },

  // Roles: BOE_MANAGER, BOE_VIEWER, ACCOUNT_ACCESS, REPORT_VIEWER
  "boe_activity": {
    "total": 0,                                    // date/company scoped
    "linked_to_allotment": 0,                      // has >= 1 allotment link
    "direct": 0,                                   // no allotment link
    "pending_licence_mapping": 0,                  // no RowDetails (licence item) rows
    "without_invoice_no": 0,                       // invoice_no blank
    "recent": [                                    // cap 10, bill_of_entry_date desc
      { "id": 1, "bill_of_entry_number": "x", "bill_of_entry_date": "2026-11-01", "company_name": "x",
        "invoice_no": null, "modified_on": "2026-11-01T00:00:00Z",
        "allotment_links": 0, "licence_items": 0, "mapping_status": "mapped" | "pending_licence_mapping" }
    ],
    "recently_modified": [ /* same row shape, cap 10, modified_on desc */ ],
    "monthly_trend": [ { "month": "Jun 2026", "count": 0 } ]   // unused by V1 UI; kept for compatibility
  },

  // Roles: TRADE_MANAGER, TRADE_VIEWER, ACCOUNT_ACCESS, REPORT_VIEWER
  "invoice_activity": {
    "total": 0,                                    // trades with a non-blank invoice_number, scoped
    "paid": 0, "partially_paid": 0, "unpaid": 0,   // derived from trade.due_amount / paid_or_received
    "open": 0,                                     // partially_paid + unpaid
    "total_amount_inr": "0.00",
    "paid_inr": "0.00",
    "outstanding_inr": "0.00",
    "by_direction": {
      "sale":     { "total": 0, "outstanding_inr": "0.00" },
      "purchase": { "total": 0, "outstanding_inr": "0.00" }
    },
    "not_tracked": ["draft", "pending", "confirmed", "posted"],   // states not in the schema
    "recent": [                                    // cap 10, invoice_date desc
      { "id": 1, "invoice_number": "x", "invoice_date": "2026-11-01", "direction": "sale",
        "party_name": "x", "total_amount_inr": "0.00", "outstanding_inr": "0.00", "status": "paid" | "partially_paid" | "unpaid" }
    ]
  },

  // Verified exceptions only (count > 0). Frontend maps `key` to an action and href.
  "attention": [
    { "key": "expired_with_balance", "count": 0, "severity": "high" | "medium" | "low",
      "section": "licence_portfolio" }
  ],
  // Checks the dashboard cannot verify. Shown as notes, never as alerts.
  "not_monitored": [ { "key": "reconciliation_issues", "reason": "..." } ]
}
```

Rules for every section:

- A section is **absent** when the caller's roles do not grant it. It is never filled with zeros.
- A section that fails is replaced by `{ "error": "<message>" }`. Other sections are unaffected. The failure is logged with the module name.
- `attention` is derived only from sections that succeeded. Missing a section never produces a 0-count alert.
- Money is a decimal string with 2 dp, computed from the engine. The frontend formats it; it never recomputes it.

### 4.3 Attention keys (backend-defined, verified counts)

| Key | Section | Severity | Count definition |
|---|---|---|---|
| `expired_with_balance` | licence_portfolio | high | expired licences with financial available > 0 |
| `expiring_7d_usable` | licence_portfolio | high | active, 0..7 d, live balance ≥ 100 |
| `missing_dgft` | licence_portfolio | high | `flags.is_null = true` |
| `over_utilised` | financial | high | licences with raw available < 0 |
| `stale_expiry_flags` | licence_portfolio | medium | `flags.is_expired` ≠ (expiry < as_of) |
| `c969_link_review` | licence_portfolio | medium | `c969_link_review.count` |
| `boe_pending_licence_mapping` | boe_activity | medium | BOEs with no licence item rows |
| `boe_without_invoice_no` | boe_activity | low | `invoice_no` blank |
| `invoices_outstanding` | invoice_activity | medium | invoices with outstanding > 0 |

`not_monitored` (always returned, no count): `draft/pending/confirmed/posted` invoice states, `reconciliation_issues`, `duplicate_debit_findings`, `invalid_licence_mappings`, `incomplete_allotments` — each with the reason.

### 4.4 Frozen contract

This section is the freeze point. After implementation starts:

- Backend and frontend both implement §4.1–4.3 exactly. A change requires editing this document first and bumping `dashboardApiContract.version`.
- Frontend TypeScript types and the contract test are updated together with the backend tests. The old `dashboardApiContract` (v2) is replaced.

### 4.5 Layout

```
┌ Header ─────────────────────────────────────────────────────────────────────────┐
│ Dashboard · as of 02-11-2026 (UTC)     [Company ▾] [Date range ▾] [Search…]  │
│ Updated 10:15 · [Refresh]  [Attention n]   [+ Licence] [+ Allotment] [+ BOE] … │
└─────────────────────────────────────────────────────────────────────────────────┘
┌ Primary KPIs (4) ───────────────────────────────────────────────────────────────┐
│ Authorised CIF │ Utilised CIF │ Reserved CIF │ Available CIF                   │
│ $ · context    │ BOE + sale   │ allotments   │ financial available · tooltip   │
└─────────────────────────────────────────────────────────────────────────────────┘
┌ Attention required ─────────────────┐ ┌ Financial overview ──────────────────────┐
│ verified rows: count · sev · action │ │ bridge (bar) · committed % · notes       │
└─────────────────────────────────────┘ └──────────────────────────────────────────┘
┌ Licence portfolio ──────────────────────────────────────────────────────────────┐
│ secondary counts (Total, Active, Expired, Missing DGFT) · expiry distribution   │
│ within 7 / 15 / 30 / 60 chips (each a link) · drill-down table (expiring)        │
└─────────────────────────────────────────────────────────────────────────────────┘
┌ Allotments ──────────┐ ┌ BOE activity ─────────────────────────────────────────┐
│ counts · recent table│ │ counts · tabs: Recent / Unmapped / Recently modified  │
└──────────────────────┘ └───────────────────────────────────────────────────────┘
┌ Invoices ─────────────────────────────────────────────────────────────────────────┐
│ paid / partial / unpaid · outstanding ₹ · recent table · not-tracked note        │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Responsive: one column below 768 px; KPI row 2×2 below 1024 px; tables scroll horizontally inside their card. Dark mode uses the existing `dark:` tokens.

### 4.6 Component architecture (frontend)

- `pages/Dashboard.tsx` — data hook, scope state, layout only.
- `pages/dashboardContract.ts` — v3 types and the frozen contract object.
- `components/dashboard/` — `DashboardHeader`, `KpiCard` (one component for every KPI), `FinancialOverview` (bridge chart via the existing `recharts` dependency), `LicencePortfolio` (distribution chart + drill-down), `AttentionCentre`, `AllotmentActivity`, `BoeActivity`, `InvoiceActivity`, `QuickActions`, `DashboardSection` (card + loading + error + empty), `formatters.ts` (money and dates in one place).

### 4.7 Quick actions (permission-gated)

| Action | Route | Roles |
|---|---|---|
| New Licence | `/licenses/create` | LICENSE_MANAGER (or superuser) |
| New Allotment | `/allotments/create` | ALLOTMENT_MANAGER |
| New BOE | `/bill-of-entries/create` | BOE_MANAGER |
| New Invoice | `/trades/create` | TRADE_MANAGER |
| Reconciliation | `/reconciliation` | existing reconciliation rule |
| View Reports | `/reports/item-report` | REPORT_VIEWER (no index page exists) |

The role rules are the ones the existing route guards use. The implementer must check each one in `AppRoutes.tsx` before wiring the button.

---

## 5. Open items and business questions

1. **DEC-010** (ISS-016): which balance is "available" for allotment and reporting. Dashboard labels its figure; no formula changed.
2. **F-02**: confirm that "Missing DGFT" is the right label for `is_null` (balance < $500).
3. **DD-05**: confirm that expiry counts use all active licences, with the usable-balance rule kept only for the drill-down.
4. **Business timezone**: `TIME_ZONE = "UTC"` means "today" flips at 05:30 IST. Changing `TIME_ZONE` is a global decision and is not made here.
5. **ISS-008**: the dashboard's Reserved CIF inherits the engine's behaviour for partly used allotments.

---

## 6. Test plan

| Area | Test | Where |
|---|---|---|
| Engine refactor | `calculate_financial_balance_for_licenses` output unchanged; components sum to `available` per licence; floor is the only difference | `backend/apps/license/tests/test_dashboard_summary.py` |
| Bridge identity | `raw_available` and `available` identities hold on a mixed fixture (purchase, hidden BOE, allotment, over-utilisation) | same |
| Expiry | as-of date boundaries: expiry = today → 0 d; yesterday → expired; 30/31 d; null expiry → `no_expiry`; flag/date disagreement → `stale_expiry_flags` | same |
| Scope | `company_id` filters every activity section; unknown id → 400; bad dates → 400 | same |
| Permissions | each section absent for roles without the grant; superuser sees all; no zeros for absent sections | same |
| Errors | one failing section returns `{error}` and others still succeed | same |
| Cache | refresh bypasses read; key includes scope; invalidation pattern still clears | same |
| Query budget | constant query count across row counts (`assertNumQueries` range) | same |
| Frontend contract | v3 shape, endpoint with params, no request on unmounted tree | `Dashboard.contract.test.tsx` |
| Frontend KPIs | value, unit, context and link for each KPI; no trend when history absent | `Dashboard.test.tsx` |
| Frontend states | loading, empty, error (per section), refresh, stale-data label, permission gating | `Dashboard.test.tsx` |
| Navigation | every link resolves to a declared filter name (`LINK_PARAMS` table test) | `dashboardLinks.test.ts` |
| Sorting / search | BOE and allotment tables sort and search | `Dashboard.test.tsx` |
| Dark mode and responsive | class checks and E2E viewport screenshots | Playwright (`frontend/e2e`) |
| Gates | typecheck, lint, vitest, build, pytest (dashboard + balance + license suites) | repo scripts |

---

## 7. VERIFY — results

Every number here is measured. Items marked PENDING are not yet run.

### 7.1 Backend

| Check | Result |
|---|---|
| Engine refactor (`calculate_financial_balance_for_licenses` reads from `calculate_financial_components_for_licenses`) — old formula vs new, dev DB, 222 licences | **0 mismatches** (old formula rebuilt from the unchanged component methods) |
| Dashboard backend tests (`test_dashboard_summary.py`, `test_dashboard_balance_cif.py`, `test_dashboard_c969_link_review.py`) | **26 passed** |
| Balance suites (`test_balance_ledger_views.py`, `test_balance_calculator.py`, `test_canonical_cif_balance_scenarios.py`, `tests/test_all_conditions.py`, dashboard API integration test) | **158 passed, 1 skipped, 2 xfailed** — same skip and xfail as the V1 tracker baseline (ISS-008, ISS-011) |
| Endpoint on dev DB, superuser, uncached | **0.18 s, 30 queries**, no section errors |
| Bridge identity on dev DB | authorized 130,855,423.84 − previous-owner 114,373,602.09 + purchased 51,924,669.68 − sale 44,488,452.91 − BOE 19,218,758.34 − reserved 207,550.16 + rounding −0.00 = raw 4,491,730.02; raw + over-utilisation floor 13,949,843.08 = available 18,441,573.10 ✔ |
| Lint / format | PENDING: no ruff in the project venv; `py_compile` clean; unused imports removed |

### 7.2 Findings from the real-data run (not defects in the dashboard)

- **56 licences are over-utilised** (raw available < 0). The engine floors them at zero, so the displayed available figure hides **$13,949,843.08** of negative balance. The bridge shows this as a separate line. This is ISS-009 at scale and needs the DEC-010 answer (question 5).
- **114,373,602.09 of previous-owner utilisation** is removed from authorised CIF before available is shown. Its meaning depends on DEC-010 question 3.
- **560 invoices have an outstanding amount** and **109 licences are flagged missing DGFT** (`is_null`, balance < $500). Both are shown as counts with links, not as KPIs.
- **15 licences have a stale `is_expired` flag** (flag disagrees with the expiry date). This confirms F-03.

### 7.3 Frontend

PENDING — the frontend agent is building the v3 UI against the same contract. Its gates (typecheck, lint, vitest, build) and E2E checks will be recorded here.

### 7.4 Tracker

PENDING — `docs/V1_MASTER_TRACKER.md` will be updated after the frontend gates pass.

## 8. FREEZE

*Set after all acceptance criteria in the brief §9 pass and §7 is complete.*

---

## 9. BOE and invoice sections — repair (2026-11-02)

Scope: the BOE Activity and Invoice Activity cards only. No other dashboard section changed.

### 9.1 Root causes

| Symptom | Cause | Evidence |
|---|---|---|
| BOE: "The server response did not match the expected format." | The process on `127.0.0.1:8000` (PID 9723, `manage.py runserver 127.0.0.1:8000 --noreload`, started 14:12) runs code from before `pending_mapping` was added. Its BOE payload has no `pending_mapping` key. | Raw response from that process: `boe_activity` keys omit `pending_mapping`. The current code's response includes it. |
| Invoice: "Dashboard section 'invoice_activity' could not be loaded." | The same stale process raises inside the invoice builder, which the server converts to a section error. Its code predates the fix for the grouped aggregate that referenced an annotation the filtered queryset did not carry (`column "outstanding" does not exist`). | Raw response from the stale process: `invoice_activity` is `{error}`. The current code returns 560 invoices with a real aggregate. |
| The browser reaches the stale process | `frontend/.env` sets `VITE_API_URL=http://localhost:8000`, so axios calls port 8000 directly and bypasses the Vite proxy. | Captured network response: `http://localhost:8000/api/dashboard/` with `cached: false` and no `pending_mapping`. |
| Retry refetched the whole dashboard | No section-scoped request existed. Every section came from one payload. | `Dashboard.tsx` and `useDashboardData` before this change. |

Two defects were in this session's code and are fixed:
- `RETRYABLE_SECTIONS` captured builder function objects, so a patched builder bypassed the mapping. The fix looks builders up at call time.
- The invoice split into sale and purchase used a second filtered aggregate over an annotated queryset. It is now one aggregate with filtered sums, and the tests cover each direction.

### 9.2 Invoice states

The data model has **no** Draft, Confirmed, Posted or Cancelled state. `LicenseTrade` has no status field, and the licence `Invoice` model has none either. A trade invoice is classified from its own settlement properties, `due_amount` and `paid_or_received`:

- Paid: due ≤ 0
- Partially paid: due > 0 and something settled
- Unpaid: due > 0 and nothing settled

Overpayment is not netted against other invoices. Outstanding is `max(total − settled, 0)` per invoice. Draft, Pending, Confirmed and Posted are reported as not tracked, not as zero. Cancelled is not reported, because the model has no such state.

The aggregation was checked against the model properties on the dev database: 11 of 11 totals match. The dev database has 560 invoices and no recorded payments, so every invoice is Unpaid. That is the data, not a calculation fault.

### 9.3 Response contracts

**`GET /api/dashboard/?section=boe_activity`** (also `allotment_activity`, `invoice_activity`)

- Role-gated. An unknown or licence-section name returns **400**. A role without the grant returns **403**. A builder failure returns **200** with `{ "error": ... }` in place of the section.
- Body: `{ "meta": {...}, "<section>": {...} }`. The section is the same object as in the full payload.
- Not cached. The client sends `refresh=1` on a retry.
- Lists are plain arrays, not paginated. Row caps: 10 for lists, 25 for expiring licences and exception lists.

**Section shapes**

- `boe_activity`: `total`, `linked_to_allotment`, `direct`, `pending_licence_mapping`, `without_invoice_no` (numbers); `recent`, `pending_mapping`, `recently_modified` (rows: `id`, `bill_of_entry_number`, `bill_of_entry_date`, `company_name`, `invoice_no`, `modified_on`, `allotment_links`, `licence_items`, `mapping_status`); `monthly_trend`.
- `invoice_activity`: `total`, `paid`, `partially_paid`, `unpaid`, `open` (numbers); `total_amount_inr`, `paid_inr`, `outstanding_inr` (2-dp strings, INR); `by_direction.{sale,purchase}` (`total`, `outstanding_inr`); `not_tracked`; `recent` (rows: `id`, `invoice_number`, `invoice_date` nullable, `direction`, `party_name` nullable, `total_amount_inr`, `outstanding_inr`, `status`).

### 9.4 Frontend contract and resilience

- `payloadContract.ts` validates the full payload and single sections against the same field checks. A mismatch becomes a section error, plus a logged violation naming the path. A missing section is a violation, never an empty one.
- `useDashboardData.retrySection(section)` sends `?section=<name>&refresh=1`, merges only that section, and ignores a second click while the first is in flight. A failed retry shows a section error with a Retry button.
- `DashboardSection` shows a Retry button on error and a skeleton while a retry is in flight.
- Classification of BOEs as allotment or direct is shown through the Allotments column (0 means direct) and the summary tiles. It is not a separate column.

### 9.5 Files changed

Backend:
- `backend/apps/license/services/dashboard_summary.py`: `RETRYABLE_SECTIONS`, `user_can_see`, `build_section_on_its_own`
- `backend/apps/license/views/dashboard.py`: `?section=` handling
- `backend/apps/license/tests/test_dashboard_sections.py` (new)

Frontend:
- `frontend/src/components/dashboard/payloadContract.ts`: `parseDashboardSection`, `RetryableSection`
- `frontend/src/components/dashboard/useDashboardData.ts`: `retrySection`, `retrying`, `SECTION_RETRY_FAILED`
- `frontend/src/components/dashboard/DashboardSection.tsx`: Retry button and retrying skeleton
- `frontend/src/components/dashboard/BoeActivity.tsx`, `InvoiceActivity.tsx`: retry props
- `frontend/src/pages/Dashboard.tsx`: retry wiring for the two sections only
- Tests: `payloadSection.test.ts`, `useDashboardRetry.test.tsx`, `InvoiceActivity.test.tsx`, `BoeActivityRetry.test.tsx`, `pages/DashboardSections.integration.test.tsx`, `e2e/dashboard.sections.spec.ts`

### 9.6 Tests and results

| Gate | Result |
|---|---|
| Backend dashboard suites (`test_dashboard_sections`, `test_dashboard_summary`, `test_dashboard_balance_cif`, `test_dashboard_c969_link_review`) | 48 passed |
| Invoice aggregation vs trade model properties (dev DB, 560 invoices) | 11 of 11 match |
| Live section endpoint over HTTP (isolated backend) | `boe_activity` 200, `invoice_activity` 200, unknown section 400, licence section 400 |
| Typecheck | passes |
| Lint | 0 errors; no warnings in dashboard files |
| Vitest, full suite | 93 files, 716 tests passed |
| Production build | passes |
| Playwright, sections spec | 5 passed (both sections, BOE failure isolation, malformed invoice, empty invoice, failed retry then recovery) |
| Playwright, boe-contract and responsive dashboard specs | 4 passed (from earlier in this session) |
| Live browser check (isolated backend on 8010, Vite on 5174 using the proxy) | BOE 10 rows, invoices 10 rows, one dashboard request, 0 page errors, 0 contract violations |

Note on retries: the shared axios client already retries a failed GET twice, with backoff. A retry that keeps failing therefore reaches the server three times. The browser test models that.

### 9.7 Remaining issues

1. **The running server on port 8000 must be restarted.** PID 9723 is `--noreload` and serves old code, so both sections show their errors until it is restarted. Port 8000 now also has a second listener (27969). Confirm which process should own the port. This is an environment fact, not a code fault. I did not stop either process.
2. `frontend/.env` points the browser at `http://localhost:8000` and bypasses the Vite proxy. Changing it to an empty value would route through the proxy. I did not change it, because other developers may depend on it.
3. Desktop layout: the right-hand columns of the BOE and allotment tables are clipped at the card edge, and the fixed action bar overlaps content in full-page captures. Neither is fixed here.
4. The backend full test suite has not been run in this change. The ten licence-list tests that fail on HEAD are not caused by this change.

## 10. Status

Dashboard: IN_PROGRESS. The BOE and invoice sections render real data in the live check. Not complete: the stale server must be restarted, the layout issues in 9.7 remain, and the brief's acceptance criteria are not all verified.

## 11. Allotment activity (2026-11-02)

Scope: the Allotment Activity card only. Balance formulas are unchanged. DEC-010 and ISS-008 remain open.

### 11.1 Explore

| Source | What it provides |
|---|---|
| `AllotmentModel` | `company` (customer), `item_name`, `required_quantity` (original quantity), `cif_fc`, `bill_of_entry` M2M (BOE links), `is_boe` (a cached flag; the engine warns it can be stale) |
| `AllotmentItems` | `item` → `LicenseImportItemsModel` → `license` (licence), `cif_fc`, `qty` (quantity placed on a licence item) |
| `BOEAllotmentAllocation` | `allotment_item`, `row_details`, `allocated_qty`, `allocated_cif_fc`; counted when `status = ACTIVE` and `is_current` |
| `LicenseBalanceCalculator._annotate_allotment_contribution` | `allocated`, `matched`, `contributed` (CIF) and their quantity twins, per item |
| Cancellation | None. There is no cancelled state. Cancellation is a hard delete (ISS-010). |

Figures in the dev database (44 allotments, 100 items): **0 allocation rows**, 37 allotments linked to a BOE through the M2M relation, 7 open, 4 with no items.

### 11.2 Definitions

| Concept | Source | Display |
|---|---|---|
| Original quantity | `AllotmentModel.required_quantity` | Original qty |
| Placed on licence items | Σ `AllotmentItems.qty` | Shown under the original as the allocated quantity |
| Unplaced | `max(required − placed, 0)`, the model's own `balanced_quantity` definition | "unplaced" line under the original |
| Allocated CIF | Σ `AllotmentItems.cif_fc` | Allocated CIF (FC) |
| Utilised CIF | Σ engine `matched` (min of item CIF and BOE-allocated CIF) | Utilised CIF (FC) |
| Remaining reservation | Σ engine `contributed`. Zero for every BOE-linked allotment (ISS-008). | Remaining reservation, with remaining quantity beneath |
| Not reserved | `allotted − consumed − reserved`. Zero when no BOE is linked; the ISS-008 gap otherwise. | Amber "Not reserved" line |
| Status | Derived from engine figures (see below) | Badge, plus BOE count |

Status definitions:
- **Fully utilised**: allocated > 0 and utilised ≥ allocated CIF.
- **Partly utilised**: allocated > 0 and utilised below the allocated CIF.
- **BOE linked, no allocation**: a BOE link exists and no allocation rows exist.
- **Open**: none of the above.

### 11.3 Critique: findings

| ID | Finding | Evidence | Resolution |
|---|---|---|---|
| A-1 | A partly utilised, BOE-linked allotment was labelled **Consumed**, because the engine reports zero reservation for it. | Test `test_a_partly_utilised_boe_linked_allotment_is_never_labelled_consumed` fails on the old rule | Status now comes from utilised against allocated |
| A-2 | Reference, licence, original quantity, BOE count and section totals were missing. | Old contract: id, item, company, date, four CIF and quantity fields, status | Added, additively, with the contract tests |
| A-3 | **37 of 44 allotments show zero utilised CIF.** Their BOEs are linked by M2M but have no allocation rows. | Probe: 0 allocation rows | Shown as "BOE linked, no allocation", not as zero consumption. The business decision is open (DEC-010 Q2, Q4) |
| A-4 | Of the 37, the BOE debit rows match the allotment items in **11** cases. Four have no debit rows. Several CIF and quantity differences look like rounding or unit errors (for example 99 against 99,000). | Read-only cross-check of RowDetails against allotment items | Not corrected. Recorded here as a data-quality issue |
| A-5 | **Not reserved totals 4,808,628.02**, which matches the figure in the ISS-008 register. | Section total equals the ISS-008 data run | Confirms the gap is real. Disclosed on the card |
| A-6 | Cancelled allotments: none exist. A deleted allotment disappears. | Test `test_deleting_an_allotment_removes_it_from_every_figure` | No cancelled status is shown |
| A-7 | Duplicate allotments: none in the dev data (grouped by customer, item, invoice, quantity, CIF and arrival date). | Probe: 0 groups | No de-duplication was needed |
| A-8 | Direct BOEs must not appear as allotments. | Test `test_a_direct_boe_is_not_an_allotment_and_does_not_change_the_section` | Verified |
| A-9 | A BOE linked to several allotments, or an allotment linked to several BOEs, must not double-count. | Tests `test_several_boes_against_one_allotment…`; the M2M count is `distinct` | Verified |
| A-10 | The allotment-side reserved total must equal the licence-side engine total. | Test `test_the_section_totals_reconcile_and_match_the_licence_side_engine`; live: 207,550.16 = 207,550.16 | Verified |
| A-11 | Columns clipped at the card edge. | Earlier screenshots | The card takes the full row at `xl`, and the table has a minimum width inside a labelled, focusable scroller |

### 11.4 Contract

`GET /api/dashboard/?section=allotment_activity` returns `meta` and `allotment_activity`. The full payload carries the same section.

- `total` and `counts` (open, partly_consumed, consumed, boe_linked)
- `totals`: allotted, consumed, reserved, not_reserved. These are sums over every allotment in scope, not only the recent rows.
- `recent` (up to 10): `id`, `reference` (`#<id>`), `item_name`, `company_name`, `created_on`, `licences` (up to 5, distinct, with `id` and `license_number`), `licence_count`, `original_quantity`, `allocated_quantity`, `unplaced_quantity`, `allotted_cif`, `consumed_cif`, `reserved_cif`, `not_reserved_cif`, `remaining_quantity`, `boe_count`, `status`

Quantities and CIF are 2-decimal strings. Every CIF figure comes from the engine's annotations. The only derived figures are `not_reserved_cif` (a subtraction of engine outputs) and `unplaced_quantity` (the model's own definition).

### 11.5 Financial integrity

- The identity holds on every scope: allotted = consumed + reserved + not reserved (test and live).
- The allotment side and the licence side give the same reserved total (207,550.16). They are two independent paths to one figure.
- A partly used BOE-linked allotment is never shown as fully utilised.
- Nothing is counted twice: one row per allotment, however many BOEs are linked.
- No formula was added to React. The frontend formats the figures and sorts on them.

### 11.6 Files changed

- `backend/apps/license/services/dashboard_summary.py`: `_allotment_status` (new rule), `build_allotment_activity` (rebuilt), imports and `LICENCE_LIST_LIMIT`
- `backend/apps/license/tests/test_dashboard_allotments.py` (new, 14 tests)
- `frontend/src/components/dashboard/AllotmentActivity.tsx` (rewritten)
- `frontend/src/pages/dashboardContract.ts`: `AllotmentActivityRow`, `AllotmentActivity`
- `frontend/src/components/dashboard/payloadContract.ts`: allotment shape
- `frontend/src/components/dashboard/dashboardLinks.ts`: `licenceOverviewPath`
- `frontend/src/components/dashboard/fixtures.ts`: sample allotment
- `frontend/src/pages/Dashboard.tsx`: retry wiring and the full-row class for this card only
- Tests: `AllotmentActivity.test.tsx`, `allotmentContract.test.ts`, `pages/DashboardAllotment.integration.test.tsx`, `e2e/dashboard.allotments.spec.ts`

### 11.7 Tests and results

| Check | Result |
|---|---|
| Backend allotment tests (14): open, partial, full, several BOEs, BOE link without allocation, direct BOE, deletion, two licences, reconciliation with the licence side, date range, query budget, contract, regression | 14 passed |
| All backend dashboard suites (5 files) | 62 passed |
| Frontend, allotment-specific (component, contract, integration) | 25 passed |
| Frontend, dashboard subset (16 files) | 146 passed |
| Frontend, full suite | 96 files, 741 tests passed |
| Playwright, allotment spec (4): desktop columns inside the card, phone scroll, link targets, isolated failure and retry | 4 passed |
| Playwright, all dashboard specs | 12 passed |
| Typecheck, lint, production build | Typecheck passes (after one fix to the test typing). Lint: 0 errors, 9 warnings, none in dashboard files. Build passes |
| Live check, isolated backend and Vite through the proxy | 10 rows, no overflow, unplaced quantities rendered, 0 page errors, 0 contract violations |

Keyboard scrolling of the table region was **not verified**. In headless Chromium, End and ArrowRight did not move a focused region, while the wheel did. The test asserts focus and wheel scrolling only.

### 11.8 Remaining issues

1. **DEC-010 and ISS-008 are open.** They decide whether a BOE draw-down on a linked allotment counts as utilised and whether the rest is reserved. Until they are answered, the card shows the engine's figures and the gap, not a corrected value.
2. **A-4 data quality.** The BOE rows and the allotment items disagree on 33 of 37 linked allotments, mainly on CIF and sometimes on quantity. Some of this may be unit or exchange-rate differences. Not investigated further.
3. **Four allotments have no items.** They show original quantity, zero allocated, and no licence.
4. **The stale server on port 8000** still needs a restart before this card is visible in your browser.
5. The backend full suite has not been run for this change.

## 12. Autonomous completion pass (2026-11-02)

### 12.1 Environment (Phases 0–1)

Root cause of every "did not match the expected format" error in the browser:

| Finding | Evidence | Action |
|---|---|---|
| A launch agent `com.license-manager.backend` ran `scripts/development/serve-backend.sh`: `runserver 127.0.0.1:8000 --noreload`, `KeepAlive` on. It respawned the stale process each time it was killed. | `launchctl print`, `launchctl` restart at 15:17 after the stale process was stopped | Unloaded with `launchctl bootout`. The plist stays on disk. Restore with `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.license-manager.backend.plist` |
| The browser reached the stale process. `frontend/.env` sets `VITE_API_URL=http://localhost:8000`, which resolves to 127.0.0.1 and was answered by the `--noreload` process, not by the IDE-owned server on `*:8000`. | `lsof` listeners; `curl` to `localhost:8000` returned the pre-change allotment shape | Stopped the stale process (project-owned, confirmed by command and working directory) |
| The IDE-owned backend (PyCharm → debugpy, PID 35639) on `*:8000` serves the current code and reloads on save. | Probe: `section=allotment_activity` returns `totals`, `unplaced_quantity` and the other current fields | Kept. Not killed. |
| Vite on 5173 (PyCharm → `npm run dev`, PID 35611) is current. | Playwright run against `http://localhost:5173/dashboard` | Kept |

**Configuration decision.** The direct base URL is kept (`VITE_API_URL=http://localhost:8000`), not the Vite proxy. Reason: the IDE owns the running Vite process, and the proxy would need a restart of it. The proxy stays the documented alternative. `.env.example` already matches.

**Guard.** `scripts/development/check-dev-ports.sh` is read-only. It reports listeners on 8000 and 5173, fails on more than one backend listener, and warns when the `--noreload` launch agent is loaded.

Not touched: a Vite process from a baseline copy (`/private/tmp/lm-baseline`, port 5180). It does not serve the dashboard.

### 12.2 Browser verification (Phase 13, partial)

Against `http://localhost:5173/dashboard`, real backend on 8000, login by token:

| Check | Result |
|---|---|
| API requests | `/api/auth/me/`, `/api/dashboard/` and `/api/masters/companies/` only. No failed (≥400) responses. |
| Console | No errors or warnings |
| Uncaught exceptions | None |
| BOE Activity | 8 columns, none clipped, no horizontal overflow at 1440 px |
| Allotment Activity | 10 columns, none clipped |
| Invoice Activity | 7 columns, none clipped |
| Footer | The shell's sticky quick-actions footer begins 66 px below the last card when scrolled to the bottom. No overlap. |
| Mobile (390 px) | No document overflow |
| Dark theme (`localStorage.theme = dark`) | Renders. BOE card readable. |

The OS colour scheme does not switch the app's theme. The app uses its own stored preference (`ThemeContext`), which is expected.

### 12.3 Licence health (Phase 7)

Each dashboard count matches the licence list endpoint with the same filter the link uses:

| Count | Dashboard | List endpoint |
|---|---|---|
| Missing DGFT (live balance < 200) | 111 | `is_null=True` → 111 |
| Expired | 135 | `is_expired=True` → 135 |
| Not expired (active) | 87 | `is_expired=False` → 87 |
| Expiring within 7 / 15 / 30 / 60 days | 0 / 6 / 13 / 20 | `license_expiry_date_from/to` → 0 / 6 / 13 / 20 |
| Expiry bands | 135 + 0 + 6 + 7 + 7 + 67 = 222 | Partition check passes |

Known difference: the list uses the server's local date (`date.today()`), and the dashboard uses `timezone.localdate()`, which follows `settings.TIME_ZONE = "UTC"`. The two can disagree for licences expiring today during the local-to-UTC offset window. Recorded, not changed. A single business date needs an explicit decision.

Thresholds are unchanged: live Null-DFIA is ₹200 (licence list), and the persisted `flags.is_null` is ₹500 (signal). They are not unified.

### 12.4 Performance and access (Phases 9, 11)

| Measurement | Result |
|---|---|
| Uncached full payload, dev database (222 licences) | 0.23–0.31 s |
| Single section (`boe_activity`, `invoice_activity`, `allotment_activity`) | about 26 ms each |
| Cached full payload | about 10 ms |
| Unauthenticated request | 401 |
| Invalid token | 401 |
| Section a role does not grant | 403 (tested) |
| Unknown or licence section | 400 (tested) |

### 12.5 Decision blocking Phase 6 (needs your answer)

The approved D-1 rule (`licence-management-v2-financial-engine.md`): utilised = BOE + allotment + billed-without-BOE, and available = original − utilised, unfloored. It is implemented in `financial_position.py` and is not used by any consumer, including this dashboard. The same document says consumers may switch only after three preconditions are resolved:

- **P1:** verify original CIF against the engine for every licence.
- **P2:** sign off the residue defect. Dropped residue on partly used allotments is 629,911.48 FC across 56 items. Fixing it changes the figures for those items.
- **P3:** billed-without-BOE has no licence-level link yet, so it is 0 everywhere.

The dashboard currently shows the canonical engine's figures, which are floored at zero. Over-utilisation is shown as a separate figure (56 licences, $13,949,843.08 floor), so nothing is hidden.

**Question for you:** Should the dashboard headline (Utilised and Available CIF) switch to the D-1 figures now, showing over-utilisation unfloored and treating billed-without-BOE as 0 until P3 is resolved? Or should it stay on the canonical engine until P2 is signed off?

Recommendation: keep the canonical engine as the headline until P2 is signed off. Show D-1 over-utilisation as a labelled reconciliation line now. Switching the headline before P2 changes reported figures without sign-off.

Phases 6 headline work waits on this answer. Phases 7–13 continue.

### 12.6 Test results at this pass

| Suite | Result |
|---|---|
| Full backend (`pytest -n 4 --create-db`) | 3,327 passed, 1 skipped, 2 xfailed, 11 failed, 4 errors |
| Full backend, classification | 9 failures and 1 collection error are the tracker's ISS-019 baseline. `test_license_overview_summary_view` also fails on the committed code (reproduced). `test_license_ledger_package_jobs` (1 failure, 1 error) and `test_invoice_secure_links` (2 errors) are order-dependent: they share the username `ledger-package-owner` across workers. Run alone, the two files pass 11 of 11. |
| Dashboard backend (5 files) | 62 passed |
| Frontend unit, full | 96 files, 741 tests passed |
| Frontend typecheck | Passes |
| Frontend lint | 0 errors, 9 warnings, none in dashboard files |
| Frontend production build | Passes |
| Dashboard browser suite (Playwright) | 13 passed |
| Live browser audit, 5173 | Clean (see 12.2) |

Not changed in this pass: the ISS-019 failures and the username collision in the ledger and invoice test files. Both are outside the dashboard, so they are recorded here rather than fixed.
