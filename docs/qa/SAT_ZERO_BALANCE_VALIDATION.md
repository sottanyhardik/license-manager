# SAT — Zero-balance validation (P0 addendum §H)

Date 2026-11-20 · branch `feature/v5` @ `ec3604cb` · local DB `lmanagement@localhost` **read-only** · audit only, nothing
forced or fixed. Evidence: `~/lm_sat_evidence/cifrecon/zero_balance.py`, `zero_balance.json`, `licence_balances.json`,
`item_rows.tsv` (all exit 0). Method and independent formulas: `SAT_IMPORT_ITEM_CIF_RECONCILIATION.md` §2.

Rule tested: for a fully consumed entitlement, expected available CIF = 0 and expected available qty = 0, checked **per
import item** and again at licence level. A licence-level zero is not accepted as proof for its items. No balance was
forced to zero. Tolerances: qty 0.001 and CIF 0.01. No rounding was applied before comparing.

## 1. Item level (26,818 items)

| Check | Count | Amount | Verdict |
|---|---|---|---|
| Items with qty fully consumed (\|independent remaining\| ≤ 0.001) | 664 | — | — |
| …of which the engine/API does **not** show 0 | **0** | — | **PASS** |
| Items whose own CIF is fully consumed (\|attributed remaining\| ≤ 0.01), out of 2,555 items with their own CIF | 114 | — | PASS (engine = independent, 0 diffs) |
| Qty over-used (signed remaining < 0) | 44 | −3,749,209.142 | Signed value preserved; API flags `is_quantity_over_utilised` (35/35 rechecked) — **PASS-EXC** (data, see §3) |
| Item CIF over-used (attributed remaining < 0) | 13 | −6,102,280.09 | Floored to 0 with **no CIF over-use flag** — **FAIL vs rule "flag over-utilisation"** → DEC-50 |
| …of which the licence balance is still positive | 6 | −5,518,485.10 | Licence-level figure hides item-level over-use (the case §H warns about) |
| Qty residual 0.001–1 unit after BOE debits | 3,483 | 1,734.670 | The live engine shows the residual. The stored column / Customs PDF floor it to 0 (RC13; D-F decided 3 dp, not implemented) — **PASS-EXC** |
| Stored `available_quantity` = 0 while live qty remains | 862 | 6,790,655.003 | AR deducted by a stale writer, plus the whole-number floor (`SAT_IMPORT_ITEM_CIF_RECONCILIATION.md` §4) — **FAIL (carried RC3/RC13)** |
| Zero **only if** AR (ARO) is deducted | 27 | 5,776,458.000 kg live | Depends on DEC-01: live shows the qty available, stored shows 0 |
| Qty exhausted, item CIF left | 25 | 1,993,549.35 | Consistent arithmetic; eligibility question → DEC-51 |
| Item CIF exhausted (0.01 marker), qty left | 89 | — | The 0.01 marker items share the licence ceiling, so this is by design — PASS |

### Fully consumed items: sample rows (expected 0 / actual 0)

| Licence | Item (sr) | Original qty | Debited | Outstanding AT | Expected | Engine | API canonical | Stored |
|---|---|---|---|---|---|---|---|---|
| 0911008577 | 28273 (13) | 10,127.000 | 10,127.000 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| 0911008257 | 28375 (3) | 106,206.000 | 106,206.000 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| 0311010975 | 12602 (1) | 294,861.420 | 294,861.420 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |

These two `0911…` items are also in the independent reviewer's sample (`SAT_CIF_RECON_INDEPENDENT_REVIEW.md`).

### Item over-use (signed values kept; top rows)

| Licence | Item (sr) | Unit | Original qty | BOE debited qty | Outst. AT | Remaining (signed) | Licence balance |
|---|---|---|---|---|---|---|---|
| 0910061491 | 3127 (3) | kg | 722,264.000 | 1,454,600.000 | 0 | −732,336.000 | 2,677,567.24 |
| 0910061490 | 3142 (3) | kg | 862,963.030 | 1,524,940.000 | 0 | −661,976.970 | 3,178,823.29 |
| 0910060696 | 10630 (3) | kg | 185,986.080 | 774,940.000 | 0 | −588,953.920 | 916,013.54 |
| 0910061780 | 3112 (3) | kg | 198,482.640 | 774,940.000 | 0 | −576,457.360 | 836,408.26 |
| 0910059715 | 3209 (1) | kg | 734,764.800 | 1,003,440.000 | 0 | −268,675.200 | 526,846.43 |
| 0310543354 | 6397 (3) | kg | 334,000.000 | 465,924.000 | 0 | −131,924.000 | 0.59 |
| 0911005591 | 18158 (1) | kg | 672.380 | 120,140.150 | 0 | −119,467.770 | 1,499.25 |
| 3411008581 | 40132 (1) | kg | 1,091,691.380 | 1,085,060.000 | 80,000.000 | −73,368.620 | −96,869.32 |

| Licence | Item (sr) | Own CIF | BOE debit CIF | Outst. AT CIF | Attributed (signed) | App item value | Licence balance |
|---|---|---|---|---|---|---|---|
| 0310653755 | 32156 (1) | 198,420.00 | 5,178,561.36 | 0 | −4,980,141.36 | 0.00 | 8,676,005.26 |
| 0310543354 | 6397 (3) | 74,482.00 | 397,523.56 | 0 | −323,041.56 | 0.00 | 0.59 |
| 0910038160 | 13747 (2) | 18,000.00 | 226,148.36 | 0 | −208,148.36 | 0.00 | −48,695.15 |
| 0310493058 | 31982 (4) | 20,440.00 | 193,510.51 | 0 | −173,070.51 | 0.00 | −40,877.48 |
| 0610012279 | 16138 (3) | 71,500.00 | 184,464.00 | 0 | −112,964.00 | 0.00 | 3,576,863.19 |
| 3411008581 | 40132 (1) | 3,706,669.33 | 3,547,298.65 | 256,240.00 | −96,869.32 | 0.00 | −96,869.32 |
| 5211016746 | 31378 (1) | 3,250,277.56 | 3,227,941.57 | 76,000.00 | −53,664.01 | 0.00 | −75,036.77 |
| 5211016747 | 31518 (1) | 3,211,728.90 | 3,023,139.41 | 188,900.00 | −310.51 | 0.00 | −310.51 |

On 5211016746 and 5211016747, the outstanding AT includes `is_boe`-without-M2M allotments (SAT-DEF-002 / DEC-02). If those
allotments are treated as consumed, these items move to about 0 or a positive value.

## 2. Licence level (2,185 licences)

| Check | Count | Amount | Verdict |
|---|---|---|---|
| Independent (Σ export CIF − visible − hidden − AT − AR) vs financial engine | **0 diffs** | — | **PASS** |
| Licence balance exactly 0 | 10 | — | 3 real zeros (0311010975, 0311013329, 0311013333): export CIF = BOE debit and every item's qty is 0 — **PASS**. 7 are empty licences (export CIF 0, no debits) — PASS |
| Over-utilised (signed balance < 0) | 36 | −7,054,283.95 | Signed and flagged (`is_over_utilised`, Phase 3) — **PASS** |
| All item quantities consumed but licence CIF left | 11 | 255,396.35 | **PASS-EXC**: CIF and qty are separate ceilings, so the leftover CIF is real but not usable. DEC-51 |
| Licence CIF 0 but item qty left | 5 | — | All have export CIF 0 and no debits (empty) — PASS |
| Original CIF 0 but BOEs debited | 8 | Σ debit 3,631,501.88 | **FAIL (data)**. E.g. 0310827509 (3,257,841.98 debited, balance −3,447,851.40), 0910061510, 1311001682 |
| Stored `is_null` flag ≠ live balance < 100 | 189 | Σ live 42,394.60 | **FAIL**: three thresholds (100/200/500), SAT-DEF-140 / DEC-52 |

### Licence-level zero/over-use samples

| Licence | Export CIF | Visible BOE | Hidden | Outst. AT | Outst. AR | Independent | Engine | All items qty 0? |
|---|---|---|---|---|---|---|---|---|
| 0311010975 | 67,825.03 | 67,825.03 | 0 | 0 | 0 | 0.00 | 0.00 | yes |
| 0311013329 | 83,441.35 | 83,441.35 | 0 | 0 | 0 | 0.00 | 0.00 | yes |
| 0311013333 | 150,838.66 | 150,838.66 | 0 | 0 | 0 | 0.00 | 0.00 | yes |
| 0311013069 | 2,900,000.00 | 2,743,824.83 | 0 | 0 | 0 | 156,175.17 | 156,175.17 | yes → CIF left, qty 0 |
| 0310827509 | 0.00 | 3,257,841.98 | 0 | 0 | 190,009.42 | −3,447,851.40 | −3,447,851.40 | — |
| 0310833304 | 6,824,661.89 | 6,790,943.16 | 0 | 0 | 2,011,506.09 | −1,977,787.36 | −1,977,787.36 | — |
| 0310499297 | 1,903,101.21 | 2,356,473.06 | 0 | 0 | 0 | −453,371.85 | −453,371.85 | — |

## 3. Root cause and financial impact of non-zero "consumed" cases

| Case | Exact source | Financial impact |
|---|---|---|
| Over-debited qty (BOE qty ≈ 2× the licensed qty on the `0910…` items) | BOE rows on the item exceed the licensed qty. Possibly a duplicate import, a unit difference or an amendment that was never entered. `SAT_INVOICE_BOE_QUANTITY_AUDIT.md` lists 35 items with BOE qty > licensed, +3,613,764.872 | Item qty −3,749,209.142 over 44 items. CIF is unaffected where the item shares the ceiling |
| Item CIF over-use invisible | `ItemBalanceCalculator.calculate_item_attributed_balances_for_items` floors at 0 (approved floor). No item CIF over-use field exists | −6,102,280.09 (13 items) not signalled at item level |
| Residuals < 1 unit shown as 0 | `calculate_balance.py:122` whole-number floor (stored) and Customs PDF (RC13) | 1,734.670 qty on 3,483 items |
| AR not deducted at item level | DEC-01 / SAT-DEF-001 | 27 items reach 0 only with AR; 5,776,458 kg |
| Zero-original licences with debits | Data: export items missing or CIF 0 | 3,631,501.88 debited against 0 entitlement |

## 4. Verdict

- Licence-level zero-balance arithmetic: **PASS**. The independent figure equals the engine on 2,185 / 2,185 licences, and the 3 genuine zero licences show exactly 0.00.
- Item-level live engine: **PASS**. All 664 fully consumed items show 0, and the signed qty over-use is flagged.
- Stored and secondary surfaces: **FAIL (carried)**. The stored column, the Customs PDF and the API stored fields floor to whole units, deduct AR on stale rows, and in 862 items show 0 where qty remains.
- Item CIF over-use is not flagged: **FAIL against the stated rule**. Owner question DEC-50.
- Proposed register entries: DEC-50, DEC-51, DEC-52 and SAT-DEF-140…142. They are listed in `SAT_IMPORT_ITEM_CIF_RECONCILIATION.md` §8.
