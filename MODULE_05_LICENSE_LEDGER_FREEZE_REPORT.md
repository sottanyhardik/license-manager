# MODULE 05 — LICENSE LEDGER — FREEZE REPORT

**Verdict: BLOCKED — NOT FROZEN.**

Real defects were found and fixed, including a P0 that made the primary ledger
endpoint return HTTP 500. But Module 05 cannot be frozen: Module 04 did not pass
its gate (a hard precondition), and several mandatory Module 05 gates have not
been executed. Nothing below is estimated or assumed — every number was measured.

| Item | Value |
|---|---|
| Branch | `feature/V2` |
| Starting commit | `aed3756c` |
| Ending commit | uncommitted working tree (see §8) |
| Module 04 status | **NOT FROZEN** — see `MODULE_04_INDEPENDENT_REVERIFICATION.md` |
| Production touched | **NO** |

---

## 1. Measured baselines

| Suite | Before | After |
|---|---|---|
| Backend, default command | 223 collected — `4 failed, 219 passed` | **2250 collected — 2212 passed, 0 failed, 38 skipped** |
| Backend, tests + apps | `21 failed, 723 passed, 1117 errors` (+2 files uncollectable) | **2212 passed, 0 failed** |
| Frontend `vitest` | `5 failed, 241 passed` | **246 passed, 47/47 files** |
| Frontend `tsc --noEmit` | **12 errors** | **0 errors** |
| Frontend `eslint` | 0 errors, 60 warnings | 0 errors, 60 warnings (cosmetic `react-refresh`) |

The jump from 223 to 2250 is the headline finding: `pytest.ini` had
`testpaths = tests`, so ~87% of the suite — including every License Ledger test —
had never run. See `MODULE_04_INDEPENDENT_REVERIFICATION.md` §1.1.

---

## 2. P0 — the primary ledger endpoint returned HTTP 500

`GET /api/license-ledger/{id}/ledger_detail/` — consumed by **four** frontend
call sites — raised an uncaught `KeyError` on every request.

- `canonical_ledger_service.build_canonical_ledger_dataset()` emitted 8 keys.
- `CanonicalLedgerSerializer` declared `license_number`, `license_date`,
  `expiry_date` as required with no `allow_null`; DRF re-raised `KeyError`.
  (`exporter_name` / `port_name` were `allow_null` and silently degraded to
  `null`, hiding half the gap.)
- The view serialises the dataset directly, so there was no fallback.

**Fixed in the service** (the single source of truth), not by weakening the
serializer or patching the view:

- New `_extract_license_metadata()` — ONE shared extractor covering both
  `LicenseDetailsModel` and `IncentiveLicense`, whose field names differ
  (`port` vs `port_code`). Field mapping verified against the models, not guessed.
  DFIA falls back to the `archived_exporter_name` snapshot when the exporter
  company was deleted.
- `_get_license_object()` now uses `select_related`.
- Dataset docstring corrected — it had also mis-documented `company_utilizations`
  as a list when it is a dict keyed by company_id, and omitted `affects_balance`.

`test_ledger_api_canonical_migration.py`: **16 failed / 2 passed → 18 passed.**

---

## 3. Other real defects found and fixed

| # | Defect | Severity | Status |
|---|---|---|---|
| 1 | **Materialized views could never match a row.** `apps/core/materialized_views.py` filtered `rd.transaction_type = 'DEBIT'` / `IN ('DEBIT','CREDIT')`, but the column is `max_length=2` holding `'C'`/`'D'`. Utilisation was always 0, so `license_balance_mv.balance_cif` and `item_balance_mv.available_*` were inflated by the entire debit total. | Latent (read helpers have 0 callers, but the views are created by migration and refreshed on every licence/BOE/allotment change) | **Fixed** — SQL now interpolates the canonical constants so it cannot drift again; 5 regression tests added, including one asserting the codes fit the real column. |
| 2 | **Deprecated ledger aliases rendered as floats.** `available_balance`/`db_balance` were `SerializerMethodField`s returning raw `Decimal`, which the JSON renderer coerced to float — so the same number was a 2dp string under one key and a float under another. Direct violation of the no-float-money rule. | Medium | **Fixed** — `DecimalField(source="license_running_balance")`. |
| 3 | **`AllotmentModel.required_value_with_buffer` does not exist.** Read as a model attribute at 3 sites in `apps/allotment/services/`; only ever set as a dict key in `views_actions.py`. Raised `AttributeError` instead of falling through to the author's own `or` default. | Latent (`AllocationService` has 0 production callers) | **Fixed** — `getattr(..., None)`. |
| 4 | **`AllotmentsTable.tsx` used `api`, `toast`, `openPdfPreview` without importing them** — `TS2304`, i.e. a `ReferenceError` at click time. Every Copy / Preview PDF / Download action in the Allotments table was broken. Shipped inside Module 03's "FINAL COMPLETE FREEZE". | High (user-facing) | **Fixed** — imports restored from the canonical paths used by the sibling `LicensesTable.tsx`. |
| 5 | **"Total Value" always displayed 0.** `LicenseLedgerDetail.tsx` read `ledger.total_value`, which exists nowhere in the canonical contract. | Medium (user-facing wrong number) | **Fixed** — see §4. |
| 6 | **`sion_norms` unavailable**, so the DFIA "SION Norms" row always rendered N/A. | Low | **Fixed** — restored to the dataset using the legacy definition, DFIA-only, N+1-free. |
| 7 | **Duplicate aggregate query per snapshot.** `calculate_purchase_credit_for_licenses` was issued twice — once directly by `balance_snapshot`, once inside `calculate_opening_balance_for_licenses`. | Low (performance) | **Fixed** — computed once and passed down via an optional, backward-compatible parameter. Overview summary 50 → **47** queries. |
| 8 | **Django 6.0 `Mock` incompatibility** in `test_balance_calculator.py` — the same defect the Module 04 report claimed to have fixed, but only in `tests/`; the `apps/` copy was never run. | Test-only | **Fixed** using the established pattern. |
| 9 | **13 stale milk/SION planner tests.** Commit `3c9ea7e3` deliberately changed `dwp_price` 5 → 6.5 and never updated the tests. | Test-only | **Fixed** — expectations re-derived from the algorithm (see §5). |

---

## 4. Business-rule decisions taken on evidence (not invented)

**`total_value` — deliberately NOT added to the backend.** Three competing
definitions exist:
1. `LicenseDetailsModel.opening_balance` = `calculate_credit()` = Σ export-item
   `cif_fc`. Confirmed identical, but **DFIA-only** — `IncentiveLicense` has no
   export items; its face value is `license_value` in INR.
2. The deleted legacy `build_dfia_ledger_detail()` defined it as
   `total_purchase_cif` — Σ purchase-line CIF over `PURCHASE` **and**
   `COMMISSION_PURCHASE`, in float.
3. `ledger_service.prepare_dfia_data` uses Σ `PURCHASE` lines only.

Ambiguous ⇒ no new backend field. The frontend now reads
`totals.total_purchases`, which is already in the contract, already `Decimal`,
and already carries the USD-for-DFIA / INR-for-incentive pairing the page
hardcodes — the closest faithful equivalent of the legacy meaning.

**`sion_norms` — restored using the legacy definition only.**
`trade.lines → line.sr_number → .items → .sion_norm_class.norm_class`,
comma-space joined, first-seen dedup, DFIA-only, `''` otherwise. Documented
explicitly in the dataset docstring as a *presentation-layer derivation, not a
ledger fact* — there is no per-transaction norm in the data model.

---

## 5. Verification method for the planner constants

The 13 milk/E1/E5 failures were not "fixed" by pasting observed output. The
documented `split_milk_0404` spec was independently re-implemented in Decimal
(branch on `avg = balance/qty` against `[dwp_min_price, dwp_price]`,
`dwp_qty = (balance − swp·qty)/(dwp_min − swp)`), all 10 affected scenarios were
recomputed from it, and only then compared with engine output: **0 mismatches**.

That equality is the evidence that the 5 → 6.5 price change introduced no defect.
Three scenarios had their input balances raised (300 → 350/375) because at the
new ceiling the old inputs fell into a different branch and would have silently
destroyed the coverage the tests exist to provide. Each affected file now derives
its expectations from one `DWP_CEILING` constant tied back to `MILK_CONFIG` by a
guard test, so the next price change fails loudly in one place.

---

## 6. Performance

| Path | Before | After |
|---|---|---|
| Canonical ledger, 20 transactions | 30 queries | **6** |
| Canonical ledger N+1 growth (3 → 10 txns) | 13 → 20 (1.78×) | **6 → 6 (1.00×)** |
| Licence overview summary | 50 queries | **47** |

Achieved by `Prefetch(..., to_attr=...)` carrying the identical filter (safe:
both line models declare `ordering = ["id"]`, so rows, order and sums are
unchanged), `select_related` on company FKs, one bulk company-name query
replacing a per-company lookup, and the duplicate-aggregate fix in §3.7.

---

## 7. GATES NOT MET — why this is BLOCKED

### 7.1 Module 04 is not frozen (hard precondition)
Master Sync is complete and now ~100% covered, but **no code path invokes it**:
`check_delete_on_peers` and `sync_from_peer` have zero callers, `SYNC_PUSH_ON_SAVE`
is never read, and none of the three `sync.*` Celery tasks are in the beat
schedule. Global delete protection is therefore inactive. Full detail in
`MODULE_04_INDEPENDENT_REVERIFICATION.md` §3.

### 7.2 The frontend is still a source of financial truth
Mandated: *"The frontend must never be the source of financial truth."* Audited
and **not remediated**. Verified instances include:

- `LedgerTab.tsx:229-232` recomputes a BOE running balance client-side in
  IEEE-754 floats, and `Math.max(0, running)` **clamps negatives to zero** — an
  over-utilised licence displays a balance of 0 instead of the over-utilisation.
- `LicenseBalanceModal.tsx:1081-1083` recomputes
  `quantity − debited_quantity − allotted_quantity` in the UI (untested).
- `PlanningEditor.tsx` — ~11 client-side `reduce` sums plus 8 subtraction sites
  deriving remaining/over-by.
- `AllotmentAction.tsx` — a full client-side allocation clamp engine; its own
  comment admits it duplicates a backend check.
- `AllotmentFormModal.tsx` / `useMasterFormCalculations.ts` / `NestedFieldArray.tsx`
  — CIF↔INR FX arithmetic in the browser, several expressions duplicated verbatim.
- `LedgerTab.tsx:514` / `:523` — the UI decides whether to trust the server's
  balance or its own per-item sum.

Fixing these properly requires the backend to publish the per-row running
balance and the derived caps. That is a real feature, not a cleanup, and was not
attempted rather than half-done.

### 7.3 Duplicate calculations not consolidated
The audit identified ~16 families of duplicated financial logic, e.g.
`credit − (boe_debit + allotment)` implemented 4×; the financial-balance formula
3×; the opening-balance 3-way gate 3×; item available-value 4 ways; item
available-quantity 4 ways; `apply_transaction_to_balance` is the declared
reference implementation yet is **never called in production** while
`canonical_ledger_service` re-inlines the same CREDIT/DEBIT switch twice.
Only the transaction-type literals were consolidated (§7.6). The rest stands.

### 7.4 Float money still present in live paths
Notably `apps/core/scripts/calculate_balance.py` (the writer of the six stored
balance columns) does `sum(float(...))`, `round(float, 2)`, and change-detects
with `float(x) != float(y)`; `ledger_service.get_ledger_summary` returns 12
`round(float(...), 2)` money figures; `scripts/parse_ledger.py:98-113` parses
`cif_inr`/`cif_fc`/`qty` with `float()`. Documented, not fixed.

### 7.5 Not executed at all
Idempotency suite (same request twice, Celery retry, timeout-after-commit);
concurrency suite (concurrent debit/credit/utilisation/allocation/reversal,
`select_for_update` proof, negative-balance and lost-update checks); ledger
immutability enforcement audit; security audit incl. IDOR and object-level
licence ownership; the Balance/Plan/Transactions UI/UX work; running the real
frontend against a live backend to confirm zero console errors.

### 7.6 Partially done
Transaction-type consolidation: 7 raw `'C'`/`'D'` literals moved onto
`apps.core.constants` in `calculate_balance.py`, `scripts/ledger.py`,
`clean_duplicate_rowdetails.py`, `bill_of_entry/serializers.py` (verified
behaviour-neutral: identical pass count with the change stashed). Remaining raw
literals in `condition_pool.py`, `license_balance_excel.py`,
`models/core.py:1159/1173`, `parse_ledger.py`, `parse_ledger_htm.py`. Four
separate vocabularies still coexist (`"C"/"D"`, `OPENING/PURCHASE/SALE/...`,
`"CREDIT"/"DEBIT"/"NONE"`, `LicenseTrade.DIR_*`) bridged by ad-hoc `if` chains.

---

## 8. Open items requiring a decision (found, deliberately not changed)

1. **`?company=` on `ledger_detail` is silently ignored.** `views/ledger.py:236`
   reads the param into a variable never used again, while the docstring promises
   it filters transactions. Fixing it is a semantics decision: the legacy path
   applied the filter *before* computing balances, so honouring it would rebase
   the running balance.
2. **CIF precedence divergence.** `_extract_line_cif` prefers `cif_fc` then falls
   back to `cif_inr / exc_rate`; the legacy ledger used the opposite precedence.
   Where both exist and disagree, canonical and legacy report different money.
3. **`RowDetails.save()` silently no-ops on frozen rows** — deliberate ledger
   immutability, but a write that reports success and does nothing. High blast
   radius into frozen modules; flagged rather than changed.
4. **`is_null` threshold is inconsistent**: `< 500` in `signals.py` and `tasks.py`,
   `< 100` in `calculate_balance.py`. Last writer wins.
5. **`AllocationService` is dead code.** Zero production callers.
   `apps/allotment/tests/test_module3_allocation_scenarios.py` (26 tests) is
   skipped with a documented reason rather than deleted, weakened, or left red —
   it needs a wire-it-up-or-delete-it decision. It was not running at all before.
6. **`allocationMath.ts`** — a client-side allocation engine with 15 passing tests
   and zero importers.

---

## 9. Freeze gate

| Gate | Status |
|---|---|
| Module 04 verified/frozen | ❌ **FAIL** |
| P0 ledger endpoint fixed | ✅ |
| Full backend regression green | ✅ 2212 passed, 0 failed |
| Frontend tests green | ✅ 246 passed |
| Frontend typecheck clean | ✅ 0 errors |
| One canonical ledger engine | ⚠️ exists; not the sole implementation |
| Frontend not a source of financial truth | ❌ **FAIL** |
| Duplicate calculations consolidated | ❌ **FAIL** |
| No float money | ❌ **FAIL** |
| Idempotency verified | ❌ not executed |
| Concurrency verified | ❌ not executed |
| Security/IDOR audit | ❌ not executed |
| UI/UX work | ❌ not executed |
| No production changes | ✅ |

**MODULE 05 — LICENSE LEDGER — BLOCKED.**

Declaring it frozen would require asserting gates that were never executed.
The work above is real, measured, and green; the remainder is listed honestly
rather than claimed.
