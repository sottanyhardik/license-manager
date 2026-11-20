# SAT — Planning balance audit (sat-plan)

Date 2026-11-20 · branch `feature/v5` (HEAD `ec3604cb` + ~180 uncommitted paths owned by other sessions; none touched) ·
local DB `lmanagement@localhost` **read-only** (SELECT only; every app/API call inside `transaction.atomic()` +
`set_rollback(True)`; previews additionally inside a savepoint that is rolled back) · test DB `test_lmanagement_sat_plan`.
**Audit only: no application code, formula, migration or data was changed.** Evidence:
`~/lm_sat_evidence/cifrecon/planning/` (abbreviated `EV/` below).

Builds on `docs/qa/SAT_FINANCIAL_AUDIT.md`: the licence engine there matches an independent SQL recomputation on all
2,185 licences and 26,818 items. Its defects D01 (ARO qty), D02 (`is_boe` without M2M) and D09 (shared-ceiling item cap)
are cited here, not re-derived. Owner decisions that are already made are not re-asked: D-A…D-F, D1–D4, M2M = full
consumption, the negative-balance clamp, and the 2026-11-18 planning CIF budget
(`docs/decisions/2026-11-18-planning-cif-budget-e126-split-item-pivot.md`, which includes the 500 tolerance).

## 1. Methodology

1. **Code trace.** I traced every planning surface to the source of each figure:
   - `aggregate_license_usage` / `reconcile_license_plans` (`planning_usage_reconciliation.py`);
   - `planning_operational_snapshots`;
   - `SionPlanningExecutionService.plan_sion` and `_compute_license_new_architecture` (`sion_planning_execution.py`);
   - `EntitlementPlanningService` + `compute_entitlement_plan`;
   - `plan_enforcement.plan_status_for` / `plan_line_status_for` plus the allotment `_position_payload`;
   - `LicenseDetailsViewSet.retrieve` (blocks `planning_balance_cif`, `operational_reconciliation`, `plan_utilization`);
   - the `LicenseItemPlanSerializer` reconciliation fields;
   - frontend `PlanningEditor.tsx`, `EntitlementPlanningReport.tsx` and `LicensePlanningWorkspace.tsx`.
2. **Real-data sample** (`EV/p1_sample.py` → `p1_sample.json`, exit 0, 0 errors): **81 licences / 969 import items**.
   The sample is:
   - all 36 over-utilised licences;
   - all 13 licences with an `is_boe` allotment that has no M2M link;
   - 8 with outstanding allotments + plans;
   - 6 multi-item (≥ 8 items) + plans;
   - 6 that share a product (same HSN + description on ≥ 5 licences) + plans;
   - 10 random planned licences and 6 random licences (`random.Random(20261120)`).

   For each licence and item the script computes three values:
   - an **independent** value, from raw SQL on source tables only. Hidden BOE = `invoice_no='OTH'` and the latest
     HIDE/RESTORE log is HIDE. An M2M-linked allotment counts 0. AT and AR are kept separate. `BOEAllotmentAllocation` is
     netted. Invoices = 0, because the local trade tables are empty;
   - the **planning-service** value, from `aggregate_license_usage`, `reconcile_license_plans`,
     `planning_operational_snapshots`, `ItemBalanceCalculator` bulk maps and the stored `available_quantity`;
   - the **API** value, read through the real views with a force-authenticated superuser and throttling disabled in the
     audit process only. The endpoints are `GET /api/licenses/{id}/` (81 × HTTP 200), `GET /api/license-item-plans/`,
     `GET /api/entitlement-plan/` (71 × 200; 1 × 400 multi-norm by design) and
     `POST /api/sion-planning-rules/preview-sion/` (71 × 200).
3. **Full scan** of all **1,118 licences with active plans** (2,520 plan lines): reconciliation remaining vs `max(balance,0)`
   and vs live item qty (`EV/p4_allplans.py`, exit 0).
4. **Whole-DB probes**:
   - stored vs live item qty on all 26,818 items (`p7`);
   - hidden-BOE licences (`p6`);
   - PLAN-basis allotments converted to BOEs (`p9`, `p9c`);
   - decomposition of the top cases (`p5`).
5. **Characterisation tests** on the test DB for the invoice, partial-allocation and lifecycle scenarios, which have no
   local data: `EV/tests/test_sat_planning_char.py` → **21 passed, exit 0** (`pytest_char.log`). These pin today's
   behaviour, not approved behaviour. Pinned planning suites (split-child reconciliation, entitlement planning ×2, plan
   enforcement, canonical planning, auto-plan force contract): **114 passed, exit 0** (`pytest_pinned.log`).

Tolerances: CIF 0.01, qty 0.001. Decimal throughout. Figures are reported unrounded, as the services return them.

**Row counts (local):**
- plans: 2,520 active on 1,118 licences, of which 2,472 carry a strategy snapshot `opening_operational_cif` and 32 are SPLIT_BY_PERCENT;
- active planning rules: 31 (A3627, E1, E126, E132, E5);
- BOEs with a planning target: 5,044 of 14,425;
- allotments with a target: 3,929;
- PLAN-basis allotment items: 86, all M2M-linked;
- trades / `InvoiceBOEAllocation` / `BOEAllotmentAllocation`: **0 / 0 / 0** (`EV/p0_counts.out`).

**Test-matrix mapping.** The numbered matrix is not stored in the repo. The scenario numbers from the SAT brief are used
here with these meanings:

| # | Scenario |
|---|---|
| 1 | No usage |
| 2 | BOE debit |
| 3 | Outstanding allotment |
| 4 | Invoice without BOE |
| 16 | Invoice + BOE, no double count |
| 17 | Partial BOE↔allotment allocation |
| 21 | Over-utilised licence / clamp |
| 22 | Priority |
| 23 | Multiple licences, same product |
| 24 | Plan lifecycle: inactive / cancelled / snapshot |
| 25 | Multiple import items, item-level AR / `is_boe` |

All other scenario numbers are owned by the financial, quantity, export and E2E reports.

## 2. How planning derives each figure (per import item)

| Figure | Source in planning | Evidence |
|---|---|---|
| Original entitlement qty | `LicenseImportItemsModel.quantity`. Group = Σ matched items. Multi-row groups are floored to whole kg in snapshots | `sion_planning_execution.py:520-533` · `planning_operational_snapshot.py:17-21` |
| Original CIF | SION export `cif_fc` (`plan_sion` opening) · licence `calculate_credit` (entitlement plan) · Σ all export rows (`operational_reconciliation`) | `sion_planning_execution.py:1596-1601` · `entitlement_planning_service.py:335` · `api/views/license.py:439-440` |
| Priority position | `SionPlanningRule.priority`, then pk, used **only** as a sort key. Reconciliation sorts by `planning_rule_priority`, then id | `sion_planning_execution.py:462,674` · `planning_usage_reconciliation.py:185-192,368-371` |
| Existing allotments | `AllotmentItems` with no M2M BOE **and** `allotment.is_boe=False` **and** `item.is_boe=False`. Full `qty`/`cif_fc`, no `BOEAllotmentAllocation` netting. All types (AT **and AR**) | `planning_usage_reconciliation.py:119-145` |
| Existing BOE debits | `eligible_boe_debits_for_license`: DEBIT rows, hidden BOEs excluded, each `RowDetails.pk` once | `item_usage.py:27-48` · `planning_usage_reconciliation.py:98-117` |
| Invoice consumption | **Not read** by planning usage. Enters only through the live financial balance (`get_balance_cif` / `calculate_financial_balance_for_licenses`) used as a cap, and as `AUTHORITATIVE_BALANCE_DIFFERENCE` in the entitlement plan | `sion_planning_execution.py:383-389,1614` · `entitlement_planning.py:191-195` |
| Remaining available CIF (new planning) | `min(tolerance(max(live fin, 0)), SION export CIF − planning actual)`, then decremented per line | `sion_planning_execution.py:385,1590-1617,552,619` |
| Remaining qty (new planning) | SPLIT/UNIT_VALUE: original − planning actual (`available_group_quantity`). STANDARD: **stored** `available_quantity` | `sion_planning_execution.py:520-533,749,798-805` |
| Remaining per persisted plan | theoretical − usage mapped to (source, target). Qty capped by **stored** `available_quantity`. CIF capped by live balance, **except** strategy-snapshot plans, which use the persisted `opening_operational_cif` | `planning_usage_reconciliation.py:275-358,364-390,161-178` |
| Plan “used” (allocation route) | Live AT allotments not linked to a BOE (`plan_status_for`: minus baseline; `plan_line_status_for`: PLAN basis + target). Always `min(actual, plan)` at allocation | `plan_enforcement.py:25-28,98-137,314-362` · `allocation_availability.py:46` |

## 3. Verdicts

| Q | Question | Verdict | Evidence |
|---|---|---|---|
| 1 | Existing allotments included | **PASS-EXC** | BOE + allotment per item = engine on 969/969 sample items, except the 13 D02 licences (Σ 1,160,224.05, `EV/p3_rootcause.json`). Also: AR is included (planning applies DEC-01 (a); 31 sample items differ from `ItemBalanceCalculator`), and partial allocations are not netted (latent, E-05) |
| 2 | BOE debits included | **PASS-EXC** | BOE CIF difference planning vs independent = 0.000 on every sample licence (`p3_rootcause.out`). Exception E-03: the planning “Actual Balance CIF” ignores the approved hidden-BOE opening rule (11 licences, 4,412,937.86) |
| 3 | Invoices not represented by BOEs | **PASS-EXC** (cap) / latent gap | Ceiling = min(live fin, …), so the invoice is deducted (char `s04`: ceiling 750.00 of 1,000.00). Gaps: planning usage, `operational_reconciliation.actual_balance_cif`, entitlement per-entitlement balance and planning qty all ignore invoice CIF/qty (char `s04b–d`). 0 rows locally |
| 4 | No duplicate invoice/BOE consumption | **PASS-EXC** | M2M allotment + BOE counted once (char `s03b`). Invoice linked via `trade.boes` counted once (`s16`). Inherited: an unlinked invoice + BOE is counted twice through the live cap (`s16b`, known SAT-FIN-005). Planning double-counts the allocated part of a partial `BOEAllotmentAllocation` (`s17`: ceiling 450.00 vs engine 600.00), which is conservative |
| 5 | Partial allocation | **PASS-EXC** (latent) | See E-05. 0 `BOEAllotmentAllocation` rows locally |
| 6 | Multiple licences | **PASS** | Usage is aggregated per licence (`planning_usage_reconciliation.py:97-121`). Char `s23`: licence A ceiling 700.00, B 1,000.00. The multi-licence-same-product sample shows no cross-talk (`p2_licences.json`) |
| 7 | Multiple import items | **PASS-EXC** | Per-item usage is keyed by `sr_number_id`/`item_id`. Physical source groups are not pooled across products (`sion_planning_execution.py:498-517`). Full scan: 0 items whose Σ plan remaining qty > live item qty (incl. AR) across 1,118 licences (`p4`). Exception: STANDARD + the reconciliation qty cap read the **stored** qty: stored < live on 5,981 items (under-offer, RC3 / D-D carried); stored > live on 0 items |
| 8 | Frozen / posted plans | **FAIL** | No “posted” state exists (active / deleted / cancelled / superseded only, `plan_lifecycle.py:75-99`). Inactive/cancelled plans are excluded (char `s24`). Frozen BOE rows are counted once (`entitlement_planning_service.py:263`). **E-01**: snapshot plans keep the persisted opening CIF and ignore the live balance (42 licences, Σ 633,992.64850). **E-04**: PLAN capacity is re-offered once its allotment becomes a BOE |
| 9 | Over-allocation prevented (CIF/qty, clamp) | **PASS-EXC** | New-plan ceiling ≤ `max(bal,0)` on 71/71 previews. Negative balance → ceiling 0, no lines (char `s21`). Live clamp on non-snapshot plans (`s21b`). Allocation takes `min(actual, plan)` (`allocation_availability.py:46`). Balances < 500.00 are zeroed (decided tolerance; 6 sample licences 1.90–230.56). Display exceptions E-01 / E-03 / D02 |
| 10 | Priority only an ordering | **PASS** | Priority appears only in sort keys (code refs §2). Char `s22`: priority-1 line 600.00 and priority-2 line 400.00 out of a 1,000.00 cap. No subtraction of a priority value anywhere |

**Test-matrix verdicts (planning level, char tests unless noted):**

| # | Verdict | Test | Result |
|---|---|---|---|
| 1 | PASS | `s01` | ceiling 1,000.00, line 1,000.000 @ 1.00 |
| 2 | PASS | `s02` | ceiling 700.00 |
| 3 | PASS | `s03`, `s03b` | — |
| 4 | PASS-EXC | `s04*` | — |
| 16 | PASS-EXC | `s16*` | — |
| 17 | PASS-EXC | `s17` | conservative |
| 21 | PASS-EXC | `s21*` | `s21c` reproduces E-01 |
| 22 | PASS | `s22` | — |
| 23 | PASS | `s23` | — |
| 24 | FAIL | `s24`, `s24b` | E-04 |
| 25 | PASS-EXC | `s25`, `s25b` | AR counted, `is_boe` excluded = DEC-01 / DEC-02 |

## 4. Sampled records — item quantity (45 of 969; full set `EV/p1_sample.json`)

Notes on the columns:
- Expected qty = original − visible BOE debit − outstanding allotment. AT only is the formula live today; AT+AR is DEC-01 (a).
- Invoiced = 0 on every row (no local trades).
- Planning qty is shown on two bases: the split basis (original − planning usage) and the stored qty (STANDARD and the reconciliation cap).
- The API qty is `import_license.available_quantity` from the licence detail. It equals the stored qty on 969/969 items (3 dp). It is sent as a JSON **number**, not a string.

| # | Licence | Tag | S.No | Item id | Description | HSN | Orig qty | Priority | Allotted qty AT/AR (outst.) | Debited qty | Invoiced | Expected avail qty (AT / AT+AR) | Planning avail qty (split basis) | Planning stored qty (STANDARD/cap) | API qty (`import_license.available_quantity`) | Diff planning − expected(AT+AR) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0310741378 | over | 1 | 1288 | wheat flour | 11000000 | 103117.040 | — | 0 / 0 | 19550.000 | 0 | 83567.040 / 83567.040 | 83567.040 | 83567.040 | 83567.040 | 0.000 |
| 2 | 0310821169 | over | 1 | 2128 | Wheat Flour (ITC (HS) Code: 11010000) | 11010000 | 2551840.110 | — | 0 / 0 | 1515594.000 | 0 | 1036246.110 / 1036246.110 | 1036246.110 | 1036246.110 | 1036246.110 | 0.000 |
| 3 | 0310827509 | over | 1 | 2293 | Wheat Flour (ITC (HS) Code: 11010000) | 11010000 | 1500080.073 | — | 0 / 0 | 1052040.000 | 0 | 448040.073 / 448040.073 | 448040.073 | 448040.073 | 448040.073 | 0.000 |
| 4 | 0310832464 | over | 1 | 4167 | CANE SUGAR LACTOSE/FRUCTOSE/MALTOSE/MA | 17019990 | 469494.912 | — | 0 / 469494.000 | 0 | 0 | 469494.912 / 0.912 | 0.912 | 0.912 | 0.912 | 0.000 |
| 5 | 0310832985 | over | 1 | 4222 | wheat flour | 11010000 | 517506.720 | — | 0 / 0 | 248065.000 | 0 | 269441.720 / 269441.720 | 269441.720 | 269441.720 | 269441.720 | 0.000 |
| 6 | 0310832983 | over | 1 | 4235 | wheat flour | 11010000 | 556870.580 | — | 0 / 0 | 237625.000 | 0 | 319245.580 / 319245.580 | 319245.580 | 319245.580 | 319245.580 | 0.000 |
| 7 | 0310833197 | over | 1 | 4362 | Wheat Flour (ITC (HS) Code: 110100000) | 11010000 | 584840.680 | — | 0 / 0 | 196974.000 | 0 | 387866.680 / 387866.680 | 387866.680 | 387866.680 | 387866.680 | 0.000 |
| 8 | 0310833198 | over | 1 | 4388 | wheat flour | 11010000 | 365761.255 | — | 0 / 0 | 175634.000 | 0 | 190127.255 / 190127.255 | 190127.255 | 190127.255 | 190127.255 | 0.000 |
| 9 | 0310833304 | over | 3 | 4425 | relevant fruit (juice/pulp/puree) | 20090000 | 1796368.469 | — | 0 / 0 | 1564418.000 | 0 | 231950.469 / 231950.469 | 231950.469 | 231950.000 | 231950.000 | 0.000 |
| 10 | 0310834151 | over | 1 | 4637 | cane sugar | 17019990 | 276007.200 | — | 0 / 276007.000 | 0 | 0 | 276007.200 / 0.200 | 0.200 | 0.200 | 0.200 | 0.000 |
| 11 | 0310737816 | over | 1 | 4904 | wheat flour | 11000000 | 253842.350 | — | 0 / 0 | 82500.000 | 0 | 171342.350 / 171342.350 | 171342.350 | 171342.350 | 171342.350 | 0.000 |
| 12 | 0310836031 | over | 1 | 5862 | HOT ROLLED NON-ALLOY/ALLOY STEEL STRIP | 72080000 | 3262.270 | — | 0 / 669.000 | 3067.240 | 0 | 195.030 / 0 | 0 | 0.000 | 0.000 | 0 |
| 13 | 0310836033 | over | 12 | 5890 | milk & milk products milk solids | 35022000 | 309108.768 | 6 | 0 / 0 | 309104.000 | 0 | 4.768 / 4.768 | 4.768 | 4.000 | 4.000 | 0.000 |
| 14 | 0310506757 | over | 1 | 6484 |  |  | 406386.000 | — | 0 / 0 | 488797.000 | 0 | 0 / 0 | 0 | 0.000 | 0.000 | 0 |
| 15 | 0310835522 | over | 7 | 7223 | Other confectionery ingredients :- Fru | 08023100 | 807263.300 | 1 | 0 / 0 | 807258.180 | 0 | 5.120 / 5.120 | 5.120 | 5.000 | 5.000 | 0.000 |
| 16 | 0310737558 | over | 4 | 10429 | cocoa, milk & milk products | 35022000 | 23689.120 | — | 0 / 0 | 23689.000 | 0 | 0.120 / 0.120 | 0.120 | 0.120 | 0.120 | 0.000 |
| 17 | 0311006580 | over | 10 | 11398 | Packing Material :- Polypropylene Film | 39021000 | 31188.110 | — | 0 / 0 | 31188.000 | 0 | 0.110 / 0.110 | 0.110 | 0.110 | 0.110 | 0.000 |
| 18 | 0910029777 | over | 13 | 13709 |  |  | 459520.500 | — | 0 / 0 | 438294.000 | 0 | 21226.500 / 21226.500 | 21226.500 | 21226.500 | 21226.500 | 0.000 |
| 19 | 0910038160 | over | 1 | 13743 |  |  | 73707.120 | — | 0 / 0 | 529.000 | 0 | 73178.120 / 73178.120 | 73178.120 | 73178.120 | 73178.120 | 0.000 |
| 20 | 0910043222 | over | 12 | 13813 |  |  | 53600.980 | — | 0 / 0 | 53600.000 | 0 | 0.980 / 0.980 | 0.980 | 0.980 | 0.980 | 0.000 |
| 21 | 0910057626 | over | 10 | 25007 | a) HDPE/PP/Granules Film Grade | 39020000 | 15000.000 | — | 0 / 0 | 51262.000 | 0 | 0 / 0 | 0 | 0.000 | 0.000 | 0 |
| 22 | 0910061510 | over | 3 | 24999 | COCOA POWDER | 18050000 | 30000.000 | — | 0 / 0 | 28260.000 | 0 | 1740.000 / 1740.000 | 1740.000 | 1740.000 | 1740.000 | 0.000 |
| 23 | 0910061671 | over | 11 | 25018 |  |  | 3629.360 | — | 0 / 0 | 3626.430 | 0 | 2.930 / 2.930 | 2.930 | 2.930 | 2.930 | 0.000 |
| 24 | 5211016746 | over | 1 | 31378 | (a) Silica (other than Fumed Silica) 2 | 32061190 | 1926001.080 | — | 40000.000 / 0 | 1664315.000 | 0 | 221686.080 / 221686.080 | 261686.080 | 221686.080 | 221686.080 | 40000.000 |
| 25 | 5211016747 | over | 1 | 31518 | (a) Silica (other than Fumed Silica) 2 | 32061190 | 1974545.700 | — | 100000.000 / 0 | 1441377.000 | 0 | 433168.700 / 433168.700 | 533168.700 | 433168.000 | 433168.000 | 100000.000 |
| 26 | 0310499297 | over | 1 | 31665 | MAIDA/ATTA/FLOUR | 11000000 | 1125370.950 | — | 0 / 0 | 128487.000 | 0 | 996883.950 / 996883.950 | 996883.950 | 996883.000 | 996883.000 | 0.000 |
| 27 | 0210118391 | over | 1 | 31684 | MAIDA/ATTA/FLOUR | 11090000 | 109574.120 | — | 0 / 0 | 10389.000 | 0 | 99185.120 / 99185.120 | 99185.120 | 99185.000 | 99185.000 | 0.000 |
| 28 | 0310550938 | over | 1 | 31696 | MAIDA/ATTA/FLOUR | 11000000 | 240481.450 | — | 0 / 0 | 71005.690 | 0 | 169475.760 / 169475.760 | 169475.760 | 169475.000 | 169475.000 | 0.000 |
| 29 | 0310493058 | over | 1 | 31979 | SUGAR | 17010000 | 178511.280 | — | 0 / 0 | 1715.000 | 0 | 176796.280 / 176796.280 | 176796.280 | 176796.000 | 176796.000 | 0.000 |
| 30 | 1311001682 | over | 4 | 32392 | CARDAMOM | 09083100 | 12200.000 | — | 0 / 0 | 12200.000 | 0 | 0.000 / 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 31 | 5011000781 | over | 4 | 32393 | CARDAMOM | 09083100 | 0.000 | — | 0 / 0 | 2130.000 | 0 | 0 / 0 | 0 | 0.000 | 0.000 | 0 |
| 32 | 5011000785 | over | 4 | 32394 | CARDAMOM |  | 7710.000 | — | 0 / 0 | 7710.000 | 0 | 0.000 / 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 33 | 3411007247 | over | 1 | 32903 | Relevant fats and Oils namely sesame o | 15119020 | 82050.250 | — | 12737.000 / 0 | 78730.000 | 0 | 0 / 0 | 3320.250 | 0.000 | 0.000 | 3320.250 |
| 34 | 3411007496 | over | 1 | 33991 | (a) Silica (other than Fumed Silica) 2 | 32061190 | 2207206.390 | — | 160000.000 / 0 | 1390466.000 | 0 | 656740.390 / 656740.390 | 816740.390 | 656740.000 | 656740.000 | 160000.000 |
| 35 | 3411007774 | over | 2 | 35026 | Edible Vegetable Oils such as Mustard  | 15132110 | 34408.330 | 4 | 0 / 0 | 34407.450 | 0 | 0.880 / 0.880 | 0.880 | 0.000 | 0.000 | 0.000 |
| 36 | 3411008581 | over | 1 | 40132 | Glass Formers namely, (a) Silica (othe | 32061190 | 1091691.380 | 1 | 80000.000 / 0 | 1085060.000 | 0 | 0 / 0 | 0 | 0.000 | 0.000 | 0 |
| 37 | 0311006570 | d02 | 13 | 11772 | Relevant Fruit Juice/Pulp/Puree (HS Co | 20091100 | 29797.200 | — | 18678.000 / 0 | 11119.000 | 0 | 0.200 / 0.200 | 18678.200 | 0.200 | 0.200 | 18678.000 |
| 38 | 0511031038 | d02 | 5 | 27299 | Packing Material: Polypropylene | 39021000 | 104268.830 | 10 | 49500.000 / 0 | 54768.000 | 0 | 0.830 / 0.830 | 49500.830 | 0.830 | 0.830 | 49500.000 |
| 39 | 0311043071 | d02 | 9 | 28847 | Other Confectionery Ingredients - Frui | 08029900 | 73710.260 | — | 3102.000 / 0 | 73710.000 | 0 | 0 / 0 | 0.260 | 0.000 | 0.000 | 0.260 |
| 40 | 0311044803 | d02 | 8 | 29850 | Other Confectionery ingredients -edibl | 08029900 | 12165.120 | — | 11327.000 / 0 | 12165.000 | 0 | 0 / 0 | 0.120 | 0.000 | 0.000 | 0.120 |
| 41 | 0311044791 | d02 | 9 | 29910 | Other Confectionery Ingredients -Fruit | 08029900 | 6648.180 | — | 3571.000 / 0 | 6648.000 | 0 | 0 / 0 | 0.180 | 0.000 | 0.000 | 0.180 |
| 42 | 5211016560 | d02 | 1 | 31002 | (a) Silica (other than Fumed Silica) 2 | 32061190 | 2027271.770 | — | 100000.000 / 0 | 1359815.000 | 0 | 567456.770 / 567456.770 | 667456.770 | 567456.770 | 567456.770 | 100000.000 |
| 43 | 3411007342 | d02 | 1 | 33193 | (a) Silica (other than Fumed Silica) 2 | 32061190 | 2178991.770 | — | 20000.000 / 0 | 1701680.000 | 0 | 457311.770 / 457311.770 | 477311.770 | 457311.000 | 457311.000 | 20000.000 |
| 44 | 0311051816 | d02 | 13 | 34307 | Milk Solids | 04041020 | 40884.950 | None | 3000.000 / 0 | 39020.000 | 0 | 0 / 0 | 1864.950 | 0.000 | 0.000 | 1864.950 |
| 45 | 3411007711 | d02 | 41 | 34900 | Milk & Milk Products / Milk Solids (HS | 04041020 | 173245.240 | — | 49815.000 / 0 | 122090.550 | 0 | 1339.690 / 1339.690 | 51154.690 | 1339.000 | 1339.000 | 49815.000 |

## 5. Sampled records — licence CIF (all 81)

Expected = original − visible BOE − outstanding allotment (AT+AR); invoiced = 0. The engine's financial balance equals
Expected on 80/81 licences. The exception is 0311052376 (hidden-BOE opening rule, 48,254.64; approved, RC2/RC8).

The preview ceiling is ≤ the cap on every row. Differences from the planning blocks are explained in §6.

| Licence | Tag | SION | Original CIF | Debited CIF (BOE) | Allotted CIF (outst., AT+AR) | Invoiced | Expected available (canonical, our BOEs) | Engine `get_balance_cif` | Planning new-plan ceiling (preview) | API `operational_reconciliation.actual_balance_cif` | API Σ plan `remaining_cif` | Cap `max(bal,0)` | Diff (API actual − cap) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0310741378 | over | E5 | 198645.45 | 198442.090 | 12852.00 | 0 | -12648.640 | -12648.64 | E5:0.0 | 0 | — | 0 | 0 |
| 0310821169 | over | E5 | 5365844.43 | 5357709.850 | 73242.99 | 0 | -65108.410 | -65108.41 | E5:0.0 | 0 | — | 0 | 0 |
| 0310827509 | over | E5 | 0.00 | 3257841.980 | 190009.42 | 0 | -3447851.400 | -3447851.40 | E5:0.0 | 0 | — | 0 | 0 |
| 0310832464 | over | E1 | 665335.86 | 525100.980 | 151177.36 | 0 | -10942.480 | -10942.48 | E1:0.0 | 0 | — | 0 | 0 |
| 0310832985 | over | E5 | 742663.85 | 677176.300 | 65550.85 | 0 | -63.300 | -63.30 | E5:0.0 | 0 | — | 0 | 0 |
| 0310832983 | over | E5 | 768671.49 | 697923.110 | 70977.80 | 0 | -229.420 | -229.42 | E5:0.0 | 0 | — | 0 | 0 |
| 0310833197 | over | E5 | 732374.65 | 656219.160 | 76394.81 | 0 | -239.320 | -239.32 | E5:0.0 | 0 | — | 0 | 0 |
| 0310833198 | over | E5 | 518277.75 | 470671.000 | 47777.57 | 0 | -170.820 | -170.82 | E5:0.0 | 0 | — | 0 | 0 |
| 0310833304 | over | E1 | 6824661.89 | 6790943.160 | 2011506.09 | 0 | -1977787.360 | -1977787.36 | E1:0.0 | 0 | — | 0 | 0 |
| 0310834151 | over | E1 | 397969.53 | 308977.590 | 91082.31 | 0 | -2090.370 | -2090.37 | E1:not eligible | 0 | — | 0 | 0 |
| 0310737816 | over | E5 | 286712.63 | 286571.570 | 33158.07 | 0 | -33017.010 | -33017.01 | E5:0.0 | 0 | — | 0 | 0 |
| 0310836031 | over | C473 | 1667520.00 | 1472603.790 | 397934.58 | 0 | -203018.370 | -203018.37 | C473:HTTP 400 | 0 | — | 0 | 0 |
| 0310836033 | over | E5 | 4757824.69 | 4772655.080 | 0 | 0 | -14830.390 | -14830.39 | E5:0.0 | 0 | 0.00 | 0 | 0 |
| 0310506757 | over |  | 402418.58 | 438283.560 | 0 | 0 | -35864.980 | -35864.98 | — | 0 | — | 0 | 0 |
| 0310835522 | over | E1 | 14454675.99 | 14454728.290 | 0 | 0 | -52.300 | -52.30 | E1:0.0 | 0 | 24094.20 | 0 | 0 |
| 0310737558 | over | E1 | 211696.12 | 297786.440 | 0 | 0 | -86090.320 | -86090.32 | E1:0.0 | 0 | — | 0 | 0 |
| 0311006580 | over | E1 | 0.00 | 43850.850 | 0 | 0 | -43850.850 | -43850.85 | E1:0.0 | 0 | — | 0 | 0 |
| 0910029777 | over |  | 1105489.97 | 1113911.120 | 0 | 0 | -8421.150 | -8421.15 | — | 0 | — | 0 | 0 |
| 0910038160 | over |  | 409583.04 | 458278.190 | 0 | 0 | -48695.150 | -48695.15 | — | 0 | — | 0 | 0 |
| 0910043222 | over |  | 665938.81 | 665938.880 | 0 | 0 | -0.070 | -0.07 | — | 0 | — | 0 | 0 |
| 0910057626 | over |  | 0 | 50258.850 | 0 | 0 | -50258.850 | -50258.85 | — | 0 | — | 0 | 0 |
| 0910061510 | over |  | 0 | 118303.610 | 0 | 0 | -118303.610 | -118303.61 | — | 0 | — | 0 | 0 |
| 0910061671 | over |  | 0 | 23678.190 | 0 | 0 | -23678.190 | -23678.19 | — | 0 | — | 0 | 0 |
| 5211016746 | over | A3627 | 3250277.56 | 3249314.330 | 76000.00 | 0 | -75036.770 | -75036.77 | A3627:0.0 | 963.230 | — | 0 | 963.230 |
| 5211016747 | over | A3627 | 3211728.90 | 3023139.410 | 188900.00 | 0 | -310.510 | -310.51 | A3627:0.0 | 188589.490 | — | 0 | 188589.490 |
| 0310499297 | over | E5 | 1903101.21 | 2356473.060 | 0 | 0 | -453371.850 | -453371.85 | E5:0.0 | 0 | — | 0 | 0 |
| 0210118391 | over | E5 | 166507.00 | 177900.130 | 0 | 0 | -11393.130 | -11393.13 | E5:0.0 | 0 | — | 0 | 0 |
| 0310550938 | over | E5 | 311427.54 | 337778.800 | 0 | 0 | -26351.260 | -26351.26 | E5:0.0 | 0 | — | 0 | 0 |
| 0310493058 | over | E1 | 243058.26 | 283935.740 | 0 | 0 | -40877.480 | -40877.48 | E1:0.0 | 0 | — | 0 | 0 |
| 1311001682 | over | E126 | 0.00 | 75874.080 | 0 | 0 | -75874.080 | -75874.08 | E126:not eligible | 0 | — | 0 | 0 |
| 5011000781 | over |  | 0 | 13354.560 | 0 | 0 | -13354.560 | -13354.56 | — | 0 | — | 0 | 0 |
| 5011000785 | over |  | 0 | 48339.760 | 0 | 0 | -48339.760 | -48339.76 | — | 0 | — | 0 | 0 |
| 3411007247 | over | E126 | 398638.76 | 382701.790 | 34338.95 | 0 | -18401.980 | -18401.98 | E126:0.0 | 15936.970 | — | 0 | 15936.970 |
| 3411007496 | over | A3627 | 3349190.48 | 3082417.840 | 277440.00 | 0 | -10667.360 | -10667.36 | A3627:0.0 | 266772.640 | — | 0 | 266772.640 |
| 3411007774 | over | E132 | 675271.78 | 675494.910 | 0 | 0 | -223.130 | -223.13 | E132:0.0 | 0 | 3120.000 | 0 | 0 |
| 3411008581 | over | A3627 | 3706669.33 | 3547298.650 | 256240.00 | 0 | -96869.320 | -96869.32 | A3627:0.0 | 0 | 0.000 | 0 | 0 |
| 0311006570 | d02 | E1 | 262941.61 | 163376.840 | 24113.30 | 0 | 75451.470 | 75451.47 | E1:75451.47 | 99564.770 | 1217.430 | 75451.47 | 24113.300 |
| 0511031038 | d02 | E132 | 828373.54 | 132956.520 | 49995.00 | 0 | 645422.020 | 645422.02 | E132:645422.02 | 695417.020 | 327702.04 | 645422.02 | 49995.000 |
| 0311043071 | d02 | E1 | 1204001.14 | 769351.100 | 13431.66 | 0 | 421218.380 | 421218.38 | E1:421218.38 | 434650.040 | 421218.38 | 421218.38 | 13431.660 |
| 0311044803 | d02 | E1 | 179830.51 | 84843.050 | 49045.91 | 0 | 45941.550 | 45941.55 | E1:45941.55 | 94987.460 | 45941.55 | 45941.55 | 49045.910 |
| 0311044791 | d02 | E1 | 124118.57 | 43341.190 | 15462.43 | 0 | 65314.950 | 65314.95 | E1:65314.95 | 80777.380 | 65314.95 | 65314.95 | 15462.430 |
| 5211016560 | d02 | A3627 | 2972833.09 | 2702475.880 | 270300.00 | 0 | 57.210 | 57.21 | A3627:0.0 | 270357.210 | — | 57.21 | 270300.000 |
| 3411007342 | d02 | A3627 | 3256460.88 | 3218448.600 | 38000.00 | 0 | 12.280 | 12.28 | A3627:0.0 | 38012.280 | — | 12.28 | 38000.000 |
| 0311051816 | d02 | E5 | 416785.42 | 412321.860 | 4233.00 | 0 | 230.560 | 230.56 | E5:0.0 | 4463.560 | 0.000 | 230.56 | 4233.000 |
| 3411007711 | d02 | E5 | 4024512.05 | 3725573.880 | 271071.90 | 0 | 27866.270 | 27866.27 | E5:27866.27 | 146830.070 | 0.000 | 27866.27 | 118963.800 |
| 0311051262 | outstanding_allot+plan | E1 | 466998.73 | 81044.980 | 71175.61 | 0 | 314778.140 | 314778.14 | E1:314778.14 | 314778.140 | 13011.60 | 314778.14 | 0.000 |
| 3411008158 | outstanding_allot+plan | E132 | 7814318.76 | 853146.380 | 289332.00 | 0 | 6671840.380 | 6671840.38 | E132:6671840.38 | 6671840.380 | 6671836.88000 | 6671840.38 | 0.000 |
| 5611004853 | outstanding_allot+plan | E1 | 28535.39 | 2564.020 | 568.40 | 0 | 25402.970 | 25402.97 | E1:25402.97 | 25402.970 | 14638.50 | 25402.97 | 0.000 |
| 0310833701 | outstanding_allot+plan | E1 | 380672.45 | 146035.900 | 84254.45 | 0 | 150382.100 | 150382.10 | E1:150382.1 | 150382.100 | 13524.00 | 150382.10 | 0.000 |
| 0310832494 | outstanding_allot+plan | E5 | 4439905.68 | 3834802.330 | 269627.65 | 0 | 335475.700 | 335475.70 | E5:335475.7 | 335475.700 | 2415.710 | 335475.70 | 0.000 |
| 0311052376 | outstanding_allot+plan | E5 | 171597.69 | 108653.150 | 14688.00 | 0 | 48256.540 | 1.90 | E5:0.0 | 48256.540 | 4438.80 | 1.90 | 48254.640 |
| 0310824203 | outstanding_allot+plan | E1 | 177349.09 | 0 | 40817.20 | 0 | 136531.89 | 136531.89 | E1:136531.89 | 136531.89 | 118357.19 | 136531.89 | 0.00 |
| 0311051531 | outstanding_allot+plan | E5 | 238745.71 | 225979.730 | 12752.10 | 0 | 13.880 | 13.88 | E5:0.0 | 13.880 | 877.88 | 13.88 | 0.000 |
| 0310831827 | multi_item+plan | E1 | 139052.06 | 10606.710 | 0 | 0 | 128445.350 | 128445.35 | E1:128445.35 | 128445.350 | 10894.14 | 128445.35 | 0.000 |
| 0311005370 | multi_item+plan | E5 | 706147.13 | 657567.640 | 0 | 0 | 48579.490 | 48579.49 | E5:48579.49 | 48579.490 | 48579.49 | 48579.49 | 0.000 |
| 0310793650 | multi_item+plan | E1 | 150780.63 | 110975.680 | 38400.00 | 0 | 1404.950 | 1404.95 | E1:1404.95 | 1404.950 | 0.000 | 1404.95 | 0.000 |
| 3111005758 | multi_item+plan | E5 | 107945.72 | 107738.160 | 0 | 0 | 207.560 | 207.56 | E5:0.0 | 207.560 | 26682.50 | 207.56 | 0.000 |
| 0310736178 | multi_item+plan | E5 | 149994.00 | 0 | 0 | 0 | 149994.00 | 149994.00 | E5:149994.0 | 149994.00 | 100100.00 | 149994.00 | 0.00 |
| 0310831825 | multi_item+plan | E1 | 103693.16 | 6669.100 | 26029.76 | 0 | 70994.300 | 70994.30 | E1:70994.3 | 70994.300 | 6062.82 | 70994.30 | 0.000 |
| 0910054277 | multi_licence_same_product+plan | E5 | 1108500.14 | 987689.320 | 0 | 0 | 120810.820 | 120810.82 | E5:120810.82 | 120810.820 | 43376.99 | 120810.82 | 0.000 |
| 0311037521 | multi_licence_same_product+plan | E126 | 337436.50 | 337318.620 | 0 | 0 | 117.880 | 117.88 | E126:0.0 | 117.880 | 10197.88 | 117.88 | 0.000 |
| 0310694983 | multi_licence_same_product+plan | E5 | 357845.77 | 0 | 0 | 0 | 357845.77 | 357845.77 | E5:357845.77 | 357845.77 | 227500.00 | 357845.77 | 0.00 |
| 3411008066 | multi_licence_same_product+plan | A3627 | 3856488.43 | 0 | 0 | 0 | 3856488.43 | 3856488.43 | A3627:3856488.43 | 3856488.43 | 3856488.43 | 3856488.43 | 0.00 |
| 5211015108 | multi_licence_same_product+plan | E132 | 214709.75 | 197227.620 | 0 | 0 | 17482.130 | 17482.13 | E132:17482.13 | 17482.130 | 17482.13 | 17482.13 | 0.000 |
| 0311042453 | multi_licence_same_product+plan | E1 | 790702.98 | 781036.920 | 0 | 0 | 9666.060 | 9666.06 | E1:9666.06 | 9666.060 | 9666.06 | 9666.06 | 0.000 |
| 0310837955 | random_plan | E1 | 127004.85 | 126999.030 | 0 | 0 | 5.820 | 5.82 | E1:0.0 | 5.820 | 0.00 | 5.82 | 0.000 |
| 0311032977 | random_plan | E1 | 73000.18 | 19017.410 | 0 | 0 | 53982.770 | 53982.77 | E1:53982.77 | 53982.770 | 9999.040 | 53982.77 | 0.000 |
| 0310630718 | random_plan | E1 | 308587.22 | 134981.960 | 0 | 0 | 173605.260 | 173605.26 | E1:173605.26 | 173605.260 | 18426.00 | 173605.26 | 0.000 |
| 0310782452 | random_plan | E1 | 134068.14 | 100900.080 | 31809.02 | 0 | 1359.040 | 1359.04 | E1:1359.04 | 1359.040 | 1357.040 | 1359.04 | 0.000 |
| 0310835311 | random_plan | E1 | 195708.96 | 50085.540 | 0 | 0 | 145623.420 | 145623.42 | E1:145623.42 | 145623.420 | 33600.75 | 145623.42 | 0.000 |
| 0911008444 | random_plan | E5 | 474827.34 | 227022.200 | 0 | 0 | 247805.140 | 247805.14 | E5:247805.14 | 247805.140 | 247805.14 | 247805.14 | 0.000 |
| 0311046584 | random_plan | E5 | 87544.00 | 77153.040 | 0 | 0 | 10390.960 | 10390.96 | E5:10390.96 | 10390.960 | 10390.96 | 10390.96 | 0.000 |
| 0311045036 | random_plan | E1 | 407076.38 | 279357.810 | 0 | 0 | 127718.570 | 127718.57 | E1:127718.57 | 127718.570 | 127716.68 | 127718.57 | 0.000 |
| 0311037523 | random_plan | E132 | 649896.00 | 395073.290 | 0 | 0 | 254822.710 | 254822.71 | E132:254822.71 | 254822.710 | 30676.570 | 254822.71 | 0.000 |
| 0311046315 | random_plan | E132 | 1127159.85 | 717529.100 | 0 | 0 | 409630.750 | 409630.75 | E132:409630.75 | 409630.750 | 72569.70 | 409630.75 | 0.000 |
| 0311040911 | random_any | E132 | 809027.90 | 474310.920 | 0 | 0 | 334716.980 | 334716.98 | E132:334716.98 | 334716.980 | 61725.190 | 334716.98 | 0.000 |
| 0311041018 | random_any | E1 | 799768.23 | 784454.290 | 0 | 0 | 15313.940 | 15313.94 | E1:15313.94 | 15313.940 | 15313.94 | 15313.94 | 0.000 |
| 0910056126 | random_any | E5 | 1172307.35 | 1099573.160 | 0 | 0 | 72734.190 | 72734.19 | E5:72734.19 | 72734.190 | 0.00 | 72734.19 | 0.000 |
| 0310656734 | random_any | E1 | 864852.00 | 0 | 0 | 0 | 864852.00 | 864852.00 | E1:864852.0 | 864852.00 | 49125.96 | 864852.00 | 0.00 |
| 5211011096 | random_any | A3627 | 2801206.96 | 2801205.530 | 0 | 0 | 1.430 | 1.43 | A3627:0.0 | 1.430 | — | 1.43 | 0.000 |
| 0310742587 | random_any | E5 | 286367.69 | 0 | 0 | 0 | 286367.69 | 286367.69 | E5:286367.69 | 286367.69 | 204750.00 | 286367.69 | 0.00 |

## 6. Exceptions

| Licence | Import item / plan | Invoice | BOE | Expected CIF | Actual CIF | CIF diff | Expected qty | Actual qty | Qty diff | Root cause | Severity | Financial impact |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0310837232 | item 7303 / plan 21188 (Wheat Gluten) | — | 3,104,301.76 of usage is unmapped (no target) | ≤ 279.89 (`max(bal,0)`) | 233,287.06950 (`remaining_cif`, API = service) | +233,007.17950 | — (CIF-bound) | 155,524.713 | — | **E-01**: snapshot plan, live cap bypassed (`planning_usage_reconciliation.py:161-178`). Remaining is reduced only by usage mapped to (source, target) (`:275-284`) | Medium | Display/report overstates remaining planned CIF. Not allocatable (allocation = min(actual, plan)) |
| 0311005336 | item 9512 / plan 14707 | — | 436,606.66 unmapped | ≤ 53.09 | 123,337.92 | +123,284.83 | — | 82,225.280 | — | E-01 | Medium | as above |
| 3111006003 | 3 plans | — | — | ≤ 286.74 | 68,500.79 | +68,214.05 | — | — | — | E-01 | Medium | as above |
| 0310838967 | 2 plans | — | — | ≤ 4.27 | 28,703.05900 | +28,698.78900 | — | — | — | E-01 | Medium | as above |
| 0310835522 | plan 28233 | — | — | 0 (bal −52.30, over-utilised) | 24,094.20 (API shows it next to `actual_license_balance_cif` −52.30) | +24,094.20 | — | 16,062.800 | — | E-01 | Medium | as above |
| **E-01 total** | 42 licences / all snapshot plans | — | — | — | — | **+633,992.64850** | — | — | 0 qty breaches | `EV/p4_allplans.json` `cif_over` | Medium | Display only |
| 0311052376 | licence (`operational_reconciliation`) | — | hidden BOEs | 1.90 | 48,256.54 | +48,254.64 | — | — | — | **E-03**: `actual_balance_cif` = gross − visible BOE − allotment (`api/views/license.py:433-458`). It ignores the approved opening rule original − hidden − purchase | Medium | Plan tab “Actual Balance CIF” overstated. Planning caps are unaffected |
| 0311050991 / 0311052001 / 0311051527 / 0311045787 | licence | — | hidden | 29,053.25 / 0.86 / 55,308.82 / 10,955.56 | 153,979.16 / 34,380.84 / 82,918.36 / 13,317.20 | +124,925.91 / +34,379.98 / +27,609.54 / +2,361.64 | — | — | — | E-03 (planned licences) | Medium | as above |
| **E-03 total** | 11 hidden-BOE licences (5 planned) | — | — | — | — | **+4,412,937.86** (= total hidden CIF) | — | — | — | `EV/p6_hidden.json` | Medium | Display only |
| 5211016560 · 3411007496 · 5211016747 (top 3 of 13) | items 31002 / 33991 / 31518 | — | none linked | 57.21 / 0 / 0 | 270,357.21 / 266,772.64 / 188,589.49 | +270,300.00 / +266,772.64 / +188,589.49 | 567,456.770 / 656,740.390 / 433,168.700 | 667,456.770 / 816,740.390 / 533,168.700 | +100,000 / +160,000 / +100,000 | **DEC-02 / SAT-DEF-002**: planning usage drops `is_boe` allotments with no M2M (`planning_usage_reconciliation.py:123-124`) | High (carried) | 13 licences, Σ 1,160,224.05 CIF in the planning “Actual Balance CIF” and in split-basis qty. The new-plan ceiling is safe (min with live) |
| 0311053542 | item 35532 / plan 12502 | — | 3364128 (filed 2026-08-27, after the plan of 2026-08-21) | remaining 82.49 | 2,686.86 | +2,604.37 | 77.133 | 995.133 | +918.000 | **E-04**: plan “used” counts only BOE-unlinked AT allotments (`plan_enforcement.py:25-28,118-125`). A PLAN allotment converted to a BOE restores plan capacity (char `s24b`: 300 → 500) | Medium | Bounded by the actual position: licence balance 70.56 |
| 0311054202 | item 35985 / plan 12506 | — | 3364128 | 305.07 | 6,957.84 | +6,652.77 | 231.977 | 2,576.977 | +2,345.000 | E-04 | Medium | Bounded: balance 274.59. Σ E-04 on real data 9,257.14 CIF / 3,263 qty |
| 0310833304 (and 3 more, none planned) | item 4423 | — | — (AR allotment 6,095,473 kg) | — | — | — | 0 (AT+AR) | 262,216.000 stored (STANDARD basis); split basis 0 | +262,216.000 | **DEC-01 / SAT-DEF-001** (AR not in item calc / stored cache). Planning split usage already deducts AR | High (carried) | 4 items, 584,066.54 kg offered by the STANDARD basis (`EV/p7_stored_qty.json`) |
| synthetic (`s04c`) | 1 item | SALE 250.00 no BOE | — | 750.00 | 1,000.00 (`actual_balance_cif` formula) | +250.00 | 750.000 | 1,000.000 (planning qty basis) | +250.000 | **E-02**: planning usage has no invoice term (`planning_usage_reconciliation.py:81-147`; `api/views/license.py:433-458`; `entitlement_planning.py:109-110`) | Medium (latent) | 0 locally. The new-plan ceiling is correct (750.00) |
| synthetic (`s17`) | 1 item | — | 150.00 partially allocated to a 400.00 allotment | 600.00 | 450.00 (ceiling) | −150.00 | — | — | — | **E-05**: planning counts the full allotment CIF plus the BOE (`:133-145`). No `BOEAllotmentAllocation` netting | Low (latent, conservative) | Under-plans by the allocated amount |
| 0310837232 etc. | `remaining_cif` values with 3–5 dp (233,287.06950; 28,703.05900) | — | — | — | — | — | — | — | — | **E-06**: `reconciled_cif = committed + residual × unit_price` is never quantized (`planning_usage_reconciliation.py:307,314`) | Low | Presentation only |
| UI | Plan tab group totals | — | — | — | — | — | — | — | — | **E-07**: `PlanningEditor.tsx:62` `parseFloat` sums for group remaining/used CIF (`:433-440,694-707`). `LicensePlanningWorkspace.tsx:219-220` sends percentage/unit price as `Number().toFixed(2)` (DB is 2 dp, so no loss today) | Low | Display float drift only |

Carried and unchanged here: D05 (cross-licence M2M), D03/D04/D07 (DEC-03/05/07), D09 (INDIVIDUAL mode uses
`ItemBalanceCalculator.calculate_item_balance` as the item ceiling, `sion_planning_execution.py:1585`; not measured here).

## 7. Proposed register entries (new only; not applied to the registers)

**Owner questions:**

| ID | Question | Current behaviour | Options and impact |
|---|---|---|---|
| **DEC-11** | Should a persisted strategy plan's remaining CIF be capped at today's `max(licence balance, 0)`, or keep its plan-time opening snapshot? | The snapshot is kept (E-01) | (a) Cap live: remaining planned CIF falls by 633,992.65 on 42 licences, display only. (b) Keep, but label “as planned” and show a “not fundable” amount |
| **DEC-12** | Should the Plan tab “Actual Balance CIF” (`operational_reconciliation`) apply the approved hidden-BOE opening rule and the billed-without-BOE term, i.e. equal `get_balance_cif`? | Gross − visible BOE − allotment (E-02 / E-03) | (a) Use the engine: −4,412,937.86 on 11 licences now, plus invoices once trades exist. (b) Keep, labelled “gross, before prior-owner/invoice adjustments” |
| **DEC-13** | Is plan capacity consumed by a PLAN-basis allotment that later becomes a BOE? | Capacity is restored (E-04) | (a) Keep counting it as consumed: −9,257.14 plan CIF on 2 plan lines. (b) Keep restoring it |
| **DEC-14** | Should planning usage net partial `BOEAllotmentAllocation`, as the engine does? | Not netted; conservative (E-05) | Latent; 0 rows |

**Defects:**

| ID | Short name | Sev | Ref |
|---|---|---|---|
| SAT-DEF-100 | Snapshot plan remaining CIF not capped by live balance | Medium | E-01 |
| SAT-DEF-101 | Planning usage ignores billed-without-BOE CIF/qty in display and qty basis | Medium, latent | E-02 |
| SAT-DEF-102 | `operational_reconciliation.actual_balance_cif` ignores the hidden-BOE opening rule | Medium | E-03 |
| SAT-DEF-103 | Plan “used” drops BOE-converted PLAN allotments | Medium | E-04 |
| SAT-DEF-104 | No partial-allocation netting in planning usage | Low | E-05 |
| SAT-DEF-105 | Unquantized `remaining_cif` | Low | E-06 |
| SAT-DEF-106 | Float arithmetic in the Plan tab totals | Low | E-07 |

Cited, not duplicated: DEC-01 / SAT-DEF-001 (AR qty: planning already deducts AR, so the STANDARD stored-qty path remains),
DEC-02 / SAT-DEF-002 (`is_boe` without M2M: 13 licences, 1,160,224.05 in the planning display), DEC-03, DEC-05, DEC-07.

## 8. Run log (exit codes)

| Step | File | Exit | Result |
|---|---|---|---|
| Counts | `p0_counts.py` | 0 | — |
| Sample | `p1_sample.py` | 0 | Final run; 81 licences, 0 errors |
| Analysis | `p2_analyze.py` | 0 | — |
| Root cause | `p3_rootcause.py` | 0 | — |
| Full scan | `p4_allplans.py` | 0 | 1,118 licences, 0 errors |
| Decomposition | `p5_decompose.py` | 0 | — |
| Hidden-BOE licences | `p6_hidden.py` | 0 | — |
| Stored vs live qty | `p7_stored_qty.py` | 0 | — |
| Tables | `p8_tables.py` | 0 | — |
| PLAN allotments → BOE | `p9_plan_reoffer.py` | 0 | — |
| PLAN allotments → BOE, after plan | `p9c_after.py` | 0 | — |
| Characterisation tests | `pytest_char.log` | 0 | 21 passed |
| Pinned planning tests | `pytest_pinned.log` | 0 | 114 passed |

Earlier runs, superseded by the runs above and kept on disk:
- `pytest_char_run1.log`, exit 1: 2 assertions had not accounted for the 500.00 tolerance. They were corrected to pin it, and `s16c` was added.
- The first two `p1` runs failed on API calls: HTTP 400 (ALLOWED_HOSTS), then 429 (throttling).

Quality gates were not run: this is an audit, with no code change.
