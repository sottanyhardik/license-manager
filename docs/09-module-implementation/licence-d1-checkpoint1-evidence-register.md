# Checkpoint 1 — D-1 CIF Utilisation: Evidence Register

**Scope:** D-1 rule (Utilised = BOE CIF + ALLOTMENT CIF + BILLED without BOE), the `invoiced_boe_covered` source, allotment CIF double-count risk, and six real licences from the development database.
**Method:** code trace (repository, read-only) plus independent recalculation from raw database rows (`SELECT` only, session set to `READ ONLY`). No application code or database records were modified.
**Companion documents:** `licence-cif-quantity-balance-audit.md`, `licence-cif-quantity-balance-business-rules.md`, `licence-cif-quantity-balance-open-decisions.md` (not yet reconciled line by line; see §7).
**Masking:** customer names, contacts and trade counterparties are not reproduced. Licence numbers, BOE numbers and invoice numbers are business references and are kept.

---

## 1. Code trace (verified in source)

| # | Step | Source | Finding |
|---|---|---|---|
| C1 | Utilisation identity | `backend/apps/license/services/sale_boe_allocation.py:153–291` (`compute_utilisation`) | `utilised = Σsold + Σuncovered BOE + Σover-linked + allotment`. The function asserts this equals `Σsold + ΣBOE − Σcovered + allotment`, so a BOE covered by a sale is not added again. **Verified.** |
| C2 | Uncovered BOE | `sale_boe_allocation.py:240–259` | `uncovered = BOE − Σ links from that BOE`. Links are the only way a BOE is removed from "uncovered". |
| C3 | Covered and over-linked | `sale_boe_allocation.py:210–216` | Per sale: `covered = min(sold, linked)`, `over = max(0, linked − sold)`. |
| C4 | Item balance | `backend/apps/license/services/licence_item_balance.py:109–113` | `debited = uncovered + over`; `available = original − debited − allotted − invoiced`. `invoiced_boe_covered = result.covered_total` (line 149). |
| C5 | D-1 split | `backend/apps/license/services/planning_financial_budget.py:9–13, 75–88` | `BOE CIF = debited + invoiced_boe_covered`; `ALLOTMENT CIF = allotted`; `BILLED WITHOUT BOE = invoiced − invoiced_boe_covered`; `utilised_cif = boe_cif + allotment_cif + billed_without_boe_cif`. **Arithmetic verified** (algebra reduces to `debited + allotted + invoiced`). |
| C6 | Source of `links` (covered) | `backend/apps/license/services/licence_balance_report.py:349–381` (`_item_inputs`) | **Two sources.** (a) If an active, current `InvoiceBOEAllocation` row exists for (BOE row, trade line), its `allocated_cif_fc` is used. (b) Otherwise, **every BOE on the trade's membership (`LicenseTrade.boes`) is linked at its full CIF** to that trade. Line 363 keys allocations on the trade's **first** line on the item (`t["lines"][0].id`). |
| C7 | Allotment CIF source | `licence_balance_report.py:403–421` (`allotment_link`) | If the allotment has a BOE on this item, `outstanding_cif = 0` and the BOE-linked part is ignored. The **difference** between allotted CIF and BOE-linked CIF is dropped, not reserved (documented in the function docstring). If no BOE is linked, the full allotment CIF is outstanding. |
| C8 | Double-count guard for allotment | `licence_balance_report.py:377–379, 424–435` | The allotment amount enters `allotted` only once, through `allot_residue`. The BOE on that allotment enters `debited` only once, through `debit_rows`. No BOE is counted in both places. **Verified in code and in DB (see E2, E3).** |
| C9 | Licence-level totals | `licence_balance_report.py:759–768` (`build_licence_balance_reports`) | Licence `summary_cif` = `aggregate_items` of item results; each component is a plain sum across items. |
| C10 | Licence-level CIF control | `licence_balance_report.py:662–689` (`_apply_licence_cif_control`) | For licence-level control: if pooled available < 0 and any sale has no classification or a REVIEW classification, the status is **REVIEW REQUIRED** with `is_over_utilised = False`, unless the alternative reading (unverified sales = internal) is also negative. See BUG-001. |

Scope of item and allotment rows: `_load` (`licence_balance_report.py:230–325`) fetches `LicenseImportItemsModel` (authorised item CIF, `cif_fc`), `RowDetails` with `transaction_type = "D"` (BOE debit), `LicenseTradeLine` on `SALE` trades, `InvoiceBOEAllocation` (`is_current = True`, status ACTIVE), `AllotmentItems` (status `CREATED`), and the `BillOfEntryModel.allotment` through table. Debit rows are grouped per item (`_index`, lines 710–721), so BOE and allotment matches are item-scoped.

---

## 2. Database evidence (read-only)

| Check | Result | Method |
|---|---|---|
| Total `InvoiceBOEAllocation` rows | **2** (both active and current) | `ro_conditions.py` (`SELECT` only) |
| BOE rows linked to two or more trades on the same item (over-link / double-count risk through membership fallback) | **0 rows** | `ro_conditions.py` |
| Licences surveyed | 222 (`LicenseDetailsModel`) | `ro_survey.py` via `build_licence_balance_reports` |
| Status counts | REVIEW REQUIRED 159, RECONCILED 53, OVER-UTILISED 10 | `ro_conditions.py` |
| Licence-level CIF control licences | 219 (item-level: 3) | `ro_conditions.py` |
| Licences with negative pooled available | **74** | `ro_conditions.py` |
| Negative available but **not** flagged OVER-UTILISED | **64** of 74 (all REVIEW REQUIRED) | `ro_conditions.py` |
| Licences where legacy `calculate_financial_balance` ≠ canonical available (tolerance applied by report) | **111** of 222 | `ro_conditions.py` |

**Implication of the 2 allocation rows:** the explicit allocation mechanism is effectively unused. Covered amounts come from the membership fallback (C6b) for virtually all licences. That is a business rule that has never been written down as a decision (see OPEN-001).

---

## 3. Independent recalculation of real licences

The independent script (`ro_recalc.py`, kept outside the repository) reads raw rows and applies the D-1 rules itself. It does **not** call `sale_boe_allocation` or `licence_balance_report` for its own figures. The application's figures are used only for the comparison column. The first version omitted the membership fallback; that gap was found, corrected, and rerun before any result below was accepted.

### Example E1 — Normal: BOE fully covers sales, no allotment (licence 0311051200, id 2575)

| Component | Source records | Independent | Application | Match |
|---|---|---:|---:|:---:|
| Original CIF | 11 authorised item rows (`LicenseImportItemsModel.cif_fc`) | 2,229,918.69 | 2,229,918.69 | ✅ |
| BOE CIF (debited + covered) | 11 BOE debit rows (`RowDetails`, type D) | 1,931,269.95 | 1,931,269.95 | ✅ |
| Allotment CIF | none | 0.00 | 0.00 | ✅ |
| Invoiced (sales) | 1 sale trade | 197,648.00 | 197,648.00 | ✅ |
| Invoiced BOE-covered | membership fallback, min(sold, linked) | 197,648.00 | 197,648.00 | ✅ |
| Billed without BOE | sold − covered | 0.00 | 0.00 | ✅ |
| **Utilised** | BOE + allot + billed | **1,931,269.95** | **1,931,269.95** | ✅ |
| **Available** | original − utilised | **298,648.74** | **298,648.74** | ✅ |
| Legacy balance | `calculate_financial_balance` | — | 298,648.74 (RECONCILED) | ✅ |

**Result: CONFIRMED for arithmetic.** Duplicate check: the 197,648.00 sale is inside BOE CIF and is not added to billed-without-BOE. Application status for this licence is REVIEW REQUIRED, not RECONCILED. The arithmetic matches; the extra flags behind the status are not yet traced.

### Example E2 — Full D-1: BOE covered sales, uncovered BOE, billed without BOE, allotment (licence 0311054431, id 2586)

| Component | Independent | Application | Match |
|---|---:|---:|:---:|
| Original CIF | 948,299.96 | 948,299.96 | ✅ |
| BOE CIF | 601,452.33 (debited 33,785.14 + covered 567,667.19) | 601,452.33 | ✅ |
| Allotment CIF | 24,197.55 (allotment 7208, no BOE on item) | 24,197.55 | ✅ |
| Invoiced (sales, 9 trades) | 834,550.13 | 834,550.13 | ✅ |
| Invoiced BOE-covered | 567,667.19 | 567,667.19 | ✅ |
| Billed without BOE | 834,550.13 − 567,667.19 = 266,882.94 | 266,882.94 | ✅ |
| **Utilised** | 601,452.33 + 24,197.55 + 266,882.94 = **892,532.82** | 892,532.82 | ✅ |
| **Available** | 948,299.96 − 892,532.82 = **55,767.14** | 55,767.14 | ✅ |
| Legacy balance | — | 79,964.69 (**MISMATCH**, BUG-002) | ❌ |

**Result: CONFIRMED for arithmetic.** Duplicate check: 567,667.19 is counted once (in BOE CIF) and removed from billed-without-BOE. Status per app: REVIEW REQUIRED.

### Example E3 — Over-utilised with BOE-linked allotments (licence 0311052365, id 2558)

| Component | Independent | Application | Match |
|---|---:|---:|:---:|
| Original CIF | 291,912.88 | 291,912.88 | ✅ |
| BOE CIF | 291,738.46 (all covered, 4 rows) | 291,738.46 | ✅ |
| Allotment CIF | 23,945.90 (allotment 7200; BOEs not on item → outstanding) | 23,945.90 | ✅ |
| Allotments 7189 and 7297 | BOE on item = 72,017.92 and 52,969.37 → outstanding 0 | consistent | ✅ |
| Invoiced | 291,738.46 | 291,738.46 | ✅ |
| Billed without BOE | 0.00 | 0.00 | ✅ |
| **Utilised** | **315,684.36** | 315,684.36 | ✅ |
| **Available** | **−23,771.48** | −23,771.48 | ✅ |
| Over-utilised flag | True | **OVER-UTILISED** | ✅ |
| Legacy balance | — | 174.42 (**MISMATCH**, BUG-002) | ❌ |

**Result: CONFIRMED for arithmetic and for over-utilisation flagging.** Negative balance is shown, not clamped. The legacy engine differs by 23,945.90 (exactly the outstanding allotment 7200). This is consistent with the legacy engine not reserving allotments, but that is not yet proven, so it is logged as BUG-002.

### Example E4 — Over-utilised, but reported as REVIEW REQUIRED (licence 3111006003, id 2578)

| Component | Independent | Application | Match |
|---|---:|---:|:---:|
| Original CIF | 104,205.70 | 104,205.70 | ✅ |
| BOE CIF | 68,498.54 (2 rows, both covered) | 68,498.54 | ✅ |
| Invoiced | 172,704.24 (3 trades) | 172,704.24 | ✅ |
| Invoiced BOE-covered | 68,498.54 | 68,498.54 | ✅ |
| Billed without BOE | 104,205.70 | 104,205.70 | ✅ |
| **Available** | **−68,498.54** | −68,498.54 | ✅ |
| Over-utilised flag | True (independent) | **False — status REVIEW REQUIRED** | ❌ BUG-001 |

**Result: arithmetic CONFIRMED; status CONFLICT with approved D-1 rule.** Sales exceed the authorised CIF by exactly the BOE-covered amount. The application shows REVIEW REQUIRED because some sales have no classification record (BUG-001).

### Example E5 — Normal: partial BOE cover, no allotment (licence 0310834960, id 2601)

| Component | Independent | Application | Match |
|---|---:|---:|:---:|
| Original CIF | 213,999.97 | 213,999.97 | ✅ |
| BOE CIF | 18,664.99 (uncovered 15,295.30 + covered 3,369.69) | 18,664.99 | ✅ |
| Invoiced / covered | 3,369.69 / 3,369.69 | 3,369.69 / 3,369.69 | ✅ |
| Billed without BOE | 0.00 | 0.00 | ✅ |
| **Available** | **195,334.98** | 195,334.98 | ✅ |
| Legacy balance | — | 195,334.98 (RECONCILED) | ✅ |

**Result: CONFIRMED.** Legacy and canonical agree here, which makes this a clean reference case.

### Example E6 — Sale with no BOE (licence 0310833996, id 2616)

| Component | Independent | Application | Match |
|---|---:|---:|:---:|
| Original CIF | 411,686.27 | 411,686.27 | ✅ |
| BOE CIF | 0.00 | 0.00 | ✅ |
| Billed without BOE | 192,777.50 | 192,777.50 | ✅ |
| **Available** | **218,908.77** | 218,908.77 | ✅ |
| Legacy balance | — | **28.77** (MISMATCH) | ❌ BUG-002 |

**Result: canonical CONFIRMED. The legacy figure is 218,880.00 lower than canonical** (218,908.77 − 28.77). The cause is not yet traced.

### Additional licences noted (not fully traced)

| Licence (id) | Observation | Status |
|---|---|---|
| 2583–2589 family (0311054433 and neighbours) | Five-item licences, negative pooled available of −360k to −452k, not flagged OVER-UTILISED; legacy shows 0.00 on 2583 | BUG-001, BUG-002 |
| 0311055304 (2622) | Billed without BOE = **2,280,000.00** exactly; available −837,647.77 flagged REVIEW REQUIRED; legacy +1,442,352.23 | DATA-001 |
| 5011002222 (2627) | Exactly consumed (sales = original); available 0.00, RECONCILED | Reference case (exact consumption, not over) |

---

## 4. Verdicts for D-1 sub-rules

| Rule ID | Statement | Code | Database | Status |
|---|---|---|---|---|
| D1-R1 | Utilised = BOE CIF + ALLOTMENT CIF + BILLED without BOE | C1, C5 | E1, E2, E3, E5 | **CONFIRMED** (arithmetic) |
| D1-R2 | Available = Original − Utilised, no zero floor | C1, C4 | E2, E3, E4 | **CONFIRMED** (arithmetic) |
| D1-R3 | Billed without BOE excludes invoices already represented by BOE CIF | C2, C3, C5 | E1, E2, E5 | **CONFIRMED** for tested cases; the source of "represented" is C6 |
| D1-R4 | Amounts represented by BOE CIF are not also counted in ALLOTMENT CIF | C7, C8 | E2, E3 | **CONFIRMED** for tested cases (allotment with BOE on item is zeroed) |
| D1-R5 | Negative available is visible and flagged as over-utilisation (never clamped) | C10 | E3 (flagged), E4 (not flagged), 64 licences not flagged | **CONFLICT** — BUG-001 |
| D1-R6 | Covered BOE is identified by explicit allocation | C6 | 2 allocation rows in DB; all tested covered amounts come from membership fallback | **CONFLICT / OPEN-001** |
| D1-R7 | Allotment CIF residue beyond the BOE-linked CIF is ignored, not reserved | C7 | 2558 allotment 7297: BOE 52,969.37 vs allotment 53,143.66 → 174.29 dropped | **OPEN DECISION** (OPEN-002) |

---

## 5. Bugs, conflicts and gaps raised in this checkpoint

| ID | Type | Severity | Summary | Evidence | Proposed action (not applied) |
|---|---|---|---|---|---|
| BUG-001 | CONFLICT with approved rule | High | 64 of 74 licences with negative pooled available are REVIEW REQUIRED, not OVER-UTILISED. Cause: licence-level control downgrades when any sale lacks a classification record (`_apply_licence_cif_control`). | E4 (2578), 2622, 2583, full list from `ro_conditions.py` | Business decision: keep the downgrade, or flag over-utilisation and show "unverified" as a separate reason. Do not change until approved. |
| BUG-002 | Inconsistency between two engines | High | Legacy `calculate_financial_balance` disagrees with canonical available on 111 of 222 licences. Examples: 2622 (+1,442,352.23 vs −837,647.77), 2583 (0.00 vs −452,364.64), 2558 (174.42 vs −23,771.48), 2616 (28.77 vs 218,908.77). | E3, E6, `ro_conditions.py` | Determine which engine is authoritative for each screen. Do not alter the legacy engine until the cause is traced. |
| OPEN-001 | Open business decision | High | Covered BOE is derived from trade-to-BOE membership at full CIF, not from explicit allocations (only 2 allocation rows in DB). The rule is implemented but never recorded as an approved decision. | C6, §2 | Business confirms the membership rule and says whether explicit allocation is required. |
| OPEN-002 | Open business decision | Medium | Allotment CIF residue above BOE-linked CIF (e.g., 174.29 on allotment 7297) is ignored and not reserved. Documented in code, not approved. | C7, E3 | Business confirms whether the residue is reserved, released, or reported. |
| DATA-001 | Data-quality review | Medium | Licence 0311055304 has billed-without-BOE of exactly 2,280,000.00. | §3 | Business checks whether this is a real invoice. |
| TEST-001 | Test gap | Medium | `ro_conditions.py` found no over-link (BOE on two trades, same item) in the DB, so the OVER_ALLOCATED path is untested against real data. Only the test fixture covers it. | §2 | Add a regression test with a real-shaped fixture. |
| TEST-002 | Test gap | Medium | First-line allocation keying (C6a, line 363) has no real-data example because there are only 2 allocation rows. | §2 | Find or create a fixture with a multi-line trade allocation. |

---

## 6. Reproducibility

Scratch scripts (outside the repository, read-only):

- `/tmp/lm_audit/ro_survey.py` — application report for all licences.
- `/tmp/lm_audit/ro_recalc.py <licence_id ...>` — independent recalculation and comparison.
- `/tmp/lm_audit/ro_conditions.py` — structural condition counts.

Run from the project root with `.venv/bin/python -I`. The session is forced to `READ ONLY` before any query.

Scope limits in this checkpoint: no UI, API or report-export comparison yet. Those belong to the reports checkpoint.

---

## 7. Known gaps in this register

- **Not yet reconciled** against `licence-cif-quantity-balance-business-rules.md` and `licence-cif-quantity-balance-open-decisions.md`. Until that is done, do not treat any statement here as a superseding decision.
- **Not yet traced:** why the legacy engine differs (BUG-002). The arithmetic difference is recorded, but the cause is not proven.
- **Not yet verified:** the UI, API and report output for these licences. The comparison here is at the service layer only.
- **Allocation fallback sample size:** only the 2 allocation rows exist, so the explicit allocation path is verified by code reading only.
