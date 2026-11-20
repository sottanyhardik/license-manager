# SAT — Independent review of the import-item CIF reconciliation

Date 2026-11-20 · branch `feature/v5` (no file edited except this one) · local DB `lmanagement@localhost`, **SELECT only**;
every app call ran inside `transaction.atomic()` + `transaction.set_rollback(True)`. No code, formula or data changed.
Reviewer: independent financial reviewer (subagent). Audit under review: `SAT_IMPORT_ITEM_CIF_RECONCILIATION.md`,
`SAT_ZERO_BALANCE_VALIDATION.md` and `~/lm_sat_evidence/cifrecon/{item_rows.tsv,item_recon.json,zero_balance.json}`.
Evidence: `~/lm_sat_evidence/cifrecon/review/` (§9).

## 1. Independence statement

- My expected figures came from raw SQL on the source tables only (`independent.py`, `challenge.py`). I did not import
  `balance_calculator`, `condition_pool`, `balance_snapshot` or the ledger services for them.
- I wrote my own hidden-BOE rule (`invoice_no='OTH'` and the latest HIDE/RESTORE log, ordered by `created_on DESC, id DESC`,
  is HIDE). It returns 50 hidden BOEs.
- `review_independent.json` (exit 0), `review_actual.json` (exit 0) and `review_challenge.json` (exit 0) were saved
  **before** I opened any of the audit files.
- Later I read the application code to find out what the fields mean and to challenge the audit, never to produce my figures.
- Two items in the 19-item sample were built in the challenge phase and then merged into the expected column:
  1. the 3 % pool for item 19712, from independent SQL in `review_challenge.json`;
  2. the D-A cap (`min(item value, max(licence balance, 0))`), which is applied only in the expected column.

## 2. Method

**Sample.** The 19 records in `review_sample.json`, plus 3 licence-level records:
- 0310827509 (requested);
- 0311052122 (hidden BOEs);
- 5211011493, chosen at random with `random.Random(20261120)` from the licences that have both BOE debits and allotments.

**Per item, from source:**

| Term | Source and rule |
|---|---|
| Original qty / CIF | `licenseimportitemsmodel.quantity` / `cif_fc`. The 0.01 marker is detected on `cif_fc` or `cif_inr` |
| Visible / hidden BOE debit | `rowdetails` rows with `transaction_type='D'` and `sr_number_id = item`, split by the hidden rule |
| AT / AR allotments, gross | Σ `allotmentitems` qty / `cif_fc` for the item, split by `allotmentmodel.type` |
| AT / AR allotments, outstanding | Same, but only allotments with **no** row in `billofentrymodel_allotment` (owner M2M rule). `BOEAllotmentAllocation` has 0 rows, so no partial netting applies |
| Invoiced | 0. `trade_licensetradeline` has 0 rows (verified) |
| Remaining qty | `qty − visible BOE qty − outstanding AT qty − unpaired sale qty` (D-F). Kept signed and also floored. An "incl. AR" variant is shown for DEC-01 |
| Item-attributed CIF | `cif_fc − visible BOE CIF − outstanding AT CIF`, only when `cif_fc > 0` and the item is not a 0.01 marker |
| Licence available CIF | `Σ export cif_fc − hidden BOE CIF − visible BOE CIF − outstanding AT − outstanding AR − billed`. Signed. The hidden BOEs enter through the opening balance |

**Actual values.**
- `ItemBalanceCalculator`: `calculate_unfloored_/available_quantity_for_items`, `calculate_item_attributed_balances_for_items`,
  `calculate_debited_quantity/cif_for_items`, and `calculate_item_balance` (legacy path).
- `LicenseBalanceCalculator`: `get_outstanding_allotment_totals_for_items`, `calculate_financial_balance`, `calculate_balance`,
  `calculate_customs_balance`, `calculate_opening_balance` and `calculate_hidden_boe_debit_total`.
- `condition_pool.available_value_bulk_map`.
- The stored columns on the import item.
- The real `LicenseDetailsViewSet.retrieve`, called through `APIRequestFactory` + `force_authenticate(superuser)` with
  `HTTP_HOST=localhost` and `throttle_classes=[]` set in-process. It returned HTTP 200 for all 22 licences.

Comparisons are exact Decimal, with no tolerance. Every figure below is a real DB value.

## 3. Per-record results (expected vs actual vs audit)

The "Verdict" column compares my figures with the app's live engine and with the audit. "D-A (+x)" means the live item
`available_value` is x above `max(licence balance, 0)`. That is the decided cap, which is **not yet implemented**: it is a known
decided item, not a new defect.

| # | Category | Licence | Item (sr) | Unit | Qty: expected signed | app canonical (floored / over) | audit rem_qty | Item-attr CIF: expected signed | app attributed | audit | Licence avail CIF: expected | API `balance_cif` | audit `lic_bal` | Item `available_value`: expected w/ D-A | API | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | no_txn | 1310049730 | 11384 (7) | kg | 216.000 | 216.000 / 0.000 | 216.000 | 7742.50 | 7742.50 | 7742.50 | 148373.30 | 148373.3 | 148373.30 | 7742.50 | 7742.5 | agree |
| 2 | at_outstanding_no_boe | 0511040554 | 36928 (2) | kg | 0.270 | 0.270 / 0.000 | 0.270 | n/a (shared) | — | — | 1564842.16 | 1564842.16 | 1564842.16 | 1564842.16 | 1564842.16 | agree |
| 3 | at_outstanding_plus_boe | 3411008503 | 39855 (9) | kg | 0.320 | 0.320 / 0.000 | 0.320 | n/a (shared) | — | — | 437408.590 | 437408.59 | 437408.59 | 437408.590 | 437408.59 | agree |
| 4 | at_outstanding_plus_boe | 0511040275 | 36484 (5) | kg | 31942.920 | 31942.920 / 0.000 | 31942.920 | n/a (shared) | — | — | 470279.510 | 470279.51 | 470279.51 | 470279.510 | 470279.51 | agree |
| 5 | allot_then_boe_m2m | 5211006995 | 19712 (4) | kg | 9800.840 | 9800.840 / 0.000 | 9800.840 | n/a (shared) | — | — | 629837.830 | 629837.83 | 629837.83 | 291.133 (3% pool) | 291.133 | agree |
| 6 | ar_outstanding | 0310833305 | 4443 (1) | kg | 432102.780 | 432102.780 / 0.000 | 432102.780 | n/a (shared) | — | — | 119897.220 | 119897.22 | 119897.22 | 119897.220 | 119897.22 | agree |
| 7 | ar_outstanding | 0310827444 | 2269 (1) | kg | 151501.200 | 151501.200 / 0.000 | 151501.200 | 234247.28 | 234247.28 | 234247.28 | 167523.780 | 167523.78 | 167523.78 | 167523.780 | 234247.28 | agree; D-A (+66723.500) |
| 8 | hidden_boe | 0311052122 | 40537 (19) | kg | 70960.000 | 70960.000 / 0.000 | 70960.000 | 120632.20 | 120632.20 | 120632.20 | 2649495.020 | 2649495.02 | 2649495.02 | 120632.20 | 120632.2 | agree |
| 9 | partial_boe | 0311010834 | 11836 (1) | kg | 1190.730 | 1190.730 / 0.000 | 1190.730 | 1264347.690 | 1264347.690 | 1264347.690 | 906.550 | 906.55 | 906.55 | 906.550 | 1264347.69 | agree; D-A (+1263441.140) |
| 10 | full_qty_zero | 0911008577 | 28273 (13) | kg | 0.000 | 0.000 / 0.000 | 0.000 | n/a (shared) | — | — | 882877.370 | 882877.37 | 882877.37 | 882877.370 | 882877.37 | agree |
| 11 | full_qty_zero | 0911008257 | 28375 (3) | kg | 0.000 | 0.000 / 0.000 | 0.000 | n/a (shared) | — | — | 235316.780 | 235316.78 | 235316.78 | 235316.780 | 235316.78 | agree |
| 12 | over_qty | 0910052935 | 7486 (3) | kg | -16792.690 | 0.000 / 16792.690 | -16792.690 | 0.620 | 0.620 | 0.620 | 4780519.350 | 4780519.35 | 4780519.35 | 0.620 | 0.62 | agree |
| 13 | over_qty | 0210118391 | 31692 (9) | kg | -259.000 | 0.000 / 259.000 | -259.000 | n/a (shared) | — | — | -11393.130 | -11393.13 | -11393.13 | 0 | 0.0 | agree |
| 14 | over_cif_item_lic_positive | 0310543354 | 6397 (3) | kg | -131924.000 | 0.000 / 131924.000 | -131924.000 | -323041.560 | 0.00 | -323041.560 | 0.590 | 0.59 | 0.59 | 0 | 0.0 | agree |
| 15 | dispute_row | 5611004883 | 35967 (13) | kg | 49763.920 | 49763.920 / 0.000 | 49763.920 | n/a (shared) | — | — | 18945.360 | 18945.36 | 18945.36 | 18945.360 | 18945.36 | agree |
| 16 | isboe_no_m2m | 0311051816 | 34307 (13) | kg | -1135.050 | 0.000 / 1135.050 | -1135.050 | n/a (shared) | — | — | 230.560 | 230.56 | 230.56 | 230.560 | 230.56 | agree |
| 17 | shared_ceiling_multi_item | 0311004371 | 12698 (4) | kg | 0.000 | 0.000 / 0.000 | 0.000 | n/a (shared) | — | — | 1758.390 | 1758.39 | 1758.39 | 1758.390 | 1758.39 | agree |
| 18 | shared_ceiling_multi_item | 0311019986 | 15029 (10) | kg | 0.080 | 0.080 / 0.000 | 0.080 | n/a (shared) | — | — | 54575.880 | 54575.88 | 54575.88 | 54575.880 | 54575.88 | agree |
| 19 | unit_variant | 0311050782 | 33738 (11) | KG | 0.840 | 0.840 / 0.000 | 0.840 | n/a (shared) | — | — | 65.470 | 65.47 | 65.47 | 65.470 | 65.47 | agree |

**Breakdown (source terms, all Decimal)**

| # | Item | Orig qty / CIF | Visible BOE rows (BOE no · row id · qty · CIF) | Hidden BOE qty / CIF | AT gross qty / CIF | AT outstanding qty / CIF | AR gross = outstanding qty / CIF | Allotments (id · type · M2M → BOE) | Invoiced | Qty formula |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 11384 | 216.000 / 7742.50 | — | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | — | 0 / 0 | 216.000 - visBOE 0 - outAT 0 - inv 0 = 216.000 |
| 2 | 36928 | 274727.270 / 0.00 | — | 0 / 0 | 274727.000 / 494508.60 | 274727.000 / 494508.60 | 0 / 0 | 10432·AT·unlinked | 0 / 0 | 274727.270 - visBOE 0 - outAT 274727.000 - inv 0 = 0.270 |
| 3 | 39855 | 11054.320 / 0.00 | 4931476·465552·8280.000·114281.940 | 0 / 0 | 11054.000 / 152876.82 | 2774.000 / 38364.42 | 0 / 0 | 10291·AT·→4931476 is_boe; 10292·AT·unlinked | 0 / 0 | 11054.320 - visBOE 8280.000 - outAT 2774.000 - inv 0 = 0.320 |
| 4 | 36484 | 157029.920 / 0.00 | 4827127·465451·24941.000·117234.880; 4886095·465520·26471.000·136146.210; 4886128·465521·51402.000·201482.280 | 0 / 0 | 125087.000 / 555094.25 | 22273.000 / 100183.95 | 0 / 0 | 10191·AT·→4886128 is_boe; 10295·AT·→4886095 is_boe; 10300·AT·→4827127 is_boe; 10301·AT·unlinked | 0 / 0 | 157029.920 - visBOE 102814.000 - outAT 22273.000 - inv 0 = 31942.920 |
| 5 | 19712 | 16360.840 / 0.00 | 9699455·45052·6560.000·40466.180 | 0 / 0 | 6560.000 / 40672.00 | 0 / 0 | 0 / 0 | 3814·AT·→9699455 | 0 / 0 | 16360.840 - visBOE 6560.000 - outAT 0 - inv 0 = 9800.840 |
| 6 | 4443 | 432102.780 / 0.00 | — | 0 / 0 | 0 / 0 | 0 / 0 | 432102.000 / 142593.92 | 302·AR·unlinked | 0 / 0 | 432102.780 - visBOE 0 - outAT 0 - inv 0 = 432102.780 |
| 7 | 2269 | 151501.200 / 234247.28 | — | 0 / 0 | 0 / 0 | 0 / 0 | 151501.000 / 48480.38 | 299·AR·unlinked | 0 / 0 | 151501.200 - visBOE 0 - outAT 0 - inv 0 = 151501.200 |
| 8 | 40537 | 70960.000 / 120632.20 | — | 56768.000 / 80215.800 | 0 / 0 | 0 / 0 | 0 / 0 | — | 0 / 0 | 70960.000 - visBOE 0 - outAT 0 - inv 0 = 70960.000 |
| 9 | 11836 | 900415.730 / 2719834.90 | 7446262·27804·44000.000·70840.000; 7966982·27987·50000.000·81129.520; 7983012·27988·110000.000·202231.620; 7967461·27989·44000.000·70400.000; … +10 more (total 899225.000 / 1455487.210) | 0 / 0 | 899225.000 / 1453941.87 | 0 / 0 | 0 / 0 | 2151·AT·→7446262; 2213·AT·→8048235; 2214·AT·→7966982; 2215·AT·→7983012; 2216·AT·→8014789; 2217·AT·→8047226; 2218·AT·→7992301; 2219·AT·→7993147; 2220·AT·→8154268 (BOE not on this item); 2228·AT·→7989480; 2231·AT·→7967461; 2257·AT·→8240713; 2258·AT·→8240721; 2281·AT·→8938930 | 0 / 0 | 900415.730 - visBOE 899225.000 - outAT 0 - inv 0 = 1190.730 |
| 10 | 28273 | 10127.000 / 0.00 | 9649881·204104·10127.000·13251.330 | 0 / 0 | 10127.000 / 13266.37 | 0 / 0 | 0 / 0 | 6567·AT·→9649881 | 0 / 0 | 10127.000 - visBOE 10127.000 - outAT 0 - inv 0 = 0.000 |
| 11 | 28375 | 106206.000 / 0.00 | 6589571·221730·106206.000·111642.230 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | — | 0 / 0 | 106206.000 - visBOE 106206.000 - outAT 0 - inv 0 = 0.000 |
| 12 | 7486 | 1684847.310 / 1234141.00 | 8128452·20389·250000.000·174261.130; 8153738·20390·1434840.000·1000147.350; 9192071·20391·16800.000·59731.900 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | — | 0 / 0 | 1684847.310 - visBOE 1701640.000 - outAT 0 - inv 0 = -16792.690 |
| 13 | 31692 | 398.450 / 0.00 | 156856·456299·259.000·11396.000; 990302·456300·398.450·17549.130 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | — | 0 / 0 | 398.450 - visBOE 657.450 - outAT 0 - inv 0 = -259.000 |
| 14 | 6397 | 334000.000 / 74482.00 | 645002·17123·20000.000·16600.000; 645025·17124·20000.000·16600.000; 645021·17125·50960.000·43061.200; 645024·17126·20000.000·20000.000; … +15 more (total 465924.000 / 397523.560) | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | — | 0 / 0 | 334000.000 - visBOE 465924.000 - outAT 0 - inv 0 = -131924.000 |
| 15 | 35967 | 112613.920 / 0.00 | 9830458·455181·18000.000·383886.000; 9997559·455229·18000.000·383886.000; 3266980·457993·16850.000·96008.080; 4880076·464743·10000.000·44000.000 **dispute** | 0 / 0 | 68068.000 / 993696.02 | 0 / 0 | 0 / 0 | 9321·AT·→9830458 is_boe; 9322·AT·→9997559 is_boe; 9311·AT·→9753619 (BOE not on this item) is_boe; 9910·AT·→3266980 is_boe; 10326·AT·→4880076 is_boe | 0 / 0 | 112613.920 - visBOE 62850.000 - outAT 0 - inv 0 = 49763.920 |
| 16 | 34307 | 40884.950 / 0.00 | 3104517·457904·17651.000·25093.230; 3134631·457923·18369.000·104661.050; 3220444·457962·3000.000·4264.960 | 0 / 0 | 39020.000 / 132592.04 | 3000.000 / 4233.00 | 0 / 0 | 9762·AT·→3104517 is_boe; 9760·AT·unlinked is_boe; 9872·AT·→3134631 is_boe | 0 / 0 | 40884.950 - visBOE 39020.000 - outAT 3000.000 - inv 0 = -1135.050 |
| 17 | 12698 | 1488.000 / 0.00 | 5809603·446293·1488.000·4005.240 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | — | 0 / 0 | 1488.000 - visBOE 1488.000 - outAT 0 - inv 0 = 0.000 |
| 18 | 15029 | 3477.080 / 0.00 | 7586078·36720·3477.000·3337.920 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | — | 0 / 0 | 3477.080 - visBOE 3477.000 - outAT 0 - inv 0 = 0.080 |
| 19 | 33738 | 4630.840 / 0.00 | 3598346·463968·4630.000·5548.250 | 0 / 0 | 4630.000 / 5551.37 | 0 / 0 | 0 / 0 | 9971·AT·→3598346 is_boe | 0 / 0 | 4630.840 - visBOE 4630.000 - outAT 0 - inv 0 = 0.840 |

**Licence-level records**

| Tag | Licence | Independent formula (orig − hidden − visible − out AT − out AR − billed) | App financial | API `balance_cif` / `is_over_utilised` | Audit `licence_balances.json` fin | Verdict |
|---|---|---|---|---|---|---|
| requested | 0310827509 | 0.00 - hidden 0 - visible 3257841.980 - outAT 0 - outAR 190009.42 - billed 0 = -3447851.400 | -3447851.40 | -3447851.4 / True | -3447851.40 | agree |
| hidden_boes | 0311052122 | 5427238.15 - hidden 2777743.130 - visible 0 - outAT 0 - outAR 0 - billed 0 = 2649495.020 | 2649495.02 | 2649495.02 / False | 2649495.02 | agree |
| random | 5211011493 | 3466237.92 - hidden 0 - visible 3466133.490 - outAT 0 - outAR 0 - billed 0 = 104.430 | 104.43 | 104.43 / False | 104.43 | agree |

**Summary.**
- Items: 19/19 agree with the live engine and with the audit, on all 17 audit fields compared (`compare.py`, 0 differences).
- Licences: 3/3 agree on available CIF.
- The live item `available_value` exceeds the D-A cap on 2/19 items:
  - 0311010834/11836: +1,263,441.14;
  - 0310827444/2269: +66,723.50.
- The stored or user-facing columns differ from live in the way the audit describes (RC3/RC13). Examples from this sample:

  | Licence / item | API `available_quantity` (stored) | Live | Cause |
  |---|---|---|---|
  | 0511040554 / 36928 | 0.0 | 0.270 | truncated |
  | 0511040275 / 36484 | 31942.0 | 31942.920 | truncated |
  | 0310833305 / 4443 | 0.78 | 432102.780 | stored value deducts AR |
  | 0311052122 / 40537 | 14192 | 70960 | stored value deducts hidden BOEs; stored `debited_value` 80215.8 = hidden CIF |

## 4. Challenge verdicts

| # | Challenge | Verdict | Evidence |
|---|---|---|---|
| 1a | BOE + allotment on the same goods | **PASS for the M2M rule; residual risk confirmed** | All 28 M2M-linked allotment items in the sample (of 34) contribute 0, and the app agrees. The unlinked AT allotments are genuine where they look suspicious: on 36484 (alloc 10301, 22,273 kg) and 39855 (10292, 2,774 kg), every BOE row on the item is already linked to a *different* allotment of identical qty. **Double count found:** 0311051816/34307, allotment 9760 (AT, `is_boe=True`, no M2M, 3,000 kg / 4,233.00, created 2026-07-24, co 53) ↔ BOE 3220444 (2026-08-18, co 53, 3,000 kg / 4,264.96, no M2M). The licence is deducted twice, and the item is −1,135.05 kg "over-used" only because of it. This falls under DEC-02 / SAT-DEF-002. Population: see SAT-DEF-150 |
| 1b | Same BOE stored twice | PASS (sample) | No BOE number spans more than one BOE record and no row is duplicated on the 22 licences in scope. DEC-03 is cited, not duplicated |
| 1c | Invoice + BOE | NOT TESTABLE locally | There are 0 trade lines and 0 `InvoiceBOEAllocation` rows. The audit proves it on a test DB (`SAT_INVOICE_BOE_QUANTITY_AUDIT.md`) |
| 2 | Missing invoice consumption | NOT TESTABLE locally | Same reason. `calculate_direct_sale_quantity` returned 0 for all 19 items |
| 3 | Allotment treatment (AT/AR, M2M, `is_boe`, status) | **PASS against the decided rules, with known open items** | **AR:** the licence level deducts AR (0310827509: outstanding AR 190,009.42). The item level does not: 4443 = 432,102.780, or 0.780 with AR deducted. This is DEC-01. The `%`-pool branch (`condition_pool.compute_condition_pools`) *does* deduct unlinked AR, so AR at item level is treated inconsistently even between branches; this is added to DEC-01. The writer's `allotment__type='ARO'` filter can never match, because the column is `max_length=2` with values `AR`/`AT`; the audit already notes this. **`is_boe`:** the engine ignores it (DEC-02), and `is_boe` disagrees between allotment and allotment item on 29 of the 34 sample allotment items. **Status:** all 11,610 items are `CREATED`, and `released_quantity` is 0 everywhere and is read by no code, so it has no effect today |
| 4 | BOE row → item → licence | PASS | The match is by `sr_number_id` (PK). There are 0 debit rows without a BOE (all 146,554 `C` rows are BOE-less credit rows and are correctly ignored) and 0 null qty/CIF on sample rows. New owner question: **DEC-60**, a sibling-item M2M link |
| 5 | Qty fallback | PASS (live) / FAIL (stored, carried) | The live engine uses `quantity`, never `old_quantity` (`calculate_balance.py:107`). The stored writer truncates to a whole number (`round_down(…,0)`, RC13 / D-F) |
| 6 | Priority | PASS | No priority term exists in `balance_calculator.py` or `condition_pool.py` (grep returns 0), and there is no priority column on any source table. Priority only orders planning |
| 7 | Units (kg/KG/Kg, MT) | PASS-EXC | The units are kg (26,784), KG (22) and Kg (12). There is no MT, and export items are all kg. The calculator never reads `unit`; the KG sample item 33738 agrees exactly. BOE rows carry no unit, so a BOE filed in MT cannot be detected (DEC-25, cited) |
| 8 | Import item mapping (description/HSN vs id) | PASS | The engines never read description or HSN. In the sample, the allotment `item_name` and BOE `product_name` match the item description (CARDAMOM, WHEAT GLUTEN, ALUMINIUM FOIL, DWP/SWP, FRUIT COCKTAIL) |
| 9 | Legacy item cap `calculate_item_balance` | **Confirms SAT-DEF-005 and measures it** (the audit says "not measured") | It is used by `allotment/services/allocation_service.py:73`, `sion_planning_execution.py:1585`, `effective_cif_mode.py:75` and `boe_service.py:215`. On the sample, the shared-ceiling items exceed the licence balance: see the table after this one |

**Measured legacy-cap excess (challenge 9):**

| Licence / item | Legacy cap | Licence balance | Excess |
|---|---|---|---|
| 0511040554 / 36928 | 2,023,977.40 | 1,564,842.16 | +459,135.24 |
| 3411008503 / 39855 | 570,109.79 | 437,408.59 | +132,701.20 |
| 0310833305 / 4443 | 262,491.14 | 119,897.22 | +142,593.92 (AR) |
| 5611004883 / 35967 | 248,597.46 | 18,945.36 | +229,652.10 |

Item 19712 also ignores its 3 % pool: the legacy cap is 629,837.83 against a pool of 291.133.

## 5. Agreement with the audit, and challenges to it

**Numbers.** I **agree on every record**: 19 items × 17 fields, plus 3 licences. There are 0 disagreements. The licence figures are:
- 0310827509 = −3,447,851.40: original 0, which is the audit's DQ-2;
- 0311052122 = 2,649,495.02: 22 hidden rows totalling 2,777,743.13, entering through the opening balance; customs-visible would be 5,427,238.15;
- 5211011493 = 104.43.

**Where the audit's conclusions are incomplete:**
1. SAT-DEF-002 measures "`is_boe` without M2M" through the `is_boe` flag. A probable double count with `is_boe=False` escapes that
   measure; see SAT-DEF-150.
2. §5 "mapping PASS" does not cover an M2M BOE that debits a **sibling** item. That leaves the allotted item's quantity unconsumed;
   see DEC-60.
3. SAT-DEF-005 is listed as "not measured on the DB". The measurement on this sample is in §4, challenge 9.
4. Layer 3 ("API = service, 0 differences") is true, but the API returns some CIF values unquantized; see SAT-DEF-151.

## 6. New owner question (numbered DEC-60+ per controller instruction)

| ID | Question | Evidence | Current | Options |
|---|---|---|---|---|
| DEC-60 | An allotment is M2M-linked to a BOE whose rows debit a **sibling** import item on the same licence, never the allotted item. Should the allotted item count as consumed? | 94 allotment items / 67 licences, 3,377,428 kg, CIF 8,736,879.71. 27 of them have a sibling row of identical qty, i.e. the BOE was filed against another serial. Sample: 0311010834/11836 allot 2220 (110,000 kg → BOE 8154268); 5611004883/35967 allot 9311 (5,218 kg → BOE 9753619); 5211005013 allot 3110 (110,000 kg) | The allotment gives 0 (M2M rule) and the BOE debits the sibling. The allotted item's qty is neither debited nor reserved, and the licence CIF is correct | (a) Keep, treating the BOE row's serial as authoritative. (b) Flag these as a reconciliation warning ("BOE debits a different serial than allotted"), with no balance change. (c) Re-attribute: needs an owner decision and a data change. Reviewer recommends (b). It is separate from DEC-05 (cross-licence), and 207 linked items whose BOEs do not debit the licence at all belong to DEC-05/DEC-03 |

## 7. New defects (SAT-DEF-150…)

| ID | Severity | Defect | Evidence | Note |
|---|---|---|---|---|
| SAT-DEF-150 | Medium (data, double count) | An unlinked allotment is still outstanding although a same-item, same-company, same-qty, later, visible BOE that is itself unlinked exists. The licence is debited twice | 8 allotment items, CIF 420,407.75 / 215,552 kg. 7 have `is_boe=True` (SAT-DEF-002 / DEC-02 scope, e.g. 8985 ↔ 7944812, 9760 ↔ 3220444). **1 has `is_boe=False`, so the SAT-DEF-002 measure misses it:** 0910065986 sr 1 item 39996, allotment 10178 (132,000 kg / 184,932.00, 2026-10-09) ↔ BOE 4849356 (2026-11-03, 132,000 kg / 189,677.63) | The fix is a UI M2M link (no formula change). Use this heuristic (`population.py` B) as a reconciliation warning |
| SAT-DEF-151 | Low | Item `available_value` / `balance_cif_fc` for `%`-condition items is returned unquantized (3 dp) | 5211006995/19712: API 291.133 (pool 1,358,577.10 × 3 % = 40,757.313 − 40,466.18) | Breaks "quantize 2 dp at the edge". The API is also float (SAT-DEF-142) |

## 8. Disagreements

None on figures. The four points in §5 are scope gaps in the audit's conclusions, not arithmetic errors.

## 9. Evidence (`~/lm_sat_evidence/cifrecon/review/`, every script exit 0)

| File | What |
|---|---|
| `schema.py`, `facts.py`, `facts2.py` | Schema and population facts |
| `independent.py` → `review_independent.json`, `independent.log` | My expected figures (written before any audit file was read) |
| `actual.py` → `review_actual.json`, `actual.log` | App maps, stored columns, real detail API (HTTP 200 × 22) |
| `challenge.py` → `review_challenge.json` | 3 % pool, duplicates, mapping and unit checks |
| `population.py`, `pop2.py` → `review_population.json` | DEC-60 and SAT-DEF-150 population counts |
| `compare.py` → `compare.log`, `tables.py` → `tables.md` | Comparison with `item_rows.tsv` / `licence_balances.json` |

Tests: none run (no code changed).
