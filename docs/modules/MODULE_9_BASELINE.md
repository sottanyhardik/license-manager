# MODULE 9 BASELINE: Incentive / RODTEP

## 1. SCOPE

### Purpose
Module 9 manages export incentive schemes: RODTEP, ROSTL, MEIS. These are value-based export licenses with standard 2-year validity.

### Business Entities
- **IncentiveLicense**: License header with type, number, date, expiry, value, sold status
- **IncentiveTradeLine**: Trade line line-items linking licenses to purchase/sale transactions
- **LicenseTrade**: Trade header supporting both DFIA and Incentive license types

### Key Workflows
1. **License Creation**: Exporter creates incentive license with value; expiry auto-calculated as license_date + 2 years
2. **Trade Purchase**: Supplier records incentive value purchased at rate % to compute amount
3. **Trade Sale**: Buyer records sale; sold_value updated, balance and sold_status recalculated
4. **Ledger Reporting**: Incentive licenses displayed in license ledger with balance, sold, purchase, sale metrics

### Integration Points
- **Ledger Service**: prepare_incentive_data(), get_incentive_breakdown()
- **Trade Views**: LicenseTradeViewSet handles INCENTIVE license_type trades
- **Bill of Supply PDF**: Separate itemization for incentive lines (rate % mode)
- **Export (Excel/PDF)**: Incentive license labels in trade exports

---

## 2. FINANCIAL CALCULATIONS

### Core Formula
```
balance_value = license_value - sold_value
sold_value = SUM(IncentiveTradeLine.amount_inr WHERE trade.direction='SALE')
amount_inr = license_value × rate_pct / 100
```

### Precision & Rounding
- License value fields: max_digits=15, decimal_places=2 (supports up to ₹999,999,999.99)
- Trade line fields: max_digits=20, decimal_places=2
- Rate %: decimal_places=3 (e.g., 1.567%)
- Trade totals: Rounded to nearest rupee using ROUND_HALF_UP
- Aggregation: Uses Django Sum() with Decimal operations

### Critical Assumptions
- **Sold value only from SALE trades**: PURCHASE trades do NOT reduce balance.
  (Business logic: balance is "remaining" not "committed".)
- **Balance cached, not re-derived**: The `balance_value` field is signal-maintained.
  Not recalculated from trade sums in ledger views, avoiding drift accumulation.
- **Sold status deterministic**:
  ```
  if balance <= 0: 'YES'       (fully sold)
  else if balance >= total: 'NO'      (not sold)
  else: 'PARTIAL'             (partially sold)
  ```

### Calculation Locations
| Calculation | Location | Trigger |
|---|---|---|
| balance_value | IncentiveLicense.save(), update_sold_status() | Manual save, trade signals |
| sold_value | update_sold_status() | Trade line create/delete (signals) |
| sold_status | update_sold_status(), serializer | Trade signals, API serialization |
| amount_inr | IncentiveTradeLine.save(), compute_amount() | Line save |
| trade total | LicenseTrade.recompute_totals() | create(), update() serializers |

---

## 3. DATA MODELS

### IncentiveLicense
**File**: `backend/apps/license/models/core.py:1512`

| Field | Type | Constraints | Purpose |
|---|---|---|---|
| license_type | CharField(10) | RODTEP, ROSTL, MEIS | Classification |
| license_number | CharField(50) | UNIQUE, db_index | Identifier |
| license_date | DateField | Required | Start date |
| license_expiry_date | DateField | Auto-calc (date+2yr) | 2-year validity |
| exporter | FK(Company) | on_delete=CASCADE | License holder |
| port_code | FK(Port) | on_delete=CASCADE | Port of export |
| license_value | Decimal(15,2) | ≥0 | Total license value (INR) |
| sold_value | Decimal(15,2) | ≥0, cached | Exported value (INR) |
| balance_value | Decimal(15,2) | unconstrained | Remaining value |
| sold_status | CharField(10) | NO, PARTIAL, YES | Display/filter field |
| is_active | BooleanField | default=True | Soft lifecycle |
| notes | TextField | nullable | Admin notes |

**Indexes**: license_number, license_type, exporter+license_date, license_date, license_expiry_date, is_active, sold_status

**Audit**: created_by, modified_by, created_on, modified_on (inherited from AuditModel)

### IncentiveTradeLine
**File**: `backend/apps/trade/models.py:480`

| Field | Type | Constraints | Purpose |
|---|---|---|---|
| trade | FK(LicenseTrade) | on_delete=CASCADE | Parent trade |
| incentive_license | FK(IncentiveLicense) | on_delete=PROTECT | License being traded |
| license_value | Decimal(20,2) | default=0 | Input: license value (INR) |
| rate_pct | Decimal(9,3) | default=0 | Input: billing rate % |
| amount_inr | Decimal(20,2) | default=0 | Output: calculated amount |
| created_on | DateTimeField | auto, db_index | Audit |
| modified_on | DateTimeField | auto | Audit |

**Signals**:
- post_save: calls `incentive_license.update_sold_status()` if trade.direction='SALE'
- pre_delete: calls `incentive_license.update_sold_status()` if trade.direction='SALE'

### LicenseTrade (relevant fields for incentive)
**File**: `backend/apps/trade/models.py:136`

| Field | Type | Constraints | Purpose |
|---|---|---|---|
| license_type | CharField(20) | DFIA, INCENTIVE | Route to lines or incentive_lines |
| incentive_license | FK(IncentiveLicense) | null, on_delete=SET_NULL | Single license (header-level) |
| incentive_lines | Reverse M2M | via IncentiveTradeLine | 0..N line items |
| direction | CharField(20) | PURCHASE, SALE, ... | Trade direction |

**Recompute Logic**:
```python
if license_type == 'INCENTIVE':
    subtotal = SUM(incentive_lines.amount_inr)
else:
    subtotal = SUM(lines.amount_inr)
roundoff = nearest_rupee - subtotal
total = subtotal + roundoff
```

---

## 4. BUSINESS RULES

### Validation Rules
1. **At least one line required**: Trade must have ≥1 line (regular or incentive)
2. **Company constraint**: from_company ≠ to_company (DB constraint)
3. **Duplicate invoice prevention**: Unique(from_company, invoice_number, direction) for PURCHASE; Unique(to_company, invoice_number, direction) for SALE
4. **License availability**: Rate % and license_value are free-text; no cap enforcement on trade creation
5. **Date ordering**: license_expiry_date auto-calc ensures expiry >= license_date
6. **Balance non-negative**: Not enforced at DB layer
7. **Sold status enum**: Computed field, never user-input

### Permission Requirements
| Role | Permissions |
|---|---|
| INCENTIVE_LICENSE_MANAGER | Create, read, update, delete IncentiveLicense; create/update trades |
| INCENTIVE_LICENSE_VIEWER | Read-only IncentiveLicense |
| TRADE_MANAGER | Create, read, update, delete LicenseTrade (all types) |

---

## 5. DEPENDENCIES

### Module Dependencies
| Dependency | Purpose | Files |
|---|---|---|
| License.IncentiveLicense | Model definition | models/core.py |
| Trade.IncentiveTradeLine | Trade line model | trade/models.py |
| Trade.LicenseTrade | Trade header | trade/models.py |
| Core.Company, Core.Port | Master data FKs | Foreign keys |
| Accounts.IncentiveLicensePermission | Role-based access | permissions.py |
| Ledger Service | Data preparation | services/ledger_service.py |
| Bill of Supply PDF | Trade document export | trade/bill_of_supply_pdf.py |

### API Contracts
| Endpoint | Method | Purpose |
|---|---|---|
| /api/incentive-licenses/ | GET, POST, PATCH, DELETE | CRUD incentive licenses |
| /api/trades/ | GET, POST, PATCH, DELETE | CRUD trades (supports license_type=INCENTIVE) |
| /api/trades/{id}/generate-bill-of-supply | GET | PDF export for SALE |

---

## 6. TESTS EXISTING

### Test Files
| File | Test Count | Coverage |
|---|---|---|
| test_incentive_serializers.py | 3 | Decimal fields, null handling, expiry_date write contract |
| test_ledger_service.py | 5+ | prepare_incentive_data, build_license_queryset, filters, search |
| test_masterdata_delete_protection.py | 2+ | IncentiveLicense FK constraints, cascade behavior |
| test_trade_export.py | 1 | Excel export with incentive license labels |
| test_protected_media_view.py | 1 | Permission gating for incentive licenses |

### Coverage Gaps
- No tests for update_sold_status() signal chain
- No tests for trade.recompute_totals() with incentive lines
- No tests for concurrent trade line creation
- No tests for IncentiveTradeLine.compute_amount() edge cases (0%, null rate)
- No tests for ledger aggregation accuracy (purchase vs sale totals)
- No tests for Bill of Supply PDF generation with incentive lines

---

## 7. LEGACY CODE

### Deprecated Methods
| Method | Location | Replacement |
|---|---|---|
| IncentiveLicense.get_sold_value() | models/core.py:1636 | Use .sold_value field directly |
| IncentiveLicense.get_balance_value() | models/core.py:1640 | Use .balance_value field directly |

---

## 8. RISK REGISTER

### 🔴 HIGH PRIORITY

#### R1: Balance Drift via Signal Race Condition
**Risk**: update_sold_status() called via Django signals (post_save, pre_delete). Signals NOT transactional. Concurrent trade line creation on same license causes out-of-order updates.

**Impact**: Financial accuracy; ledger shows wrong balance.

**Mitigation**: Replace signal-based update with transaction-level aggregation in serializer.create().

#### R2: Company Deletion Cascades All Incentive Licenses
**Risk**: IncentiveLicense.exporter has on_delete=CASCADE. Deleting company deletes all its licenses.

**Impact**: Data loss; no undo.

**Mitigation**: Change FK on_delete to PROTECT; require business review before deletion.

#### R3: License Balance Cannot Go Below Zero (Business Intent Unknown)
**Risk**: balance_value field unconstrained at DB layer. No validation preventing negative balance.

**Impact**: Data corruption if business intent is "balance cannot exceed sold_value."

**Mitigation**: Clarify business rules; enforce as DB check.

### 🟡 MEDIUM PRIORITY

#### R4: Trade Header incentive_license Not Validated Against Trade Parties
**Risk**: No validation that license.exporter matches trade.from_company or trade.to_company.

**Impact**: Business rule violation; revenue attribution incorrect.

**Mitigation**: Add serializer.validate() to check license ownership.

#### R5: Ledger Aggregation O(N) Queries
**Risk**: prepare_incentive_data() runs 2 queries per license (1000+ licenses = 2000+ queries).

**Impact**: Performance degradation; timeout on slow networks.

**Mitigation**: Use single annotated query with conditional Sum().

#### R6: IncentiveTradeLine.compute_amount() Edge Cases
**Risk**: No validation for nulls, 0, or negative values in rate_pct or license_value.

**Impact**: Silent data corruption if rate_pct is lost/cleared.

**Mitigation**: Add required=True to rate_pct; add null checks in compute_amount().

#### R7: Sold Status Calculated in Serializer, Not Model
**Risk**: IncentiveLicenseSerializer.get_sold_status() duplicates logic from IncentiveLicense.update_sold_status(). If one changes, other drifts.

**Impact**: Ledger and detail views show different sold_status.

**Mitigation**: Move get_sold_status() to ledger_service.py; call from both places.

### 🟢 LOW PRIORITY

#### R8: Bill of Supply PDF HSN Code Hardcoded
**Risk**: HSN='4907' hardcoded for all incentive lines.

**Impact**: Incorrect tax classification if MEIS requires different HSN.

**Mitigation**: Add optional hsn_code field to IncentiveLicense.

#### R9: No Row-Level Security on Incentive Licenses
**Risk**: IncentiveLicensePermission checks global role, not exporter ownership.

**Impact**: Data isolation violation; users with INCENTIVE_LICENSE_MANAGER can access all licenses.

**Mitigation**: Add resource_role check in permission class.

#### R10: IncentiveTradeLine FK Uses PROTECT, Blocking License Deletion
**Risk**: on_delete=PROTECT prevents IncentiveLicense deletion if any IncentiveTradeLines exist.

**Impact**: UX friction; workaround is to delete trade lines first.

**Mitigation**: Consider soft-delete flag on IncentiveLicense (is_active) instead of hard delete.

---

## 9. SUMMARY

Module 9 (Incentive/RODTEP) is a self-contained license-and-trade module with:
- **Core entity**: IncentiveLicense (value, date, expiry, sold_status)
- **Trade integration**: IncentiveTradeLine + LicenseTrade (INCENTIVE type)
- **Financial accuracy**: Cached sold_value field, signal-maintained balance, rate%-based amount calc
- **Known risks**: Signal race condition, cascade deletion, aggregation efficiency, business rule gaps

**Next steps for production readiness**:
1. Audit signal-based updates for concurrency (R1)
2. Verify company deletion protection (R2)
3. Validate ledger aggregation accuracy (R5)
4. Add compute_amount() null guards (R6)
5. Consolidate sold_status logic (R7)