# 06 — Business Rules

## Core Domain Invariants

These rules are enforced at the model/signal layer and must be preserved in any rebuild.

---

## BR-01: License Balance Materialisation

**Rule**: `LicenseDetailsModel.balance_cif` (stored in `LicenseBalance.balance_cif`) equals the sum of `available_quantity` across all linked `LicenseImportItemsModel` rows.

**Mechanism**: `post_save` signal on `LicenseImportItemsModel` recalculates and updates `LicenseBalance.balance_cif` synchronously.

**Implication**: Never read balance from a computed annotation — always read from the materialised `LicenseBalance` sub-table for performance-critical paths.

---

## BR-02: Import Item Balance = Available - Debited - Allotted

**Rule**: For each import item:
```
available_quantity = authorised_cif - debited_quantity - allotted_quantity
```

**Mechanism**:
- `RowDetails.post_save/delete` → updates `debited_quantity`
- `AllotmentItems.post_save/delete` → updates `allotted_quantity`

**Constraint**: No overshoot allowed — creating a BOE row or allotment item that would make `available_quantity < 0` should be blocked (enforced at serializer/view level).

---

## BR-03: License Expiry

**Rule**: A license is considered expired if `license_expiry_date < today`.

- DFIA validity: license_date + 1 year (auto-calculated on license creation)
- Incentive license validity: license_date + 2 years (auto-calculated)
- `is_expired` flag updated nightly by management command `update_license_expiry`
- Frontend shows warning badges on near-expiry licenses (< 30 days)

---

## BR-04: BOE Row Freezing

**Rule**: BOE rows created via ledger upload are `frozen=True` and **cannot be edited or deleted** through the normal API.

**Rationale**: Government-issued ledger data is authoritative; manual editing would break reconciliation.

**Exception**: `is_dispute=True` rows (where no matching import item was found during upload) may be manually linked to the correct item.

---

## BR-05: Allotment Type Constraints

**Rule**: Allotment type must be `AT` (allotment — pre-authorisation before BOE) or `TR` (transfer — actual license transfer to another entity).

- `AT`: reserves `required_quantity` on the import item (`allotted_quantity += required_quantity`)
- `TR`: also reserves but triggers transfer letter generation flow
- When a BOE is created from an allotment, `is_boe=True` is set on the allotment record

---

## BR-06: Unique License Number

**Rule**: `license_number` must be globally unique across the `LicenseDetailsModel` table. The API supports lookup by either `id` (integer PK) or `license_number` (string).

---

## BR-07: Trade Invoice Numbering

**Rule**: Invoice numbers are auto-generated per financial year with a company-derived prefix:

| Direction | Format | Example |
|---|---|---|
| PURCHASE | `P-PREFIX/YYYY-YY/NNNN` | `P-LM/2025-26/0024` |
| SALE | `PREFIX/YYYY-YY/NNNN` | `LM/2025-26/0001` |
| COMMISSION_PURCHASE | `COM-P-PREFIX/YYYY-YY/NNNN` | `COM-P-LM/2025-26/0001` |
| COMMISSION_SALE | `COM-PREFIX/YYYY-YY/NNNN` | `COM-LM/2025-26/0001` |

**Prefix derivation**: First 3 letters of company name if 1 word; first letter of each word if 2+ words (e.g., "Labdhi Mercantile" → "LM").

**Sequence**: Takes the maximum existing sequence number for the prefix+FY combination and adds 1 (skips gaps). Restarts at 0001 for each new financial year.

**Uniqueness constraints**:
- PURCHASE: `from_company` + `invoice_number` + `direction` must be unique (non-blank invoice_number)
- SALE: `to_company` + `invoice_number` + `direction` must be unique (non-blank invoice_number)

---

## BR-08: Trade Line Amount Calculation

**Rule**: Trade line amounts are computed based on the billing mode:

| Mode | Formula |
|---|---|
| `QTY` | `qty_kg × rate_inr_per_kg` |
| `CIF_INR` | `cif_inr × pct / 100` |
| `FOB_INR` | `fob_inr × pct / 100` |

For incentive lines:
```
amount_inr = license_value × rate_pct / 100
```

Computations happen in the frontend (live preview while filling the form) and are validated server-side before save.

---

## BR-09: Transfer Letter Generation

**Rule**: A transfer letter requires:
1. At least one party (company + template)
2. At least one license selected
3. Valid company with address lines (auto-filled from company master but can be overridden)

**CIF Editing Rule**: The system allows manual override of CIF values on the letter. The modified value affects the printed document only — it does NOT change the license balance or the BOE/allotment records.

---

## BR-10: Ledger Upload Conflict Resolution

**Rule**: When parsing a government ledger file:

1. Each row is matched to a `LicenseImportItemsModel` by `sr_number` (serial number)
2. If a match is found → create a `frozen=True` `RowDetails` row
3. If no match → create `RowDetails` with `is_dispute=True` for manual resolution
4. Duplicate rows (same sr_number + license + clearance date) are skipped to prevent double-entry

---

## BR-11: Balance Report PDF / Excel Structure

**Rule**: The license balance report includes:
- License header information
- Per-company utilisation table
- Export entitlement details
- CIF INR column (sourced from `RowDetails.cif_inr` for BOEs, `AllotmentItems.cif_inr` for allotments)
- Signature block

**Excel structure**: One sheet per license, with a cover sheet showing all licenses and total balances.

---

## BR-12: SION Norm Linkage

**Rule**: Each license may be linked to a SION (Standard Input/Output Norm) class. The SION class defines the authorised import items and their ratios. This linkage enables:
- Item Pivot Report (aggregated view across norms)
- Item Report (detailed per-item utilisation)
- Norm-class filtering in reports and allotment search

---

## BR-13: Master Data Sync

**Rule**: Master data is maintained on the canonical `license-manager` server only. Changes to masters (companies, ports, HS codes, SION norms, etc.) on follower servers are not synchronised back to the canonical server — sync is strictly one-directional.

**Sync mechanism**:
1. `audit_masters` command exports a JSON snapshot from the canonical server
2. `auto_import_masters` command on each follower imports the snapshot
3. Existing records (matched by unique business key) are updated when `--update-existing` flag is passed
4. New records are created; conflicts (duplicate keys) log a failure to `failed.csv`

---

## BR-14: Role Hierarchy

**Rule**: Superusers bypass all role checks. For non-superusers, access is controlled by Django Groups named with role codes. A user can belong to multiple groups.

**Write vs Read**: Manager roles grant write access; Viewer roles grant read-only access. Having a Manager role implies the corresponding Viewer access.

---

## BR-15: Idle Session Timeout

**Rule**: Users are automatically logged out after 30 minutes of inactivity (no mouse movement, keyboard input, clicks, or scroll events). The session is invalidated client-side; the refresh token is also blacklisted server-side if the browser is still connected.

---

## BR-16: OCR License Parsing

**Rule**: When a license PDF is uploaded via the Parse PDF feature:
1. OCR extracts text from the scanned image
2. Extracted fields: license_number, dates, file_number, exporter name, import items (serial numbers, descriptions, HS codes, CIF values)
3. Extracted data is returned as a suggested pre-fill — the user reviews and confirms before saving
4. Company names and port codes are fuzzy-matched against the company/port master

---

## BR-17: Paired Trade Auto-Creation

**Rule**: When `auto_create_paired=True` on a new trade:
- A mirror trade is created with the opposite direction (PURCHASE ↔ SALE)
- Both trades are linked via `linked_trade` FK
- Line items are duplicated
- Invoice numbers are independent (separate sequence)

---

## BR-17A: Trade Counterpart System

**Rule**: The counterpart system creates immutable, audited Sale↔Purchase pairs via `copy-to-purchase` / `copy-to-sale` API actions.

**Mechanism**:
- `counterpart` (OneToOneField, PROTECT) — reciprocal link between paired trades
- `transaction_pair_uuid` (UUIDField) — shared UUID identifying the pair
- `copied_from` / `copied_from_type` / `source_document_number` — provenance tracking
- `TradePairAudit` — append-only audit log of pair operations

**Constraint**: A trade with a `counterpart` **cannot be deleted alone**. The `prevent_single_counterpart_delete` signal raises `ValidationError`: "This trade has a linked counterpart. Use the audited pair-deletion workflow."

---

## BR-17B: Trade Deletion Rules

**Rule**: Deleting a trade removes the trade header, all child objects, and clears BOE invoice references.

**Delete Flow**:
1. User clicks delete button → confirmation dialog → `DELETE /api/trade/trades/:id/`
2. Backend validates permissions (`TRADE_MANAGER` role required)
3. Pre-delete signals fire:
   - `clear_boe_invoice_on_trade_delete`: clears `invoice_no`/`invoice_date` on linked BOEs
   - `prevent_single_counterpart_delete`: blocks if `counterpart_id` is set
4. Django CASCADE deletes: `LicenseTradeLine`, `IncentiveTradeLine`, `LicenseTradePayment`, `TradeInvoiceDocument`, `InvoiceDocumentAccessToken`, `InvoiceDocumentAuditEvent`
5. M2M relation `boes` is cleared

**Blocking Conditions**:
- Trade has a `counterpart` (paired Sale↔Purchase) — blocked by signal
- Trade referenced by `SaleClassificationDecision` — blocked by PROTECT FK
- Trade referenced by `TradePairAudit` — blocked by PROTECT FK

---

## BR-17C: Trade Force Delete (Manual Override)

**Rule**: When a trade must be deleted despite having protecting references (counterpart, audit records, classification decisions), the force delete process must be followed via Django shell or database operations. There is no API endpoint for force delete.

**Prerequisites**: Django superuser access or database admin access.

**Process**:
1. Clear the `counterpart` link on both trades in the pair by setting `counterpart = NULL`
2. Delete all `TradePairAudit` records where `source` or `counterpart` matches the trade
3. Delete all `SaleClassificationDecision` records where `trade` matches
4. Delete the trade using `trade.delete()` or `LicenseTrade.objects.filter(pk=id).delete()`

**Technical Notes**:
- Django's `QuerySet.delete()` bypasses `pre_delete` signals (`clear_boe_invoice_on_trade_delete`, `prevent_single_counterpart_delete`) but does NOT bypass `PROTECT` FK constraints
- The PROTECT FK constraints must be cleared before any delete method will succeed
- Child objects (lines, payments, documents) are still CASCADE-deleted

**Warning**: Force delete permanently destroys audit trail integrity. The `TradePairAudit` records and `SaleClassificationDecision` records are lost. Use only for:
- Data cleanup after development/testing
- Error recovery when a trade was created incorrectly
- Database maintenance operations

**Not allowed** for normal business operations — paired trades should use the audited pair-deletion workflow.

---

## BR-17D: Sale Quantity Validation (Direct Sale Without BOEs)

**Rule**: When creating a SALE trade without BOEs (direct sale bypass path), the total requested quantity per import item must not exceed the available quantity. This prevents over-selling imported goods beyond what the license allows.

**Trigger**: `direction == "SALE"` AND `boes` array is empty on trade creation.

**Available Quantity Formula**:
```
Available = total_quantity − BOE_debited − outstanding_allotted − direct_sale_quantity
```

Where:
- **total_quantity**: The import item's stored `quantity` field
- **BOE_debited**: Sum of DEBIT RowDetails quantities for this item (physical consumption via BOE linkage)
- **outstanding_allotted**: Allotment quantity not yet linked to a BOE (from `LicenseBalanceCalculator.get_outstanding_allotment_totals`)
- **direct_sale_quantity**: Quantity consumed by existing unpaired direct SALE lines (no counterpart, no linked_trade, no BOE linkage)

**Direct Sale Quantity Exclusions** (what does NOT count as consumption):
- SALE lines with a linked BOE — the BOE's RowDetails DEBIT already accounts for the physical quantity
- SALE lines with a counterpart (paired Sale↔Purchase) — net zero effect, the purchase restores the quantity
- SALE lines with a `linked_trade` — same net-zero logic for manually linked pairs
- Allocated portions via `InvoiceBOEAllocation` — only `qty_kg − allocated_qty` counts as direct consumption

**When BOEs ARE attached**: This validation is skipped — the BOE linkage itself serves as the physical quantity debit, and the BOE's RowDetails DEBIT rows track actual consumption.

**Concurrency Protection**: Uses `select_for_update()` row locks on import items during validation to prevent two concurrent direct sales from both over-consuming the same item.

**Error Message**: `"SALE quantity {requested} exceeds available quantity {available} for import item {item_id}."`

**Files**:
- `backend/apps/trade/serializers.py` — `LicenseTradeSerializer.create()` (validation logic)
- `backend/apps/license/services/balance_calculator.py` — `ItemBalanceCalculator.calculate_available_quantity()` (formula)
- `backend/apps/license/services/balance_calculator.py` — `ItemBalanceCalculator._direct_sale_quantity_rows()` (direct sale filter)

---

## BR-17E: Available Quantity Calculation — Multiple Paths

**Rule**: The system has **four different code paths** that compute "available quantity" for import items. They use **different formulas**, so the displayed balance in some UI views can differ from the amount the trade creation API actually accepts.

**Path 1 — Trade creation validation (authoritative)**:
```
Available = total_quantity − BOE_debited − outstanding_allotted − direct_sale_quantity
```
- **File**: `backend/apps/license/services/balance_calculator.py` — `ItemBalanceCalculator.calculate_available_quantity()`
- **Used by**: `LicenseTradeSerializer.create()` when validating direct SALE trades
- **Status**: ✓ Complete formula — this is the authoritative limit

**Path 2 — Stored field update**:
```
Available = quantity − debited − allotted − direct_sale_quantity
```
- **File**: `backend/apps/core/scripts/calculate_balance.py` — `calculate_available_quantity()`
- **Used by**: Model save signals, allotment/BOE completion callbacks that update `item.available_quantity`
- **Status**: ✓ Complete formula — matches Path 1

**Path 3 — Balance snapshot API**:
```
Available = total_quantity − debited_quantity − outstanding_qty
```
- **File**: `backend/apps/license/services/balance_snapshot.py` — `get_snapshot_bulk()` lines 202-203
- **Used by**: License list views, balance overview endpoints
- **Status**: ⚠️ **Missing `direct_sale_quantity`** — returns higher value than Path 1 when direct sales exist

**Path 4 — Frontend Customs Ledger display**:
```
Actual Available = quantity − boe_debited_quantity − allotted_quantity − billed_no_boe
```
- **File**: `frontend/src/pages/license-overview/CustomsLedgerSection.tsx` line 12
- **Used by**: License overview page's "Customs Ledger — Item Detail" card view
- **Status**: ⚠️ **Missing `direct_sale_quantity`** — includes `billed_no_boe` (CIF from SALE trades with no BOE attached) but still omits `direct_sale_quantity`

**Impact**: When an import item has prior direct sales, the user sees a higher "Available" quantity in the Customs Ledger section than what the API will accept for a new direct SALE trade. The discrepancy equals `direct_sale_quantity`. The "Billed (No BOE)" column now shows the CIF from SALE trade lines without BOE attachment, helping operators identify unlinked sales.

**Example**: Item with 342,672.02 kg total quantity, 0 kg BOE debited, 0 kg allotted, 10 kg billed (no BOE), and 15,251.30 kg in prior direct sales:
- Path 1 (validation): 342,672.02 − 0 − 0 − 15,251.30 = **327,420.72 kg** ✓
- Path 3 (snapshot): 342,672.02 − 0 − 0 = **342,672.02 kg** ⚠️
- Path 4 (frontend display): 342,672.02 − 0 − 0 − 10 = **342,662.02 kg** ⚠️

**Resolution guidance**: The frontend's `CustomsLedgerSection.tsx` should use the stored `item.available_quantity` field (which includes all four components) instead of computing `quantity - boe_debited_quantity - allotted_quantity - billed_no_boe`. The `balance_snapshot.py` should include `direct_sale_quantity` in its calculation to match the authoritative formula.

**Files**:
- `backend/apps/license/services/balance_calculator.py` — authoritative formula
- `backend/apps/core/scripts/calculate_balance.py` — stored field update
- `backend/apps/license/services/balance_snapshot.py` — snapshot API (incomplete)
- `frontend/src/pages/license-overview/CustomsLedgerSection.tsx` — frontend display (incomplete)
- `frontend/src/pages/license-overview/ItemsTab.tsx` — uses stored field (correct)

---

## BR-18: Financial Year Boundaries

**Rule**: All date-range filters that reference "financial year" use the Indian FY:
- Start: April 1
- End: March 31

Example: FY 2025-26 = April 1 2025 → March 31 2026.

The license ledger defaults to the current financial year. Exchange rate lookups and invoice numbering also follow this boundary.

---

## BR-19: Exchange Rate Lookup

**Rule**: When converting CIF USD → CIF INR:
```
cif_inr = cif_fc × exchange_rate_on_clearance_date
```

- Exchange rate is looked up from `ExchangeRateModel` by currency and the closest date ≤ clearance date
- If no rate found for the exact date, the most recent prior rate is used
- Exchange rates are managed manually or imported from external sources

---

## BR-19A: SION Planning — Priority Waterfall

**Rule**: SION planning executes rules in priority order (lowest number = highest priority). Each rule consumes from the remaining CIF and quantity pool. Once a source import item is claimed by a higher-priority rule, lower-priority rules cannot re-allocate it.

**Execution Order**:
1. Load all active rules for the SION norm, sorted by `priority` then `pk`
2. For each rule, evaluate the expression tree against all import items
3. Filter out already-claimed items
4. Calculate available quantity: `original_quantity − BOE_used − unlinked_allotment`
5. Allocate CIF: `min(requested CIF, remaining_waterfall_CIF)`
6. Claim source item IDs to prevent double-allocation

**CIF Allocation Formula** (`allocate_step`):
- If `balance >= requested_qty × max_price` → use `max_price`
- Else → use `balance / requested_qty` (effective rate drops below max)
- If `requested_qty == 0` or `balance == 0` → planned CIF is 0

**Files**:
- `backend/apps/license/services/sion_planning_execution.py` — `_compute_license_new_architecture()`
- `backend/apps/license/services/planning_allocation.py` — `allocate_step()`
- `backend/apps/license/services/sion_rule_engine.py` — `evaluate_expression()`

---

## BR-19B: SION Planning — CIF Restriction per Item (Implemented)

**Rule**: Each planning rule (or percentage/unit-value row) can specify a CIF restriction percentage. During planning, if an import item's used CIF (debited + allotted + already planned in this run) exceeds this percentage of its total CIF value, the planner skips that item.

**Formula**:
```
used_cif = boe_used_cif + unlinked_allotment_cif + already_planned_cif_this_run
ceiling = item.cif_fc × cif_restriction_percentage / 100
skip_if: used_cif >= ceiling
```

**Resolution**: Row-level `cif_restriction_percentage` takes precedence over rule-level; NULL at row level falls back to rule-level; NULL at both levels means no restriction.

**Allowed Values**: `2`, `3`, `5`, `10`, or `NULL` (no restriction). Serializer rejects other values.

**Scope**: Per import item, not per license total. A NULL value means the item is planned without this cap.

**Behavior**:
- The restriction is a **hard ceiling** — if already exceeded, the item is skipped entirely
- Planned CIF is tracked across all rules within a single planning run via `record_planned_cif()`
- Items skipped due to CIF restriction are silently skipped (no plan line generated)
- Applies to all three strategies: STANDARD, SPLIT_BY_UNIT_VALUE, and SPLIT_BY_PERCENT
- For STANDARD strategy, the rule-level `cif_restriction_percentage` is used
- For split strategies, row-level value overrides rule-level; NULL falls back to rule-level

**Edge Cases**:
- Item with zero CIF: ceiling is zero, item is always skipped
- Multiple rules matching the same item: CIF restriction is checked per rule/row; `record_planned_cif()` accumulates across rules
- Restriction change on existing rule: affects future planning runs only, not existing plans

**Files**:
- `backend/apps/license/models/core.py` — `cif_restriction_percentage` on `SionPlanningRule`, `SionPlanningPercentageRow`, `SionPlanningUnitValueRow`
- `backend/apps/license/services/sion_planning_execution.py` — `get_effective_cif_restriction()`, `check_cif_restriction()`, `record_planned_cif()`
- `backend/apps/license/serializers/incentive.py` — `_validate_cif_restriction()` validation
- `backend/apps/license/migrations/0056_add_cif_restriction_percentage.py`
- `frontend/src/pages/planning/AllocationStrategyEditor.tsx` — CIF restriction dropdown per row
- `frontend/src/services/api/planningRuleApi.ts` — `cif_restriction_percentage` in types

---

## BR-20: Task Visibility

**Rule**: A task is visible to:
- The user who created it (`created_by`)
- The user it is assigned to (`assigned_to`)
- Any superuser

Tasks rejected by the assignee that were created by someone else are still visible to the creator as "open" (requiring follow-up).
