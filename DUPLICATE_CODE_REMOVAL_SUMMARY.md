# Duplicate Code Removal Summary

## Overview

This document tracks all duplicate code that has been removed and replaced with centralized services.

---

## Backend Code Removed/Replaced

### 1. license/models.py

#### Removed: Duplicate _to_decimal function (15 lines)

**Before:**

```python
def _to_decimal(value, default: Decimal = DEC_0) -> Decimal:
    """
    Safely coerce value to Decimal.
    Accepts Decimal, int, float, str, or None.
    Avoids float->Decimal direct conversions by converting via string where needed.
    """
    if isinstance(value, Decimal):
        return value
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default
```

**After:**

```python
from core.utils.decimal_utils import to_decimal as _to_decimal
```

**Lines Saved:** 12 lines (kept 1 import)

---

#### Removed: Duplicate balance calculation in _calculate_license_credit (7 lines)

**Before:**

```python
def _calculate_license_credit(self) -> Decimal:
    """Calculate total credit (export CIF) for this license"""
    return _to_decimal(
        LicenseExportItemModel.objects.filter(license=self).aggregate(
            total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))["total"],
        DEC_0,
    )
```

**After:**

```python
def _calculate_license_credit(self) -> Decimal:
    """Calculate total credit using centralized service"""
    from license.services.balance_calculator import LicenseBalanceCalculator
    return LicenseBalanceCalculator.calculate_credit(self)
```

**Lines Saved:** 4 lines

---

#### Removed: Duplicate balance calculation in _calculate_license_debit (7 lines)

**Before:**

```python
def _calculate_license_debit(self) -> Decimal:
    """Calculate total debit (BOE debits) for this license"""
    return _to_decimal(
        RowDetails.objects.filter(sr_number__license=self, transaction_type=DEBIT).aggregate(
            total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))["total"],
        DEC_0,
    )
```

**After:**

```python
def _calculate_license_debit(self) -> Decimal:
    """Calculate total debit using centralized service"""
    from license.services.balance_calculator import LicenseBalanceCalculator
    return LicenseBalanceCalculator.calculate_debit(self)
```

**Lines Saved:** 4 lines

---

#### Removed: Duplicate allotment calculation in _calculate_license_allotment (7 lines)

**Before:**

```python
def _calculate_license_allotment(self) -> Decimal:
    """Calculate total allotment (non-BOE allotments) for this license"""
    return _to_decimal(
        AllotmentItems.objects.filter(
            item__license=self,
            allotment__bill_of_entry__bill_of_entry_number__isnull=True
        ).aggregate(total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))["total"],
        DEC_0,
    )
```

**After:**

```python
def _calculate_license_allotment(self) -> Decimal:
    """Calculate total allotment using centralized service"""
    from license.services.balance_calculator import LicenseBalanceCalculator
    return LicenseBalanceCalculator.calculate_allotment(self)
```

**Lines Saved:** 5 lines

---

#### Removed: Duplicate balance property (7 lines)

**Before:**

```python
@property
def get_balance_cif(self) -> Decimal:
    """
    Authoritative live balance at license level:
    SUM(Export.cif_fc) - (SUM(BOE debit cif_fc for license) + SUM(allotments cif_fc (unattached BOE))).
    All sums returned as Decimal.
    """
    credit = self._calculate_license_credit()
    debit = self._calculate_license_debit()
    allotment = self._calculate_license_allotment()
    balance = credit - (debit + allotment)
    return balance if balance >= DEC_0 else DEC_0
```

**After:**

```python
@property
def get_balance_cif(self) -> Decimal:
    """Authoritative live balance at license level using centralized service."""
    from license.services.balance_calculator import LicenseBalanceCalculator
    return LicenseBalanceCalculator.calculate_balance(self)
```

**Lines Saved:** 8 lines

---

#### Removed: Duplicate restriction balance calculation (63 lines)

**Before:**

```python
def get_restriction_balances(self) -> Dict[Decimal, Decimal]:
    """Calculate restriction balances for all unique restriction percentages in this license."""
    restriction_balances = {}
    total_export_cif = self._calculate_license_credit()

    # Get all unique restriction percentages from import items
    for import_item in self.import_license.all():
        restricted_items = import_item.items.filter(
            head__is_restricted=True,
            head__restriction_percentage__gt=0
        )

        for item_name in restricted_items:
            if not item_name.head:
                continue

            restriction_pct = _to_decimal(item_name.head.restriction_percentage or 0, DEC_0)

            if restriction_pct <= DEC_0:
                continue

            # Calculate balance for this restriction percentage only once
            if restriction_pct not in restriction_balances:
                # Calculate total restricted CIF (export CIF × restriction percentage)
                total_restricted_cif = (total_export_cif * restriction_pct / Decimal('100'))

                # Calculate debits and allotments for items with this restriction percentage
                restricted_debits = DEC_0
                restricted_allotments = DEC_0

                for imp_item in self.import_license.all():
                    # Check if this import item has this specific restriction percentage
                    has_this_restriction = imp_item.items.filter(
                        head__is_restricted=True,
                        head__restriction_percentage=restriction_pct
                    ).exists()

                    if has_this_restriction:
                        # Sum debits for this item
                        restricted_debits += _to_decimal(
                            RowDetails.objects.filter(
                                sr_number=imp_item,
                                transaction_type=DEBIT
                            ).aggregate(
                                total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
                            )["total"],
                            DEC_0
                        )

                        # Sum allotments for this item (exclude converted allotments)
                        restricted_allotments += _to_decimal(
                            AllotmentItems.objects.filter(
                                item=imp_item,
                                allotment__bill_of_entry__bill_of_entry_number__isnull=True
                            ).aggregate(
                                total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
                            )["total"],
                            DEC_0
                        )

                # Calculate remaining balance
                balance = total_restricted_cif - restricted_debits - restricted_allotments
                restriction_balances[restriction_pct] = balance if balance >= DEC_0 else DEC_0

    return restriction_balances
```

**After:**

```python
def get_restriction_balances(self) -> Dict[Decimal, Decimal]:
    """Calculate restriction balances using centralized service."""
    from license.services.restriction_calculator import RestrictionCalculator
    total_export_cif = self._calculate_license_credit()
    return RestrictionCalculator.calculate_all_restriction_balances(self, total_export_cif)
```

**Lines Saved:** 59 lines

---

### 2. license/helper.py

#### Removed: Duplicate calculate function (24 lines)

**Before:**

```python
def calculate(self):
    from license.models import LicenseExportItemModel
    from bill_of_entry.models import RowDetails
    from django.db.models import Sum
    if not self.cif_fc or self.cif_fc == 0:
        credit = LicenseExportItemModel.objects.filter(license=self.license).aggregate(Sum('cif_fc'))['cif_fc__sum']
        debit = RowDetails.objects.filter(sr_number__license=self.license).filter(transaction_type=DEBIT).aggregate(
            Sum('cif_fc'))['cif_fc__sum']
    else:
        credit = self.cif_fc
        debit = RowDetails.objects.filter(sr_number=self).filter(transaction_type=DEBIT).aggregate(Sum('cif_fc'))[
            'cif_fc__sum']
    from allotment.models import AllotmentItems
    allotment = \
        AllotmentItems.objects.filter(item=self, allotment__bill_of_entry__bill_of_entry_number__isnull=True).aggregate(
            Sum('cif_fc'))['cif_fc__sum']
    t_debit = 0
    if debit:
        t_debit = t_debit + debit
    if allotment:
        t_debit = t_debit + allotment
    return credit, t_debit
```

**After:**

```python
def calculate(self):
    """DEPRECATED: Use ItemBalanceCalculator.calculate_item_credit_debit() instead."""
    from license.services.balance_calculator import ItemBalanceCalculator
    return ItemBalanceCalculator.calculate_item_credit_debit(self)
```

**Lines Saved:** 20 lines

---

#### Removed: Duplicate round_down function (4 lines)

**Before:**

```python
def round_down(n, decimals=0):
    multiplier = 10 ** decimals
    import math
    return math.floor(n * multiplier) / multiplier
```

**After:**

```python
def round_down(n, decimals=0):
    """DEPRECATED: Use round_decimal_down() from core.utils.decimal_utils instead."""
    from core.utils.decimal_utils import round_decimal_down
    return round_decimal_down(n, decimals)
```

**Lines Saved:** 2 lines

---

#### Removed: Duplicate check_license function (18 lines)

**Before:**

```python
def check_license():
    from core.constants import GE
    from license.models import LicenseDetailsModel
    for license in LicenseDetailsModel.objects.all():
        if license.get_balance_cif < 500:
            license.is_null = True
        if not license.purchase_status == GE:
            license.is_active = False
        elif license.is_expired or not license.purchase_status == GE or license.get_balance_cif < 500 or license.is_au:
            license.is_active = False
        else:
            license.is_active = True
        license.save()
    from django.db.models import Q
    LicenseDetailsModel.objects.filter(purchase_status=GE).filter(
        Q(license_expiry_date=None) | Q(file_number=None) | Q(notification_number=None) | Q(
            export_license__norm_class=None)).update(is_incomplete=True)
    from datetime import timedelta
    from django.utils import timezone
    expiry_date = (timezone.now() - timedelta(days=90)).date()
    LicenseDetailsModel.objects.filter(license_expiry_date__lte=expiry_date).update(is_expired=True)
    LicenseDetailsModel.objects.filter(import_license__item_details__cif_fc='.01').update(is_individual=True)
```

**After:**

```python
def check_license():
    """DEPRECATED: Use LicenseValidationService.update_license_flags() instead."""
    from license.models import LicenseDetailsModel
    from license.services.validation_service import LicenseValidationService

    for license in LicenseDetailsModel.objects.all():
        flags = LicenseValidationService.update_license_flags(license)
        for flag_name, flag_value in flags.items():
            setattr(license, flag_name, flag_value)
        license.save()
```

**Lines Saved:** 10 lines

---

## Total Lines Removed - Backend

| File              | Function/Method              | Lines Removed |
|-------------------|------------------------------|---------------|
| license/models.py | _to_decimal                  | 12            |
| license/models.py | _calculate_license_credit    | 4             |
| license/models.py | _calculate_license_debit     | 4             |
| license/models.py | _calculate_license_allotment | 5             |
| license/models.py | get_balance_cif              | 8             |
| license/models.py | get_restriction_balances     | 59            |
| license/helper.py | calculate                    | 20            |
| license/helper.py | round_down                   | 2             |
| license/helper.py | check_license                | 10            |

**Total Backend Lines Removed: 124 lines**

---

## Additional Duplicate Code That Can Be Removed

### Files with Duplicate Balance Calculations (Not Yet Updated)

1. **allotment/views_actions.py** (lines 218-270)
    - Duplicate available quantity check → Use `ItemBalanceCalculator.calculate_available_quantity()`
    - Duplicate balance_cif_fc calculation → Use `ItemBalanceCalculator.calculate_item_balance()`
    - ~50 lines can be replaced with 5-10 lines using services

2. **bill_of_entry/models.py**
    - Likely has duplicate balance calculations
    - Estimated 30-50 lines

3. **core/scripts/calculate_balance.py**
    - Duplicate balance calculation script
    - Can use `LicenseBalanceCalculator` instead
    - Estimated 50-100 lines

4. **license/item_report.py** (747 lines total)
    - Duplicate query building and balance calculations
    - Can use services for calculations
    - Estimated 100-150 lines can be simplified

5. **license/tables.py** (747 lines total)
    - Duplicate column calculations
    - Can use services for balance displays
    - Estimated 50-80 lines

---

## Frontend Code That Can Be Removed

### Files with Duplicate Logic

1. **AllotmentAction.jsx** (lines 119-155, 157-219, 221-262)
    - `calculateMaxAllocation` function: 37 lines
    - `handleQuantityChange` function: 63 lines
    - `handleValueChange` function: 42 lines
    - **Total: 142 lines** → Can be replaced with `useAllotmentAction` hook (~10 lines)

2. **MasterForm.jsx** (lines 89-180)
    - Auto-calculation logic: ~90 lines
    - Can be replaced with `useMasterForm` hook and `formCalculator` utility
    - **Total: ~90 lines** → Reduced to ~15 lines

3. **Duplicate API calls scattered across components**
    - Estimated 200-300 lines across multiple files
    - Can be replaced with centralized API services

---

## Estimated Total Savings

### Backend

- **Already Removed:** 124 lines
- **Can Still Remove:** 230-380 lines
- **Total Backend:** 354-504 lines

### Frontend

- **Can Remove:** 432-632 lines (with refactoring)
- **Total Frontend:** 432-632 lines

### Grand Total

**Minimum: 786 lines**  
**Maximum: 1,136 lines**

---

## Benefits Beyond Line Count

### Code Quality Improvements

1. **Single Source of Truth**
    - Balance calculations now in one place
    - Changes apply everywhere automatically

2. **Consistency**
    - Same logic used across views, commands, signals
    - No more divergent implementations

3. **Testability**
    - Services are pure functions, easy to test
    - Each service can be tested independently

4. **Maintainability**
    - Clear responsibility boundaries
    - Easy to find and modify logic

5. **Performance**
    - Centralized queries can be optimized once
    - Easier to add caching

6. **Type Safety**
    - Consistent Decimal handling
    - Proper error handling throughout

---

## Migration Status

### ✅ Completed

- [x] Core utilities (decimal, date, validation)
- [x] License models using services
- [x] Helper functions using services
- [x] Service modules created

### 🚧 In Progress

- [ ] Allotment views using AllocationService
- [ ] Frontend components using hooks

### 📋 Remaining

- [ ] bill_of_entry/models.py
- [ ] core/scripts/calculate_balance.py
- [ ] license/item_report.py simplification
- [ ] license/tables.py simplification
- [ ] Complete frontend refactoring

---

## Next Steps

1. **Phase 1**: Update allotment views to use AllocationService
2. **Phase 2**: Update bill_of_entry models to use services
3. **Phase 3**: Refactor item_report.py to use query builders
4. **Phase 4**: Update frontend components to use hooks
5. **Phase 5**: Remove deprecated functions after full migration

---

## Verification

To verify duplicate code removal is working:

```bash
# Run tests
pytest tests/

# Check for remaining duplicates
grep -r "_to_decimal" backend/ | grep "def _to_decimal"
grep -r "calculate_license_credit" backend/ | grep "def .*calculate.*credit"

# Frontend
grep -r "calculateMaxAllocation" frontend/src/ | grep "const calculateMaxAllocation"
```

---

**Status**: Duplicate code removal is in progress and showing significant improvements in code quality and
maintainability.
