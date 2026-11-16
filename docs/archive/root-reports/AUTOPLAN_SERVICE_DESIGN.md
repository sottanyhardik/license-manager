# Auto Plan Service Design — License-First Planning Integration

## Overview

The Auto Plan service enables planning licenses directly through SION norm-based rules by reusing the canonical Module 06 planning execution infrastructure. Instead of planning by SION norm ID (the traditional norm-first approach), users can plan by license ID, which automatically resolves applicable SION norms from the export manifest and executes planning through the proven planning service.

This design integrates with the existing `SionPlanningExecutionService` (Module 06) and the legacy `SionRulePlanningService` fallback, ensuring all licenses benefit from module-specific planning logic without changes to the core execution engine.

---

## Endpoints

### 1. POST /api/sion-planning-rules/plan-license/

Plan a single license through all applicable SION norms.

**Permission Required:** `LICENSE_MANAGER` role

**Request Body:**
```json
{
  "license_id": 42,
  "mode": "NEW"
}
```

**Parameters:**
- `license_id` (integer, required): Primary key of the license to plan
- `mode` (string, optional, default="NEW"): Planning mode
  - `"NEW"` — Skip licenses already planned to ≥99% balance coverage
  - `"ALL"` — Replan all licenses, even if fully planned

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
      "rules_executed": [
        { "id": 1, "version": 1, "priority": 1 }
      ],
      "write_results": [
        {
          "license_id": 42,
          "status": "PLANNED",
          "lines_written": 3
        }
      ]
    },
    {
      "sion_id": 8,
      "sion_code": "E5",
      "status": "SKIPPED_ALREADY_PLANNED"
    }
  ],
  "total_results": {
    "sions_processed": 2,
    "sions_skipped": 1,
    "total_lines_written": 3
  }
}
```

**Error Responses:**
- `400 Bad Request` — License not found, license has no export manifest, or planning failed
- `403 Forbidden` — License belongs to another company (company isolation error)

---

### 2. POST /api/sion-planning-rules/plan-licenses/

Plan multiple licenses through all applicable SION norms (bulk operation).

**Permission Required:** `LICENSE_MANAGER` role

**Request Body:**
```json
{
  "license_ids": [42, 43, 44],
  "mode": "ALL"
}
```

**Parameters:**
- `license_ids` (array of integers, required): Primary keys of licenses to plan
- `mode` (string, optional, default="NEW"): Planning mode

**Response (200 OK):**
```json
{
  "mode": "ALL",
  "licenses_processed": [
    {
      "license_id": 42,
      "license_number": "PLC/2024/0042",
      "applicable_sions": [
        {
          "sion_id": 5,
          "sion_code": "E1",
          "status": "EXECUTED",
          "write_results": [...]
        }
      ],
      "total_lines_written": 3
    },
    {
      "license_id": 43,
      "license_number": "PLC/2024/0043",
      "applicable_sions": [...],
      "total_lines_written": 5
    }
  ],
  "summary": {
    "total_licenses": 3,
    "total_sions": 5,
    "total_lines_written": 8,
    "failed_licenses": []
  }
}
```

---

## Architecture

### Data Flow

```
POST /api/sion-planning-rules/plan-license/
  ↓
SionPlanningRuleViewSet.plan_license() [NEW action]
  ↓
LoadLicenseAndResolveSions(license_id)
  └─ Query: LicenseDetailsModel.objects.get(pk=license_id)
  └─ Query: license.export_license.all()
           .values_list("norm_class_id").distinct()
  ↓
For each SION:
  │
  ├─ SionRulePlanningService.plan_sion(
  │    sion_id, license_ids=[license_id],
  │    company_id=user.company_id, mode=mode
  │  )
  │   ↓
  │   Check: SionPlanningExecutionService.supports(sion)
  │   ├─ YES → SionPlanningExecutionService.plan_sion() [Module 06]
  │   └─ NO  → SionRulePlanningService._legacy_plan() [Fallback]
  │
  └─ Persist results and collect response
  ↓
Return aggregated response
```

### Key Components

#### 1. **SionPlanningRuleViewSet** (Existing)
- Location: `/backend/apps/license/views/sion_planning_rule.py`
- Existing actions: `plan_sion()`, `preview_sion()`
- New actions:
  - `plan_license()` — Single license entry point
  - `plan_licenses()` — Bulk license entry point

#### 2. **SionRulePlanningService.plan_sion()** (Reused)
- Location: `/backend/apps/license/services/sion_rule_engine.py:459`
- Already handles Module 06 dispatch via `SionPlanningExecutionService.supports()`
- No changes required — service is agnostic to caller (norm-first or license-first)

#### 3. **SionPlanningExecutionService** (Module 06 — Reused)
- Location: `/backend/apps/license/services/sion_planning_execution.py:191`
- Canonical planning executor
- Automatically routed when `supports(sion)` returns `True`
- No changes required

#### 4. **License-to-SION Resolution** (New Helper)
Helper function in the viewset or a new service:

```python
@staticmethod
def _resolve_sions_for_license(license_id, company_id=None):
    """Load license and determine all applicable SION norms from export manifest.
    
    Returns: (license_obj, sion_ids_list)
    Raises: License not found, no export, or company isolation error
    """
    license_obj = (
        LicenseDetailsModel.objects
        .filter(pk=license_id)
        .select_related("exporter")
        .prefetch_related("export_license__norm_class")
        .first()
    )
    if not license_obj:
        raise LicenseNotFound(f"License {license_id} not found")
    
    if company_id is not None and license_obj.exporter_id != int(company_id):
        raise CompanyIsolationError(
            f"License {license_id} belongs to another company"
        )
    
    export_items = license_obj.export_license.all()
    if not export_items.exists():
        raise NoExportManifest(f"License {license_id} has no export manifest")
    
    sion_ids = sorted(set(
        item.norm_class_id
        for item in export_items
        if item.norm_class_id is not None
    ))
    
    return license_obj, sion_ids
```

---

## Implementation Details

### Step 1: Add Serializers

In `/backend/apps/license/serializers/incentive.py`:

```python
class LicenseIdOnlySerializer(serializers.Serializer):
    """Single-license planning request."""
    license_id = serializers.IntegerField(required=True, min_value=1)
    mode = serializers.ChoiceField(
        choices=("NEW", "ALL"), required=False, default="NEW"
    )


class BulkLicensePlanningSerializer(serializers.Serializer):
    """Bulk-license planning request."""
    license_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=True,
        allow_empty=False,
    )
    mode = serializers.ChoiceField(
        choices=("NEW", "ALL"), required=False, default="NEW"
    )
```

### Step 2: Add ViewSet Actions

In `/backend/apps/license/views/sion_planning_rule.py`:

```python
@action(detail=False, methods=("post",), url_path="plan-license")
def plan_license(self, request):
    """Plan a single license through all applicable SION norms."""
    request_serializer = LicenseIdOnlySerializer(data=request.data)
    request_serializer.is_valid(raise_exception=True)
    values = request_serializer.validated_data
    
    try:
        license_obj, sion_ids = self._resolve_sions_for_license(
            values["license_id"], company_id=self._company_id()
        )
    except (LicenseNotFound, CompanyIsolationError, NoExportManifest) as exc:
        return Response(exc.as_dict(), status=status.HTTP_400_BAD_REQUEST)
    
    mode = values["mode"]
    applicable_sions = []
    
    for sion_id in sion_ids:
        try:
            with transaction.atomic():
                result = SionRulePlanningService.plan_sion(
                    sion_id, license_ids=[license_obj.pk],
                    company_id=self._company_id(),
                    mode=mode,
                )
        except CompanyIsolationError as exc:
            return Response(exc.as_dict(), status=status.HTTP_403_FORBIDDEN)
        except PlanningError as exc:
            return Response(exc.as_dict(), status=status.HTTP_400_BAD_REQUEST)
        
        applicable_sions.append({
            "sion_id": sion_id,
            "sion_code": result.get("sion"),
            "status": "EXECUTED" if result.get("write_results") else "SKIPPED",
            "rules_executed": result.get("rules_executed", []),
            "write_results": result.get("write_results", []),
        })
    
    self._audit(
        "LICENSE_PLAN_EXECUTED",
        extra={
            "license_id": license_obj.pk,
            "license_number": license_obj.license_number,
            "sions_count": len(applicable_sions),
            "mode": mode,
        },
    )
    
    return Response({
        "license_id": license_obj.pk,
        "license_number": license_obj.license_number,
        "mode": mode,
        "applicable_sions": applicable_sions,
        "total_results": {
            "sions_processed": len(applicable_sions),
            "sions_executed": len([s for s in applicable_sions if s["status"] == "EXECUTED"]),
            "total_lines_written": sum(
                len(wr.get("write_results", []))
                for s in applicable_sions
                for wr in s.get("write_results", [])
            ),
        },
    })


@action(detail=False, methods=("post",), url_path="plan-licenses")
def plan_licenses(self, request):
    """Plan multiple licenses through all applicable SION norms."""
    request_serializer = BulkLicensePlanningSerializer(data=request.data)
    request_serializer.is_valid(raise_exception=True)
    values = request_serializer.validated_data
    
    license_ids = values["license_ids"]
    mode = values["mode"]
    
    # Load all licenses and collect their SIONs
    licenses_by_id = {}
    license_sions_map = {}
    all_sions = set()
    
    for license_id in license_ids:
        try:
            license_obj, sion_ids = self._resolve_sions_for_license(
                license_id, company_id=self._company_id()
            )
            licenses_by_id[license_id] = license_obj
            license_sions_map[license_id] = sion_ids
            all_sions.update(sion_ids)
        except (LicenseNotFound, CompanyIsolationError, NoExportManifest) as exc:
            return Response(
                {
                    "error": str(exc),
                    "license_id": license_id,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
    
    # Plan each SION with all its applicable licenses
    results_by_license = {lid: [] for lid in license_ids}
    sion_execution_log = []
    
    for sion_id in sorted(all_sions):
        applicable_license_ids = [
            lid for lid, sion_ids in license_sions_map.items()
            if sion_id in sion_ids
        ]
        
        try:
            with transaction.atomic():
                result = SionRulePlanningService.plan_sion(
                    sion_id, license_ids=applicable_license_ids,
                    company_id=self._company_id(),
                    mode=mode,
                )
        except CompanyIsolationError as exc:
            return Response(exc.as_dict(), status=status.HTTP_403_FORBIDDEN)
        except PlanningError as exc:
            return Response(exc.as_dict(), status=status.HTTP_400_BAD_REQUEST)
        
        sion_code = result.get("sion", "UNKNOWN")
        sion_execution_log.append({
            "sion_id": sion_id,
            "sion_code": sion_code,
            "licenses_executed": len(applicable_license_ids),
            "rules_executed": result.get("rules_executed", []),
        })
        
        # Attach results to each license
        for write_result in result.get("write_results", []):
            lid = write_result.get("license_id")
            if lid in results_by_license:
                results_by_license[lid].append({
                    "sion_id": sion_id,
                    "sion_code": sion_code,
                    "write_result": write_result,
                })
    
    # Assemble response per license
    licenses_processed = []
    total_lines = 0
    
    for license_id in license_ids:
        license_obj = licenses_by_id[license_id]
        lines_written = sum(
            len(wr.get("write_result", {}).get("write_results", []))
            for wr in results_by_license[license_id]
        )
        total_lines += lines_written
        
        licenses_processed.append({
            "license_id": license_id,
            "license_number": license_obj.license_number,
            "applicable_sions": results_by_license[license_id],
            "total_lines_written": lines_written,
        })
    
    self._audit(
        "LICENSES_PLAN_EXECUTED",
        extra={
            "licenses_count": len(license_ids),
            "sions_count": len(all_sions),
            "mode": mode,
            "total_lines": total_lines,
        },
    )
    
    return Response({
        "mode": mode,
        "licenses_processed": licenses_processed,
        "summary": {
            "total_licenses": len(license_ids),
            "total_sions": len(all_sions),
            "total_lines_written": total_lines,
            "sion_execution_log": sion_execution_log,
        },
    })
```

### Step 3: Add Helper Methods to ViewSet

```python
@staticmethod
def _resolve_sions_for_license(license_id, company_id=None):
    """Load license and determine applicable SION norms from export manifest.
    
    Returns: (license_obj, sion_ids_list)
    """
    from apps.license.services.canonical_planning_service import CompanyIsolationError
    
    license_obj = (
        LicenseDetailsModel.objects
        .filter(pk=license_id)
        .select_related("exporter")
        .prefetch_related("export_license__norm_class")
        .first()
    )
    if not license_obj:
        raise PlanningError(
            f"License {license_id} not found.",
            code="LICENSE_NOT_FOUND",
        )
    
    if company_id is not None and license_obj.exporter_id != int(company_id):
        raise CompanyIsolationError(
            f"License {license_id} belongs to another company."
        )
    
    export_items = license_obj.export_license.all()
    if not export_items.exists():
        raise PlanningError(
            f"License {license_id} has no export manifest.",
            code="NO_EXPORT_MANIFEST",
        )
    
    sion_ids = sorted(set(
        item.norm_class_id
        for item in export_items
        if item.norm_class_id is not None
    ))
    
    if not sion_ids:
        raise PlanningError(
            f"License {license_id} has no SION norms in export manifest.",
            code="NO_SION_NORMS",
        )
    
    return license_obj, sion_ids
```

### Step 4: Update Serializer Imports

In `/backend/apps/license/serializers/__init__.py`, add:
```python
from .incentive import LicenseIdOnlySerializer, BulkLicensePlanningSerializer
```

---

## Integration with Module 06

### Dispatch Logic

The new endpoints do **not** call legacy planners directly. Instead:

1. **Endpoint resolves SION(s) from license export**
   - `license.export_license.all().values_list("norm_class_id")`

2. **Calls existing `SionRulePlanningService.plan_sion(sion_id, ...)`**
   - This service already checks `SionPlanningExecutionService.supports(sion)`

3. **Module 06 handles supported norms automatically**
   - If `supports()` returns `True` → routes to `SionPlanningExecutionService.plan_sion()`
   - If `False` → falls back to legacy rule-based planning

### No Changes Required to:
- `SionPlanningExecutionService` — Already implements correct logic
- `SionRulePlanningService.plan_sion()` — Already dispatches to Module 06
- Legacy planners (E1_PLAN, E5_PLAN, E132_PLAN) — Not called directly by new endpoints

---

## Testing Strategy

### Unit Tests

1. **Test license resolution:**
   - Single SION on export manifest
   - Multiple SIONs on export manifest
   - No export manifest (error case)
   - Company isolation (error case)

2. **Test single-license planning:**
   - E1 SION with NEW mode
   - E5 SION with ALL mode
   - Multiple SIONs → multiple plan_sion calls
   - Error handling and response format

3. **Test bulk-license planning:**
   - Multiple licenses, multiple SIONs
   - Some licenses already planned (NEW mode behavior)
   - Aggregated response structure

4. **Test permission checks:**
   - LICENSE_MANAGER role required
   - Non-manager users rejected

### Integration Tests

Example structure in `/backend/apps/license/tests/test_sion_planning_execution_api.py`:

```python
def test_plan_single_license_resolves_sion_and_executes():
    """Test that plan-license endpoint resolves SION from export and plans."""
    # Setup
    sion = SionNormClassModel.objects.create(norm_class="E1", is_active=True)
    license_obj = LicenseDetailsModel.objects.create(...)
    LicenseExportItemModel.objects.create(license=license_obj, norm_class=sion)
    
    # Execute
    response = client.post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk, "mode": "NEW"},
        format="json",
    )
    
    # Assert
    assert response.status_code == 200
    assert response.data["license_id"] == license_obj.pk
    assert len(response.data["applicable_sions"]) == 1
    assert response.data["applicable_sions"][0]["sion_id"] == sion.pk


def test_plan_licenses_bulk_with_multiple_sions():
    """Test that plan-licenses endpoint plans multiple licenses with multiple SIONs."""
    # Setup
    sion_e1 = SionNormClassModel.objects.create(norm_class="E1", is_active=True)
    sion_e5 = SionNormClassModel.objects.create(norm_class="E5", is_active=True)
    
    license1 = LicenseDetailsModel.objects.create(license_number="L1", ...)
    license2 = LicenseDetailsModel.objects.create(license_number="L2", ...)
    
    LicenseExportItemModel.objects.create(license=license1, norm_class=sion_e1)
    LicenseExportItemModel.objects.create(license=license2, norm_class=sion_e5)
    
    # Execute
    response = client.post(
        "/api/sion-planning-rules/plan-licenses/",
        {"license_ids": [license1.pk, license2.pk], "mode": "ALL"},
        format="json",
    )
    
    # Assert
    assert response.status_code == 200
    assert response.data["summary"]["total_licenses"] == 2
    assert response.data["summary"]["total_sions"] == 2
```

---

## Error Handling

### License-Level Errors

| Error | HTTP | Response | Cause |
|-------|------|----------|-------|
| License not found | 400 | `{"error": "License X not found.", "code": "LICENSE_NOT_FOUND"}` | License PK doesn't exist |
| No export manifest | 400 | `{"error": "License X has no export manifest.", ...}` | License has no export items |
| No SION norms | 400 | `{"error": "License X has no SION norms...", ...}` | Export items have NULL norm_class |
| Company isolation | 403 | `{"error": "License X belongs to another company.", ...}` | User's company doesn't own license |

### Planning-Level Errors

| Error | HTTP | Response | Cause |
|-------|------|----------|-------|
| SION has no rules | 400 | `{"error": "The selected SION has no active saved rules."}` | No active rules for SION |
| Rule conflicts | 400 | `{"error": "Saved rule conflicts must be resolved...", "conflicts": [...]}` | Multiple rules match same item |
| Planning execution failure | 400 | Service-specific error dict | Adapter or computation error |

---

## Audit Trail

Both new endpoints call `_audit()` with appropriate event names:

- **Single license:** `LICENSE_PLAN_EXECUTED`
- **Bulk licenses:** `LICENSES_PLAN_EXECUTED`

Audit fields include:
- `license_id` / `licenses_count`
- `license_number` (if single)
- `sions_count`
- `mode` ("NEW" or "ALL")
- `total_lines` (total items written across all SIONs)

---

## Summary

The Auto Plan service provides a **license-first** planning interface that:

1. ✅ Loads license and resolves SION(s) from export manifest
2. ✅ Delegates to `SionRulePlanningService.plan_sion()` (unchanged)
3. ✅ Automatically routes to Module 06 when supported
4. ✅ Falls back to legacy planners for unsupported norms
5. ✅ Never calls E1_PLAN, E5_PLAN, E132_PLAN directly
6. ✅ Enforces `LICENSE_MANAGER` permission
7. ✅ Provides aggregated response with per-SION details
8. ✅ Supports both single and bulk planning
9. ✅ Maintains audit trail and company isolation

No changes are required to existing core services; the new endpoints are pure view-layer additions that compose existing pieces.
