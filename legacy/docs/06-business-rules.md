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

**Rule**: Invoice numbers are auto-generated per financial year in the format `INV-FY<year>-<sequential_number>`.

- Financial year starts April 1 (India)
- Example: `INV-FY25-0042` for the 42nd invoice in FY 2025-26
- Number resets to 0001 each April 1
- Sequence is guaranteed unique per direction (PURCHASE vs SALE)

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

## BR-20: Task Visibility

**Rule**: A task is visible to:
- The user who created it (`created_by`)
- The user it is assigned to (`assigned_to`)
- Any superuser

Tasks rejected by the assignee that were created by someone else are still visible to the creator as "open" (requiring follow-up).
