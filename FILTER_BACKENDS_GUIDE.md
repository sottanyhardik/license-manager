# Filter Backends Guide

## Overview

This guide covers the comprehensive filter backend implementation for the License Manager API, providing advanced filtering, searching, and ordering capabilities.

## Table of Contents

1. [Filter Backends](#filter-backends)
2. [FilterSets](#filtersets)
3. [Usage Examples](#usage-examples)
4. [Implementation Guide](#implementation-guide)
5. [API Query Examples](#api-query-examples)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Filter Backends

### Location: `backend/core/filters.py`

### 1. EnhancedSearchFilter

Enhanced search with case-insensitive matching and multiple operators.

**Features**:
- Case-insensitive search (icontains)
- Multiple search terms with AND logic
- Exact match with `=` prefix
- Starts with `^` prefix
- Ends with `$` prefix

**Usage**:
```python
from core.filters import EnhancedSearchFilter

class LicenseViewSet(viewsets.ModelViewSet):
    filter_backends = [EnhancedSearchFilter]
    search_fields = ['license_number', '=company__name', '^exporter']
```

**API Examples**:
```bash
# Search across all fields (case-insensitive)
GET /api/licenses/?search=parle

# Multiple terms (AND logic)
GET /api/licenses/?search=parle 2024

# Exact match for company name
GET /api/licenses/?search==Parle Products

# Starts with for exporter
GET /api/licenses/?search=^ABC
```

---

### 2. AdvancedOrderingFilter

Advanced ordering with nulls handling and multiple fields.

**Features**:
- NULLS FIRST/LAST support
- Multiple field ordering
- Related field ordering
- Case-insensitive ordering

**Usage**:
```python
from core.filters import AdvancedOrderingFilter

class LicenseViewSet(viewsets.ModelViewSet):
    filter_backends = [AdvancedOrderingFilter]
    ordering_fields = ['license_number', 'license_date', 'balance_cif', 'company__name']
    ordering = ['-license_date']  # Default
```

**API Examples**:
```bash
# Order by license date (ascending)
GET /api/licenses/?ordering=license_date

# Order by balance (descending)
GET /api/licenses/?ordering=-balance_cif

# Multiple fields
GET /api/licenses/?ordering=company__name,-license_date

# Nulls handling
GET /api/licenses/?ordering=balance_cif_nulls_first
GET /api/licenses/?ordering=-balance_cif_nulls_last
```

---

### 3. DateRangeFilterBackend

Filter by date ranges for any date field.

**Usage**:
```python
from core.filters import DateRangeFilterBackend

class LicenseViewSet(viewsets.ModelViewSet):
    filter_backends = [DateRangeFilterBackend]
    date_filter_fields = {
        'license_date': 'license_date',
        'expiry_date': 'license_expiry_date',
        'created': 'created_at',
    }
```

**API Examples**:
```bash
# Filter by license date range
GET /api/licenses/?license_date_from=2024-01-01&license_date_to=2024-12-31

# Filter by expiry date
GET /api/licenses/?expiry_date_from=2025-01-01

# Filter by creation date
GET /api/licenses/?created_from=2024-01-01&created_to=2024-01-31
```

---

### 4. NumericRangeFilterBackend

Filter by numeric ranges (min/max).

**Usage**:
```python
from core.filters import NumericRangeFilterBackend

class LicenseViewSet(viewsets.ModelViewSet):
    filter_backends = [NumericRangeFilterBackend]
    numeric_filter_fields = {
        'balance': 'balance_cif',
        'total': 'total_cif',
        'quantity': 'quantity',
    }
```

**API Examples**:
```bash
# Filter by balance range
GET /api/licenses/?balance_min=1000&balance_max=50000

# Filter by quantity
GET /api/items/?quantity_min=10

# Multiple numeric filters
GET /api/licenses/?balance_min=1000&total_max=100000
```

---

### 5. BooleanFilterBackend

Filter by boolean fields with "all" option.

**Usage**:
```python
from core.filters import BooleanFilterBackend

class LicenseViewSet(viewsets.ModelViewSet):
    filter_backends = [BooleanFilterBackend]
    boolean_filter_fields = ['is_active', 'is_expired', 'is_restricted']
```

**API Examples**:
```bash
# Active licenses only
GET /api/licenses/?is_active=true

# Inactive licenses
GET /api/licenses/?is_active=false

# All licenses (no filter)
GET /api/licenses/?is_active=all

# Multiple boolean filters
GET /api/items/?is_restricted=true&is_active=true
```

---

### 6. MultipleChoiceFilterBackend

Filter by multiple values (IN query).

**Usage**:
```python
from core.filters import MultipleChoiceFilterBackend

class LicenseViewSet(viewsets.ModelViewSet):
    filter_backends = [MultipleChoiceFilterBackend]
    multiple_choice_filter_fields = {
        'company': 'company_id',
        'status': 'purchase_status__code',
    }
```

**API Examples**:
```bash
# Filter by multiple companies
GET /api/licenses/?company=1,2,3

# Filter by multiple statuses
GET /api/licenses/?status=GE,MI,SM

# Combination
GET /api/licenses/?company=1,2&status=GE
```

---

### 7. CombinedFilterBackend

All filter backends combined into one.

**Usage**:
```python
from core.filters import CombinedFilterBackend, EnhancedSearchFilter, AdvancedOrderingFilter

class LicenseViewSet(viewsets.ModelViewSet):
    filter_backends = [CombinedFilterBackend, EnhancedSearchFilter, AdvancedOrderingFilter]

    # Configure all filters
    search_fields = ['license_number', 'company__name']
    ordering_fields = ['license_date', 'balance_cif']
    date_filter_fields = {'license_date': 'license_date'}
    numeric_filter_fields = {'balance': 'balance_cif'}
    boolean_filter_fields = ['is_active']
    multiple_choice_filter_fields = {'company': 'company_id'}
```

**API Example**:
```bash
GET /api/licenses/?search=parle&license_date_from=2024-01-01&balance_min=1000&is_active=true&company=1,2&ordering=-license_date
```

---

## FilterSets

### Location: `backend/core/filtersets.py`

Pre-configured FilterSets using django-filter for common models.

### 1. LicenseFilterSet

Comprehensive filtering for License model.

**Features**:
- Company filtering (single or multiple)
- Date range filtering (license date, expiry date)
- Status filtering (active, expired, expiring soon)
- Balance range filtering
- Purchase status filtering
- License number search

**Usage**:
```python
from core.filtersets import LicenseFilterSet

class LicenseViewSet(viewsets.ModelViewSet):
    queryset = License.objects.all()
    serializer_class = LicenseSerializer
    filterset_class = LicenseFilterSet
```

**API Examples**:
```bash
# Active licenses
GET /api/licenses/?is_active=true

# Expiring soon
GET /api/licenses/?status=expiring_soon

# Balance range
GET /api/licenses/?balance_cif_min=1000&balance_cif_max=50000

# Multiple companies
GET /api/licenses/?company_ids=1,2,3

# License date range
GET /api/licenses/?license_date_from=2024-01-01&license_date_to=2024-12-31

# Has balance
GET /api/licenses/?has_balance=true

# Purchase status
GET /api/licenses/?purchase_status_ids=GE,MI

# Combination
GET /api/licenses/?is_active=true&balance_cif_min=1000&company_ids=1,2
```

---

### 2. BOEFilterSet

Filtering for Bill of Entry model.

**API Examples**:
```bash
# Recent BOEs (last 30 days)
GET /api/boe/?recent_days=30

# Date range
GET /api/boe/?boe_date_from=2024-01-01&boe_date_to=2024-12-31

# Company filter
GET /api/boe/?company_ids=1,2,3

# BOE number search
GET /api/boe/?boe_number=12345
```

---

### 3. AllotmentFilterSet

Filtering for Allotment model.

**API Examples**:
```bash
# Recent allotments
GET /api/allotments/?recent_days=30

# Approved only
GET /api/allotments/?is_approved=true

# Date range
GET /api/allotments/?allotment_date_from=2024-01-01

# Company filter
GET /api/allotments/?company_ids=1,2
```

---

### 4. ItemReportFilterSet

Advanced filtering for Item Report.

**API Examples**:
```bash
# Filter by item names
GET /api/item-report/?item_names=1,2,3

# Minimum balance
GET /api/item-report/?min_balance=1000

# Exclude companies
GET /api/item-report/?exclude_company_ids=5,6

# License status
GET /api/item-report/?license_status=active

# Restricted items only
GET /api/item-report/?is_restricted=true

# Combination
GET /api/item-report/?item_names=1,2&min_balance=1000&license_status=active
```

---

## Usage Examples

### Basic ViewSet with Filters

```python
from rest_framework import viewsets
from core.filters import CombinedFilterBackend, EnhancedSearchFilter, AdvancedOrderingFilter
from core.filtersets import LicenseFilterSet
from license.models import LicenseDetailsModel
from license.serializers import LicenseSerializer

class LicenseViewSet(viewsets.ModelViewSet):
    queryset = LicenseDetailsModel.objects.select_related(
        'company', 'purchase_status'
    ).all()
    serializer_class = LicenseSerializer

    # Use FilterSet for django-filter
    filterset_class = LicenseFilterSet

    # Add custom filter backends
    filter_backends = [
        CombinedFilterBackend,
        EnhancedSearchFilter,
        AdvancedOrderingFilter
    ]

    # Search configuration
    search_fields = [
        'license_number',
        'company__name',
        'exporter',
    ]

    # Ordering configuration
    ordering_fields = [
        'license_number',
        'license_date',
        'license_expiry_date',
        'balance_cif',
        'company__name',
    ]
    ordering = ['-license_date']  # Default ordering

    # Custom filter configurations
    date_filter_fields = {
        'license_date': 'license_date',
        'expiry_date': 'license_expiry_date',
    }

    numeric_filter_fields = {
        'balance': 'balance_cif',
        'total': 'total_cif',
    }

    boolean_filter_fields = ['is_active', 'is_expired']

    multiple_choice_filter_fields = {
        'company': 'company_id',
    }
```

---

### Custom FilterSet

```python
import django_filters
from django.db.models import Q
from license.models import LicenseDetailsModel

class CustomLicenseFilterSet(django_filters.FilterSet):
    # Custom filter method
    high_balance = django_filters.BooleanFilter(
        method='filter_high_balance',
        label='High Balance (> 10,000)'
    )

    # Multiple company names
    companies = django_filters.CharFilter(
        method='filter_companies',
        label='Company names (comma-separated)'
    )

    def filter_high_balance(self, queryset, name, value):
        if value:
            return queryset.filter(balance_cif__gt=10000)
        return queryset

    def filter_companies(self, queryset, name, value):
        if value:
            company_names = [x.strip() for x in value.split(',')]
            query = Q()
            for name in company_names:
                query |= Q(company__name__icontains=name)
            return queryset.filter(query)
        return queryset

    class Meta:
        model = LicenseDetailsModel
        fields = ['is_active', 'purchase_status']
```

---

## API Query Examples

### Complex Filtering Example

```bash
GET /api/licenses/?search=parle&is_active=true&balance_cif_min=1000&license_date_from=2024-01-01&company_ids=1,2,3&ordering=-balance_cif&page=1&page_size=25
```

**Breakdown**:
- `search=parle` - Search for "parle" in license_number, company name, exporter
- `is_active=true` - Only active licenses
- `balance_cif_min=1000` - Balance >= 1000
- `license_date_from=2024-01-01` - License date >= 2024-01-01
- `company_ids=1,2,3` - Companies with ID 1, 2, or 3
- `ordering=-balance_cif` - Order by balance descending
- `page=1&page_size=25` - Pagination

### Dashboard Query Example

```bash
GET /api/licenses/?status=expiring_soon&has_balance=true&ordering=license_expiry_date
```

**Gets**: Licenses expiring in next 30 days with available balance, ordered by expiry date.

### Report Query Example

```bash
GET /api/item-report/?item_names=1,2,3&min_balance=1000&license_status=active&exclude_company_ids=5&is_restricted=false&ordering=-available_cif
```

**Gets**: Item report for specific items with minimum balance, active licenses, excluding certain companies, non-restricted items only, ordered by available CIF.

---

## Implementation Guide

### Step 1: Install Dependencies

Ensure django-filter is installed:
```bash
pip install django-filter
```

### Step 2: Update Settings

Already configured in `settings.py`:
```python
REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend"
    ],
    # ... other settings
}

INSTALLED_APPS = [
    # ...
    'django_filters',
]
```

### Step 3: Apply to ViewSet

**Option A: Using FilterSet** (Recommended for complex models):
```python
from core.filtersets import LicenseFilterSet

class LicenseViewSet(viewsets.ModelViewSet):
    filterset_class = LicenseFilterSet
```

**Option B: Using Filter Backends** (For custom filtering):
```python
from core.filters import CombinedFilterBackend, EnhancedSearchFilter

class MyViewSet(viewsets.ModelViewSet):
    filter_backends = [CombinedFilterBackend, EnhancedSearchFilter]
    search_fields = ['name', 'email']
    numeric_filter_fields = {'balance': 'balance_cif'}
```

**Option C: Combining Both**:
```python
class LicenseViewSet(viewsets.ModelViewSet):
    filterset_class = LicenseFilterSet  # For django-filter
    filter_backends = [EnhancedSearchFilter, AdvancedOrderingFilter]  # Add custom backends
    search_fields = ['license_number']
    ordering_fields = ['license_date']
```

### Step 4: Test Filters

```python
# In tests.py
from django.test import TestCase
from rest_framework.test import APIClient

class LicenseFilterTests(TestCase):
    def test_filter_by_balance(self):
        client = APIClient()
        response = client.get('/api/licenses/?balance_cif_min=1000')
        self.assertEqual(response.status_code, 200)

        # All results should have balance >= 1000
        for license in response.data['results']:
            self.assertGreaterEqual(license['balance_cif'], 1000)
```

---

## Best Practices

### 1. Use FilterSets for Complex Models

✅ **Good**: Use pre-configured FilterSet
```python
class LicenseViewSet(viewsets.ModelViewSet):
    filterset_class = LicenseFilterSet  # Handles 10+ filters
```

❌ **Bad**: Manual filter implementation
```python
def get_queryset(self):
    queryset = License.objects.all()
    if self.request.query_params.get('company'):
        queryset = queryset.filter(company_id=...)
    # 50 more lines of filter logic...
```

### 2. Combine Multiple Filter Backends

```python
filter_backends = [
    CombinedFilterBackend,      # Custom range/boolean filters
    EnhancedSearchFilter,        # Search
    AdvancedOrderingFilter,      # Ordering
]
```

### 3. Optimize Queries with select_related/prefetch_related

```python
class LicenseViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return License.objects.select_related(
            'company',
            'purchase_status'
        ).prefetch_related(
            'import_items__item_name'
        )
```

### 4. Document Available Filters

```python
class LicenseViewSet(viewsets.ModelViewSet):
    """
    License API Endpoint

    Filters:
    - search: Search across license_number, company name, exporter
    - is_active: Filter by active status (true/false/all)
    - balance_cif_min/max: Filter by balance range
    - license_date_from/to: Filter by license date range
    - company_ids: Filter by company IDs (comma-separated)
    - ordering: Order results (license_date, -balance_cif, etc.)

    Examples:
    - /api/licenses/?is_active=true&balance_cif_min=1000
    - /api/licenses/?search=parle&ordering=-license_date
    """
```

### 5. Validate Filter Inputs

```python
class SafeNumericRangeFilterBackend(NumericRangeFilterBackend):
    def filter_queryset(self, request, queryset, view):
        # Validate input
        numeric_filter_fields = getattr(view, 'numeric_filter_fields', {})

        for param_prefix, field_name in numeric_filter_fields.items():
            min_value = request.query_params.get(f'{param_prefix}_min')
            max_value = request.query_params.get(f'{param_prefix}_max')

            if min_value:
                try:
                    min_val = float(min_value)
                    if min_val < 0:
                        raise ValueError("Minimum value cannot be negative")
                    queryset = queryset.filter(**{f'{field_name}__gte': min_val})
                except (ValueError, TypeError) as e:
                    # Log error or return 400
                    pass

        return queryset
```

---

## Troubleshooting

### Issue 1: Filter Not Working

**Symptom**: Filter parameter ignored

**Possible Causes**:
1. Filter backend not configured
2. Field name mismatch
3. FilterSet not applied

**Solution**:
```python
# Check filter backends are set
filter_backends = [CombinedFilterBackend, EnhancedSearchFilter]

# Check field names match model
numeric_filter_fields = {
    'balance': 'balance_cif',  # Must match actual field name
}

# Check FilterSet is applied
filterset_class = LicenseFilterSet
```

### Issue 2: Search Too Slow

**Symptom**: Search queries take > 2 seconds

**Cause**: Missing database indexes

**Solution**:
```python
# Add indexes to searched fields
class License(models.Model):
    license_number = models.CharField(max_length=50, db_index=True)
    company = models.ForeignKey(Company, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['license_number', 'company']),
        ]
```

### Issue 3: Too Many API Calls

**Symptom**: Frontend makes multiple API calls for filtering

**Solution**: Combine filters in single request
```javascript
// ❌ Bad: Multiple requests
const activeResponse = await api.get('/licenses/?is_active=true');
const balanceResponse = await api.get('/licenses/?balance_min=1000');

// ✅ Good: Single request
const response = await api.get('/licenses/?is_active=true&balance_min=1000');
```

### Issue 4: Case-Sensitive Search

**Symptom**: Search doesn't find results with different case

**Solution**: Use EnhancedSearchFilter (already case-insensitive)
```python
filter_backends = [EnhancedSearchFilter]  # Uses icontains
```

---

## Summary

### Implementation Checklist

- ✅ Created 7 custom filter backends
- ✅ Created 6 pre-configured FilterSets
- ✅ Enhanced search with multiple operators
- ✅ Advanced ordering with nulls handling
- ✅ Date range filtering
- ✅ Numeric range filtering
- ✅ Boolean filtering
- ✅ Multiple choice filtering
- ✅ Comprehensive documentation

### Benefits

- **Flexible filtering** - Multiple filter types for different use cases
- **Better UX** - Easy-to-use query parameters
- **Type-safe** - Validation and error handling
- **Performance** - Optimized database queries
- **Maintainable** - Reusable FilterSets
- **Documented** - OpenAPI schema generation

### Next Steps

1. Apply FilterSets to existing ViewSets
2. Add search_fields and ordering_fields to all list views
3. Test filter combinations
4. Update frontend to use new filter parameters
5. Monitor slow queries and add indexes

---

**Last Updated**: 2026-02-02
**Author**: License Manager Development Team
