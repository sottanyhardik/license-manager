# SAT Phase 9 — Independent Review (sat-review)

| | |
|---|---|
| Date | 2026-11-20 |
| Branch / HEAD | `feature/v5` @ `ec3604cb` |
| Working-tree fingerprint | `git diff \| shasum \| cut -c1-12` = **`f6dd80443ee6`** (180 dirty paths). SAT started at `6f1712e03000`, so peers changed the tree during SAT. `backend/apps/license/services/balance_calculator.py` and `bill_of_entry/models.py` are **clean** (not in the diff); several exporters and the licence view/serializer are peer-modified |
| DB | `lmanagement@localhost` (PostgreSQL 18.7), READ ONLY: `SET TRANSACTION READ ONLY` / `BEGIN READ ONLY`, every app call inside `atomic()` + `set_rollback(True)` |
| Row counts | licences 2,185 · export items 2,178 · import items 26,818 · BOEs 14,425 · BOE rows 168,629 (D 22,075 / C 146,554, C rows have no BOE) · allotments 6,526 (AT 6,494 / AR 32) · allotment items 11,610 (all CREATED) · BOE↔allotment M2M 6,427 · recon log 75 (61 HIDE) · **trades 0, trade lines 0, trade_boes 0, InvoiceBOEAllocation 0, BOEAllotmentAllocation 0, licence purchases 0** · LicenseBalance 2,185 (`00_rowcounts.txt`) |
| Test DBs | `test_lmanagement_sat_rev` (my pytest runs) · `test_lmanagement_sat_sec` (security repro, `--reuse-db`, per-test rollback, MEDIA_ROOT = pytest tmp) |
| Evidence | `~/lm_sat_evidence/review/` (every script, raw output and exit code cited below) |
| Mode | Test and document only. No application code, tests, migrations or other docs touched. This file is the only repo write |

## 1. Method

1. **Blind recalculation first (Step A).** I wrote `step_a_recalc.py` from `.claude/rules/business-rules.md` and the
   approved decisions *before* opening the Phase 3 report. The independent side is one raw SQL statement over source tables.
   It imports nothing from `balance_calculator`, the ledger builders or the snapshot services:
   - ORIGINAL = Σ export `cif_fc`.
   - BOE CIF = Σ DEBIT `RowDetails.cif_fc` with a BOE, net of active/current `InvoiceBOEAllocation`.
   - HIDDEN = the same rows whose BOE has `invoice_no='OTH'` **and** whose latest HIDE/RESTORE log is `HIDE_BOE`.
     These are previous-owner rows, removed through the opening balance.
   - ALLOTMENT = Σ `greatest(cif − least(cif, active BOEAllotmentAllocation), 0)` over allotment items whose parent has
     **no** M2M BOE link (DECIDED 2026-11-17).
   - BILLED = Σ SALE trade-line `cif_fc`.
   - AVAILABLE = ORIGINAL − HIDDEN − BOE − ALLOTMENT − BILLED, signed, quantised to 2 dp only at the end.

   I compared this against `calculate_financial_balance` (single), `calculate_financial_balance_for_licenses` (bulk, all
   2,185 licences), `get_balance_cif`, `calculate_balance` (non-hidden customs), the stored `LicenseBalance.balance_cif`,
   and the **real licence list API** (`APIClient` → `/api/licenses/?search=…`, with `is_expired` / `flags__is_null`
   overrides so expired and null licences are found).
2. **Circularity disclosure (applies to me too).** `business-rules.md` says only "non-hidden" and does not define *hidden*. I took the
   hidden predicate from the `annotate_and_exclude_hidden` docstring (`bill_of_entry/models.py:57-140`), so that term is
   **code-derived, not rule-derived**. The legacy `trade.boes` exclusion and the purchase opening-gate are not in the
   canonical rule. I did not model them beyond the empty-table zero, because no local data could test them.
3. Then (Step B) I read the Phase 3/6/1-2-8 reports, the registers and the state file, and I reproduced every
   critical/high defect with my own scripts and tests (§4). For the double-counting and data-realism questions I wrote
   targeted SQL probes (§5, §6).
4. Tolerances: CIF 0.01, qty 0.001. Decimal throughout (the SQL `numeric` and Python `Decimal`).

## 2. Step A — blind recalculation

Script `step_a_recalc.py` → `step_a_output.log` (**exit=0**), `step_a_result.json`. Totals: `step_a_totals.py` →
`step_a_totals.log` (**exit=0**).

**Summary counts**
- Sample: 58 distinct licences. That is 30 random (`random.Random(9091).sample(sorted ids, 30)`), all 11 hidden-BOE
  licences, the 10 most negative, and the 10 named licences. Three licences fall in two groups.
- **58 / 58 MATCH** across all of: independent = engine single = engine bulk = `get_balance_cif` = list API. Max diff 0.00.
- **Population: 2,185 / 2,185** licences, independent = bulk engine, **0 mismatches**.
- Population totals (independent) are identical to the Phase 3 report to the cent:
  - Original 2,393,537,328.28
  - visible BOE 1,733,748,635.75
  - hidden 4,412,937.86 (11 licences)
  - allotment 31,592,776.75
  - Σ available 623,782,977.92
  - 36 over-utilised licences, Σ −7,054,283.95

  Phase 3's raw evidence is lost, so **these figures are now independently corroborated and reproducible**.
- The stored cache `LicenseBalance.balance_cif` differs from live on **38 / 2,185** licences (`stored_cache_mismatch.json`):
  - all **36 negative licences are stored as 0.00**;
  - 2 positive licences are stale: 0310834962 is stored 142,937.32 against a live 179,688.20; 3411008583 is stored 1,639,086.95
    against a live 1,895,326.95. The Δ 256,240.00 is exactly allotment 10317, which was M2M-linked to a BOE on 2026-11-03.

  The list and detail APIs do not read this column, but filters do (see NEW-02).

**Item-level available qty** (`step_a_items.py` → `step_a_items.log`, exit=0)

| Licence / item | Qty | Debited (visible) | AT outstanding | AR qty | Independent, no AR | Independent, with AR | Engine `calculate_available_quantity` | Stored `available_quantity` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0310825235 / 2393 | 3,838,607.000 | 0 | 0 | 3,838,597.000 | 3,838,607.000 | **10.000** | 3,838,607.000 | 10.000 |
| 0310705160 / 2362 | 3,191,198.220 | 39,350.000 | 0 | 3,151,848.000 | 3,151,848.220 | **0.220** | 3,151,848.220 | 0.220 |
| 0310831630 / 4281 | 2,520,971.340 | 7,800.000 | 0 (7,800 M2M-linked) | 2,513,171.000 | 2,513,171.340 | **0.340** | 2,513,171.340 | 0.340 |

- The engine equals my "no AR" figure, so the live engine deducts AR nowhere at item level.
- The legacy writer `_get_aggregated_values` returns `aro_qty = 0.00` for all three (`calculate_balance.py:79-81`
  filters `'ARO'` on a 2-char field whose value is `'AR'`).
- The stored columns still show the AR-deducted values (10 / 0.22 / 0.34) because they were written before. When D-D
  ("screens show live values") is implemented, these screens will **jump** to the overstated live value unless SAT-DEF-001 is fixed first.
- At licence level the engine **does** deduct AR CIF. Licence 0310825235's ALLOTMENT component is 1,221,131.07, which is exactly
  the Σ of its 4 AR items. Licence and item level therefore disagree by construction.

**Per-licence table** (all 58; the list API column is the real `/api/licenses/` `balance_cif`; `get_balance_cif` was identical on every row)

| Licence | Sample | Original | Hidden | BOE (ours) | Allotment | Independent | Engine single | Engine bulk | List API `balance_cif` | Max diff | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0310493058 | random30 | 243058.26 | 0 | 283935.740 | 0 | -40877.48 | -40877.48 | -40877.48 | -40877.48 | 0.00 | MATCH |
| 0310499297 | neg10 | 1903101.21 | 0 | 2356473.060 | 0 | -453371.85 | -453371.85 | -453371.85 | -453371.85 | 0.00 | MATCH |
| 0310609241 | random30 | 367156.46 | 0 | 367153.550 | 0 | 2.91 | 2.91 | 2.91 | 2.91 | 0.00 | MATCH |
| 0310610591 | random30 | 1127272.83 | 0 | 1127270.740 | 0 | 2.09 | 2.09 | 2.09 | 2.09 | 0.00 | MATCH |
| 0310651968 | random30 | 2317477.00 | 0 | 2309346.500 | 0 | 8130.50 | 8130.50 | 8130.50 | 8130.5 | 0.00 | MATCH |
| 0310679837 | random30 | 815076.32 | 0 | 815067.790 | 0 | 8.53 | 8.53 | 8.53 | 8.53 | 0.00 | MATCH |
| 0310683421 | random30 | 1043647.99 | 0 | 1043634.080 | 0 | 13.91 | 13.91 | 13.91 | 13.91 | 0.00 | MATCH |
| 0310709467 | random30 | 331594.93 | 0 | 262867.920 | 68562.16 | 164.85 | 164.85 | 164.85 | 164.85 | 0.00 | MATCH |
| 0310737558 | neg10 | 211696.12 | 0 | 297786.440 | 0 | -86090.32 | -86090.32 | -86090.32 | -86090.32 | 0.00 | MATCH |
| 0310738727 | random30 | 3769892.16 | 0 | 3769890.150 | 0 | 2.01 | 2.01 | 2.01 | 2.01 | 0.00 | MATCH |
| 0310815822 | named | 978259.87 | 0 | 978036.150 | 0 | 223.72 | 223.72 | 223.72 | 223.72 | 0.00 | MATCH |
| 0310821169 | neg10 | 5365844.43 | 0 | 5357709.850 | 73242.99 | -65108.41 | -65108.41 | -65108.41 | -65108.41 | 0.00 | MATCH |
| 0310824203 | random30 | 177349.09 | 0 | 0 | 40817.20 | 136531.89 | 136531.89 | 136531.89 | 136531.89 | 0.00 | MATCH |
| 0310825235 | named | 4908995.47 | 0 | 1410742.790 | 1221131.07 | 2277121.61 | 2277121.61 | 2277121.61 | 2277121.61 | 0.00 | MATCH |
| 0310827509 | named, neg10 | 0.00 | 0 | 3257841.980 | 190009.42 | -3447851.40 | -3447851.40 | -3447851.40 | -3447851.4 | 0.00 | MATCH |
| 0310829894 | random30 | 69323.73 | 0 | 1665.600 | 13016.29 | 54641.84 | 54641.84 | 54641.84 | 54641.84 | 0.00 | MATCH |
| 0310833304 | named, neg10 | 6824661.89 | 0 | 6790943.160 | 2011506.09 | -1977787.36 | -1977787.36 | -1977787.36 | -1977787.36 | 0.00 | MATCH |
| 0310834927 | random30 | 16084.03 | 0 | 993.690 | 0.00 | 15090.34 | 15090.34 | 15090.34 | 15090.34 | 0.00 | MATCH |
| 0310836031 | neg10 | 1667520.00 | 0 | 1472603.790 | 397934.58 | -203018.37 | -203018.37 | -203018.37 | -203018.37 | 0.00 | MATCH |
| 0311002454 | hidden | 328985.02 | 321058.990 | 0 | 0 | 7926.03 | 7926.03 | 7926.03 | 7926.03 | 0.00 | MATCH |
| 0311009988 | random30 | 12792.82 | 0 | 12667.490 | 0 | 125.33 | 125.33 | 125.33 | 125.33 | 0.00 | MATCH |
| 0311011361 | random30 | 89701.81 | 0 | 6594.510 | 0 | 83107.30 | 83107.30 | 83107.30 | 83107.3 | 0.00 | MATCH |
| 0311020085 | random30 | 593017.88 | 0 | 109666.200 | 0 | 483351.68 | 483351.68 | 483351.68 | 483351.68 | 0.00 | MATCH |
| 0311021572 | random30 | 338840.60 | 0 | 291296.300 | 0 | 47544.30 | 47544.30 | 47544.30 | 47544.3 | 0.00 | MATCH |
| 0311033007 | random30 | 1219800.76 | 0 | 1219680.980 | 0 | 119.78 | 119.78 | 119.78 | 119.78 | 0.00 | MATCH |
| 0311036271 | random30 | 15168.98 | 0 | 15155.870 | 0 | 13.11 | 13.11 | 13.11 | 13.11 | 0.00 | MATCH |
| 0311039216 | random30 | 532974.68 | 0 | 532970.530 | 0 | 4.15 | 4.15 | 4.15 | 4.15 | 0.00 | MATCH |
| 0311039992 | random30 | 488378.42 | 0 | 488345.340 | 0 | 33.08 | 33.08 | 33.08 | 33.08 | 0.00 | MATCH |
| 0311045787 | hidden | 73482.80 | 2361.640 | 60165.600 | 0 | 10955.56 | 10955.56 | 10955.56 | 10955.56 | 0.00 | MATCH |
| 0311050784 | hidden | 696538.47 | 350428.170 | 0 | 0 | 346110.30 | 346110.30 | 346110.30 | 346110.3 | 0.00 | MATCH |
| 0311050991 | hidden | 171086.36 | 124925.910 | 0 | 17107.20 | 29053.25 | 29053.25 | 29053.25 | 29053.25 | 0.00 | MATCH |
| 0311051037 | hidden | 299749.98 | 90720.000 | 85281.240 | 0 | 123748.74 | 123748.74 | 123748.74 | 123748.74 | 0.00 | MATCH |
| 0311051200 | random30 | 2229918.69 | 0 | 2229917.580 | 0 | 1.11 | 1.11 | 1.11 | 1.11 | 0.00 | MATCH |
| 0311051287 | hidden | 71568.95 | 71359.860 | 0 | 0 | 209.09 | 209.09 | 209.09 | 209.09 | 0.00 | MATCH |
| 0311051527 | hidden | 92128.06 | 27609.540 | 0 | 9209.70 | 55308.82 | 55308.82 | 55308.82 | 55308.82 | 0.00 | MATCH |
| 0311052001 | hidden | 138160.02 | 34379.980 | 96138.180 | 7641.00 | 0.86 | 0.86 | 0.86 | 0.86 | 0.00 | MATCH |
| 0311052122 | hidden | 5427238.15 | 2777743.130 | 0 | 0 | 2649495.02 | 2649495.02 | 2649495.02 | 2649495.02 | 0.00 | MATCH |
| 0311052376 | hidden | 171597.69 | 48254.640 | 108653.150 | 14688.00 | 1.90 | 1.90 | 1.90 | 1.9 | 0.00 | MATCH |
| 0311054605 | random30 | 446649.55 | 0 | 115608.580 | 0 | 331040.97 | 331040.97 | 331040.97 | 331040.97 | 0.00 | MATCH |
| 0511002494 | hidden | 768992.85 | 564096.000 | 0 | 0 | 204896.85 | 204896.85 | 204896.85 | 204896.85 | 0.00 | MATCH |
| 0910056125 | random30 | 1190730.47 | 0 | 1069241.260 | 0 | 121489.21 | 121489.21 | 121489.21 | 121489.21 | 0.00 | MATCH |
| 0910061510 | neg10 | 0 | 0 | 118303.610 | 0 | -118303.61 | -118303.61 | -118303.61 | -118303.61 | 0.00 | MATCH |
| 1311001682 | neg10 | 0.00 | 0 | 75874.080 | 0 | -75874.08 | -75874.08 | -75874.08 | -75874.08 | 0.00 | MATCH |
| 3010093604 | random30 | 119250.00 | 0 | 119151.370 | 0 | 98.63 | 98.63 | 98.63 | 98.63 | 0.00 | MATCH |
| 3411007247 | named | 398638.76 | 0 | 382701.790 | 34338.95 | -18401.98 | -18401.98 | -18401.98 | -18401.98 | 0.00 | MATCH |
| 3411007496 | named | 3349190.48 | 0 | 3082417.840 | 277440.00 | -10667.36 | -10667.36 | -10667.36 | -10667.36 | 0.00 | MATCH |
| 3411007817 | random30 | 3938881.48 | 0 | 3938860.940 | 0 | 20.54 | 20.54 | 20.54 | 20.54 | 0.00 | MATCH |
| 3411008564 | random30 | 3084326.49 | 0 | 0 | 0 | 3084326.49 | 3084326.49 | 3084326.49 | 3084326.49 | 0.00 | MATCH |
| 3411008581 | neg10 | 3706669.33 | 0 | 3547298.650 | 256240.00 | -96869.32 | -96869.32 | -96869.32 | -96869.32 | 0.00 | MATCH |
| 5211006127 | random30 | 1149164.77 | 0 | 438237.950 | 0 | 710926.82 | 710926.82 | 710926.82 | 710926.82 | 0.00 | MATCH |
| 5211006440 | named | 2095821.45 | 0 | 2095805.270 | 0 | 16.18 | 16.18 | 16.18 | 16.18 | 0.00 | MATCH |
| 5211007783 | random30 | 4184761.69 | 0 | 4146894.000 | 0 | 37867.69 | 37867.69 | 37867.69 | 37867.69 | 0.00 | MATCH |
| 5211011577 | random30 | 3468402.80 | 0 | 3468345.730 | 0 | 57.07 | 57.07 | 57.07 | 57.07 | 0.00 | MATCH |
| 5211013142 | random30 | 2756272.96 | 0 | 2756267.270 | 0 | 5.69 | 5.69 | 5.69 | 5.69 | 0.00 | MATCH |
| 5211013552 | random30 | 3822190.95 | 0 | 3752381.590 | 0 | 69809.36 | 69809.36 | 69809.36 | 69809.36 | 0.00 | MATCH |
| 5211016746 | named, neg10 | 3250277.56 | 0 | 3249314.330 | 76000.00 | -75036.77 | -75036.77 | -75036.77 | -75036.77 | 0.00 | MATCH |
| 5211016747 | named | 3211728.90 | 0 | 3023139.410 | 188900.00 | -310.51 | -310.51 | -310.51 | -310.51 | 0.00 | MATCH |
| 5211018767 | named | 2897987.18 | 0 | 2897771.330 | 0 | 215.85 | 215.85 | 215.85 | 215.85 | 0.00 | MATCH |


Hidden-BOE licences: the financial engine (and the list) = original − hidden − ours − allotment. `calculate_balance` (non-hidden
customs) is higher by exactly the hidden total. For example, on 0311002454 it is 328,985.02 against 7,926.03. This matters for NEW-01.

## 3. Review of the financial auditor's methodology (Phase 3)

| Aspect | Finding |
|---|---|
| Coverage | Strong. It covered the full population (2,185 licences, 26,818 items) and the full list API, which is better than a sample. My blind run reproduced every headline total exactly |
| Circularity | **Partial.** The "independent" SQL transcribes the engine's own structure: the opening-balance 3-way gate, including "any purchase → opening 0", and the legacy `trade.boes` exclusion. These are code semantics, not canonical-rule semantics, so the comparison can only prove *the SQL equals the code*, not *the code equals the rule*, for those terms. The hidden predicate is code-derived in both their SQL and mine |
| Discriminating power | **Weak where it matters most.** Trades, InvoiceBOEAllocation, BOEAllotmentAllocation and purchases have 0 rows. On the real data, BILLED = 0, the invoice netting = 0, partial allotment netting = 0 and the purchase gate never fires, so "0 discrepancies" is only evidence for ORIGINAL, BOE, HIDDEN and M2M-ALLOTMENT. Invoice-related correctness rests on developer-written pinned tests (also circular: written with the code) and 13 throwaway characterisation tests that pin behaviour, not approval |
| Sample bias | None for the list API (full). Detail API: 166 licences, all hidden and all negative, which is adequate. The export auditor's per-sheet values were **not** value-diffed for the bulk Excel (X03 "limitation"); this is exactly where NEW-01 hides |
| Evidence durability | `/tmp/sat/` is gone, so no Phase 3/6 figure was verifiable before this review. The figures I re-derived are now durable (§2); figures I did not re-derive (RC re-run 4,831, D04 665,624.43, D07 131,125.49) remain report-only |
| Over-reach | The D02 "probable double count" and "4 over-utilised flags caused by D02" claims are only partly supported (§4, DEF-002). The X02/D01 "negative balances show 0.00" claim is a misdiagnosis (§4, DEF-010) |

## 4. Defect reproduction

| ID | Reproduced | My evidence | My severity | Agree / disagree |
|---|---|---|---|---|
| **SAT-DEF-001** ARO | **Y**, exact | `probe_def001_scope.out`: 158 items carry AR, 157 overstated on 156 licences, Σ **40,992,712.93 kg**, AR CIF 17,934,272.36. Identical to Phase 3. Item rows in §2 | High | **Agree.** The live `ItemBalanceCalculator` filters `allotment__type='AT'` (`balance_calculator.py:919,957`), and the legacy writer uses `'ARO'` (`calculate_balance.py:80-81`; constant `ARO="AR"`, `core/constants.py:22`). This quantity feeds the Allotment Max-button and planning, so 41 M kg of phantom availability can be allotted. Licence CIF still caps it, so it is not Critical |
| **SAT-DEF-002** is_boe without M2M | **Partial** | See the breakdown below the table | High (the rule conflict is real) | **Agree on the defect, disagree on the evidence and the flag claim.** The DEC-02 recommendation "link the 12 allotments through the UI" is **wrong for 8357**: linking it to BOE 25789 would double-link a BOE already consumed by twin 8369. The fix there is to delete the duplicate allotment |
| **SAT-DEF-003** BOE 8391561 twice | **Y** | `probe_def002_003.out`: ids 28686 (date 2026-03-30, created 2026-07-15, "OLIVE OIL") and 27109 (date 2026-04-30, **created 2026-04-06, which is before its own BOE date**, "OLIVE POMACE OIL", row 454900 `is_dispute`, linked to allotment 9049). Port 710, company 637, invoice "GE 41", item 33479, qty 5,800, CIF 14,835.860, CIF INR 1,398,280 all identical. Both are manual (`is_fetch=False`). No other BOE of company 637 on port 710 has a similar number | Medium | **Agree.** Extra evidence for a duplicate: a record created before its own BOE date points to a mistyped date on 27109. Against it: the product names differ. The owner must check DGFT |
| **SAT-DEF-010** Balance Excel Financial Ledger | **Y** | `repro_exports.log` exit=0. 0310815822: "Current Balance 978259.87 · MISMATCH vs Balance Engine (Δ $978,036.15) · FINANCIAL RECONCILIATION FAILED", engine 223.72. 0310827509: "Current Balance 0 … Δ $3,447,851.40" | High (misleading financial statement on 15/16 licences) | **Agree that it is a defect; disagree with the diagnosis and the "expected" value.** (1) 978,259.87 = the licence's ORIGINAL CIF with no purchases or sales. 0310827509 shows 0 because its ORIGINAL CIF **is 0** (DQ-2), **not** a floor. (2) `LEDGER_APPROVED_SEMANTICS.md` (approved 2026-08-10) defines the License Running Balance as Opening + PURCHASE − SALE only, and requires Screen/PDF/Excel to use one dataset. The Excel figure follows the approved semantics. The genuine defects are the false "RECONCILIATION FAILED" verdict, which compares two different quantities, and the PDF/Excel divergence. "Expected 223.72" (DEC-04 option a) would **reopen an approved decision** and must be presented that way |
| **SAT-DEF-011** Item Pivot Excel text | **Y** | `repro_def011.log` exit=0, `def011_pivot_E5.xlsx`: numeric-looking text cells 228 / 188 / 2,250 on the first 3 sheets (`E4='3609764.80'`, `C4='2027-02-28'`) | **Medium** | **Disagree (High→Medium).** No value is wrong (Phase 6: 0 value diffs; `TOTAL_Summary` is numeric), and nothing is stored or computed from it. The risk is a user `SUM` silently returning 0, which is a usability/presentation defect with an easy workaround |
| **SAT-DEF-030** BOE list N+1 | **Y** | `repro_def030.log` exit=0: page 10 → **432 queries** (43.2/row, 0.91 s); 25 → 1,604 (64.2/row, 2.46 s); 50 → 3,021 (60.4/row, 4.46 s). Top repeats: per-row allotment aggregate, trade-line CIF Σ, export CIF Σ | High | **Agree.** It grows per row and makes a main list take seconds. The repeated queries are per-licence balance calls, so the bulk `_for_licenses` paths exist but are not used |
| **SAT-DEF-031** payments POST 500 | **Y** | `repro_def031.log` exit=0 (test DB `test_lmanagement_sat_rev`): POST `/api/payments/` → 500 `text/html`, with or without `trade`; no row is created | Medium | **Agree with the controller downgrade (High→Medium).** Frontend grep: the only `payments/` callers are `acctPost/acctGet` (accounting API, `pages/accounting/Payments.tsx:104,227`, `TradeTracking.tsx:56`). Trade payments are nested in TradeForm. No data is corrupted. It is still a public endpoint that always fails, so it is not Low |

**SAT-DEF-002 breakdown** (`probe_def002_003.out`, `probe_def002_b.out`, exit=0). There are 15 items, Σ 1,160,224.05, which matches the report.
- **Strong same-goods evidence, Σ 235,475.75.** For each of these, an **unlinked** BOE has the same company and port, the identical qty and CIF within 1 %, and was filed within days:
  - 8520 ↔ BOE 26396 (12,737 kg; 34,338.95 vs 34,557.85)
  - 8985 ↔ 26598 (3 items, qty exact)
  - 9468 ↔ 28701
  - 9760 ↔ 29530
- **Plausible, Σ 76,000.** 8677 ↔ 26298: qty and CIF exact, but the company differs (568 vs 192).
- **Not an allotment+BOE pair, Σ 270,300.** 8357 ↔ 25789 is the report's headline pair, but BOE 25789 is M2M-linked to allotment **8369**. 8369 is a twin of 8357: same invoice 7621791162, item, qty 100,000 and CIF 270,300, created the next day. 8357 is a **duplicate allotment**, not an allotment that double-counts against 25789.
- **No evidence, Σ 578,448.30:**
  - 8605: all 9 candidate BOEs are linked to other allotments.
  - 8897 and 8914: every item-33991 BOE is linked elsewhere.
  - 8711 and 8964: no qty match.
  - 8795: its cited BOE 26394 is linked to 8805; the only unlinked candidate is 26530 on another port.
- **Over-utilised flags.** The data supports the claim for only **2 of the 4** licences: 3411007247 (via 8520, strong) and 5211016746 (via 8677, plausible). For 5211016747 (8605) and 3411007496 (8897/8914), no BOE carries the goods, so the reservation may be genuine and the over-utilisation flag may be correct.

### Security (forwarded mid-task; reproduced on `test_lmanagement_sat_sec`)

`sec_tests/test_sat_rev_sec.py` asserts the **vulnerable** behaviour, so PASS means reproduced. `sec_repro.log`: 4 passed,
**exit=0** (`sec_repro.exit`), evidence `sec_repro_evidence.json`. A first run exited 1 only because I asserted 403 where the server
returns 404 for the protected file; I fixed the assertion and reran.

| ID | Reproduced | My evidence | My severity | Agree / disagree |
|---|---|---|---|---|
| SAT-DEF-050 recover-orphan key | **Y** | TRADE_VIEWER: recover-orphan with `source_storage_key="boe_copies/2026/rev-boe-copy.pdf"` → 200. Direct `/api/media/boe_copies/…` was **404** before, and `/api/media/trade/purchase_invoices/recovered-12-…` is **200 with identical bytes** after. The report's own example (an `accounting/vouchers/…` file) is weak: that file was **already** readable directly (200, which is SAT-DEF-054) | High | **Agree on severity, correct the evidence.** The confidentiality bypass is real for *protected* prefixes (BOE copies); the integrity write is real too. The cited voucher example shows only the integrity half |
| SAT-DEF-051 viewer upload | **Y** | TRADE_VIEWER: job 202, upload 200, second upload 200, and the document is overwritten (`uploaded-6-de33…-a.png` → `uploaded-6-2ba1…-b.png`). PATCH trade → 403 | High | **Agree.** Note: the original `test_B03` only asserted the PATCH 403. Its "PASSED" did not prove the upload, which was proven by the JSON only. My test asserts it |
| SAT-DEF-052 HTML inline | **Y** | LICENSE_MANAGER upload `.html` → 201. LICENSE_VIEWER GET → 200 `text/html`, `inline`, no CSP (`nosniff` present, which does not help for a declared text/html) | High | **Agree** |
| SAT-DEF-053 tracked environment files | Presence confirmed by `git ls-files`; contents **not read** | `backend/lmanagement/settings.py:24-33`: the backend DGFT environment file holds "DGFT session cookies and CSRF values … short-lived browser credentials" (last commit 2026-08-31). The repo-root file is 0 B. The two frontend files are Vite build vars, which are public in the bundle by design. Related, not secret: `update_license_ownership.py:19-22` hard-codes the production server URL and a default username | **Medium** until the owner checks | **Partly disagree** with "else Low". By the code's own description the DGFT file **is** a credential file, so "Low" is unlikely. Expired session cookies make "High" unlikely too. Medium is the evidence-based default; the owner check decides (DEC-40) |
| SAT-DEF-054 media prefixes | Incidentally **Y** | TRADE_VIEWER GET `/api/media/accounting/vouchers/…` → 200 (`DEF050.direct_media_before`) | Medium | Agree |

I did not reproduce the other security FAILs (055–065). Their severities look proportionate on the report's evidence. UI/E2E report: **not received, not reviewed.**

## 5. Double-counting analysis

| Path | Result |
|---|---|
| BOE ↔ allotment (M2M) | **No double count in the engine.** `_annotate_allotment_contribution` zeroes any allotment with an M2M link through an `Exists()` subquery, with no join fan-out (`balance_calculator.py:798-832`). My SQL with `NOT EXISTS` gives the same population figure |
| BOE ↔ allotment (no M2M, `is_boe=True`) | **Double count proven for 235,475.75, plausible for 76,000.** The 270,300 case is a duplicate allotment (DEF-002 breakdown above) |
| BOE ↔ BOE (identical rows) | Phase 3 declared 2,136 identical-row pairs "consecutive container BOEs, not duplicates". My probe, using the same item, CIF, qty, date and port with a different number (`probe_identical_pairs*.out`, exit=0), finds **2,170 pairs / 2,031 BOEs, Σ 254,262,627.64**. Phase 3's definition must have differed slightly. Results: **0 pairs share an allotment**. 890 pairs (144.0 M) link to *different* allotments, which is strong evidence of separate shipments. 798 unlinked pairs are both customs-fetched (`is_fetch`), so they carry distinct ICEGATE numbers. **"Consecutive" is not supported**: 1,258 of the 2,170 pairs have numbers more than 50 apart. **Residual risk: 461 unlinked pairs with at least one manual BOE, Σ 33,841,842.79, remain unproven.** That is the same class as the confirmed duplicate DEF-003 (both manual). The blanket "not duplicates" verdict is too strong for that subset |
| D05 cross-licence M2M (sample 5, `probe_d05.out`) | Each BOE is debited once, on licence B, so **there is no double count**. Case by case: 3495 (80,000 kg) → BOE debits 5211006446 (80,000 kg). 3526 → split over 3 licences totalling 100,000. 10317 → 3411008581, exact. Two cases release **more than the BOE consumed**: allotment 183 reserved 140,000 kg on two licences, but BOE 6206028 debits only 40,000; allotment 7479 reserved 200,000, but its BOE debits 100,000 on 3011006735. That is an **under-count of utilisation** (100,408 kg and 100,000 kg released with no debit), and it is exactly what the approved "full consumption, no remainder" rule (2026-11-17 §1) prescribes. Many of these allotments were created 2025-12-02 (the migration date) against 2019–2023 BOEs, so they are migrated history |
| BOE ↔ SALE invoice | **Known, unapproved double count.** When a SALE line and a BOE debit the same item without a `trade.boes` link or an `InvoiceBOEAllocation`, both are counted in full (`test_balance_calculator.py:839-864`, "deferred … a DATA problem"). The canonical rule says "billed CIF … not represented by BOEs, **excluding duplicates**". No document in `docs/decisions/` accepts this deferral. Locally there are 0 trades, so the amount cannot be measured. Production has trades |
| Single vs bulk parity | Population parity holds (0 diffs). There is a latent asymmetry: single `get_debit_rows` filters `bill_of_entry__isnull=False` (`:428-432`), but bulk `calculate_boe_debit_total_for_licenses` does not (`:553-555`). It has no effect today because all 22,075 DEBIT rows have a BOE |

## 6. Data realism and what it means for acceptance

- The local DB is a realistic copy for licences, BOEs and allotments: 168 k rows, real negatives, hidden BOEs, cross-licence links, data-quality junk.
- **The whole invoice side is empty**: 0 trades, 0 trade lines, 0 `trade_boes`, 0 InvoiceBOEAllocation, 0 BOEAllotmentAllocation, 0 licence purchases.
- Therefore **BILLED CIF WITHOUT BOE, invoice netting, partial-allocation netting, the purchase/opening gate, COMMISSION handling and the
  SALE↔BOE double-count path were never exercised on real data**. They are covered only by developer-written pinned tests (my run:
  `pytest_pinned.log`, 4 files, **139 passed, exit=0**) and by synthetic characterisation tests.
- **For acceptance:** the licence-level balance can be accepted **only for licences with no trading activity**. For any licence with
  purchase/sale invoices in production, the SAT provides **no real-data evidence**. A production-copy re-run of Step A (my script works
  unchanged and models the invoice terms) is required before the financial results are relied on for traded licences. The register lists
  SAT-FIN-004/005 as "BLOCKED → PASS on test DB"; that should read **"NOT VERIFIED ON REAL DATA"**.

## 7. FAIL / BLOCKED review

| ID | Status in report | Blocker real? | Alternative adequate? |
|---|---|---|---|
| SAT-FIN-004/005 invoice / billed | BLOCKED → PASS (test DB) | Yes (0 trades) | **No.** The tests are developer-written and one of them pins a known double count (§5). Re-label NOT VERIFIED ON REAL DATA |
| SAT-FIN-008 (D01), -014 (D02/D03) | FAIL | — | Correct status. My reproduction differs on D02's scope |
| SAT-EXP X07 package PDF | BLOCKED | **No.** The 400 "Select exactly one licence" was by design; the auditor never retried with one id. The security run created package jobs with one licence (202) | **No.** Re-run with one licence id |
| SAT-EXP X22, X25 trade exports | BLOCKED | Yes (0 trades) | Partly. The export tests pass (192) but are synthetic; same caveat as §6 |
| SAT-EXP X01/X02/X05/X06 | FAIL | — | Valid, but the D01 diagnosis needs correcting (DEF-010 row) |
| SAT-EXP X03 bulk balance Excel | **PASS-EXC** | — | **Wrong status.** The sheet-level balance was not diffed, and it is wrong for every hidden-BOE licence (NEW-01). It should be **FAIL** |
| SAT-ARCH-009 / SAT-DEF-037 (0067 unapplied) | FAIL / environment class | Yes | Adequate. It is environmental; classifying it as a defect at Medium overstates it (§8) |
| SAT-BE-003/010/012/015, PERF-004/007 | FAIL | — | Valid. I reproduced 003 (DEF-031) and PERF-004 (DEF-030) |
| SAT-SEC-021/039/040 | NOT-RUN | 021: there is nothing to test. 039/040: real (no install, no network) | Adequate. Dependency audit remains an open gap for acceptance |
| Phase 4/5 (integration, E2E) | PENDING | — | Not reviewed (no report) |

## 8. Severity review

| ID | Report | Mine | Reason |
|---|---|---|---|
| SAT-DEF-011 | High | **Medium** | Values are correct and only the cell type is wrong. A presentation defect |
| SAT-DEF-031 | Medium (controller; agent High) | Medium | **Agree with the downgrade.** There is no UI caller (verified by grep) and no data impact |
| SAT-DEF-002 | High | High | Keep, but the proven double-count scope is 235,475.75 (+76,000 plausible), not 1,160,224.05. Only 2 of the 4 flags are supported |
| SAT-DEF-010 | High | High | Keep. The fix requires owner action because it touches the approved ledger semantics |
| SAT-DEF-037 | Medium | **Low (environment)** | Migration not applied on a local copy. That is not a product defect |
| SAT-DEF-053 | High if live, else Low | **Medium** default | See §4 security |
| SAT-DEF-007 | "Approved-rule violation" | **BRA** | It is classified as a violation but simultaneously needs DEC-06. `LEDGER_APPROVED_SEMANTICS` governs the ledger, not explicitly the CIF engine |
| Others reviewed (001, 003, 030, 050, 051, 052, 054) | as reported | same | — |

## 9. Silent assumptions and DEC register

**Silent assumptions found**
1. **SAT-FIN-005 PASS** depends on the unapproved interpretation that an unlinked SALE plus BOE for the same goods is "a data problem", not a
   double count (§5). This needs an owner decision. → **Missing DEC (proposed DEC-41).**
2. **DEF-010 / DEC-04** treats "licence CIF balance" as the expected Financial Ledger balance, which contradicts the approved
   `LEDGER_APPROVED_SEMANTICS.md` (invoice-only running balance). DEC-04 must state that option (a) **reopens LEDGER-C-HYBRID-CANONICAL**.
3. **DEC-03 (a)** "a rowless BOE link keeps the allotment outstanding" contradicts the approved 2026-11-17 §1 ("contributes 0 … whatever the
   linked BOE's CIF"). It is not a new question. Present it as a request to amend an approved decision. The placeholder BOE `1234567` is a
   data fix, not a decision.
4. **DEC-05**: the math is already decided (2026-11-17 §1, the same wording). Only the "cross-licence warning" is new, and that is an enhancement,
   not a business-rule question. **Remove DEC-05, or reduce it to "approve a warning feature"**. The partial-release cases (183, 7479) are
   the decided behaviour.
5. **DEC-02 recommendation** "link the 12 allotments through the UI" assumes each one has a matching unlinked BOE. That is false for 8357
   (a duplicate allotment), 8605, 8897, 8914, 8711, 8964 and 8795.
6. **Identical-row pairs "not duplicates"** is asserted for all 2,136 pairs. The evidence supports this for about 1,709 pairs only (§5).

**Register hygiene:** DEC-01, 02, 06, 07, 08, 09 and 10 are genuinely open. None is answered verbatim by `docs/decisions/`
(D-A…D-F and D1–D4 do not cover AR, is_boe, disputes or transfers). The missing entries are DEC-41 (SALE↔BOE unlinked double count) and
DEC-42 (whether exports may use the non-hidden customs balance; see NEW-01; probably a defect, not a decision, since `get_balance_cif` =
financial is established).

## 10. New findings (not in any phase report)

| # | Sev | Finding | Evidence | Example |
|---|---|---|---|---|
| **NEW-01** | **High** | **Bulk Balance Excel "Balance CIF $" uses the non-hidden customs engine** (`license_balance_excel_bulk.py:361`/HEAD, `calculate_balance_for_licenses`, then `float()` at `:160`). It **overstates the available CIF by the full hidden (previous-owner) total** on every hidden-BOE licence, against the licence list, detail and PDF. This is committed code (in HEAD), not a peer change | `repro_exports.log` exit=0, `bulk_hidden.xlsx`, `bulk_hidden_cell.log` (cell B6) | 0311002454: Excel **328,985.02** vs licence **7,926.03** (+321,058.99). 0311052122: 5,427,238.15 vs 2,649,495.02 (+2,777,743.13). 0311050784: 696,538.47 vs 346,110.30. Population exposure: 11 licences, Σ +4,412,937.86 |
| NEW-02 | Medium | The stored `LicenseBalance.balance_cif` cache is stale on 38 licences: all 36 negatives are stored as 0.00 (pre-2026-11-16 floor), and 2 are stale positives that were not refreshed after an M2M link. Readers: `core/filtersets.py:136-137` (`balance_cif_min/max`), `:184-186` (`has_balance`), the `is_null` flag (balance < 500), `materialized_views.py:419` | `stored_cache_mismatch.json` | 3411008583: stored 1,639,086.95 vs live 1,895,326.95 (Δ 256,240.00 = allotment 10317 linked 2026-11-03). A filter `balance_cif_max=-1` returns none of the 36 over-utilised licences. Owner D-D already decided "one writer", so this needs no approval |
| NEW-03 | Medium (process) | SAT-DEF-001 interacts with D-D. Today the stored item columns *look* right only because they predate the AR exclusion. Implementing D-D (live values) before DEF-001 would make 157 item screens show up to +3.84 M kg each | §2 item table | 0310825235/2393: stored 10.000 → live 3,838,607.000 |
| NEW-04 | Low | Decimal-safety violations on money in export and dashboard paths: `license_balance_excel_bulk.py:160` (`float`), `dashboard.py:282` (`float(balance)`), `item_pivot_row.py:213` | code | — |
| NEW-05 | Low (latent) | Single/bulk parity gap: `bill_of_entry__isnull=False` exists only on the single path (§5) | code | 0 rows today |

## 11. Disagreements (each settled by evidence)

1. DEF-010: "negatives show 0.00" → **refuted**. 0310827509's ORIGINAL CIF is 0.00 (`step_a_result.json`), so the invoice-only ledger is 0 by arithmetic. "Expected 223.72" → contradicts the approved ledger semantics.
2. DEF-002: "8357 ↔ BOE 25789 double count" → **refuted**. 25789 is linked to twin allotment 8369, and 8357 is a duplicate allotment. "4 flags caused by D02" → **2 of 4 supported**.
3. Identical-row pairs "consecutive container BOEs, not duplicates" → **partly refuted**. 1,258 pairs are not consecutive, and 461 pairs (33.8 M) are unproven.
4. DEF-050 confidentiality example → the voucher was already readable (DEF-054). **Re-proved with a protected prefix** (404 → 200).
5. DEF-011 High → Medium. DEF-037 Medium → Low (environment). DEF-053 → Medium default.
6. X03 PASS-EXC → FAIL (NEW-01). X07 BLOCKED → not a real blocker.
7. SAT-FIN-004/005 "PASS on test DB" → NOT VERIFIED ON REAL DATA.

## 12. Reviewer verdict

**What can be relied on.** The licence-level CIF balance figures for the local dataset:
- original, BOE, hidden and allotment components;
- the signed available balance on the list, detail, `get_balance_cif` and engine paths.

I re-derived them blind, they match to the cent on 2,185/2,185 licences, and they corroborate every Phase 3 total. They can be relied on **for licences without trading activity**, which is every licence in the local copy.

**What cannot be relied on yet:**
- (a) Any figure involving invoices: billed-without-BOE, invoice netting, purchases, commission. These have no real-data evidence, and there is a known unapproved SALE↔BOE double-count path.
- (b) Item-level available quantity, because of SAT-DEF-001.
- (c) The bulk Balance Excel balance on hidden-BOE licences (NEW-01).
- (d) Filters on the stored balance cache (NEW-02).
- (e) The Financial Ledger Excel/screen verdict (DEF-010).

**Overall: ESCALATE-TO-OWNER.** The engine is correct against the canonical rule on the data available. Acceptance of the financial results for traded licences requires a production-copy re-run and owner decisions on DEC-41, DEC-04 (as a reopening of the approved ledger semantics), DEC-01 and DEC-02.

## 13. UI/E2E review (appended after `SAT_UI_UX_AUDIT.md` and its controller addendum arrived)

This is numbered §13 because §11 already exists. Sources: `SAT_UI_UX_AUDIT.md` (including the addendum), SAT-DEF-080..089, and
`~/lm_sat_evidence/e2e/` + `int/`. I did not run the browser harness. I ran one new quick API test (`d10_triage.log`, exit=0).

**FAIL / BLOCKED / NOT-RUN and the API-level alternative (257 passed)**

| ID | Blocker real? | Does the alternative cover the claim? |
|---|---|---|
| INT-003, INT-014 | Resolved: the controller created a real BOE | Yes. Browser + API, diff 0.00 |
| INT-004 (allotment → BOE, no double count) | **No.** The seeded allotment exists and is BOE-linked. It is just hidden by the default list scope (D10 below) | **Rule yes, workflow no.** `test_m2m_full_consumption` proves the math on synthetic data, not the UI link/consume flow. Call it "PASS (rule, API)", not a workflow PASS |
| INT-007 (invoice ↔ BOE) | Yes in the browser | Synthetic only, and it does not cover the unapproved unlinked SALE+BOE double count (§5, DEC-41). **NOT VERIFIED ON REAL DATA** |
| INT-002, INT-008/011 write paths | No blocker; not driven | **No.** The 257 suites contain no licence create/edit, mapping or planning write test |
| INT-009 transfer | No blocker; not driven | **No.** Hidden-BOE/opening-balance tests are not a transfer workflow |
| INT-010 BOE upload | **Weak.** "No route found, not pursued", yet a BOE PDF upload path exists (`boe_documents.py:205-221`, cited by sat-sec) | No |
| E2E-007 BOE detail | **No longer real.** `sat-int-boe` creates a BOE | Not run, so open |
| E2E-023 sort, E2E-025 delete | Selector miss / delete done via API | **No.** The UI behaviour is unverified |
| UX-012 focus trap, UX-013 dark mode | No blocker | Not run, so open |
| E2E-019 / UX-016, UX-006..010 | Real a11y FAILs | n/a |

**Severities SAT-DEF-080..089:**
- 080–085 and 087: agree.
- 086 (errors only after retries): agree Low.
- 088: agree that it is BRA (business-rule ambiguity).
- **089 → close as not a product defect** (see D10 below), replaced by a Low contract note.

**Regression failures classified as test/harness:**
- masters ×2, 401 `token_not_valid`: the whole run took **2.6 min** (`harness-regression.log`), so expiry is excluded. The message is "Token is invalid", not "expired" or "blacklisted", which means a signature or key mismatch, consistent with a stale stored auth state from an earlier harness instance. "Harness" is **plausible but unproven**, and nobody has tested whether the frontend's queued refresh retries an in-page POST after a 401.
- Login throttle: genuine product behaviour (10 failures, then 429, by design), so the harness classification is fair. The throttle message is also unannounced (DEF-080).
- **reports-menu: should not be treated as harness.** The spec looks for `button "Reports"` in the main navigation for a non-superuser mock user. A **peer uncommitted change** to `frontend/src/components/navigation/navConfig.ts:183` now passes per-item `roles` into the Reports section. If that filtering empties the menu for the mock user, the button disappears. That is either an intended role-gating change (update the spec) or a regression. It must be triaged against that diff.

**SAT-UX-D10: a seed artifact plus a scope inconsistency, not a hidden-valid-allotment defect.**
- `seed_browser_2509.py:308-325,361` creates the allotment with `is_allotted=False`, deletes its items, then M2M-links it to the seed BOE (`boe.allotment.set([allotment])`). The real link flow sets `is_boe=True` (`boe_service.py:1334,1406`); the seed leaves the flag `False`.
- On a reproduction of that exact state (`d10_triage.log`, exit=0):
  - with no params, or with only `is_boe=all`, the list returns **0**, because the server default is `is_allotted=True` (`allotment/api/views.py:290-293`);
  - with the UI default `type=AT&is_boe=False&is_allotted=all` (`masterListConfig.ts:46`), it returns **0**, with or without search;
  - with `is_allotted=all` alone, it returns **1**.
- So the "Not BOE" view excludes this BOE-linked allotment even though the stored flag is `False`, which is consistent with "M2M link = consumed" (2026-11-17).
- The seed builds an itemless, unallotted, BOE-consumed allotment and the spec expects it on the "pending" list. That is an expectation error.
- Product notes, both Low:
  1. The raw API default (`is_allotted=True`) differs from the UI default (`all`), so an "unfiltered" API call is not unfiltered. This explains the addendum's "total 0".
  2. `?is_approved=all` → 500 (already in DEF-059).
