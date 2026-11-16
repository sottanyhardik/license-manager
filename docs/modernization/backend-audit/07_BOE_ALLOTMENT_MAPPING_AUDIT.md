# Backend Audit 07: BOE / Allotment / Product / Supplier mapping

Status: **read-only audit, 2026-11-16, feature/v5 working tree.** No code, test, migration or other doc was
changed. No database was queried. Paths are relative to `backend/apps/` unless they start with `frontend/`.
Evidence is `file:line` from reads made in this session. Line numbers can drift because the tree has
uncommitted edits by other tasks.

Purpose: provide the code evidence behind `DECISION_REGISTER.md` OD-BA-a (supplier source), OD-BA-b (supplier
normalisation) and OD-BA-c (product key). It also lists every failure mode that grouping
Supplier → Product → record could hit.

What is approved and what is not:
- **Approved:** only `frontend-audit/06` §7.1 and `DECISION_REGISTER.md` "Approved" D4 grouping.
- **PROPOSED, not approved:** the target design in doc 06 §7.4 (line grain, `classification`, linked-allotment
  exclusion from totals = OD-BA-e).
- **Not approved:** quantity semantics, covered in `08`.

Approved constraints this audit checks against:
- Every source record is preserved.
- Different suppliers are never grouped together.
- Quantities in incompatible units are never aggregated.
- Canonical CIF is unchanged, with no double counting of invoices or allotments that a BOE represents.

---------------------------------------------------------------------------------------------------

## 1. Entity map (as built)

```
CompanyModel (iec UNIQUE, name non-unique)            ItemNameModel (name UNIQUE, normalized_name)
   ^ company (null)        ^ company (NOT null)             ^  M2M  "items"
   |                       |   ^ related_company (null)     |
BillOfEntryModel --M2M "allotment"--> AllotmentModel        |
   | 1                                   | 1                |
   | * item_details                      | * allotment_details
RowDetails --sr_number (NOT null)--> LicenseImportItemsModel <--item (null)-- AllotmentItems
   |  (C/D rows)                         (unit lives HERE only)                 |
   | 1                                                                          | 1
   | *  BOEAllotmentAllocation (row_details ↔ allotment_item; PROTECT; ledger)  *
   | *  InvoiceBOEAllocation (row_details ↔ LicenseTradeLine; PROTECT; ledger)
   | *  ExternalInvoiceLink (row_details + free-text invoice no.)
LicenseTrade --M2M "boes"--> BillOfEntryModel            LicenseTradeLine --sr_number (NOT null)--> import item
```

### 1.1 Relationship table

| # | Relationship | Field / evidence | Cardinality | Nullability | Main readers |
|---|---|---|---|---|---|
| R-1 | BOE → supplier | `BillOfEntryModel.company` FK `CompanyModel` (`bill_of_entry/models.py:188-194`) | N:1 | **nullable** (`null=True, blank=True`) | `license_overview_boes.py:110` (`supplier`), BOE serializers, exports |
| R-2 | BOE → lines | `RowDetails.bill_of_entry` FK, `related_name="item_details"` (`bill_of_entry/models.py:380-386`) | 1:N | **nullable** FK on the line (orphan lines possible) | `license_overview_boes.py:56-87` (groups by `bill_of_entry_id`, drops `None` at :90), `BillOfEntryModel.get_total_*` (:282-301) |
| R-3 | BOE line → licence import item (SR) | `RowDetails.sr_number` FK `LicenseImportItemsModel`, CASCADE (`:388-392`) | N:1 | **not null** | engine debit rows, `calculate_available_quantity` (`license/services/balance_calculator.py:1990-1998`), overview selectors |
| R-4 | BOE line identity | `unique_together = (bill_of_entry, sr_number, transaction_type)` (`:428`); `transaction_type` ∈ {C, D}, default D (`:393`, `core/constants.py:11-18`) | ≤ 2 rows per (BOE, SR): one CREDIT + one DEBIT | n/a | engine filters `transaction_type=DEBIT` (`balance_calculator.py:551`, `:1994`); **`license_overview_boes.py:58` does not** |
| R-5 | BOE header product | `BillOfEntryModel.product_name` free text (`:210`), generated as `' or '`-joined canonical names of all lines (`generate_product_name_from_items`, `:333-375`); `planning_target_item` FK `ItemNameModel` (`:185`) + `planning_mapping_status` default `UNMAPPED_AMBIGUOUS` (`:186`) | header-level, 1 value per BOE | `product_name` default `""`; `planning_target_item` nullable | planning; not used by overview selectors |
| R-6 | BOE ↔ allotment (coarse link) | `BillOfEntryModel.allotment` M2M (`:211-215`), written by `bill_of_entry/api/serializers.py:315, :350` (`.set`), `bill_of_entry/services/boe_service.py:292` (merge `.add`); cache flag `AllotmentModel.is_boe` (`allotment/models/core.py:110`) set at `serializers.py:319, :358, :369` | M:N, **header to header** (no SR / line / licence check) | optional | engine `Exists()` (`balance_calculator.py:798-800`), `license_overview_allotments.py:64-68`, summary (`license_overview_summary.py:89+`) |
| R-7 | Allotment → supplier/customer | `AllotmentModel.company` FK (`allotment/models/core.py:49-53`) | N:1 | **not null** (PROTECT) | `license_overview_allotments.py:76` (`customer`), `AllotmentsTab.tsx:82` header "Customer" |
| R-8 | Allotment → related party | `AllotmentModel.related_company` FK (`:104-109`) | N:1 | nullable | allotment forms/PDFs; not used by overview |
| R-9 | Allotment header product | `AllotmentModel.item_name` CharField, required, no FK (`:91`); `planning_target_item` FK `ItemNameModel` nullable (`:46`) | 1 per allotment | `item_name` not null (may be any text) | `license_overview_allotments.py:77` (`product`) |
| R-10 | Allotment → lines | `AllotmentItems.allotment` FK, CASCADE (`:220-227`) | 1:N | **nullable** | `license_overview_allotments.py:37-47` (drops `None` at :46), `AllotmentModel.balanced_quantity / alloted_quantity / allotted_value` (`:172-208`) |
| R-11 | Allotment line → SR | `AllotmentItems.item` FK `LicenseImportItemsModel`, CASCADE (`:212-219`) | N:1 | **nullable** | engine R1/R2 (`balance_calculator.py:845-893, :895-925`), overview (`item__license=` filter excludes null items) |
| R-12 | Allotment line identity | `UniqueConstraint(item, allotment, allocation_basis, planning_target_item)` when target set; `(item, allotment, allocation_basis)` when target null (`:335-347`) | per (allotment, SR): **1 ACTUAL row + 1 PLAN row per planning target** | n/a | A1 merge logic (doc 05 D8) |
| R-13 | Allotment type | `AllotmentModel.type` ∈ {`AR` ARO, `AT` Allotment} (`:54`, `core/constants.py:22-28`) | — | default AT | R2 filters `type='AT'` (`balance_calculator.py:919, :958`); stored writer filters literal `'ARO'` (`core/scripts/calculate_balance.py:56-57`), which never matches (doc 05 D3) |
| R-14 | SR → canonical product | `LicenseImportItemsModel.items` M2M `ItemNameModel` (`license/models/items.py:90`) | **M:N** (one SR may carry 0..n names) | blank allowed (0 names) | `get_items_detail` (`license/api/serializers/license.py:232-266`), `CustomsLedgerSection.tsx:13` (joins names with ", ") |
| R-15 | SR unit | `LicenseImportItemsModel.unit` CharField `choices=UNIT_CHOICES` {kg, pcs, nos, mts}, default `kg` (`license/models/items.py:95`, `core/constants.py:33-43`) | 1 per SR | not null; **choices are not DB-enforced** (test writes `"MT"`: `license/tests/test_plan_grouping.py:109`) | serializer `unit`; `plan_utilization.py:270-274` (only unit-aware aggregation) |
| R-16 | Ledger link BOE line ↔ allotment line | `BOEAllotmentAllocation(row_details, allotment_item)` PROTECT both (`reconciliation/models.py:369-378`); qty 4dp, CIF 3dp | M:N via rows; app-level "one active current pair" (`reconciliation/services/allocation_service.py:474-484`) | n/a | engine `_annotate_allotment_contribution` (`balance_calculator.py:711-842`), `license_overview_boes.py:44-78` |
| R-17 | Ledger link BOE line ↔ invoice line | `InvoiceBOEAllocation(trade_line, row_details)` (`reconciliation/models.py:263-272`) | M:N via rows | n/a | engine `calculate_debit` (`:459-509`), `_direct_sale_quantity_rows` (`:1882-1891`) |
| R-18 | External invoice mark | `ExternalInvoiceLink(row_details, invoice_number text)` (`reconciliation/models.py:468-472`) | N per row | n/a | `remaining_for_row_details_invoice_side` only; **never feeds the engine** (model docstring) |
| R-19 | Trade ↔ BOE (coarse) | `LicenseTrade.boes` M2M (`trade/models.py:183-187`) | M:N header to header | optional | `billed_no_boe*` filters `trade__boes__isnull=True` (`license/api/serializers/license.py:376, :411`; `license/services/item_usage.py:188, :230`); engine direct-sale `Exists()` requires a DEBIT row **on the same SR** (`balance_calculator.py:1898-1902`) |
| R-20 | Trade line → SR | `LicenseTradeLine.sr_number` FK PROTECT, not null (`trade/models.py:525-529`); quantity field is named `qty_kg` (`:536`) whatever the SR unit | N:1 | not null | engine, billed maps, trade serializers |
| R-21 | Trade ↔ allotment | **none** (no FK/M2M in `trade/models.py`). `AllotmentModel.invoice` is free text (`allotment/models/core.py:94`) | — | — | — |
| R-22 | Supplier identity | `CompanyModel.iec` `unique=True` (`core/models.py:227`); `name` `blank=True, default=''`, not unique (`:245`). No `normalized_name` (contrast `ItemNameModel.normalize_name`, `:399-402`) | — | name may be empty | all `company.name` readers |

### 1.2 What the current overview selectors actually group

| Selector | Grain | Supplier | Product | Quantity | Caveats found |
|---|---|---|---|---|---|
| `license/services/license_overview_boes.py:41-116` | 1 row per BOE (`values("bill_of_entry_id")`, :79) | `boe.company.name` or `None` (:110) | none | `qty` summed at :82, **not returned** | **LATENT / LOW.** There is no `transaction_type` filter at :58, so C and D rows would be summed, unlike the engine (`balance_calculator.py:551`). Today no writer attaches a C row to a BOE (see note below), so only historical data can trigger it (measure with §5 M8). |
| `license/services/license_overview_allotments.py:36-83` | 1 row per allotment (this licence's share, :38) | `allotment.company.name` (:76) | `allotment.item_name` free text (:77) | `Sum(qty)` over **all** `AllotmentItems` of this licence: AT and AR, ACTUAL and PLAN, linked and unlinked, every SR and unit (:37-44) | **HIGH for user-visible numbers.** Not netted by `BOEAllotmentAllocation`; linked state is only a status label (:98-99). The client "Total Allotted" (`AllotmentsTab.tsx:71-72, :126-130`) routinely includes linked-allotment CIF that `BoesTab` already shows, and it disagrees with the engine's ALLOTMENT CIF (`calculate_allotment`). |

Why the C+D sum in the BOEs selector is latent today:
- `RowDetailsSerializer` exposes no `transaction_type` field (`bill_of_entry/api/serializers.py:111-128`).
- The model default is D (`bill_of_entry/models.py:393`), and `serializers.py:391` defaults to D.
- The ledger import writes C rows with `bill_of_entry=None` (`core/scripts/ledger.py:277-278`). The selector
  drops those at `license_overview_boes.py:90`.

Correction to `frontend-audit/06` §7.2 ("BOE rows have no product at all"): **lines** have no product of their
own, but the BOE **header** carries `product_name` (generated text) and `planning_target_item` (R-5). Neither
works as a line-level grouping key: a BOE spanning several SRs gets one joined string such as `"A or B"`.

---------------------------------------------------------------------------------------------------

## 2. How an allotment becomes "represented by" a BOE

Three mechanisms exist. They are **not** equivalent.

| Mechanism | Grain | Effect on ALLOTMENT CIF (engine R1) | Effect on outstanding allotment qty (R2) | Effect on reconciliation remaining (R5) | Production writer |
|---|---|---|---|---|---|
| M2M `BillOfEntryModel.allotment` | header ↔ header | `contributed = 0` for **every** `AllotmentItems` row of that allotment, on every SR and licence (`balance_calculator.py:798-800, :824-831`) | `contributed_qty = 0` (`:834-841`) | none: `remaining_for_allotment_item` ignores the M2M (`reconciliation/services/allocation_service.py:173-198`, doc 05 D5) | BOE form (`bill_of_entry/api/serializers.py:315, :350`), BOE merge (`boe_service.py:292`), `seed_browser_2509` |
| `BOEAllotmentAllocation` | line ↔ line | `cif_fc − min(cif_fc, Σ allocated_cif_fc)` (`:818-831`) | `qty − min(qty, Σ allocated_qty)` (`:812-841`) | subtracted | **none in production** (doc 05 §1(e): only tests call `create_boe_allotment_allocation`) |
| `AllotmentModel.is_boe` flag | header | none (engine deliberately ignores it, docstring `:733-745`) | none | none | same serializer; stale at scale (selector comment `license_overview_allotments.py:56-62`) |

Gaps relevant to grouping:
- **M2M has no SR match.** Allotment X has items on SR 3 and SR 5. BOE B lists X and has rows only on SR 3. X's
  SR 5 line is still zeroed (header-level `Exists`), although no BOE line on SR 5 represents it. Shown per
  product, SR 5's "linked allotment" has no matching BOE line under the same product.
- **M2M has no licence match.** Nothing stops a BOE of licence L1 being linked to an allotment whose items are on
  licence L2. L2's ALLOTMENT CIF then drops with no L2 BOE debit (R1 uses the real M2M).
- **Ledger link checks licence, not SR.** `create_boe_allotment_allocation` rejects cross-licence pairs
  (`allocation_service.py:461-468`) but allows RowDetails on SR 3 to be matched with an AllotmentItems on SR 5
  of the same licence. Their quantities may be in different units (R-15).
  - The only auto-matcher, `reconciliation/services/boe_link_reconciler.py:59-62`, is **invoice ↔ BOE only** and
    filters on the same SR.
  - The manual invoice service checks licence only (`allocation_service.py:248-254`).
  - **No allotment ↔ BOE auto-matcher exists.**
- **M2M update cannot clear.** `update` only sets the M2M when the list is non-empty
  (`bill_of_entry/api/serializers.py:345`), so the last link cannot be removed through this path (observation;
  not verified in UI).

Invoices: the trade side has the same two-level structure. A coarse `LicenseTrade.boes` (R-19) sits beside a
fine `InvoiceBOEAllocation` (R-17), and the quantity readers disagree on which one counts (see `08` §2).
Trades never link to allotments (R-21).

---------------------------------------------------------------------------------------------------

## 3. Units

- **Transaction lines carry no unit.** `RowDetails`, `AllotmentItems`, `AllotmentModel` (incl.
  `required_quantity`, `:55`), `BOEAllotmentAllocation`, `InvoiceBOEAllocation` and `LicenseTradeLine` have no
  unit field. `LicenseTradeLine.qty_kg` is named kg whatever the SR unit.
- For transaction quantities, the effective unit is `LicenseImportItemsModel.unit` (R-15).
- Other models also have a `unit`, but none of them is attached to a transaction line:
  - export item `license/models/items.py:55`
  - core masters `core/models.py:425, :478, :506`
  - planning `license/models/planning.py:253, :595`
- **Within one SR the unit cannot differ between lines**: every line inherits the SR's single unit. Changing
  `unit` on an SR silently re-labels every historical line (no unit history).
- **Across SRs it can differ**:
  - A BOE (R-2/R-3), an allotment (R-10/R-11) or a canonical product (R-14) can span SRs with different units.
  - `UNIT_CHOICES` is not enforced in the DB (`"MT"` in `test_plan_grouping.py:109`).
  - Casing and synonyms (`kg` vs `KGS`) are possible from parsers (`license/parsers/dfia_pdf.py:787-802`
    captures a raw UOM; whether it is mapped before save was not traced: **not verified**).
- **Conversion code: none for transactions.**
  - `plan_utilization.py:270-274` sets `unit_conversion = 1` for a single-unit group, `None` otherwise, and
    blocks mixed groups (`STATUS_BLOCKED_UNIT_MISMATCH`, :247-249).
  - `plan_group_key` keeps units apart (`test_plan_grouping_never_compares_different_units`).
  - `SionPlanningMapping.conversion_factor` (`license/models/planning.py:587`) is stored and serialized only
    (`license/services/sion_planning_profile.py:63`). It is never used in arithmetic.
- Unit-blind sums found:
  - `BillOfEntryModel.get_total_quantity` (`bill_of_entry/models.py:296-301`, all rows, all SRs, C+D) and
    `get_unit_price` (:311-320), served as `total_quantity`/`unit_price` (`bill_of_entry/api/serializers.py:153-165`)
    and in `reconciliation/selectors.py:161`.
  - `AllotmentModel.balanced_quantity/alloted_quantity` (`allotment/models/core.py:172-196`).
  - `license_overview_allotments.py:42`.
  - `item_pivot_item_summary.py:56-99` (buckets by `(canonical_item_id, sion)` with no unit).
  - Client totals (`08` §1.2).

---------------------------------------------------------------------------------------------------

## 4. Failure modes for Supplier → Product → record grouping

Grain assumed (doc 06 §7.4): BOE line = `RowDetails` per (`bill_of_entry_id`, `sr_number_id`); allotment
line = `AllotmentItems` row.

| ID | Failure mode | Where it arises | Consequence if ignored | Safe handling (proposal only) |
|---|---|---|---|---|
| F1 | **Null BOE supplier** | R-1 nullable | `company_id IS NULL` would merge with another bucket or be dropped by an inner join | Explicit "No supplier recorded" L1 bucket keyed `null`; LEFT JOIN |
| F2 | **Empty or duplicate supplier names** | R-22: name blank allowed, not unique | Grouping by name merges distinct IECs (forbidden), and blank names collapse together | Group by `company_id` only (OD-BA-b (a)); display `name or iec` |
| F3 | **Allotment party semantics** | R-7 labelled "Customer" in UI; R-8 `related_company` optional | The same `company_id` can be a BOE supplier and an allotment customer, so one L1 group holds both roles | Keep `record_type` + role on every row; OD-BA-a |
| F4 | **Unmapped SR** (0 canonical names) | R-14 `blank=True` | No L2 key if grouped by name | L2 key = SR id; label falls back to `description`, then "Unmapped product" (as `CustomsLedgerSection.tsx:13`) |
| F5 | **SR with several canonical names** | R-14 M:N | A JOIN on `items` multiplies each line once per name, so CIF/qty is counted 2..n times | Never join the M2M into the aggregate; L2 key = SR; names fetched separately for display |
| F6 | **Same canonical name on several SRs** (same or other licence) | R-14 reverse side | Grouping by name merges SRs that may differ in unit (F7) | L2 = SR; an optional "same product" super-label is display only |
| F7 | **Mixed units** | §3 | Adding kg to pcs | Per-unit subtotals only; flag `mixed_units` and omit the single qty total |
| F8 | **BOE spanning several SRs** | R-2/R-3 | A BOE-level CIF repeated under each product double counts | Line grain; each product gets only its own line CIF; supplier total = Σ distinct lines; record count = distinct BOE ids |
| F9 | **BOE with both CREDIT and DEBIT rows on one SR** (LATENT/LOW: only historical data, see §1.2 note) | R-4 | `license_overview_boes.py` would add C to D (sign-blind). Engine BOE CIF counts D only | Filter `transaction_type=D` for BOE CIF; show C rows separately or exclude (owner decision OD-MAP-1) |
| F10 | **BOE spanning licences** | R-3 per line | `get_total_quantity/fc` mixes licences | Licence-scoped endpoint filters lines by `sr_number__license` (as today) |
| F11 | **Allotment spanning SRs** | R-10/R-11 | `item_name` is one header string for several SRs, and `balanced_quantity` mixes units | One allotment line per `AllotmentItems`; the same allotment appears under each SR with its own qty/CIF; count distinct allotment ids |
| F12 | **Several AllotmentItems per (allotment, SR)** | R-12 (ACTUAL + PLAN rows) | Two rows for one allotment under one product; summing both may double count if D8 (doc 05) merged them wrongly | Keep both rows with `allocation_basis`; no merge |
| F13 | **Orphan lines** | R-2 / R-10 / R-11 nullable | `AllotmentItems.item IS NULL` never appears on a licence; `allotment IS NULL` and `bill_of_entry IS NULL` rows are dropped by both selectors (:46, :90) | Report counts (§5); not shown in a licence workspace |
| F14 | **Linked allotments** (M2M) | §2 | Showing linked allotment CIF in totals double counts it against the BOE line (approved CIF rule) | PROPOSED (not approved; OD-BA-e): `classification=LINKED_ALLOTMENT`, shown and excluded from totals (doc 06 §7.4) |
| F15 | **Linked allotment whose SRs differ from the BOE's SRs** | §2 gap 1 | Under product SR 5 the allotment is "linked" but no BOE line on SR 5 exists, so the user sees CIF disappear from SR 5 | Surface `linked_boe_numbers` + flag `link_sr_mismatch` (display only) |
| F16 | **Allotment linked to several BOEs** | R-6 M:N | A per-BOE JOIN fans out | `Exists()` / `ARRAY_AGG(DISTINCT)` only, never a JOIN in the sum (engine already does this, `balance_calculator.py:790-797` comment) |
| F17 | **Partial ledger allocation** | R-16 | Classification is not binary: part outstanding, part linked | Split by engine annotation `contributed` / `contributed_qty` (`:818-841`); never re-derive |
| F18 | **Cross-SR ledger allocation** | §2 gap 3 | Allotment on SR 5 netted by a BOE line on SR 3 (possibly another unit) | Flag; do not "fix" (owner decision OD-MAP-3) |
| F19 | **Cross-licence M2M** | §2 gap 2 | Allotment CIF on L2 zeroed by an L1 BOE | Flag in measurement; owner decision OD-MAP-2 |
| F20 | **AR-type allotments** | R-13 | Counted in licence ALLOTMENT CIF (R1, no type filter) but not in qty (R2 AT-only; `'ARO'` literal) | Expose `allotment_type`; no total change (doc 05 O3) |
| F21 | **Hidden (previous-owner) BOEs** | `annotate_and_exclude_hidden` (`bill_of_entry/models.py:57+`) | Must be excluded identically to `overview-boes/` | Reuse the same helper |
| F22 | **Header product fields disagree with lines** | R-5/R-9 | `product_name` "A or B", and free-text `item_name` unrelated to the SR's canonical name | Secondary label only (OD-BA-c) |

---------------------------------------------------------------------------------------------------

## 5. Measurements pending owner approval (NOT RUN)

DB access was not authorised for this audit. The statements below are **read-only** counts. They are meant to
run against a local dev/test copy (re-synced DBs change; see memory "Local DB gets re-synced"). Table names are
Django defaults (no `db_table` overrides found in the six model modules). Confirm with `\dt` before running.
None of these is a write. Run each inside `BEGIN READ ONLY; … ROLLBACK;`.

Every count also needs a licence-scoped variant: add `JOIN license_licenseimportitemsmodel ii ON ii.id = <sr col>`
and `WHERE ii.license_id = :id`.

```sql
-- M1 (F1) BOEs with no supplier, total and with ≥1 line
SELECT count(*) FILTER (WHERE b.company_id IS NULL) AS no_supplier, count(*) AS total
FROM bill_of_entry_billofentrymodel b
WHERE EXISTS (SELECT 1 FROM bill_of_entry_rowdetails r WHERE r.bill_of_entry_id = b.id);

-- M2 (F2) companies sharing a normalised name (distinct IECs) and blank names
SELECT upper(regexp_replace(btrim(name), '\s+', ' ', 'g')) AS k, count(*) AS n, array_agg(iec ORDER BY iec) AS iecs
FROM core_companymodel GROUP BY 1 HAVING count(*) > 1 ORDER BY n DESC;
SELECT count(*) FROM core_companymodel WHERE btrim(coalesce(name, '')) = '';

-- M3 (F3) allotments with related_company set / different from company; companies used in both roles
SELECT count(*) FILTER (WHERE related_company_id IS NOT NULL) AS with_related,
       count(*) FILTER (WHERE related_company_id IS NOT NULL AND related_company_id <> company_id) AS related_differs,
       count(*) AS total
FROM allotment_allotmentmodel;
SELECT count(DISTINCT a.company_id) FROM allotment_allotmentmodel a
WHERE EXISTS (SELECT 1 FROM bill_of_entry_billofentrymodel b WHERE b.company_id = a.company_id);

-- M4 (F4/F5) SRs by number of canonical names, restricted to SRs that carry transactions
WITH n AS (
  SELECT ii.id, count(m.itemnamemodel_id) AS names
  FROM license_licenseimportitemsmodel ii
  LEFT JOIN license_licenseimportitemsmodel_items m ON m.licenseimportitemsmodel_id = ii.id
  GROUP BY ii.id)
SELECT names, count(*) AS srs,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM bill_of_entry_rowdetails r WHERE r.sr_number_id = n.id)
                         OR EXISTS (SELECT 1 FROM allotment_allotmentitems ai WHERE ai.item_id = n.id)) AS srs_with_txn
FROM n GROUP BY names ORDER BY names;

-- M5 (F6/F7) canonical names whose SRs use more than one unit
SELECT m.itemnamemodel_id, array_agg(DISTINCT ii.unit) AS units
FROM license_licenseimportitemsmodel_items m JOIN license_licenseimportitemsmodel ii ON ii.id = m.licenseimportitemsmodel_id
GROUP BY 1 HAVING count(DISTINCT ii.unit) > 1;

-- M6 (F7) unit values in use, including values outside UNIT_CHOICES
SELECT unit, count(*) FROM license_licenseimportitemsmodel GROUP BY unit ORDER BY count(*) DESC;

-- M7 (F8/F10/F7) BOEs spanning SRs / licences / units
SELECT count(*) FILTER (WHERE srs > 1) AS multi_sr, count(*) FILTER (WHERE lics > 1) AS multi_licence,
       count(*) FILTER (WHERE units > 1) AS multi_unit, count(*) AS boes
FROM (SELECT r.bill_of_entry_id, count(DISTINCT r.sr_number_id) srs, count(DISTINCT ii.license_id) lics,
             count(DISTINCT ii.unit) units
      FROM bill_of_entry_rowdetails r JOIN license_licenseimportitemsmodel ii ON ii.id = r.sr_number_id
      WHERE r.bill_of_entry_id IS NOT NULL GROUP BY 1) s;

-- M8 (F9) CREDIT rows, and BOEs with both C and D on the same SR
SELECT transaction_type, count(*), sum(qty), sum(cif_fc) FROM bill_of_entry_rowdetails GROUP BY 1;
SELECT count(*) FROM (SELECT bill_of_entry_id, sr_number_id FROM bill_of_entry_rowdetails
                      GROUP BY 1, 2 HAVING count(DISTINCT transaction_type) > 1) s;

-- M9 (F11/F12/F7) allotments spanning SRs / licences / units; several rows per (allotment, SR)
SELECT count(*) FILTER (WHERE srs > 1) multi_sr, count(*) FILTER (WHERE lics > 1) multi_licence,
       count(*) FILTER (WHERE units > 1) multi_unit, count(*) allotments
FROM (SELECT ai.allotment_id, count(DISTINCT ai.item_id) srs, count(DISTINCT ii.license_id) lics, count(DISTINCT ii.unit) units
      FROM allotment_allotmentitems ai JOIN license_licenseimportitemsmodel ii ON ii.id = ai.item_id
      WHERE ai.allotment_id IS NOT NULL GROUP BY 1) s;
SELECT allocation_basis, count(*) FROM (SELECT allotment_id, item_id, allocation_basis, count(*) c
  FROM allotment_allotmentitems GROUP BY 1, 2, 3) s WHERE c > 1 GROUP BY 1;     -- PLAN rows with several targets
SELECT count(*) FROM (SELECT allotment_id, item_id FROM allotment_allotmentitems
  GROUP BY 1, 2 HAVING count(DISTINCT allocation_basis) > 1) s;                 -- ACTUAL + PLAN on same SR

-- M10 (F13) orphan lines
SELECT (SELECT count(*) FROM allotment_allotmentitems WHERE item_id IS NULL) AS ai_no_item,
       (SELECT count(*) FROM allotment_allotmentitems WHERE allotment_id IS NULL) AS ai_no_allotment,
       (SELECT count(*) FROM bill_of_entry_rowdetails WHERE bill_of_entry_id IS NULL) AS rd_no_boe;

-- M11 (F14/F16) linked allotments, multi-BOE links, stale is_boe
SELECT count(DISTINCT allotmentmodel_id) AS linked_allotments,
       count(*) AS links FROM bill_of_entry_billofentrymodel_allotment;
SELECT count(*) FROM (SELECT allotmentmodel_id FROM bill_of_entry_billofentrymodel_allotment
                      GROUP BY 1 HAVING count(*) > 1) s;
SELECT count(*) FILTER (WHERE linked AND NOT is_boe) stale_false, count(*) FILTER (WHERE NOT linked AND is_boe) stale_true
FROM (SELECT a.id, a.is_boe, EXISTS (SELECT 1 FROM bill_of_entry_billofentrymodel_allotment t
                                      WHERE t.allotmentmodel_id = a.id) linked FROM allotment_allotmentmodel a) s;

-- M12 (F15/F19) linked allotment lines with no DEBIT line of any linked BOE on the same SR; cross-licence links
SELECT count(*) FROM allotment_allotmentitems ai
WHERE EXISTS (SELECT 1 FROM bill_of_entry_billofentrymodel_allotment t WHERE t.allotmentmodel_id = ai.allotment_id)
  AND NOT EXISTS (SELECT 1 FROM bill_of_entry_billofentrymodel_allotment t
                  JOIN bill_of_entry_rowdetails r ON r.bill_of_entry_id = t.billofentrymodel_id
                  WHERE t.allotmentmodel_id = ai.allotment_id AND r.sr_number_id = ai.item_id AND r.transaction_type = 'D');
SELECT count(DISTINCT (t.billofentrymodel_id, t.allotmentmodel_id))
FROM bill_of_entry_billofentrymodel_allotment t
JOIN allotment_allotmentitems ai ON ai.allotment_id = t.allotmentmodel_id
JOIN license_licenseimportitemsmodel ia ON ia.id = ai.item_id
WHERE NOT EXISTS (SELECT 1 FROM bill_of_entry_rowdetails r JOIN license_licenseimportitemsmodel ib ON ib.id = r.sr_number_id
                  WHERE r.bill_of_entry_id = t.billofentrymodel_id AND ib.license_id = ia.license_id);

-- M13 (F17/F18) ledger allocations: volume and cross-SR pairs
SELECT status, is_current, count(*) FROM reconciliation_boeallotmentallocation GROUP BY 1, 2;
SELECT count(*) FROM reconciliation_boeallotmentallocation x
JOIN bill_of_entry_rowdetails r ON r.id = x.row_details_id JOIN allotment_allotmentitems ai ON ai.id = x.allotment_item_id
WHERE x.status = 'ACTIVE' AND x.is_current AND r.sr_number_id <> ai.item_id;
SELECT count(*) FROM reconciliation_invoiceboeallocation x
JOIN bill_of_entry_rowdetails r ON r.id = x.row_details_id JOIN trade_licensetradeline tl ON tl.id = x.trade_line_id
WHERE x.status = 'ACTIVE' AND x.is_current AND r.sr_number_id <> tl.sr_number_id;

-- M14 (F20) AR-type allotments carrying lines
SELECT a.type, count(DISTINCT a.id), count(ai.id), sum(ai.cif_fc)
FROM allotment_allotmentmodel a LEFT JOIN allotment_allotmentitems ai ON ai.allotment_id = a.id GROUP BY 1;
```

ORM equivalents for the two counts most likely to block the endpoint (same semantics, read-only):

```python
# M1
BillOfEntryModel.objects.filter(item_details__isnull=False).distinct().filter(company__isnull=True).count()
# M4 (SRs with != 1 canonical name that carry transactions)
from django.db.models import Count, Q, Exists, OuterRef
LicenseImportItemsModel.objects.annotate(n=Count("items", distinct=True)).filter(
    Q(Exists(RowDetails.objects.filter(sr_number=OuterRef("pk")))) |
    Q(Exists(AllotmentItems.objects.filter(item=OuterRef("pk"))))).values("n").annotate(c=Count("id"))
```

---------------------------------------------------------------------------------------------------

## 6. Owner decisions raised by this audit (not resolved)

These add to OD-BA-a/b/c/e in `DECISION_REGISTER.md`. IDs are new to avoid collisions.

| ID | Question | Why it matters | Options (recommendation marked) |
|---|---|---|---|
| OD-MAP-1 | How do BOE **CREDIT** rows (`transaction_type='C'`) appear in the grouped workspace? | `overview-boes/` would sum C+D (`license_overview_boes.py:58,81`), but engine BOE CIF uses D only (`balance_calculator.py:551`). LATENT/LOW: current writers never attach a C row to a BOE, so only historical data is affected (M8) | (a) BOE lines = D only; C rows listed as separate record type, excluded from totals **[RECOMMENDED: matches engine]**; (b) keep today's C+D sum (contradicts engine); (c) net C against D (no rule exists) |
| OD-MAP-2 | Is a BOE ↔ allotment M2M link across licences, or with no shared SR, valid? | Zeroes ALLOTMENT CIF with no matching BOE debit (F15/F19) | (a) keep and flag in the UI + measurement report **[RECOMMENDED: no behaviour change]**; (b) validate on write (API behaviour change); (c) make the engine SR-aware (BUSINESS-RULE CHANGE) |
| OD-MAP-3 | Should a manual `BOEAllotmentAllocation`/`InvoiceBOEAllocation` require the same SR on both sides? | Auto matcher requires it, manual service does not (§2) | (a) flag only **[RECOMMENDED until O6 in doc 05 is decided]**; (b) enforce same SR |
| OD-MAP-4 | Does the grouped workspace show AR-type allotments, and under which classification? | R1 counts them in CIF; R2 does not count their qty (F20, doc 05 O3) | (a) show with `allotment_type` badge, use the engine's classification **[RECOMMENDED]**; (b) hide |
| OD-MAP-5 | Unit hygiene: treat non-choice unit values (`MT`, case variants) as distinct units, or normalise for display grouping? | F7; "never aggregate incompatible units" needs a definition of "same unit" | (a) exact string match = same unit; anything else is a different unit **[RECOMMENDED: safest]**; (b) case-fold only; (c) owner-supplied synonym table (no conversion) |
| OD-MAP-6 | Show PLAN-basis `AllotmentItems` rows as their own records, or fold them into the allotment line? | F12; summing ACTUAL+PLAN of one allotment/SR | (a) separate rows with `allocation_basis` badge **[RECOMMENDED: preserves every record]**; (b) fold (needs rule) |

## 7. Incidental observations (not grouping blockers; no change made)

- **OWNER ESCALATION (out of scope here): duplicate CREDIT rows on ledger re-import.**
  - **Cause:** `core/scripts/ledger.py:308-311` finds existing rows with `transaction_type=DEBIT` and
    `bill_of_entry__in`. C rows have `bill_of_entry=None` (`:277-278`), so a re-import never matches them and
    bulk-creates them again.
  - **Effect:** `usable` / `opening_balance` are inflated (`license/models/items.py:353, :367`).
  - **Coverage:** untested. The only caller is `convert_license_table.py:39`.
  - **Next step:** needs owner/boe-reconciliation review before any fix (data cleanup would be a data operation).

- `bill_of_entry/api/serializers.py:302-308` comment says unique is (number, date, port) and calls
  `update_or_create(number, date, port)`. The model constraint is (number, date) (`bill_of_entry/models.py:234`),
  so the same number and date with a different port would raise IntegrityError rather than update. Not verified
  by test.
- `BillOfEntrySerializer.unit_price` is `decimal_places=2` (`bill_of_entry/api/serializers.py:160-165`) over a
  3dp HALF_UP model value (`models.py:316`).
- `frontend/src/pages/license-overview/types.ts:104` documents `balance_qty` as `total − debited − allotted`.
  The server now returns stored `available_quantity` (`license/services/license_overview_items.py:49`).

## Not verified

- Every count in §5 (not run). Whether production has any BOE-attached CREDIT rows, cross-licence M2M links or
  cross-SR ledger rows is unknown.
  - The comment at `license_overview_summary.py:69-78` ("over-counted by exactly 1") is **weak evidence** that
    C+D BOEs exist.
  - NULL-BOE credit rows forming one extra DISTINCT group explain the same symptom equally well.
- Parser unit normalisation path (§3).
- Tests run in this session (read-only, test DB only):
  `apps/license/tests/test_sale_trade_quantity_consumption.py`, `test_license_overview_{allotments,boes,items}_view.py`,
  `test_plan_grouping.py` and `test_balance_calculator.py` gave **92 passed**. No gate was run.
