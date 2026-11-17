# Backend Audit 11: Quantity discrepancy report (measured)

Status: **read-only measurement, 2026-11-17, feature/v5 working tree.** No formula, code, test, migration, DB
value or existing doc was changed. This doc builds on `07_BOE_ALLOTMENT_MAPPING_AUDIT.md` (mapping, §5 query
sketches) and `08_QUANTITY_RECONCILIATION_PROPOSAL.md` (inventory S1–S22 / C1–C12, candidates QA/QL/QB/QG/QR,
decisions OD-QTY-*). It does not restate them. It adds real numbers.

How it was measured:
- Database: **only** the clone `lmanagement_restore_verify_live4_20261116`. Every script asserted
  `settings.DATABASES['default']['NAME']` and `current_database()` equal the clone, and ran inside
  `transaction.atomic()` + `SET TRANSACTION READ ONLY`, ending in a forced rollback. `lmanagement` was never
  opened. Scripts live in `/tmp/qty_audit/` (outside the repo).
- Engine values come from calling the existing engine (`ItemBalanceCalculator` / `LicenseBalanceCalculator`).
  Wire values come from calling `LicenseImportItemSerializer` and `compute_item_ledger_rows`. Client values
  C1–C4 were replicated in Python from the exact TS expressions cited. IEEE-754 doubles (same as JS `Number`)
  were used, and `toFixed` was emulated as exact-binary round-half-up. For the 10 sample items, the replicated
  C1/C2 matched the values recomputed from live serializer output exactly (`wireC1/C2 match=True`).
- Licence numbers, company names and IECs are not printed. Sample licences are L1..L10.
- Clone size: 221 licences, 2 377 import items (SRs), 1 044 BOEs, 8 159 `RowDetails` (6 654 C / 1 505 D),
  45 allotments / 102 `AllotmentItems`, 874 trade lines (573 SALE / 301 PURCHASE).
- Whether production matches the clone is **INFERRED** (the clone is a live restore dated 2026-11-16).

Paths are relative to `backend/apps/` unless they start with `frontend/`. Every row is tagged **MEASURED**
(run against the clone in this session) or **INFERRED** (from reading code or by reasoning).

---------------------------------------------------------------------------------------------------

## 0. Findings by severity

| ID | Sev | Finding | Evidence |
|---|---|---|---|
| Q-1 | **CRITICAL** | The stored `available_quantity` (S3) still subtracts **hidden-BOE** debits that the engine (S1) excludes. 253 SRs on 95 licences are understated by 15 859 437.72 in total. **140 SRs show 0 while the engine has 10 482 020.97 available.** S3 feeds the overview-items `balance_qty` ("Balance Qty"), the modal "Available" column, and the A1/A2 allotment gates (08 S3). | MEASURED (§2.2, §6 L7/L8). Effect on gates: INFERRED from 08 S3 / doc 05 D2 |
| Q-2 | HIGH | C1 (CustomsLedgerSection "Actual Available") subtracts S8, which ignores sale/purchase pairing. 37 paired SALE lines on trades with no BOE (4 563 266.99) are subtracted although S1 nets them to 0. **30 SRs on 28 licences** differ from S1. 26 show a negative value, and 2 show 0 ("Exhausted") while the engine has the full balance (L10). | MEASURED (§5, §6 L6/L10) |
| Q-3 | HIGH | C2 (LicenseBalanceModal "Balance") uses stored `debited_quantity` (S4, which includes hidden BOEs). **265 SRs on 106 licences** differ from S1, and 13 are negative. | MEASURED (§2.2) |
| Q-4 | HIGH | C3 AllotmentsTab "Total Allotted" Qty = 2 841 560 across 57 licences. The engine's outstanding allotment qty (S2) is 129 799. 54/57 licences disagree. 94 of the rows shown are "Linked to BOE" and are already represented by BOE debits. | MEASURED (§5) |
| Q-5 | HIGH | Duplicate CREDIT rows from ledger re-import (07 §7 escalation) are confirmed. There are 988 duplicate groups with 4 296 extra C rows, adding 99 436 947.913 qty. **968 SRs have Σ C qty > SR quantity.** This inflates `usable`/`opening_balance` (S22). C1–C4 are not affected. | MEASURED (§5) |
| Q-6 | HIGH (for grouping, 07 F1/F4) | 825 of 1 041 BOEs with lines have no supplier. 1 372 of 2 377 SRs have no canonical name. 282 companies have a blank name. | MEASURED (§2.1 M1/M2/M4) |
| Q-7 | MEDIUM | **Schema drift.** The clone's columns are `numeric(15,2)` for `LicenseImportItemsModel.quantity/old_quantity/available_quantity/debited_quantity/allotted_quantity` and `AllotmentModel.unit_value_per_unit`, but the models declare `15,3`. `AllotmentModel.exchange_rate` is `double precision`, but the model declares `Decimal(15,6)`. The migration plan shows **0 unapplied** migrations. No value is lost today: no D/allotment qty has a 3rd decimal. A 3dp write to these columns would be rounded by Postgres. | MEASURED on the clone; production INFERRED |
| Q-8 | MEDIUM | 4 unpaired SALE lines (66 018.30) have no BOE link and no allocation, yet a D row with the **identical qty exists on the same SR**. S1 subtracts both (example SRs 37581–37583). This is either a missing `trade.boes` link (an engine double subtraction) or two genuine events. | MEASURED count; "double" is INFERRED |
| Q-9 | MEDIUM | Stale stored cache. 1 SR has S3 = 220 000 while the engine gives 0 (a 220 000 direct sale is not reflected). 3 SRs have stale S4. | MEASURED |
| Q-10 | MEDIUM | S3 integer floor drops a fractional part on 1 848 SRs: up to 0.99 each, 883.93 in total. 2 041 SRs carry a fractional quantity. | MEASURED |
| Q-11 | LOW | Unit strings are `kg` 2 343, `KG` 30, `Kg` 2, `mts` 2. Mixed strings appear in 7 licences, 4 BOEs, 2 allotments and 10 canonical names. **Every mix is a case variant of kg**: 0 canonical names and 0 HS codes mix genuinely different units. The 2 `mts` SRs (163 077.02 and 166 831.32 "mts") are traded with `qty_kg` equal to the SR quantity, so the unit label is doubtful. | MEASURED; label doubt INFERRED |
| Q-12 | LOW | Float math in C1/C2 gives a value that differs from exact Decimal on 1 965/1 971 SRs. The **displayed** value never differs (0 cases ≥ 0.001 after `toFixed`), and there are 0 status flips of the X9 kind. | MEASURED |
| Q-13 | LOW | 14 SRs are over-utilised (unfloored S1 < 0, 1 775 155.76 in total). S1/S3 floor them to 0, while C1/C2 show negatives. 17 SRs have S1 = 0 while C1 ≠ 0, so "Exhausted" is not shown. | MEASURED |

---------------------------------------------------------------------------------------------------

## 1. Every quantity calculation mapped to its API field (08 inventory → wire → UI)

The scope is the four client formulas (C1–C4) and the server fields that feed them. The other 08 rows
(S9–S12, S16–S22, C5–C12) do not feed C1–C4. They are listed in 08 §1 and were not re-traced here.

| 08 # | Frontend field / formula (file:line) | Wire field (serializer / service, file:line) | Model / engine source (file:line) | Tag |
|---|---|---|---|---|
| C1 | `CustomsLedgerSection.tsx:15` `actualAvailableQuantity = quantity − boe_debited_quantity − allotted_quantity − billed_no_boe_qty`; injected at `:76`; shown with `fmtNum(v, 3)` (`:20`, `licenseBalanceHelpers.ts:6-11` → `toFixed`); status `=== 0` → "Exhausted" (`:16`) | licence detail `import_license[]` (`LicenseImportItemSerializer` via `import_license_read`, `license/api/serializers/license.py:553`) | — | MEASURED (replicated = wire) |
| ↳ | `quantity` | `ModelSerializer` field, Decimal string 3dp (e.g. `'66859.780'`) | `LicenseImportItemsModel.quantity` (`license/models/items.py:93`; DB 15,2, see Q-7) | MEASURED |
| ↳ | `boe_debited_quantity` (S5) | `get_boe_debited_quantity` `license.py:307-318` (`float`); batched map injected at `:895-898` | `ItemBalanceCalculator.calculate_debited_quantity_for_items` `license/services/balance_calculator.py:2012-2039` (D rows, `exclude_hidden`) | MEASURED |
| ↳ | `allotted_quantity` (S6) | `get_allotted_quantity` `license.py:323-324` (`float` of stored column) | stored by `core/scripts/calculate_balance.py:108-111` from S2 (`balance_calculator.py:895-925`) | MEASURED |
| ↳ | `billed_no_boe_qty` (S8) | `get_billed_no_boe_qty` `license.py:384-417`. The licence detail never injects `billed_no_boe_qty_map` (only `item_pivot_service.py:188` and `allotment/api/views_actions.py:549` use the bulk map), so this is **one query per item** | `LicenseTradeLine.qty_kg`, SALE, `trade__boes__isnull=True`, no pairing/allocation netting | MEASURED |
| C2 | `LicenseBalanceModal.tsx:1025-1034` `quantity − debited_quantity − allotted_quantity`, `formatFiniteDecimal` (`components/licenseBalanceHelpers.ts:13`, `toFixed(2)`) | same licence detail fields | `debited_quantity` (S4): `get_debited_quantity` `license.py:304-305` ← stored `calculate_balance.py:102-105` (`round(debited+aro+direct_sale, 2)`, **no hidden exclusion**: `:41-45`) | MEASURED |
| C2' | `LicenseBalanceModal.tsx:901` shows `available_quantity` | `get_available_quantity` `license.py:270-273` (`float`) | stored S3 `calculate_balance.py:73-98` (`round_down(…, 0)`, floor 0) | MEASURED |
| S13 | `ItemsTab.tsx:100` "Balance Qty" `fmtNum(row.balance_qty)`; type `types.ts:110` | `GET /licenses/<id>/overview-items/` `balance_qty` = `item.available_quantity` (`license/services/license_overview_items.py:49, :63`) | stored S3 | MEASURED (= S3 on all 10 samples) |
| C3 | `AllotmentsTab.tsx:71` `totalQty = Σ Number(a.quantity)`, shown `:129` | `overview-allotments/` `quantity` = `Σ AllotmentItems.qty` per allotment for this licence (`license/services/license_overview_allotments.py:37-44, :78`) | `AllotmentItems.qty` (15,3), not netted, linked rows included | MEASURED |
| C4 | `AllotmentsTab.tsx:92` `rate = cif_fc / quantity` | same row (`cif_fc` `:79`) | `AllotmentItems.cif_fc` / `qty` | MEASURED |
| S1 (reference) | not exposed to the licence workspace | trade SALE validation, `balance_snapshot` (08 S1) | `ItemBalanceCalculator.calculate_available_quantity` `balance_calculator.py:1969-2009`; bulk `:2041-2092` (equal on all 10 samples) | MEASURED |
| S7 (reference) | not exposed | — | `_direct_sale_quantity_rows` `balance_calculator.py:1872-1936` | MEASURED |

---------------------------------------------------------------------------------------------------

## 2. 07 §5 measurements (real numbers)

### 2.1 M1–M14 (all MEASURED, global scope)

| ID | Query (07 §5) | Result |
|---|---|---|
| M1 | BOEs with ≥1 line and no supplier | **825 / 1 041** (79 %). All BOEs: 828 / 1 044 |
| M2 | Normalised company-name collisions | 13 groups / 306 companies. One group is the **blank name (282 companies)**; the other 12 groups have 2 IECs each |
| M2b | Blank company names | 282 / 1 026 |
| M3 | Allotments with `related_company` | 0 / 45 (related_differs 0) |
| M3b | Companies acting as both BOE supplier and allotment customer | 13 |
| M4 | SRs by number of canonical names (all / with transactions) | 0 names: 1 372 / 1 372 · 1: 754 / 744 · 2: 200 / 196 · 3: 34 / 32 · 4: 17 / 17. **251 SRs have ≥2 names** (07 F5 fan-out risk) |
| M5 | Canonical names whose SRs use >1 unit string | 10. All are `kg`+`KG` or `kg`+`Kg`, covering 18–98 SRs each |
| M6 | Import-item units | `kg` 2 343 · `KG` 30 · `Kg` 2 · `mts` 2. `KG`, `Kg` and `mts` are outside `UNIT_CHOICES` casing (choices are `kg, pcs, nos, mts`) |
| M7 | BOEs spanning SRs / licences / units | multi-SR 199 · multi-licence 189 · multi-unit 4 · of 1 041 |
| M8 | Rows by type | C 6 654 rows, Σ qty 219 149 429.489, **all with `bill_of_entry_id` NULL** · D 1 505 rows, Σ qty 37 694 124.800, 0 with NULL BOE |
| M8b | (BOE, SR) with both C and D | **0**. OD-MAP-1 / X12 stays LATENT on this data |
| M9 | Allotments spanning SRs / licences / units | multi-SR 18 · multi-licence 18 · multi-unit 2 · of 42 with items |
| M9b/c | Duplicate (allotment, SR, basis) rows; ACTUAL+PLAN on the same SR | 0 / 0. All 102 rows are `ACTUAL` (no PLAN rows exist) |
| M10 | Orphans | `AllotmentItems` with no item: 0 · with no allotment: 0 · `RowDetails` with no BOE: 6 654 (exactly the C rows) |
| M11 | Linked allotments / links | 38 allotments / 38 links |
| M11b | Allotments in >1 BOE | **0** |
| M11c | Stale `is_boe` | stale_false 0 · stale_true 2 (of 45) |
| M12 | Linked allotment lines with no same-SR D row in any linked BOE (07 F15) | **6 of 96** linked lines |
| M12b | Cross-licence M2M pairs (07 F19) | **5 of 38** |
| M13 | `BOEAllotmentAllocation` rows | **0** (no ledger allotment netting exists; R1/R2 depend on the M2M only) |
| M13b | Cross-SR BOE↔allotment allocations | 0 |
| M13c | `InvoiceBOEAllocation` | 2 ACTIVE/current, Σ qty 198 000 |
| M13d | Cross-SR invoice↔BOE allocations | 0 |
| M14 | Allotment types | AT only: 45 allotments, 102 lines, Σ qty 2 841 560, Σ CIF 5 416 140.06. **0 AR**, so X10 / OD-MAP-4 cannot occur on this data |

The 08 "Not verified" X1/X2 query was also run (MEASURED). There are 37 paired SALE lines on trades with no
BOE (Σ 4 563 266.99), and 0 allocated SALE lines on trades with no BOE (X2 does not occur in the data).

### 2.2 Item-level parity: all 2 377 SRs (MEASURED)

| Comparison | SRs with \|Δ\| ≥ 0.001 | Licences | Cause breakdown |
|---|---|---|---|
| S3 stored (`balance_qty`) vs S1 engine | **2 102** | 95 with \|Δ\| ≥ 1 | integer floor only 1 848 · hidden-BOE 253 (all 253 fully explained by hidden D qty) · stale cache 1 |
| C1 vs S1 | **30** | 28 | S8 ≠ S7 16 · over-use floor 11 · both 3 |
| C2 vs S1 | **265** | 106 | hidden-BOE 253 · over-use floor 11 · stale S4 1 |
| C1 vs C2 | 276 | — | — |
| S6 stored vs S2 live | 0 | — | — |
| S4 stored vs live (raw D + S7) | 4 | — | stale (37581–37583, 39199) |

Hidden BOEs: 508 of 1 044 BOEs are genuinely hidden (`annotate_and_exclude_hidden(hidden_only=True)`), with
646 D rows. The engine excludes them (`balance_calculator.py:1996`, `:2033`). The stored writer
`calculate_balance.py:41-45` does not, which is X16 in 08. X16 is not a corner case: it is the dominant
divergence.

---------------------------------------------------------------------------------------------------

## 3. Unit inconsistencies (MEASURED)

Transaction tables have no unit column (07 §3). The effective unit is the SR's `unit`. The counts below
attribute each row to the unit of its SR.

| Source | `kg` | `KG` | `Kg` | `mts` |
|---|---|---|---|---|
| Import items (SRs) | 2 343 (219 lic, Σ 118 344 680.70) | 30 (7 lic, Σ 190 591.68) | 2 (1 lic, Σ 8 328.67) | 2 (2 lic, Σ 329 908.34) |
| BOE rows D | 1 498 (Σ 37 672 887.800) | 7 (Σ 21 237.000) | 0 | 0 |
| BOE rows C | 6 620 | 30 | 2 | 2 |
| Allotment items | 99 (Σ 2 834 324) | 3 (Σ 7 236) | 0 | 0 |
| Trade lines SALE / PURCHASE | 563 / 296 | 7 / 0 | 1 / 1 (qty 0) | 2 / 4 (Σ 329 908.34 / 659 816.68) |
| Export items | 221 (`kg` only) | — | — | — |

Other unit vocabularies (not attached to transactions; listed for OD-MAP-5):
- SION import units: `KILOGRAMS (KGS)` 5 804, blank 3 406, `GRAMS (GMS)` 428, `METRIC TON (MTS)` 168, … plus
  stray `kg` 1, `MT` 1.
- HS-code master units: `kg.` 4 191, `kg` 4 024, `u` 2 685, blank 1 158, `Kg` 107, `mt` 41, `m2`/`m 2`/`M2`,
  `m3`/`m 3`/`M3`.
- No mapping table between these vocabularies and `UNIT_CHOICES` exists (07 §3).

Same item, different unit strings across sources:

| Grain | Count | Genuinely different after case-fold |
|---|---|---|
| Licences whose SRs mix unit strings | 7 (6 × {`kg`,`KG`}, 1 × {`kg`,`Kg`,`KG`}) | 0 |
| BOEs spanning unit strings | 4 ({`kg`,`KG`}) | 0 |
| Allotments spanning unit strings | 2 ({`kg`,`KG`}) | 0 |
| Canonical names on SRs with different unit strings | 10 | 0 |
| HS codes on SRs with different unit strings | 12 | 0 |
| Within one SR across BOE / allotment / trade | impossible by design (lines inherit the SR unit) | — |

`mts` (MEASURED + INFERRED): SRs 39558/39559 hold 163 077.02 and 166 831.32 "mts". They have no D rows and
no allotments. They do have 3 trade lines each, with `qty_kg` exactly equal to the SR quantity, on a
PURCHASE/SALE pair. 163 077 metric tonnes on one SR is implausible, so the label is probably wrong (kg or
metres). `LicenseTradeLine.qty_kg` carries the SR's unit whatever its name (07 R-20). Owner check needed.

Consequence:
- Under 07 OD-MAP-5 option (a) (exact string), 7 licences, 4 BOEs and 2 allotments would show split
  `kg`/`KG` subtotals that are the same physical unit.
- Under option (b) (case-fold), the data has no conflicts.

---------------------------------------------------------------------------------------------------

## 4. Rounding and precision

### 4.1 Decimal scale per column (MEASURED from `information_schema` on the clone vs model declarations)

| Column | Clone DB | Model | Drift |
|---|---|---|---|
| `LicenseImportItemsModel.quantity`, `old_quantity` | numeric(15,**2**) | (15,3) `items.py:93-94` | **yes** |
| `LicenseImportItemsModel.available_quantity`, `debited_quantity`, `allotted_quantity` | numeric(15,**2**) | (15,3) `items.py:100-106` | **yes** |
| `LicenseImportItemsModel.cif_fc` | (15,2) | (15,2) | no |
| `RowDetails.qty`, `cif_fc`, `cif_inr` | (15,3) | (15,3) | no |
| `AllotmentItems.qty`, `released_quantity`, `reactivated_quantity` | (15,3) | (15,3) | no |
| `AllotmentItems.cif_fc` | (15,2) | (15,2) | no |
| `AllotmentModel.required_quantity` | (15,2) | (15,2) | no |
| `AllotmentModel.unit_value_per_unit` | (15,**2**) | (15,3) (`allotment/migrations/0001_initial.py:27`) | **yes** |
| `AllotmentModel.exchange_rate` | **double precision** | Decimal(15,6) | **yes** |
| `LicenseTradeLine.qty_kg` | (20,4) | (20,4) | no |
| `LicenseTradeLine.cif_fc` | (20,2) | (20,2) | no |
| `BOEAllotmentAllocation.allocated_qty` / `InvoiceBOEAllocation.allocated_qty` / `ExternalInvoiceLink.qty` | (20,4) | (20,4) | no |
| `…allocated_cif_fc` | (20,3) | (20,3) | no |
| `LicenseExportItemModel.cif_fc`, `net_quantity` | double precision | (not re-checked) | — |

`MigrationExecutor.migration_plan` on the clone lists **0 unapplied** migrations, yet the columns differ. The
DB was probably built from an older schema and the migrations were faked (INFERRED).

Data currently at risk (MEASURED):
- D `RowDetails.qty` with a 3rd decimal: 0 of 1 505.
- `AllotmentItems.qty` with a 3rd decimal: 0 of 102.
- C rows with a 3rd decimal: 280. They live in a 15,3 column, so they are safe.
- `qty_kg` with a 4th decimal: 0. PURCHASE lines with a 3rd decimal: 7.
- Allocation qty with a 4th decimal: 0.

So no value is lost today. Any future 3dp SR quantity or stored availability would be silently rounded to 2dp.

### 4.2 Server-side rounding (MEASURED)

| Site | Rule | SRs affected | Magnitude |
|---|---|---|---|
| S3 `calculate_balance.py:98` `round_down(…, 0)` | integer floor | 1 848 | Σ 883.93, max 0.99 per SR (e.g. L1 66 859.78 → 66 859) |
| S4 `calculate_balance.py:104` `round(…, 2)` | 2dp float | 0 beyond staleness (D qty has no 3rd decimal) | — |
| S6 `round(…, 2)` | 2dp float | 0 | — |
| Serializer `float()` on S3–S8 | Decimal → double | no 15-digit value loses a 3dp digit | — |

### 4.3 Client rounding and float math (MEASURED)

| Site | Effect | Count |
|---|---|---|
| C1 float result ≠ exact Decimal of the same inputs | e.g. residues of 1e-11 | 1 965 SRs |
| C1 displayed value (`toFixed(3)`) ≠ exact Decimal rounded to 3dp | — | **0** |
| C2 float ≠ exact Decimal | — | 1 971 SRs |
| C2 displayed value (`toFixed(2)`) differs from exact by ≥ 0.001 | — | **0** (SR quantities are 2dp in the DB) |
| C1 status flip (exact 0, float ≠ 0; the X9 shape) | — | **0** |
| C4 Rate (`cif_fc/quantity`) vs stored `unit_value_per_unit` (≥ 0.01) | — | 3 of 100 (allotment, licence) rows. 2 rows divide across >1 SR |

Conclusion: float drift is real but does not change any displayed value on this data. The visible differences
come from formula differences (§2.2), not from precision. X9 stays a derived risk only.

---------------------------------------------------------------------------------------------------

## 5. Duplicate or missing contributions

| # | Check | Count | Example / note | Sev | Tag |
|---|---|---|---|---|---|
| D-1 | Allotment qty shown next to the BOE qty that represents it (M2M-linked) | 96 lines / 54 licences, Σ qty 2 711 761, Σ CIF 4 921 330.82. C3 includes them, and 94 rows are labelled "Linked to BOE". The engine counts them as 0 | L3: S14 3 774 shown while S2 = 0 | HIGH (Q-4) | MEASURED |
| D-1b | Linked line qty vs same-SR D qty in the linked BOE | 96 lines: 6 have no same-SR D row (M12); 10 have a different qty. Σ allotment 2 711 761 vs Σ D 2 085 827.17 | the M2M zeroes the whole line whatever the BOE qty (07 §2) | MEDIUM | MEASURED |
| D-2 | `RowDetails` with no SR / D rows with no BOE | 0 / 0 (`sr_number` NOT NULL) | — | — | MEASURED |
| D-3 | C rows not attached to a BOE | 6 654 (all of them) | by design of the ledger import (07 §1.2) | info | MEASURED |
| D-4 | Duplicate C rows (same SR, qty, cif_fc, cif_inr) | 988 groups, 987 SRs, **4 296 extra rows, Σ extra qty 99 436 947.913**; 968 SRs with Σ C > SR quantity | 07 §7 re-import defect, confirmed. Affects `usable` / `opening_balance` (S22) only | HIGH (Q-5) | MEASURED |
| D-5 | Trade lines with a missing `sr_number` | 0 (NOT NULL, PROTECT) | — | — | MEASURED |
| D-6 | Paired SALE counted by S8 (X1) | 37 lines, Σ 4 563 266.99 | L6: C1 −31 142.000 vs S1 2 708.820. L10: C1 0.000 ("Exhausted") vs S1 163 077.020 | HIGH (Q-2) | MEASURED |
| D-7 | Allocated SALE on a trade with no BOE (X2, double subtraction) | 0 | latent only | LOW | MEASURED |
| D-8 | SALE whose trade has BOEs but none debiting the same SR (X3: S8 omits, S7 counts) | 33 lines, Σ 1 484 | small | LOW | MEASURED |
| D-9 | Unpaired, unlinked, unallocated SALE with an identical-qty D row on the same SR | 4 lines, Σ 66 018.30 | SRs 37581–37583 (15 898 / 15 511 / 19 358): S1 subtracts the D row **and** the sale | MEDIUM (Q-8) | count MEASURED, double INFERRED |
| D-10 | Hidden-BOE D qty counted by stored S3/S4 but not by S1/S5 | 253 SRs, Σ 15 859 437.72 | L8: S3 0 vs S1 12 335.890 | CRITICAL (Q-1) | MEASURED |
| D-11 | Allotments in several BOEs (07 F16) | 0 | — | — | MEASURED |
| D-12 | Cross-licence M2M (07 F19) / linked line with no same-SR debit (F15) | 5 pairs / 6 lines | engine zeroes those allotment lines with no matching debit | MEDIUM | MEASURED |
| D-13 | BOEs with no rows / allotments with no items | 3 / 3 | invisible in licence views | LOW | MEASURED |
| D-14 | D rows on BOEs spanning licences | 641 of 1 505 | `get_total_quantity` (S16) mixes licences (07 F10) | LOW (not in C1–C4) | MEASURED |
| D-15 | Stale stored cache | S3: 1 SR (39199, 220 000 vs engine 0). S4: 3 SRs | stored writer not re-run after a trade save | MEDIUM (Q-9) | MEASURED |

---------------------------------------------------------------------------------------------------

## 6. Before/after for 10 sample items (MEASURED)

Columns:
- `balance_qty` is the server overview-items value (`license_overview_items.py:49`). It equals the serializer's
  `available_quantity` on all 10.
- **C1** is `CustomsLedgerSection.tsx:15` and **C2** is `LicenseBalanceModal.tsx:1032-1034`, both with the
  display rounding they use.
- **Canonical** is the 08 §3.1 QA-1 value: engine S1 (`balance_calculator.py:1969-2009`), Decimal 3dp, floored,
  plus `over_utilised_quantity = max(−unfloored, 0)`.
- Inputs: Q = quantity, S5 = BOE debited (non-hidden), D_all = all D incl. hidden, S2 = outstanding allotment,
  S14 = raw allotment qty, S7 = engine direct sale, S8 = billed-no-BOE, S4/S6 = stored.

| L | Case | Unit | Q | S5 / D_all | S2 / S14 | S7 / S8 | S4 / S6 | `balance_qty` (S3) | C1 | C2 | Canonical (over-use) | Main divergence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| L1 | normal, untouched | kg | 66 859.78 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | **66 859** | 66 859.780 | 66 859.78 | 66 859.780 (0) | S3 integer floor |
| L2 | partial BOE | kg | 1 253.62 | 1 014 / 1 014 | 0 / 0 | 0 / 0 | 1 014 / 0 | **239** | 239.620 | 239.62 | 239.620 (0) | S3 floor |
| L3 | BOE-linked allotment | kg | 17 625.86 | 10 185.68 / same | 0 / **3 774** | 0 / 0 | 10 185.68 / 0 | 7 440 | 7 440.180 | 7 440.18 | 7 440.180 (0) | C3 shows 3 774 that S2 treats as represented |
| L4 | outstanding allotment, over-used | kg | 274 630.58 | 249 880 / same | 33 080 / 49 910 | 24 750 / **233 050.58** | 274 630 / 33 080 | 0 | **−241 380.000** | **−33 079.42** | 0.000 (33 079.420) | S8 includes paired sale; signed vs floored |
| L5 | multi-unit BOE (`KG` SR on a `kg`+`KG` BOE) | KG | 16 530.49 | 7 220 / same | 0 / 0 | 0 / 0 | 7 220 / 0 | 9 310 | 9 310.490 | 9 310.49 | 9 310.490 (0) | S3 floor only; unit string casing (§3) |
| L6 | traded, paired sale (X1) | kg | 33 850.82 | 31 142 / same | 0 / 31 142 (linked) | 0 / **33 850.82** | 31 142 / 0 | 2 708 | **−31 142.000** | 2 708.82 | 2 708.820 (0) | C1 subtracts paired sale |
| L7 | traded direct sale + hidden BOE | kg | 58 965.61 | 19 233 / **57 000** | 0 / 0 | 21 314 / 21 314 | 78 314 / 0 | **0** | 18 418.610 | **−19 348.39** | 18 418.610 (0) | S3/S4 count hidden 37 767 |
| L8 | hidden BOE (X16) | kg | 12 335.89 | 0 / **12 335** | 0 / 0 | 0 / 0 | 12 335 / 0 | **0** | 12 335.890 | **0.89** | 12 335.890 (0) | S3/S4 count hidden |
| L9 | over-utilised | kg | 321 000.00 | 434 670 / same | 0 / 0 | 0 / 0 | 434 670 / 0 | 0 | **−113 670.000** | **−113 670.00** | 0.000 (113 670.000) | signed (client) vs floored (server) |
| L10 | odd unit `mts`, paired trade | mts | 163 077.02 | 0 / 0 | 0 / 0 | 0 / **163 077.02** | 0 / 0 | 163 077 | **0.000 → "Exhausted"** | 163 077.02 | 163 077.020 (0) | C1 subtracts paired sale; unit label doubtful |

The per-item `calculate_available_quantity` result equals the bulk `calculate_available_quantity_for_items`
result on all 10 samples.

---------------------------------------------------------------------------------------------------

## 7. Recommended canonical quantity (refines 08 §3; PROPOSAL, not approved)

The evidence supports **QA-1** and narrows it. The proposal is a single server value, with every client
reading it and none computing:

```
available_quantity_canonical(SR) =
    max( SR.quantity
         − Σ D RowDetails.qty  on non-hidden BOEs          (S5, exclude_hidden)
         − Σ outstanding AT AllotmentItems contributed_qty  (S2, engine)
         − Σ direct-sale contributed_qty                    (S7: unpaired, BOE-same-SR-aware, allocation-netted)
       , 0 )                                     Decimal, 3dp, no float, no integer floor
over_utilised_quantity = max(−unfloored, 0);  is_quantity_over_utilised = over_utilised_quantity > 0
unit = SR.unit   (grouping key = lower(btrim(unit)) only if owner picks OD-MAP-5 (b))
```

This is exactly `ItemBalanceCalculator.calculate_available_quantity_for_items`, so it re-derives nothing. The
evidence-driven refinements:

1. **Hidden-BOE exclusion is the governing rule (Q-1).** Any stored or cached quantity must use the engine's
   `exclude_hidden`. The stored writer `calculate_balance.py:41-45` disagrees on 253 SRs. Either stop showing
   S3/S4, or make the writer hidden-aware. That second option is a **BUSINESS-RULE CHANGE** to a cached value
   and the A1/A2 gate input, and it equals doc 05 O2 / OD-QTY-4.
2. **S7 replaces S8 in every availability formula (Q-2, OD-QTY-2).** This fixes 19 of the 30 C1 divergences.
   The other 11 are the floor (refinement 3). S8 can stay as a separate "billed without BOE (header-level)"
   diagnostic.
3. **Floor plus flag (OD-QTY-3).** 14 over-utilised SRs show signed negatives in C1/C2 today. Under QA-1 they
   show 0 with an over-use figure (L4 33 079.420, L9 113 670.000).
4. **No integer floor and no 2dp float (Q-10, OD-QTY-13).** The canonical value keeps 3dp. Before any column
   holds a 3dp availability, the 15,2 column drift (Q-7) must be resolved.
5. **Allotment quantity at line grain (QL-1).** `outstanding_qty = contributed_qty` and
   `represented_qty = qty − contributed_qty`. Totals use outstanding only, which turns C3's 2 841 560 into
   129 799. The 6 linked lines with no same-SR debit and the 5 cross-licence pairs need a flag (OD-MAP-2).
6. **Units:** never sum across distinct unit keys. On this data, case-folding removes every mix (§3), and
   `mts` needs owner confirmation before it appears in any total.
7. **Data defects stay out of the formula.** D-4 (duplicate C rows) and D-9 (possible missing BOE link) are data
   or reconciliation issues for owner review. The canonical formula must not special-case them.

### 7.1 Regression tests required (names, fixtures, assertions; not written)

The 08 §4 list stands. The tests below are **added or tightened** by this evidence. Each pins current
behaviour first; mark xfail only for the option the owner chooses.

| Test (proposed path::name) | Fixture | Assertions |
|---|---|---|
| `license/tests/test_quantity_parity.py::test_hidden_boe_debit_excluded_by_engine_counted_by_stored` | SR 12 335.89; D row 12 335 on a BOE with `invoice_no=OTH` + latest `HIDE_BOE` log (L8 shape) | S1 = 12 335.890; `boe_debited_quantity` = 0; stored `available_quantity` = 0; `debited_quantity` = 12 335; overview `balance_qty` = 0 (pins Q-1) |
| `::test_hidden_boe_restore_log_keeps_boe_visible` | same, plus a later `RESTORE_BOE` log | S1 = 0.890; S5 = 12 335 |
| `::test_paired_sale_whole_quantity_c1_inputs` | SR 163 077.02 `mts`; PURCHASE/SALE pair with `counterpart` set, no `trade.boes` (L10 shape) | S1 = 163 077.020; S7 = 0; `billed_no_boe_qty` = 163 077.02 (so C1 = 0) |
| `::test_paired_sale_plus_boe_debit_c1_negative_inputs` | L6 shape: Q 33 850.82, D 31 142, paired sale 33 850.82 | S1 = 2 708.820; `boe_debited_quantity` + `billed_no_boe_qty` > Q |
| `::test_unpaired_sale_with_equal_debit_on_same_sr_subtracts_both` | Q 20 000, D 15 898, unpaired SALE 15 898 with no `trade.boes` (D-9) | S1 = 0 (floored; unfloored −11 796) — pins Q-8 until the owner rules |
| `::test_stored_available_integer_floor_fractional_qty` | Q 66 859.78, no transactions (L1) | stored = 66 859; S1 = 66 859.780 |
| `::test_over_utilised_floor_and_over_use_value` | L9: Q 321 000, D 434 670 | S1 = 0; unfloored = −113 670 (computed in test); stored `available_quantity` = 0 |
| `::test_bulk_equals_per_item_available_quantity` | L1–L10 shapes in one licence | `calculate_available_quantity_for_items` == per-item for each |
| `license/tests/test_license_overview_allotments_view.py::test_linked_allotment_rows_included_in_quantity` | allotment of 3 774 M2M-linked to a BOE with a same-SR D row (L3) | row `status` = "Linked to BOE", `quantity` = 3 774; engine S2 = 0 |
| `::test_linked_allotment_without_same_sr_debit_still_zeroed` | M2M link; BOE rows on another SR only (M12 shape) | S2 = 0 for that line (pins 07 F15) |
| `license/tests/test_unit_grouping.py::test_case_variant_units_are_distinct_strings` | 2 SRs `kg` and `KG` on one licence | any per-unit grouping helper returns 2 keys under option (a) (pins OD-MAP-5 until decided) |
| `core/tests/test_ledger_import.py::test_reimport_duplicates_credit_rows` (08 §4, now MEASURED-backed) | same C row imported twice | C count = 2; `usable` doubled (xfail after owner ruling) |
| `core/tests/test_schema_scale.py::test_quantity_columns_match_model_scale` | introspect the **current** DB (`connection.introspection`) | `numeric_scale` for the Q-7 columns equals the model `decimal_places`. Under pytest the test DB is built from migrations and passes. Also run it as a read-only management check against restored DBs |
| Frontend `CustomsLedgerSection.test.tsx::"paired sale makes actual available 0 and Exhausted"` | L10 wire values | renders `0.000`, status "Exhausted" (pins current) |
| Frontend `LicenseBalanceModal.test.tsx::"balance uses stored debited incl hidden"` | L8 wire values | shows `0.89` |
| Frontend `AllotmentsTab.test.tsx::"total qty includes linked rows"` | 2 rows: linked 3 774 + pending 100 | footer Qty `3,874.00` |

Gates to run with any change: `license/tests/test_balance_*`, `test_sale_trade_quantity_consumption.py`,
`test_license_overview_*`, `reconciliation/tests/*`, `allotment/tests/test_*allocat*`, then
`scripts/dev/quality-gate.sh backend` and `frontend`.

---------------------------------------------------------------------------------------------------

## 8. Owner approvals needed (none granted here)

| # | Approval | Links |
|---|---|---|
| A-1 | The canonical item "Available Quantity" definition and field name (QA-1, refined in §7) | OD-QTY-1 |
| A-2 | Whether the stored `available_quantity`/`debited_quantity` writer becomes hidden-aware (**BUSINESS-RULE CHANGE**; A1/A2 gate input), or S3/S4 are simply no longer displayed | Q-1, doc 05 O2, OD-QTY-4 |
| A-3 | "Billed (No BOE)" qty: S7 or S8 in availability | Q-2, OD-QTY-2 |
| A-4 | Over-use display: floor + flag vs signed | Q-13, OD-QTY-3 |
| A-5 | Allotment line qty split and total (QL-1); treatment of the 6 no-same-SR and 5 cross-licence linked lines | Q-4, OD-QTY-5, OD-MAP-2 |
| A-6 | Unit equality rule: exact vs case-fold; confirm the true unit of the 2 `mts` SRs | Q-11, OD-MAP-5, OD-QTY-7 |
| A-7 | **Schema drift remediation** (15,2 vs 15,3; `exchange_rate` double vs decimal). This is a migration on historical data and needs the `migration-safety` review | Q-7 (new decision) |
| A-8 | **Data cleanup of 4 296 duplicate C rows** (irreversible data operation; boe-reconciliation review) | Q-5, 07 §7 |
| A-9 | Review of the 4 D-9 SALE lines (missing `trade.boes` link vs genuine second consumption) | Q-8 (new decision) |
| A-10 | Refresh of the stale stored caches (1 S3, 3 S4). A recompute is a data write | Q-9 |
| A-11 | Licence-detail performance: inject `billed_no_boe_qty_map` (removes per-item queries) only if S8 is kept | §1 (not a quantity change) |

## Not verified

- Production equality with the clone (all MEASURED values are clone-only).
- Whether S3 actually blocks allotments in production. The A1/A2 gating on S3 comes from doc 05 D2 and was not
  re-executed.
- The physical meaning of the D-9 lines and the `mts` SRs.
- No test or gate was run in this session (measurement only; no code changed).

## 9. Owner decisions recorded (2026-11-17)

- **A-1 APPROVED, as "engine as-is".** The canonical item Available Quantity is exactly
  `ItemBalanceCalculator.calculate_available_quantity_for_items`: S7 direct-sale netting, floored at 0,
  Decimal at 3dp. It is exposed additively as server fields (`available_quantity_canonical`,
  `over_utilised_quantity`, `is_quantity_over_utilised`). Client formulas C1 (CustomsLedgerSection) and
  C2 (LicenseBalanceModal) read those fields instead of computing. A-3 and A-4 alternatives are NOT adopted;
  they remain open only if the owner wants to deviate from the engine.
- **A-2: NOT APPROVED (owner, 2026-11-17; supersedes every earlier note here).** Option (i), the hidden-aware
  stored writer, is paused. Its uncommitted hunk in `calculate_balance.py:50-70` and the 5 tests in
  `test_stored_available_quantity_hidden.py` are preserved for review, not committed, and skipped. Reconsideration
  requires a cif-balance-auditor review (done: ESCALATE-TO-OWNER; 253 items / 94 licences would change on recompute and
  enter allotment candidate lists), documented before/after evidence, reconciliation of the conflicting rules, and a
  separate explicit owner approval. History: chosen, then paused, then reaffirmed in this thread, then superseded.
  Option (i), a BUSINESS-RULE CHANGE: The stored
  `debited_quantity` / `available_quantity` writer (`core/scripts/calculate_balance.py`) excludes hidden BOEs
  exactly as the engine does, using Decimal arithmetic. Allotment gating (`views_actions.py:315,644`,
  `filter_service.py:30`) then uses the corrected value.
  Scope limits:
  - **quantity only**; the CIF fields `debited_value` / `available_value` are unchanged (CIF needs separate approval);
  - **no bulk refresh**: stored rows update only through their existing recompute signals (A-10 not approved);
  - **no data correction**, and no change to rounding or the integer floor (Q-10) or the column scale (A-7).
- Still unapproved: A-3 … A-11 (except as implied by A-1 above).
