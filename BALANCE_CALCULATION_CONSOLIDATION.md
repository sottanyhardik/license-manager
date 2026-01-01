# Balance Calculation Consolidation - Complete Guide

## Summary

All balance_cif calculations have been consolidated to use a **single source of truth**: `LicenseBalanceCalculator` service.

## Expected Result for License 0311045597

```
Opening Balance (Export CIF):  $1,11,302.61
Total Sales (DFIA Credits):   -$77,934.12
─────────────────────────────────────────
Final Balance:                  $33,368.49 ✅
```

## Single Source of Truth

All balance calculations now go through:
```python
from license.services.balance_calculator import LicenseBalanceCalculator

# License-level balance
balance = LicenseBalanceCalculator.calculate_balance(license_obj)

# Components
credit = LicenseBalanceCalculator.calculate_credit(license_obj)      # Export CIF
debit = LicenseBalanceCalculator.calculate_debit(license_obj)        # BOE debits
allotment = LicenseBalanceCalculator.calculate_allotment(license_obj) # Allotments (no BOE)
trade = LicenseBalanceCalculator.calculate_trade(license_obj)        # Trade (no invoice)

# Formula
balance = credit - (debit + allotment + trade)
```

## Changes Made (Commit: 66b1dff)

### 1. Consolidated Model Methods

**File**: `backend/license/models.py`

| Method | OLD | NEW |
|--------|-----|-----|
| `opening_balance` | Direct aggregation on export_license | ✅ `_calculate_license_credit()` |
| `get_total_debit` | Direct aggregation on import_license.debited_value | ✅ `_calculate_license_debit()` |
| `get_total_allotment` | Direct aggregation on import_license.allotted_value | ✅ `_calculate_license_allotment()` |
| (NEW) `_calculate_license_trade()` | N/A | ✅ Added for completeness |
| `get_balance_cif` | Already using service ✅ | No change needed |

### 2. Wrapper Methods (Already Exist)

```python
class LicenseDetailsModel:
    def _calculate_license_credit(self) -> Decimal:
        """Total export CIF"""
        return LicenseBalanceCalculator.calculate_credit(self)

    def _calculate_license_debit(self) -> Decimal:
        """Total BOE debits"""
        return LicenseBalanceCalculator.calculate_debit(self)

    def _calculate_license_allotment(self) -> Decimal:
        """Total allotments without BOE"""
        return LicenseBalanceCalculator.calculate_allotment(self)

    def _calculate_license_trade(self) -> Decimal:
        """Total trade without invoice"""
        return LicenseBalanceCalculator.calculate_trade(self)

    @property
    def get_balance_cif(self) -> Decimal:
        """Final calculated balance"""
        return LicenseBalanceCalculator.calculate_balance(self)
```

## Key Fixes Applied

### 1. Correct Allotment Filter (Commit: c4b0056)

**BEFORE (Wrong)**:
```python
allotment__bill_of_entry__bill_of_entry_number__isnull=True
```
- Checks if a specific field is null
- Incorrect logic

**AFTER (Correct)**:
```python
allotment__bill_of_entry__isnull=True
```
- Checks if ManyToMany relationship is empty
- Correctly identifies allotments WITHOUT BOE linked

Applied to all files:
- ✅ `license/services/balance_calculator.py` (3 places)
- ✅ `license/services/restriction_calculator.py`
- ✅ `license/models.py`
- ✅ `core/scripts/calculate_balance.py`
- ✅ `license/management/commands/sync_licenses.py`

### 2. Automatic Updates via Signals

**File**: `license/signals.py`

Signals automatically update `balance_cif` when:
- ✅ Export items change (add/modify/delete)
- ✅ Import items change (add/modify/delete)
- ✅ Allotment items change (add/modify/delete)
- ✅ BOE items change (add/modify/delete)
- ✅ Trade items change (add/modify/delete)

All signals call: `update_license_flags(license_instance)` which:
1. Calls `license.get_balance_cif` (uses centralized service)
2. Updates stored `balance_cif` field
3. Updates `is_null` flag (balance < $500)
4. Updates `is_expired` flag

## Deployment Steps

### Step 1: Pull Latest Code
```bash
ssh django@139.59.92.226
cd ~/license-manager/backend
git pull origin version-4.1
```

### Step 2: Recalculate All Balance Values
```bash
# Recalculate all licenses with NEW logic
python manage.py update_balance_cif

# Or just one license to test
python manage.py update_balance_cif --license-number 0311045597
```

### Step 3: Restart Application
```bash
sudo systemctl restart gunicorn
```

### Step 4: Verify
Visit: https://labdh.duckdns.org/licenses/0311045597/ledger-detail

**Expected Result**:
- Available Balance: $33,368.49 ✅
- Balance CIF (ledger): $33,368.49 ✅

## Why This Works

### Before Consolidation
```
❌ Multiple calculation methods
❌ Inconsistent logic
❌ Hard to maintain
❌ Different results possible
```

### After Consolidation
```
✅ Single source of truth (LicenseBalanceCalculator)
✅ Consistent calculation everywhere
✅ Easy to maintain and debug
✅ Guaranteed same result
✅ Automatic updates via signals
```

## Formula Breakdown for 0311045597

```python
# Credit (Export CIF)
credit = $1,11,302.61

# Debit (BOE transactions)
debit = $0.00  # No BOE debits

# Allotment (without BOE)
allotment = $77,934.12  # 3 DFIA sales

# Trade (without invoice)
trade = $0.00  # No trade lines

# Final Balance
balance = $1,11,302.61 - ($0 + $77,934.12 + $0)
balance = $33,368.49 ✅
```

## Testing

### Debug Script
Use the included debug script to verify calculations:
```bash
cd ~/license-manager/backend
python debug_balance.py
```

This will show:
- Credit, Debit, Allotment, Trade components
- Manual calculation vs service calculation
- Stored balance_cif vs calculated balance
- Allotment details (with/without BOE)

## Files Modified

### Commit c4b0056: Fix M2M Relationship Checks
1. `license/services/balance_calculator.py`
2. `license/services/restriction_calculator.py`
3. `license/models.py`
4. `core/scripts/calculate_balance.py`
5. `license/management/commands/sync_licenses.py`

### Commit 66b1dff: Consolidate Balance Calculations
1. `license/models.py`
   - Updated `opening_balance`
   - Updated `get_total_debit`
   - Updated `get_total_allotment`
   - Added `_calculate_license_trade`

## Benefits

1. **Consistency**: All calculations use same logic
2. **Maintainability**: Single place to fix bugs
3. **Automatic**: Signals keep stored values updated
4. **Testable**: Centralized service easy to test
5. **Reliable**: Expected output: $33,368.49 for license 0311045597

## Support

If balance still shows $0.00 after deployment:
1. Verify code pulled: `git log -1 --oneline` should show commit `66b1dff`
2. Verify command ran: `python manage.py update_balance_cif --license-number 0311045597`
3. Check logs: `tail -f /var/log/gunicorn/error.log`
4. Use debug script: `python debug_balance.py`
