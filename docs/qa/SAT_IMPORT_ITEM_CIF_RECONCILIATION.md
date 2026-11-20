# SAT — Import item CIF and quantity reconciliation (P0 addendum §A, §C)

Date 2026-11-20 · branch `feature/v5` @ `ec3604cb` + peer-owned uncommitted paths (none edited) · local DB
`lmanagement@localhost` **read-only** (SELECT only; every app call inside `atomic()` + `set_rollback(True)`).
Audit only: **no fix and no formula change**. Owner: session `license-manager-2c`.
Evidence: `~/lm_sat_evidence/cifrecon/` (scripts, logs and JSON are listed in §9).

Related reports from this addendum:
- `SAT_PLANNING_BALANCE_AUDIT.md`
- `SAT_INVOICE_BOE_QUANTITY_AUDIT.md`
- `SAT_ZERO_BALANCE_VALIDATION.md`
- `SAT_CIF_RECON_INDEPENDENT_REVIEW.md` (independent reviewer, §J)

Earlier licence-level work, cited and not redone: `SAT_FINANCIAL_AUDIT.md` (Phase 3) and `SAT_EXPORT_AUDIT.md` (Phase 6).

## 1. Scope and population

| Population | Count |
|---|---|
| Licences | 2,185 (2,182 have import items) |
| Import items | 26,818. 2,555 carry their own CIF on 1,540 licences; 24,263 have `cif_fc = 0`, which means they share the licence ceiling |
| BOE debit rows | 22,075. 0 have no import item |
| Hidden previous-owner BOEs | 50 |
| M2M-linked allotments | 6,401 |
| Trade lines (invoices) | **0** |
| `InvoiceBOEAllocation` rows | **0** |
| `BOEAllotmentAllocation` rows | **0** |

Because there are no invoices locally, invoice terms are proven on a test DB in `SAT_INVOICE_BOE_QUANTITY_AUDIT.md`.

Units on import items:
- `kg`: 26,784 items
- `KG`: 22 items
- `Kg`: 12 items

There are no MT items. BOE rows carry no unit; they inherit the item's unit. See DEC-25.

## 2. Method

1. **Independent side** (`item_recon.py`): raw SQL on the source tables only. The balance engine is not used for these figures. Per import item it computes:

   | Field | Definition |
   |---|---|
   | Original qty / CIF | Item `quantity` / `cif_fc` |
   | Visible BOE debit | qty and CIF of DEBIT rows, excluding hidden BOEs. A BOE is hidden when `invoice_no='OTH'` and its latest HIDE/RESTORE log is HIDE |
   | Hidden BOE debit | qty and CIF of the hidden BOEs |
   | Outstanding AT / AR | Per allotment item, `cif − min(cif, allocated)`, and the same for qty. The value is 0 when the parent allotment is M2M-linked to a BOE (owner rule 2026-11-17) |
   | Gross AT | Total AT allotted, before netting |
   | Invoiced qty / CIF | 0, because no trade lines exist |
   | Disputed-row CIF | CIF on `is_dispute` rows |
   | `is_boe` without M2M | CIF on allotments flagged `is_boe` that have no M2M link |
   | Remaining qty | `qty − visible debit − outstanding AT − direct sale`, kept signed |
   | Item-attributed remaining CIF | `cif_fc − visible debit CIF − outstanding AT CIF`, only for items that carry their own CIF |

2. **Backend service**: the bulk maps on `ItemBalanceCalculator` and `LicenseBalanceCalculator`, run for all 26,818 items:
   - `calculate_unfloored_/available_quantity_for_items`
   - `calculate_debited_quantity/cif_for_items`
   - `get_outstanding_allotment_totals_for_items`
   - `calculate_item_attributed_balances_for_items`
   - `calculate_direct_sale_quantity_for_items`
   - `condition_pool.available_value_bulk_map` (the live item available CIF)
   - `calculate_financial_balance_for_licenses`

3. **Database stored columns** on `LicenseImportItemsModel`: `available_quantity/value`, `debited_quantity/value` and `allotted_quantity/value`.

4. **API**: the real `LicenseDetailsViewSet.retrieve`, called in-process with a superuser and throttling disabled in-process only. It ran on **526 licences / 6,679 items**:
   - every licence with a negative item;
   - every licence with an AR allotment;
   - every licence with a hidden BOE;
   - every licence with an over-used item CIF;
   - every licence with a fully used item;
   - 60 random licences (seed 20261120).

   Fields compared: `quantity`, `cif_fc`, `available_quantity`, `available_value`, `balance_cif_fc`, `debited_quantity`, `boe_debited_quantity`, `debited_value`, `allotted_quantity`, `allotted_value` and `available_quantity_canonical`.

5. **Licence level**: the licence-level CIF is recomputed independently as `Σ export cif − visible BOE − hidden BOE − outstanding AT − outstanding AR`, with no trades. It is compared with the financial engine for all 2,185 licences.

6. **Excel / PDF / screens**: cited from `SAT_EXPORT_AUDIT.md` (25 export families, 19 licences) and the cross-surface report. They were not re-run because the code is unchanged since then.

Tolerances: CIF 0.01, qty 0.001. Decimal throughout, with no rounding before the comparison.

## 3. Results — the layers compared

| # | Layer compared | Items / licences | Differences | Verdict |
|---|---|---|---|---|
| 1 | Source (independent) vs **backend service**, 8 metrics | 26,818 items | **0** on every metric | **PASS** |
| 2 | Source vs **licence-level financial engine** | 2,185 licences | **0** | **PASS** |
| 3 | Service maps vs **API** live fields | 6,679 items / 526 licences | **0** | **PASS** |
| 4 | Source vs **DB stored columns** | 26,818 | 5,981 avail-qty · 186 allotted-qty · 183 allotted-value · 32 debited-qty · 30 debited-value · 3,050 stored vs live avail-value | **FAIL — carried RC3 / RC4b / RC13** (decided D-D/D-F, not implemented) |
| 5 | Source vs **API user-facing stored fields** | 6,679 | 1,167 `available_quantity` · 158 `allotted_quantity` · 30 `debited_value` | **FAIL — same root cause as #4** |
| 6 | API `available_quantity_canonical` | 6,679 | 0 unexplained. 44 items are floored to 0 by design; on the 35 rechecked, `over_utilised_quantity` = −remaining and `is_quantity_over_utilised` = true (35/35) | **PASS** |
| 7 | Live item available CIF vs licence cap | 26,818 | 1,382 items / 1,233 licences show more than `max(licence balance,0)`. Total excess 518,744,833.47 | **FAIL — carried RC4a** (decided D-A, not implemented) |
| 8 | Excel / PDF | cited | Balance Excel financial sheet (SAT-DEF-010) · Item Pivot Excel text cells (011) · PDF item Balance = RC4a value (N1) · PDF unit split (N4) | **FAIL — carried** (`SAT_EXPORT_AUDIT.md`) |
| 9 | Planning screen | see `SAT_PLANNING_BALANCE_AUDIT.md` | — | see that report |
| 10 | Import item list totals | cited RC11 | 632 licences show a footer of 0 because the CIF sits on export items | **PASS-EXC** (legitimate, unlabelled) |

Independent population totals (`item_recon.json`):

| Term | Amount |
|---|---|
| Original item qty | 2,056,126,185.848 |
| Original item CIF | 1,563,112,511.11. This is only items with their own CIF; the licence original is Σ export CIF 2,393,537,328.28 |
| Visible BOE debit qty | 704,627,602.249 |
| Visible BOE debit CIF | 1,733,748,635.75 |
| Hidden BOE CIF | 4,412,937.86 |
| Outstanding AT qty / CIF | 5,729,849.000 / 13,658,504.39 |
| Outstanding AR qty / CIF | 47,064,684.000 / 17,934,272.36 |
| Invoiced | 0 |

These totals are identical to the Phase 3 independent run, so nothing drifted since then.

## 4. Root-cause breakdown of the stored-column differences (layer 4/5)

Classified per item (`classify.py`, `classify.json`). The writer is `core/scripts/calculate_balance.py`.

| Column | Count | Total stored − correct | Cause | Code |
|---|---|---|---|---|
| `available_quantity` | 4,980 | −613,276.822 | The stored value is truncated to a **whole number**, e.g. 1,777.65 → 1,777 (0311056941 item 39662) | `calculate_balance.py:122` `round_down(…, 0)` |
| `available_quantity` | 831 | −1,009,039.093 | The stored value is 0 when less than 1 unit remains, e.g. 7,039.905 − 7,039 = 0.905 → 0 (0310701930 item 31833) | same |
| `available_quantity` | 153 | −40,408,645.910 | The stored value **deducts AR**, e.g. 0310825251 item 2402: live 1,118,006 kg, stored 0. The live engine does not deduct AR (DEC-01). The current writer's `'ARO'` filter never matches, so these rows were written by an earlier writer | stale or older writer. See §6 note |
| `available_quantity` | 17 | −2,024,897.000 | The stored value **deducts hidden BOEs**, e.g. 0311052122 item 40531: 9,580 live vs 1,916 stored | stale, older writer |
| `allotted_quantity` | 154 / 15 / 17 | +40,647,360 / +951,039 / +428,994 | The stored value includes AR / gross AT (BOE-covered allotments not netted) / unexplained, i.e. stale | stale; RC3 |
| `debited_value` | 30 | +4,412,937.86 | Stored debited CIF **includes hidden BOEs**: the CIF aggregate has no `exclude_hidden` while the qty aggregate does. It is written as `float` | `calculate_balance.py:62-65` |
| `available_value` (stored vs live) | 3,050 | +384,430,657.66 | There are two writers, the stored value is stale, and it uses float | RC4b |

API exposure: `LicenseImportItemSerializer.get_available_quantity`, `get_debited_quantity`, `get_debited_value`,
`get_allotted_quantity` and `get_allotted_value` return the **stored** columns as `float`
(`api/serializers/license.py:304-358`). The live, correct value is only in `available_quantity_canonical`,
`boe_debited_quantity` and `available_value`. A user sees two different "available qty" figures for the same item. Owner decision D-D already covers this ("screens show live values"); it is not implemented.

## 5. Mapping of import items to entitlement (scenarios 16–19)

`mapping.py` / `mapping.json`:

- BOE debits link to the entitlement by **import item primary key** (`RowDetails.sr_number_id`).
  - 0 debit rows have no item.
  - 0 licences have duplicate serial numbers.
  - The BOE header has no licence field, so there is nothing that could contradict the item's licence.
- The licence-level and item-level balance engines read **no description/HSN mapping** (`balance_calculator.py`). So "same description / different HSN" (506 descriptions) and "same HSN / different description" (259 HSNs) **cannot** move CIF between items. **PASS** for the balance arithmetic.
- 1,656 (description, HSN) products appear on more than one licence; for example "refined cane sugar" 17019990 is on 600 licences. Licence balances are per licence, so attribution across licences is exact. Phase 3 showed no loss and no duplication on 3,244 multi-licence BOEs.
- Identity is weak for planning and pivot mapping, though not for the balance: 3,368 items have no HSN and 3,355 have a blank description. Planning uses ItemNameModel identity (owner decision 2026-11-18) and the "Not verified" HSN/SION policy, so this is a data-quality list, not a defect.
- Multiple import items under one licence: Σ item visible debit = licence visible debit on all 2,182 licences, i.e. 0 lost rows.

## 6. Exceptions (consolidated)

Each row cites the canonical register entry where one exists. Rows marked **NEW** are proposed in §8.

| Licence | Import item | Invoice | BOE | Expected CIF | Actual CIF | CIF diff | Expected qty | Actual qty | Qty diff | Root cause | Severity | Financial impact |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0310825251 | 2402 (sr 1) | — | — | n/a (shared ceiling) | — | — | 1,118,006.000 (live, AR not deducted) | API `available_quantity` 0.000 | −1,118,006.000 | Stored column deducts AR, live does not (DEC-01 / SAT-DEF-001) + RC3 | High | One item shows 2 contradictory qty figures; 153 items, −40,408,645.91 kg in total |
| 0311056941 | 39662 (sr 11) | — | — | — | — | — | 1,777.650 | 1,777.000 | −0.650 | Stored qty truncated to whole number (RC13, decided D-F) | Low | 4,980 items, −613,276.822 |
| 0310701930 | 31833 (sr 6) | — | — | — | — | — | 0.905 | 0.000 | −0.905 | Same; residual < 1 unit hidden as 0 | Low | 831 items, −1,009,039.093 (includes the 153-item AR overlap; see `classify.json`) |
| 0311052122 | 40531 (sr 13) | — | hidden BOEs | — | — | — | 9,580.000 | 1,916.000 | −7,664.000 | Stored qty deducts hidden BOEs; live excludes them (RC3/RC8) | Medium | 17 items, −2,024,897 |
| 0311052122 (and 29 other items) | 30 items | — | hidden BOEs | visible debit | stored `debited_value` = visible + hidden | +4,412,937.86 total | — | — | — | `calculate_balance.py:62-65`: the CIF aggregate has no `exclude_hidden`, qty does | Medium | The API `debited_value` overstates debited CIF by 4,412,937.86 on 30 items |
| 1,233 licences | 1,382 items | — | — | ≤ max(licence bal, 0) | live item available CIF | +518,744,833.47 total excess | — | — | — | RC4a, decided D-A, not implemented | High (carried) | Planning/allotment could be offered more CIF than the licence has (see planning report) |
| 0310543354 | 6397 (sr 3) | — | 22 BOE rows | −323,041.56 (item attributed, signed) | API `available_value` 0.00 · licence +0.59 | item over-use invisible | −131,924.000 | API canonical 0, over-utilised 131,924 flagged | — | Item CIF over-use is floored with **no CIF over-use flag** (qty has one). The licence stays positive | Medium **NEW → DEC-50** | 6 items with licence balance > 0 hide −5,518,485.10 item CIF over-use; 13 items −6,102,280.09 in total |
| 0910061491 | 3127 (sr 3) | — | BOE rows on the item | — | — | — | 722,264.000 − 1,454,600.000 = −732,336.000 | flagged over-utilised | — | BOE qty ≈ 2× the licensed qty; possibly a unit or duplicate problem (also `SAT_INVOICE_BOE_QUANTITY_AUDIT.md`) | High (data) | 44 items qty-over-used, −3,749,209.142 kg; 30 of them sit on licences whose CIF is still positive |
| 0311021420 | 18968 (sr 1) | — | — | 123,380.34 available | 123,380.34 | 0 | 0.001 | 0.001 | 0 | Quantity exhausted but item CIF left. Consistent, but the item can't be used | Low **NEW → DEC-51** | 25 items, 1,993,549.35 CIF "available" with no qty |
| 8 licences e.g. 0310827509 | — | — | 30 BOEs | original 0 | −3,447,851.40 | — | — | — | — | Export CIF 0 but BOEs debited (data, DQ-2) | High (data) | Σ debits on zero-original licences 3,631,501.88 |
| 189 licences e.g. 0311056941 | — | — | — | flag per live balance | stored `is_null=True` with live 100–500 | — | — | — | — | Three "null DFIA" thresholds: 100 (`calculate_balance.py:238`, dashboard `:142,:262`), 200 (licence list filter `views/license.py:723-729`), 500 (`signals.py:357`, `validation_service.py:48,322`) | Medium **NEW → DEC-52 / SAT-DEF-140** | Which licences are "null" depends on the screen; Σ live balance of the 189 = 42,394.60 |

Carried and not repeated here: SAT-DEF-002 (`is_boe` without M2M, 1,160,224.05), DEC-03 duplicate BOE 8391561
(14,835.86), DEC-05 cross-licence M2M (8,133,632.89), DEC-07 disputed rows (131,125.49).

## 7. Section C field extract

The full per-item extract for all 26,818 items is in `~/lm_sat_evidence/cifrecon/item_rows.tsv`. Its columns:

- licence, serial, item id, description, HSN, unit, condition;
- original qty / CIF;
- debited qty / CIF and BOE row count;
- hidden qty / CIF;
- gross and outstanding AT qty / CIF, and outstanding AR qty / CIF;
- invoiced qty / CIF;
- disputed CIF and `is_boe`-without-M2M CIF;
- remaining qty (signed and incl. AR) and attributed remaining CIF;
- licence balance;
- every app map value and every stored column.

"Priority" is not a property of an import item. It is a planning order (see `SAT_PLANNING_BALANCE_AUDIT.md`).

## 8. Proposed register entries (for the SAT controller to merge; numbering DEC-50+, SAT-DEF-140+)

| ID | Type | Question / defect | Current | Options | Recommended |
|---|---|---|---|---|---|
| DEC-50 | Owner decision | Should an item whose **CIF** is over-used (signed attributed CIF < 0) carry an over-utilisation flag, as quantity does (`over_utilised_quantity`)? | CIF is floored at 0 with no flag; the licence may still be positive (0310543354: item −323,041.56, licence +0.59) | (a) Add an additive `over_utilised_cif` and flag (no balance change). (b) Keep | (a). It honours "preserve negatives and flag over-utilisation" without changing the approved floor |
| DEC-51 | Owner decision | Should an item with **qty exhausted but CIF left** (or CIF exhausted but qty left) be shown as available to planning or allotment? | Both values are shown independently; 25 items carry 1,993,549.35 CIF with ≤ 0.001 qty | (a) Treat as exhausted when either is ≤ 0. (b) Keep showing both | (a) for planning eligibility, with both figures still displayed |
| DEC-52 | Owner decision | What is the "null DFIA" threshold: 100, 200 or 500? | Three thresholds in code; 189 stored flags disagree with the list filter | Choose one value, held as a constant in one place | Owner to choose |
| SAT-DEF-140 | Defect (Medium, CD) | The `is_null` flag has 3 definitions (`calculate_balance.py:238` < 100, `signals.py:357` < 500, list filter `views/license.py:723` < 200, `validation_service.py:322` < 500, dashboard < 100) | 189 licences flagged null with live balance 100–500 | Single constant after DEC-52 | — |
| SAT-DEF-141 | Defect (Medium, CD; extends RC3) | Stored `debited_value` includes hidden BOEs (CIF aggregate has no `exclude_hidden`; qty does) and is float | 30 items, +4,412,937.86 on the API `debited_value` | Covered by D-D (live values); until then, apply `exclude_hidden` in the writer | — |
| SAT-DEF-142 | Defect (Low, CD) | Import item API returns qty/CIF as `float` (`api/serializers/license.py:304-358`), against the Decimal-to-the-edge invariant | All item responses; no difference seen at the current magnitudes (≤ 15 significant digits) | String Decimal, as `available_quantity_canonical` already does (API contract change, needs approval) | — |

Note for the controller on SAT-DEF-001 (D01): the current writer's `'ARO'` filter never matches. Even so, 153 stored rows
equal "live − AR". They therefore come from an earlier writer (or `sync_from_ge_server`'s `balance_quantity` path) and are
stale. The live engine and the current writer both leave AR out of item qty, so DEC-01 stands as stated.

## 9. Evidence (all exit 0)

| File in `~/lm_sat_evidence/cifrecon/` | What |
|---|---|
| `item_recon.py` / `.log` / `.json`, `item_rows.tsv` | Independent vs service vs stored, all 26,818 items |
| `classify.py` / `classify.json` | Stored-column root-cause classification |
| `zero_balance_lic.py` / `.log`, `licence_balances.json` | Licence financial/customs balances + stored `is_null` flag |
| `api_items.py` / `.log` / `.json` | Real detail API, 526 licences / 6,679 items (first 600 diff rows stored; counts complete) |
| `api_overuse.py` / `.log` | 35/35 over-utilised qty fields correct |
| `mapping.py` / `.log` / `.json` | Item identity / mapping checks |
| `review_sample.json` | IDs handed to the independent reviewer |

Tests: no repository test was run for this report, because no code changed. Pinned financial tests from Phase 3: 278 passed, exit 0 (`SAT_FINANCIAL_AUDIT.md` §4).

## 10. Independent review (§J) and consolidated exception table (all four addendum reports)

The independent reviewer (fresh Opus context, `SAT_CIF_RECON_INDEPENDENT_REVIEW.md`) recalculated 19 sampled items and 3
licences from raw SQL. Its figures were saved before it read this audit. Result:

- **0 figure disagreements**: 17 fields × 19 items, and 3/3 licences.
- Challenges that PASS: M2M rule, BOE→item→licence matching, priority, units, description/HSN mapping.
- Challenges that cannot be tested locally: invoice + BOE, and missing invoice consumption (0 trade lines).
- New findings: DEC-60, SAT-DEF-150, SAT-DEF-151.
- SAT-DEF-005 is now measured at up to +459,135.24 over the licence balance (item 36928).
- Controller check: SAT-DEF-150's main example was re-verified with SQL (`verify_def150.py`). AT allotment 10178 (0910065986, item 39996, 132,000 kg, CIF 184,932.00, 2026-10-09) has no M2M link. BOE 4849356 (2026-11-03, same company, item and qty, CIF 189,677.63) also has no M2M link. Both are counted.

Consolidated exceptions, in order of financial impact. "—" means not applicable; the source report holds the full rows.

| # | Licence | Import item | Invoice | BOE | Expected CIF | Actual CIF | CIF diff | Expected qty | Actual qty | Qty diff | Root cause | Severity | Financial impact | Source / ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1,233 licences | 1,382 items | — | — | ≤ max(lic bal,0) | live item avail | +518,744,833.47 | — | — | — | Item CIF not capped at licence (RC4a) | High | Over-offer at item level | D-A decided, not implemented |
| 2 | 67 licences | 94 allotment items (e.g. 11836, allot 2220) | — | e.g. 8154268 (debits sibling item) | — | — | CIF 8,736,879.71 released | allotted item consumed | not consumed | 3,377,428 kg | M2M link to a BOE that debits a sibling item | Medium | Item qty overstated | DEC-60 (review) |
| 3 | 172 licences | 207 items | — | cross-licence | — | — | 8,133,632.89 | — | — | — | M2M BOE on another licence | Medium | Licence A under-utilised? | DEC-05 (carried) |
| 4 | 156 licences | 157 items | — | — | AR deducted? | not deducted | 17,934,272.36 item-level | — | — | +40,992,712.93 kg | ARO/AR not consumed at item level; %-pool deducts AR but attributed branch does not | High | Item qty overstated | DEC-01 / SAT-DEF-001 |
| 5 | 11 licences e.g. 0311052376 | — | — | hidden BOEs | 1.90 | 48,256.54 | +4,412,937.86 total | — | — | — | Plan tab "Actual Balance CIF" ignores hidden-BOE opening rule | Medium | Plan tab overstates balance | SAT-DEF-102 (planning E-03) |
| 6 | 30 items | — | — | hidden BOEs | visible debit | stored debited_value | +4,412,937.86 | — | — | — | Stored writer CIF aggregate lacks `exclude_hidden` | Medium | API `debited_value` overstated | SAT-DEF-141 |
| 7 | 13 items (6 on positive licences) | e.g. 6397 on 0310543354 | — | — | −323,041.56 | 0.00 (no flag) | hidden −6,102,280.09 | — | — | — | Item CIF over-use floored without flag | Medium | Over-use invisible | DEC-50 |
| 8 | 8 licences e.g. 0310827509 | — | — | 30 BOEs | original 0 | debited 3,257,841.98 | Σ 3,631,501.88 | — | — | — | Original CIF 0 with debits (data) | High (data) | Over-utilisation | DQ-2 |
| 9 | 0910061491 + 43 items | 3127 | — | rows on item | — | — | — | 722,264.000 | debited 1,454,600.000 | −732,336.000 (Σ −3,749,209.142) | BOE qty > licensed qty | High (data) | Qty over-use | this report §6; qty audit |
| 10 | 12 BOEs / 43 rows e.g. BOE 5128829 | — | — | 5128829, 8741982 | qty > 0 | qty 0 | CIF 5,056,539.16 with qty 0 | — | — | — | BOE rows with zero qty but CIF | Medium (data) | Qty consumption understated | qty audit / DEC-26 |
| 11 | 13 licences e.g. 5211016560 | — | — | 25789 | — | — | 1,160,224.05 | — | — | — | `is_boe` allotment without M2M (engine vs planning differ) | High | Probable double count | DEC-02 / SAT-DEF-002 |
| 12 | 42 licences e.g. 0310837232 | plan 21188 | — | — | ≤ 279.89 | 233,287.07 | Σ +633,992.65 | — | — | — | Saved plan snapshot not capped by live balance | Medium | Plan display over-offer | DEC-11 (controller reclassified SAT-DEF-100 as a business-rule question: snapshot kept intentionally, `planning_usage_reconciliation.py:167-173`) |
| 13 | 0910065986 + 7 cases | 39996 | — | 4849356 | one consumption | allotment + BOE | Σ 420,407.75 | 132,000 | 264,000 consumed | 132,000 kg | Unlinked allotment with matching later BOE | Medium | Probable double count | SAT-DEF-150 (review) |
| 14 | 0311021420 + 24 | 18968 | — | — | — | 123,380.34 avail | Σ 1,993,549.35 | 0.001 | 0.001 | 0 | Qty exhausted, CIF left | Low | Eligibility | DEC-51 |
| 15 | 0311053542, 0311054202 | plans 12502/12506 | — | — | consumed | restored | +9,257.14 | — | — | 3,263 | Plan capacity restored after PLAN→BOE | Medium | Plan over-offer | DEC-13 / SAT-DEF-103 |
| 16 | 189 licences | — | — | — | per live bal | stored is_null | Σ live 42,394.60 | — | — | — | Null-DFIA thresholds 100/200/500 | Medium | Screen-dependent "null" | DEC-52 / SAT-DEF-140 |
| 17 | 5211018767 | 33479 | GE 41 | 8391561 ×2 | once | twice | 14,835.86 | 5,800 | 11,600 | 5,800 | Duplicate BOE stored twice | Medium | Double debit | DEC-03 (carried) |
| 18 | 4,980 + 831 items | e.g. 39662, 31833 | — | — | — | — | — | 1,777.650 / 0.905 | 1,777 / 0 | Σ −1,622,315.915 | Stored qty whole-unit floor | Low | Display | RC13, D-F decided |
| 19 | synthetic (test DB) | — | SALE lines | linked BOE | — | — | — | invoice qty | BOE qty used | varies | Invoice qty rule: BOE wins; blank/0/negative invoice qty stored as 0, not flagged; `qty_comparison` gives full BOE qty to every invoice | Medium (latent) | 0 trades locally | SAT-DEF-120…132, DEC-20…26 |
| 20 | synthetic | — | invoiced 250 | — | ceiling −250 | not deducted | +250 per 250 | — | — | — | Planning usage has no invoice term | Medium (latent) | — | SAT-DEF-101 (planning E-02) |

Proposed register entries from this addendum (merged by the SAT controller):

| Report | Owner questions | Defects |
|---|---|---|
| Planning | DEC-11…14 | SAT-DEF-100…106 |
| Invoice/BOE quantity | DEC-20…26 | SAT-DEF-120…132 |
| This report | DEC-50…52 | SAT-DEF-140…142 |
| Independent review | DEC-60 | SAT-DEF-150, 151 |
