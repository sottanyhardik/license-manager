# Centralization Analysis Report

## Executive Summary
Analysis of backend codebase to identify calculations that should be centralized in license models for consistency.

## 1. Available Value Usage

### Files Using `available_value`:
1. **core/scripts/calculation.py** - Item calculation logic
2. **core/scripts/calculate_balance.py** - Balance calculation utilities
3. **license/item_report.py** - Reporting
4. **license/models.py** - Model definition (CORRECT - Source of truth)
5. **license/serializers.py** - API serialization (Uses model property - CORRECT)
6. **license/management/commands/check_item_balance.py** - Diagnostic command
7. **license/management/commands/update_balance_cif.py** - Update command
8. **license/management/commands/debug_item.py** - Debug command
9. **license/management/commands/update_restriction_balances.py** - Restriction update command
10. **license/tables.py** - Table rendering
11. **license/views/license.py** - View logic
12. **allotment/signals.py** - Signal handlers
13. **allotment/views_actions.py** - Allotment actions

### Recommendation:
- `available_value` is a DATABASE FIELD on LicenseImportItemsModel
- It's updated by management commands and signals
- Current usage is correct - it's not a calculation, it's a stored value
- **NO CHANGES NEEDED**

## 2. Balance CIF Usage

### Files Using `balance_cif`:
1. **data_script/fetch_bisc.py** - Data fetching
2. **data_script/fetch_conf.py** - Data fetching
3. **core/management/commands/report_fetch.py** - Reporting
4. **core/scripts/license_script.py** - License utilities
5. **core/scripts/calculate_balance.py** - Balance utilities
6. **license/item_report.py** - Reporting
7. **license/models.py** - Model with `balance_cif_fc` property (CORRECT - Source of truth)
8. **license/serializers.py** - Uses model property (CORRECT)
9. **license/ledger_pdf.py** - Uses model property (CORRECT after our updates)
10. **license/management/commands/** - Various commands
11. **license/helper.py** - Helper functions
12. **license/tables.py** - Table rendering
13. **license/views/license.py** - View logic
14. **allotment/signals.py** - Signal handlers
15. **allotment/views_actions.py** - Allotment actions

### Current Model Methods (ALREADY CENTRALIZED):
- `LicenseDetailsModel.get_balance_cif` ✅ (License level)
- `LicenseDetailsModel._calculate_license_credit()` ✅
- `LicenseDetailsModel._calculate_license_debit()` ✅
- `LicenseDetailsModel._calculate_license_allotment()` ✅
- `LicenseDetailsModel.get_restriction_balances()` ✅ (NEW - Added)
- `LicenseImportItemsModel.balance_cif_fc` ✅ (Item level)
- `LicenseImportItemsModel._calculate_item_debit()` ✅
- `LicenseImportItemsModel._calculate_item_allotment()` ✅

### Recommendation:
- Balance CIF calculations are ALREADY CENTRALIZED in models
- Most files correctly use model properties
- **AUDIT NEEDED**: Check if any files calculate balance directly instead of using properties

## 3. Available Quantity Usage

### Files Calculating `available_quantity`:
1. **license/item_report.py** - May have calculations
2. **license/models.py** - Has `balance_quantity` property (CORRECT)
3. **license/management/commands/update_balance_cif.py** - Updates field
4. **license/tables.py** - Display logic
5. **allotment/signals.py** - Updates on allotment changes
6. **allotment/views_actions.py** - Updates on actions

### Current Model Methods:
- `LicenseImportItemsModel.balance_quantity` property ✅
  - Delegates to `core.scripts.calculate_balance.calculate_available_quantity`
  - Fallback: `quantity - debited - allotted`

### Recommendation:
- `available_quantity` is a DATABASE FIELD (cached value)
- `balance_quantity` is a CALCULATED PROPERTY (always fresh)
- Signals update `available_quantity` field when transactions occur
- **AUDIT NEEDED**: Ensure all calculations use `balance_quantity` property, not custom logic

## 4. Action Plan

### Phase 1: Verification (Current Status)
✅ License-level balance: `get_balance_cif` (DONE)
✅ Item-level balance: `balance_cif_fc` (DONE)
✅ Restriction balances: `get_restriction_balances()` (DONE - Just added)
✅ Available quantity: `balance_quantity` (DONE)

### Phase 2: Audit Files (TODO)
Files to check for direct calculations instead of using model properties:

**HIGH PRIORITY:**
- [ ] `license/item_report.py` - Check if it calculates instead of using properties
- [ ] `license/tables.py` - Check if it calculates instead of using properties
- [ ] `license/views/license.py` - Check if it calculates instead of using properties
- [ ] `license/helper.py` - Check if it has duplicate calculation logic
- [ ] `allotment/signals.py` - Ensure it updates fields correctly
- [ ] `allotment/views_actions.py` - Ensure it uses model properties

**MEDIUM PRIORITY:**
- [ ] `core/scripts/calculation.py` - May have legacy calculation logic
- [ ] `core/scripts/calculate_balance.py` - Check if redundant with model methods
- [ ] `license/management/commands/update_balance_cif.py` - Verify it uses centralized methods
- [ ] `license/management/commands/update_restriction_balances.py` - Should use new `get_restriction_balances()`

**LOW PRIORITY (Reports/Debug):**
- [ ] `data_script/fetch_bisc.py`
- [ ] `data_script/fetch_conf.py`
- [ ] `license/management/commands/check_item_balance.py`
- [ ] `license/management/commands/debug_item.py`

### Phase 3: Consolidation (TODO)
If audit finds duplicate logic:
1. Add missing methods to models if needed
2. Update files to use model properties
3. Remove duplicate calculation code
4. Add tests for centralized methods

## 5. Current Centralized Methods Summary

### LicenseDetailsModel (License Level)
```python
# Balance calculations
@property
def get_balance_cif(self) -> Decimal
def _calculate_license_credit(self) -> Decimal
def _calculate_license_debit(self) -> Decimal
def _calculate_license_allotment(self) -> Decimal

# Restriction calculations (NEW)
def get_restriction_balances(self) -> Dict[Decimal, Decimal]
```

### LicenseImportItemsModel (Item Level)
```python
# Balance calculations
def balance_cif_fc(self) -> Decimal
def _calculate_item_debit(self) -> Decimal
def _calculate_item_allotment(self) -> Decimal

# Quantity calculations
@cached_property
def balance_quantity(self) -> Decimal
```

### LicenseExportItemModel (Export Level)
```python
def balance_cif_fc(self) -> Decimal  # Delegates to license.get_balance_cif
```

## 6. Conclusion

**Good News:**
- Most calculations are ALREADY centralized in model properties
- The codebase follows good practices by using properties
- Database fields (`available_value`, `available_quantity`) are maintained by signals and commands

**Action Required:**
- Audit specific files to ensure they use model properties
- Update `update_restriction_balances.py` command to use new `get_restriction_balances()` method
- Remove any duplicate calculation logic found during audit

**No Major Refactoring Needed:**
- The architecture is sound
- Just need to verify consistency across files
