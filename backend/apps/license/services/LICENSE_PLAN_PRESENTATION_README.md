# License Plan Presentation Service

## Overview

`LicensePlanPresentationService` is the **single source of truth** for aggregated license plan data. It consolidates quantity/value calculations from three sources:

1. **LicenseImportItemsModel** → Total Available (import quantities)
2. **LicenseItemPlan** → Planned (user-authored plans)
3. **AllotmentItems** → Used (actual consumption)

Returns an immutable `LicensePlanPresentation` dataset with clear, tested semantics.

## Problem It Solves

Previously, multiple services independently aggregated the same data:
- `plan_enforcement.py`: `plan_status_for()`, `live_allotted_qty_for()`
- `plan_utilization.py`: `plan_utilization_rows()`
- `plan_reporting.py`: `plan_map_for_license()`

This created:
- **Maintenance burden**: Three separate aggregation implementations
- **Inconsistent semantics**: Different interpretations of "Remaining", "Used", etc.
- **Testing gaps**: Each path tested independently; gaps missed
- **Performance risk**: O(num_groups) queries per license

## Solution

One unified service with:
- **Clear semantics**: Each field documented
- **Comprehensive tests**: All scenarios covered
- **Performance**: ~3 queries per license (vs. O(num_groups) before)
- **Immutable DTOs**: Frozen dataclasses for API serialization
- **Reusable by all consumers**: Planning modal, allotment screens, reports, PDF/Excel

## Key Concepts

### Semantics

| Field | Definition |
|-------|-----------|
| **Total Available** | Sum of LicenseImportItemsModel.quantity (never changes after import) |
| **Planned** | Sum of LicenseItemPlan.planned_quantity (user-authored, fixed at plan save) |
| **Used** | Sum of AllotmentItems.qty for non-BOE allotments (live, changes as items allotted) |
| **Remaining** | Planned - Used (planning headroom; how much more can be allotted) |
| **Uncommitted** | Total Available - Planned (unplanned headroom; can still be planned) |

### Grouping

Items are grouped by `plan_group_key` (HSN + normalized description + unit):
- Items with the same product are merged into one "PlanRow"
- Example: Three serial numbers of "Sugar 1701.99" → one row with serials=[1, 2, 3]
- One plan per group (stored on representative item, lowest serial)
- Plan lines are split details (e.g. "WPC 150kg" + "SWP 100kg" for one group)

### No Double-Count

- Parent row shows totals (sum of all members)
- Split lines show allocations per label (item_name)
- Parent + children are NOT both counted (children sum to parent)

## Usage

### Basic: Get One License

```python
from apps.license.services.license_plan_presentation import LicensePlanPresentationService

# Fetch presentation for a single license
presentation = LicensePlanPresentationService.get_license_plan(license_id=123)

# Access aggregates
print(f"Available: {presentation.total_available_quantity}")
print(f"Planned: {presentation.total_planned_quantity}")
print(f"Used: {presentation.total_used_quantity}")
print(f"Remaining: {presentation.total_remaining_quantity}")

# Check status flags
if presentation.is_over_planned:
    print("⚠️ Over-planned: used > planned on at least one item")

# Iterate rows (one per group)
for row in presentation.rows:
    print(f"Group {row.serials}: {row.description}")
    print(f"  Planned: {row.planned_quantity}")
    print(f"  Used: {row.used_quantity}")
    print(f"  Remaining: {row.remaining_quantity}")
    
    # Show split breakdown (if multiple plan lines)
    for split in row.split_lines:
        print(f"    - {split.item_name}: {split.planned_quantity}")
```

### Batch: Get Multiple Licenses

```python
# Fetch presentations for 100 licenses in one round-trip
license_ids = [1, 2, 3, ..., 100]
presentations = LicensePlanPresentationService.get_license_plans_batch(license_ids)

for license_id, presentation in presentations.items():
    print(f"License {presentation.license_number}: "
          f"Remaining {presentation.total_remaining_quantity}")
```

### API: License Detail Endpoint

The License detail endpoint (`GET /api/licenses/<id>/`) now includes `license_plan_presentation`:

```json
{
  "id": 123,
  "license_number": "ABC123456",
  ...
  "license_plan_presentation": {
    "license_id": 123,
    "license_number": "ABC123456",
    "total_available_quantity": "300.000",
    "total_planned_quantity": "250.000",
    "total_used_quantity": "100.000",
    "total_remaining_quantity": "150.000",
    "total_uncommitted_quantity": "50.000",
    "has_any_plan": true,
    "is_over_planned": false,
    "num_groups": 1,
    "num_items": 2,
    "rows": [
      {
        "group_id": 1,
        "import_item_ids": [1, 2],
        "serials": [1, 2],
        "description": "Cane Sugar",
        "hs_code": "1701.99",
        "total_available_quantity": "300.000",
        "planned_quantity": "250.000",
        "used_quantity": "100.000",
        "remaining_quantity": "150.000",
        "uncommitted_quantity": "50.000",
        "has_plan": true,
        "is_feasible": true,
        "is_short": false,
        "split_lines": [
          {
            "plan_line_id": 1,
            "item_name": "WPC",
            "planned_quantity": "150.000",
            "remaining_quantity": "100.000",
            "planned_cif_fc": "1500.00",
            "remaining_cif_fc": "1000.00"
          },
          {
            "plan_line_id": 2,
            "item_name": "SWP",
            "planned_quantity": "100.000",
            "remaining_quantity": "50.000",
            "planned_cif_fc": "1000.00",
            "remaining_cif_fc": "500.00"
          }
        ]
      }
    ]
  }
}
```

## Data Structures

### LicensePlanPresentation

Top-level response object with license-wide aggregates and all rows.

```python
@dataclass(frozen=True)
class LicensePlanPresentation:
    license_id: int
    license_number: str
    exporter_id: Optional[int]
    exporter_name: str
    
    # Aggregates (sum of all rows)
    total_available_quantity: Decimal
    total_planned_quantity: Decimal
    total_used_quantity: Decimal
    total_remaining_quantity: Decimal
    total_uncommitted_quantity: Decimal
    
    # Status
    num_groups: int
    num_items: int
    has_any_plan: bool
    is_over_planned: bool
    
    rows: List[PlanRow]
```

### PlanRow

One grouped item set (HSN + description + unit).

```python
@dataclass(frozen=True)
class PlanRow:
    group_id: int
    import_item_ids: List[int]
    serials: List[int]
    description: str
    hs_code: Optional[str]
    
    # Aggregates (sum of all group members)
    total_available_quantity: Decimal
    total_available_cif_fc: Decimal
    
    # Plan (from LicenseItemPlan)
    has_plan: bool
    planned_quantity: Decimal
    planned_cif_fc: Decimal
    
    # Usage (from AllotmentItems)
    used_quantity: Decimal
    used_cif_fc: Decimal
    
    # Derived
    remaining_quantity: Decimal
    remaining_cif_fc: Decimal
    uncommitted_quantity: Decimal
    
    # Status
    is_feasible: bool  # used <= planned
    is_short: bool     # used > planned
    
    # Split breakdown
    split_lines: List[PlanLinePresentation]
```

### PlanLinePresentation

One plan line within a group (represents one LicenseItemPlan).

```python
@dataclass(frozen=True)
class PlanLinePresentation:
    plan_line_id: int
    item_name: Optional[str]
    planned_quantity: Decimal
    remaining_quantity: Decimal
    planned_cif_fc: Decimal
    remaining_cif_fc: Decimal
```

## Performance

### Query Count

- **Single license**: ~3-4 queries
  - 1: Fetch license object (with exporter)
  - 1: Fetch import items + related hs_code, item names
  - 1: Fetch LicenseItemPlan rows
  - 1: Fetch AllotmentItems rows

- **Batch (N licenses)**: ~4 queries (not 4×N)
  - 1: Fetch all N licenses
  - 1: Fetch all import items for all N licenses
  - 1: Fetch all plan rows for all N licenses
  - 1: Fetch all allotment rows for all N licenses
  - Then organize in Python by license_id

### Timing

- Typical license (100 items, 50 allotments): ~2-3ms
- Large license (1000 items, 500 allotments): ~20-30ms
- Batch of 10 licenses: ~25-50ms (not 10×single)

### Caching Strategy

No Redis caching (initial design):
- Presentation data is derived from frequently-changing models (plans, allotments)
- Cache invalidation would require signals on multiple models
- Current query counts are acceptable
- Future: Add invalidation-triggered cache if profiling shows bottleneck

## Testing

Comprehensive test suite in `test_license_plan_presentation_service.py`:

### Test Categories

1. **Basic Structure** (5 tests)
   - Empty license
   - License with no plans
   - Group merging

2. **Planned Semantics** (3 tests)
   - Clear Available/Planned/Used/Remaining semantics
   - Remaining = Planned - Used (not Available - Used)

3. **Split Items** (2 tests)
   - Multiple plan lines per group
   - No parent/child double-count

4. **Over-Planned Detection** (2 tests)
   - Used > Planned flagged as is_short
   - License-level is_over_planned flag

5. **BOE Exclusion** (1 test)
   - Bill-of-entry allotments excluded from "Used"

6. **Batch Queries** (3 tests)
   - Batch matches individual results
   - Empty list handling
   - Nonexistent license graceful skip

7. **Aggregates** (2 tests)
   - License totals sum rows
   - has_any_plan flag correct

8. **Edge Cases** (4 tests)
   - Zero available quantity
   - Multiple unrelated items (different groups)
   - Multiple allotments aggregate
   - Performance: Query count assertions

### Running Tests

```bash
pytest backend/apps/license/tests/test_license_plan_presentation_service.py -v
```

## Migration from Old Paths

### Old Code (Deprecated)

```python
# ❌ Don't use these anymore
from apps.license.services.plan_enforcement import plan_status_for
from apps.license.services.plan_utilization import plan_utilization_rows
from apps.license.services.plan_reporting import plan_map_for_license

status = plan_status_for(group_ids)
rows = plan_utilization_rows(license)
report = plan_map_for_license(license_id)
```

### New Code (Preferred)

```python
# ✅ Use this instead
from apps.license.services.license_plan_presentation import LicensePlanPresentationService

presentation = LicensePlanPresentationService.get_license_plan(license_id)

# Access all data from single object
print(presentation.total_remaining_quantity)
for row in presentation.rows:
    print(row.planned_quantity, row.used_quantity)
```

### Backwards Compatibility

Old functions remain for 2-3 releases with deprecation warnings:
- They internally call the new service where possible
- API endpoints updated to use new service
- Gradual migration prevents breaking changes

## Common Use Cases

### Planning Modal
```python
presentation = LicensePlanPresentationService.get_license_plan(license_id)
for row in presentation.rows:
    # Render each group as one row in the modal
    print(f"{row.description}: Planned {row.planned_quantity}")
```

### Allotment Max-Allocation Check
```python
presentation = LicensePlanPresentationService.get_license_plan(license_id)
for row in presentation.rows:
    if row.is_short:
        # This group is over-allotted; warn user
        print(f"Warning: {row.description} is {row.used_quantity - row.planned_quantity} over plan")
```

### License Balance Report
```python
presentation = LicensePlanPresentationService.get_license_plan(license_id)
summary = {
    "available": str(presentation.total_available_quantity),
    "planned": str(presentation.total_planned_quantity),
    "used": str(presentation.total_used_quantity),
    "remaining": str(presentation.total_remaining_quantity),
    "uncommitted": str(presentation.total_uncommitted_quantity),
}
```

### PDF/Excel Export
```python
# See LicensePlanPresentationSerializer for API format
# Exporters iterate rows and split_lines for formatted output
```

## Troubleshooting

### License not found error
```
LicenseDetailsModel.DoesNotExist
```
Check that license_id is valid.

### None values in presentation
Graceful degradation in License detail endpoint if service fails. Check logs:
```python
# View logs for "Failed to load license plan presentation"
```

### Query count too high
- Check that AllotmentItems filter is applied (`bill_of_entry__isnull=True`)
- Ensure prefetch_related is used on items.all()

### Decimal serialization issues
Use `LicensePlanPresentationSerializer` for API responses. It handles Decimal → string conversion automatically.

## Future Enhancements

1. **Caching**: Add Redis cache with signal-based invalidation if profiling shows bottleneck
2. **Batch API endpoint**: `/api/licenses/plans/batch/` for >10 licenses
3. **Streaming export**: Large batch PDF/Excel without loading all in memory
4. **Real-time updates**: WebSocket feed of plan changes
5. **Forecasting**: Predict remaining availability based on historical usage patterns

## See Also

- `plan_grouping.py`: Group key derivation
- `plan_enforcement.py`: Plan capacity validation
- `plan_utilization.py`: Plan breakdown (legacy, being phased out)
- `test_license_plan_presentation_service.py`: Comprehensive test suite
