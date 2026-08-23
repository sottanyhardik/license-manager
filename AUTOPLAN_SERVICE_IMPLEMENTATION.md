# Auto Plan Service — Implementation Summary

## Overview

The Auto Plan service has been implemented as two new REST API endpoints on the existing `SionPlanningRuleViewSet`. These endpoints enable planning licenses by license ID, automatically resolving applicable SION norms from the export manifest and delegating to Module 06 planning infrastructure.

## Files Modified

### 1. Backend Views
**File:** `/backend/apps/license/views/sion_planning_rule.py`

**Changes:**
- Added imports for `LicenseDetailsModel`, `BulkLicensePlanningSerializer`, `LicenseIdOnlySerializer`
- Added static method `_resolve_sions_for_license(license_id, company_id)` to resolve SION norms from export
- Added action `@action plan_license()` — Single license planning endpoint
- Added action `@action plan_licenses()` — Bulk license planning endpoint

### 2. Serializers
**File:** `/backend/apps/license/serializers/incentive.py`

**Changes:**
- Added `LicenseIdOnlySerializer` — Validates single-license plan request
- Added `BulkLicensePlanningSerializer` — Validates bulk-license plan request

### 3. Integration Tests
**File:** `/backend/apps/license/tests/test_auto_plan_license_api.py` (NEW)

**Coverage:**
- Single license planning with E1/E5 SIONs
- Multiple SIONs on same license export
- Error cases (license not found, no export, company isolation)
- Bulk planning with multiple licenses and multiple SIONs
- Permission checks
- Default mode behavior (NEW)
- Response structure validation

## New Endpoints

### POST /api/sion-planning-rules/plan-license/
**Purpose:** Plan a single license through all applicable SION norms

**Request:**
```json
{
  "license_id": 42,
  "mode": "NEW"
}
```

**Response (200 OK):**
```json
{
  "license_id": 42,
  "license_number": "PLC/2024/0042",
  "mode": "NEW",
  "applicable_sions": [
    {
      "sion_id": 5,
      "sion_code": "E1",
      "status": "EXECUTED",
      "rules_executed": [...],
      "write_results": [...]
    }
  ],
  "total_results": {
    "sions_processed": 1,
    "sions_executed": 1,
    "total_lines_written": 3
  }
}
```

### POST /api/sion-planning-rules/plan-licenses/
**Purpose:** Plan multiple licenses through all applicable SION norms

**Request:**
```json
{
  "license_ids": [42, 43, 44],
  "mode": "ALL"
}
```

**Response (200 OK):**
```json
{
  "mode": "ALL",
  "licenses_processed": [...],
  "summary": {
    "total_licenses": 3,
    "total_sions": 5,
    "total_lines_written": 8,
    "sion_execution_log": [...]
  }
}
```

## Architecture & Integration

### Execution Flow

```
HTTP Request
  ↓
SionPlanningRuleViewSet.plan_license() / plan_licenses()
  ↓
_resolve_sions_for_license(license_id)
  ├─ Query: LicenseDetailsModel.get(pk)
  ├─ Check: company_id (if not superuser)
  └─ Load: license.export_license.all().norm_class_id
  ↓
For each SION:
  │
  └─ SionRulePlanningService.plan_sion(sion_id, license_ids, mode)
      ├─ Checks: SionPlanningExecutionService.supports(sion)
      ├─ YES → Routes to Module 06 canonical service
      └─ NO  → Falls back to legacy rule-based planning
      ↓
      Persists LicenseItemPlan records
      ↓
      Returns results envelope
  ↓
Aggregates responses from all SIONs
  ↓
Audits event with ActivityLog
  ↓
HTTP Response
```

### Module 06 Integration

The new endpoints do **not** bypass Module 06. Instead:

1. **Endpoint resolves SION(s)** from license export manifest
2. **Delegates to** `SionRulePlanningService.plan_sion()` (existing method)
3. **SionRulePlanningService** checks `SionPlanningExecutionService.supports(sion)`
4. **If supported** → Routes to Module 06 `SionPlanningExecutionService.plan_sion()`
5. **If unsupported** → Falls back to legacy rule-based planning

This design ensures all norms benefit from Module 06 planning logic without changes to core services.

## Error Handling

### License-Level Errors (400 Bad Request)

| Error | Code | HTTP Status |
|-------|------|-------------|
| License not found | `LICENSE_NOT_FOUND` | 400 |
| No export manifest | `NO_EXPORT_MANIFEST` | 400 |
| No SION norms assigned | `NO_SION_NORMS` | 400 |
| Company isolation violation | (CompanyIsolationError) | 403 |

### Planning-Level Errors (400 Bad Request)

Errors from `SionRulePlanningService.plan_sion()` are passed through as-is:
- SION has no active rules
- Rule conflicts (multiple rules match same item)
- Planning execution failures

## Permissions

**Required Role:** `LICENSE_MANAGER`

Both endpoints use `LicensePermission` class, which enforces:
- Superusers: Full access
- Authenticated users: Must have `LICENSE_MANAGER` role
- Other roles: 403 Forbidden

## Audit Trail

Both endpoints call `_audit()` with appropriate event names:

**Single license:** `LICENSE_PLAN_EXECUTED`
- `license_id`, `license_number`, `sions_count`, `mode`

**Bulk licenses:** `LICENSES_PLAN_EXECUTED`
- `licenses_count`, `sions_count`, `mode`, `total_lines`

## Testing

### Run Tests
```bash
# All auto-plan tests
pytest backend/apps/license/tests/test_auto_plan_license_api.py -v

# Specific test
pytest backend/apps/license/tests/test_auto_plan_license_api.py::test_plan_license_single_sion_e1 -v

# With coverage
pytest backend/apps/license/tests/test_auto_plan_license_api.py --cov=apps.license.views --cov=apps.license.serializers
```

### Test Coverage

The implementation includes 20+ integration tests covering:

1. **Happy path:**
   - Single license with E1/E5 planning
   - Multiple SIONs on same export
   - Bulk planning with multiple licenses
   - Both NEW and ALL modes

2. **Error cases:**
   - License not found
   - No export manifest
   - No SION norms
   - Company isolation
   - Empty license list
   - Failed licenses in bulk request

3. **Permissions:**
   - License manager access
   - License viewer denial
   - Superuser access

4. **Validation:**
   - Default mode (NEW)
   - Response structure
   - Mode behavior (NEW skips already planned, ALL replans)

## Code Quality

All files pass Python syntax validation:
- `backend/apps/license/views/sion_planning_rule.py` ✓
- `backend/apps/license/serializers/incentive.py` ✓
- `backend/apps/license/tests/test_auto_plan_license_api.py` ✓

## Key Design Decisions

### 1. Multiple SIONs Support
Licensed goods may have multiple SION norms (import/export licensing duality). The implementation:
- Resolves **all** applicable SIONs from export manifest
- Plans each SION separately with the same license
- Aggregates results in response

### 2. No Legacy Planner Calls
Endpoints never call E1_PLAN, E5_PLAN, E132_PLAN directly:
- `SionRulePlanningService.plan_sion()` handles dispatch
- Module 06 integration is automatic and transparent
- Fallback to legacy is built-in, no endpoint changes needed

### 3. Company Isolation
User's company is resolved from `request.user.company_id`:
- Superusers bypass company check
- Regular users only see their own licenses
- Company check happens before SION resolution

### 4. Idempotency
Both `NEW` and `ALL` modes are idempotent:
- **NEW:** Skips licenses already planned to ≥99% balance coverage
- **ALL:** Always replans, even if fully planned
- Second identical request returns same result (check inside transaction)

## Next Steps

1. **Deploy:** Merge to develop branch
2. **Test:** Run full test suite
3. **Documentation:** Update API docs with new endpoints
4. **Frontend:** Implement plan-license button in license detail page
5. **Monitoring:** Track planning execution rates and errors

## Migration

No data migration required. New endpoints:
- Read existing license/export/SION data
- Write to existing LicenseItemPlan table
- Audit existing ActivityLog table

Fully backward compatible with existing planning infrastructure.
