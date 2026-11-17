# Licence Overview "Total Allotted" double-counting audit (Phase 1, 2026-11-17)

Baseline `feature/v5` @ `9fec5b48`. Engine (`balance_calculator.py`) **not modified**. Read-only DB numbers from the local
dev DB (`localhost`/`lmanagement`, read-only transaction, rolled back) at 2026-11-17T02:22:51 — the DB is re-synced
periodically, so values are a snapshot. Scripts outside the repo: `/tmp/erp_audit/{check_db,recon,partial}.py`.

## Verdict

The double count is real but **not where assumed**. The summary card "Allotted CIF" and the engine agree on all 102
live licences. The defect is the **Allotments tab footer "Total Allotted"**, which summed gross `cif_fc` of every
allotment, including allotments already represented by a BOE (whose CIF is already in BOE CIF).

Separately, the engine's own rule for BOE-linked allotments **zeroes the whole allotment on any M2M link**, so a partly
consumed allotment's remainder is not counted. That is a **rule-vs-code conflict escalated to the owner** (not changed).

## Trace

| Place | file:line | Nets BOE-linked allotments like `calculate_allotment`? |
|---|---|---|
| Engine | `balance_calculator.py:711-835` `_annotate_allotment_contribution`, `:970` `calculate_allotment`, `:1196` bulk | reference; single = bulk on 102 licences |
| Snapshot | `balance_snapshot.py:160, :248` `outstanding_allotted_cif` | yes |
| Summary card "Allotted CIF" | `license_overview_summary.py:65,145` → `overview-summary` → `LicenseMetricsGrid.tsx:66-68` | yes (0 differences) |
| **Allotments tab "Total Allotted"** | `license_overview_allotments.py:37-44` raw `Sum(cif_fc)` → `overview-allotments` → `AllotmentsTab.tsx:72` client sum | **no — root cause** |
| Ledger builder rows | `license_balance_ledger_builder.py:458, :912` | yes |
| Stored item `allotted_value` / Items tab | `core/scripts/calculate_balance.py:59` → `items.py:107`; `license_overview_items.py:45` | yes (AT type only) |
| Item pivot | `item_pivot_generate.py:441-447`; `item_pivot_row.py:65-72` | binary M2M exclusion only |
| Plan enforcement, item_usage, condition_pool, `header.py:447`, `items.py:168/195`, `sync_licenses.py:252`, `planning_usage_reconciliation.py:122` | as cited | binary `allotment__bill_of_entry__isnull=True` |
| `license_balance_mv` | `core/materialized_views.py:58-62, :94` | **no** (raw `ai.cif_fc`, row fan-out, `cif_inr`); no reader found |

## Root cause

1. `list_allotment_rows` returned only gross `cif_fc` per allotment; the link to a BOE was a status label only. The tab
   summed it in TypeScript. DB check: tab − engine = **4,144,946.34** = exactly Σ `cif_fc` of M2M-linked allotments.
2. Engine practice: `contributed = 0` if the allotment has **any** `BillOfEntryModel.allotment` link, else
   `max(cif_fc − min(cif_fc, Σ allocations), 0)`. `BOEAllotmentAllocation` has **0 rows** (no production writer), so
   partial netting never happens in practice.

## Lifecycle scenarios (original CIF 100)

| Scen. | Representable today? | Engine ALLOTMENT / customs available | Old tab footer | Fixed tab footer | Expected per rule |
|---|---|---|---|---|---|
| A allot 40, no BOE | yes | 40 / 60 | 40 | 40 | 40 / 60 |
| B allot 40 + linked BOE 40 | yes (M2M) | 0 / 60 | 40 (double) | 0 | 0 / 60 |
| C allot 40 + linked BOE 15 | M2M zeroes all | 0 / 85 (**25 dropped**) | 40 | 0 | 25 / 60 — **owner decision** |
| C′ same via allocation row | only via `create_boe_allotment_allocation` (no prod writer) | 25 / 60 | 40 | 25 | 25 / 60 |
| D allot 60 + BOEs 20+15 | M2M | 0 / 65 (25 dropped) | 60 | 0 | 25 / 40 — **owner decision** |
| E multiple allotments | yes | per allotment | gross sum | per allotment outstanding | — |
| F cancellation/reversal | **not representable**: no allotment cancel status; release fields + `AllocationVersion` have no writer (doc 05 O7) | — | — | — | needs model decision |
| G unmatched BOE | BOE debits count in BOE CIF; no allotment touched | — | — | — | consistent |
| H duplicate BOE | 0 duplicates (number+date unique constraint, migration 0013) | — | — | — | guarded |

Tests: A, B, C (pinning current M2M zeroing), C′, D in
`backend/apps/license/tests/test_license_overview_allotments_view.py::OverviewAllotmentsOutstandingCifScenarioTests`;
engine pins `test_balance_calculator.py:1141` (linked → 0), `:1188` (allocation 300 of 500 → 200).

## Database reconciliation (local snapshot)

Row counts: licences 222 (102 live), allotments 47, allotment items 104, BOEs 1,044, BOE row details 8,159.

| Metric (102 live licences, FC) | Existing (tab footer) | Canonical (engine) | Difference |
|---|---:|---:|---:|
| Original CIF | 38,974,414.57 | 38,974,414.57 | 0.00 |
| Total Allotted (tab footer) | 4,999,764.29 | — | — |
| Outstanding Allotment (ALLOTMENT CIF) | 4,999,764.29 | 854,817.95 | **4,144,946.34** |
| BOE CIF (`calculate_boe_debit_total`) | — | 13,184,392.63 | — |
| BOE CIF (`calculate_debit`, invoice-represented excluded) | — | 787,057.74 | — |
| Billed CIF without BOE (sale) | — | 29,894,238.25 | — |
| Utilised CIF (customs engine) | — | 14,039,210.58 | — |
| Available CIF (customs engine) | — | 24,935,203.99 | — |
| Utilised / Available (financial engine, incl. opening + purchase terms) | — | 31,536,113.94 / 6,661,518.32 | — |

45 licences differ (tab vs engine); card vs engine: 0 differ. Top differences (engine allotment 0 in each):
0311050703 423,394.03 · 0311051202 366,628.85 · 0311051203 340,333.24 · 5211018714 333,314.22 · 0811016790 234,094.00 ·
0311054433 198,663.25 (financial available −398,086.39) · 0311053006 198,467.93 · 0311053078 167,177.78 ·
3411007532 158,550.56 · 0311052365 139,339.86.

Data checks: `BOEAllotmentAllocation` 0 rows · M2M links 38 (38 allotments) · BOEs linked to >1 allotment 2 · allotments
linked to >1 BOE 0 · links where the BOE has no rows on the allotment's licences 3 · duplicate BOE number+date 0 ·
hidden BOEs 508 · partial links (linked BOE debit < allotment CIF) 57 (allotment, licence) pairs, remainder zeroed by the
engine 422,766.62 (of which 239,495.66 has no linked BOE debit on that licence at all; inference — a BOE debit may also
cover goods outside the allotment).

**No historical records were changed.** The fix changes display only; stored values are untouched.

## Fix implemented (display path only; **BUSINESS-RULE (display) CHANGE**, additive API)

- `backend/apps/license/services/license_overview_allotments.py`: each row gains `outstanding_cif_fc` = Σ of the engine's
  per-row `contributed` for that allotment on this licence (`LicenseBalanceCalculator.get_allotment_rows`), one batched
  query. `cif_fc` (gross) unchanged. Query count 5 → 6 (constant).
- `frontend/src/pages/license-overview/AllotmentsTab.tsx`: footer headline "Outstanding Allotted" = Σ `outstanding_cif_fc`
  (equals the summary card / engine ALLOTMENT CIF); "Gross allotted" shown separately. Each component stays visible;
  nothing clamped.
- API contract: additive field only. Display contract: footer figure and label change.

## Escalations (owner decides — not implemented)

1. **M2M link = full consumption?** Engine zeroes the remainder of partially billed allotments (C/D; 57 pairs,
   422,766.62 locally). Options: (a) keep; (b) count `cif_fc − linked BOE debit on this licence` (needs a rule for BOEs
   that cover goods outside the allotment); (c) introduce a production writer for `BOEAllotmentAllocation`.
2. Links to hidden or other-licence BOEs still zero the allotment (3 links).
3. `license_balance_mv` is non-netted and fanned out; unread. Retire or fix.
4. Item pivot / plan enforcement use binary exclusion; equal to the engine only while the allocation table is empty.
5. Allotment cancellation/reversal (scenario F) has no model support.
6. Allotments tab quantity total mixes units (doc 08 C3) — unchanged.
