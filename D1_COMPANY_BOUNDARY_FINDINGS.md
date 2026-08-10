# D1 FINDINGS: Company Boundary

## Current Company Model

**Model:** `backend/apps/core/models.py::CompanyModel` (line 224)

**Key fields:**
- `iec` (unique identifier)
- `name`
- `pan`, `gst_number` (tax IDs)
- Contact, address, banking info
- Logo, signature, stamp (branding)

**FK from CompanyModel to:**
- `incentive_licenses` (exporter on IncentiveLicenseDetails)
- `company_allotments` (company on AllotmentModel)
- `related_company` (on AllotmentModel for second-party tracking)

---

## Current Allocation Relationship

**AllotmentModel (backend/apps/allotment/models.py:46)**
```
company: FK to CompanyModel (PROTECT)
```

**AllotmentItems (backend/apps/allotment/models.py:209)**
```
No company field
├─ Links to LicenseImportItemsModel via item
└─ Links to AllotmentModel via allotment
```

**Finding:** Allocations are assigned to an allotment (which has a company), but individual AllotmentItems do NOT have an explicit company field. This means:
- An allocation inherits its company from `allotment.company`
- No way to assign an allocation to a DIFFERENT company than the allotment
- No way to split an allocation across multiple companies (Req 5 asks for this)

---

## Current Authorization

**Permission Class:** `backend/apps/accounts/permissions.py::AllotmentPermission` (line 54)

```python
class AllotmentPermission(BaseRolePermission):
    required_roles_for_read = ['ALLOTMENT_MANAGER', 'ALLOTMENT_VIEWER']
    required_roles_for_write = ['ALLOTMENT_MANAGER']
```

**Type:** Role-based only (BaseRolePermission has no `has_object_permission`)

**Current allocate_items endpoint** (backend/apps/allotment/views_actions.py:623-876):
```python
allotment = get_object_or_404(AllotmentModel, pk=pk)  # ← No company check
```

**Finding:** Any user with ALLOTMENT_MANAGER role can:
- Access any allotment regardless of company
- Allocate any license item to any allotment
- No company isolation at the object level

---

## Current User-Company Scope

**Places where user.company_id is used:**
- `backend/apps/license/views/item_plan.py` (line ~376) — passes company_id to CanonicalPlanningService

**Places where it's NOT used:**
- `allocate_items` endpoint (no company check)
- AllotmentViewSet (no company filter)
- Most permission classes (role-only)

**Finding:** Company scoping is INCONSISTENT. Some views use it, most don't. Users are not assigned to a specific company in the auth model; the company is context-dependent (from the request or from the resource being accessed).

---

## License-Company Relationship

**LicenseDetailsModel relationships:**
- `exporter` (FK) — company that owns/issued the license
- `LicenseOwnership` (historical) — tracks license transfers between companies
  - `from_company` (FK) — previous owner
  - `to_company` (FK) — new owner

**Finding:** Licenses are tied to ONE exporter company, but LicenseOwnership can track transfers. A license belongs to exactly one company at any given time.

---

## Required Change

Per Requirement 5:
> "The user manually chooses which company receives an allocation. The user may split quantity across multiple companies."

Example:
```
Available = 30
Company A = 15
Company B = 15
```

**Current limitation:** AllotmentItems has no company field. An allocation can only be assigned to the allotment's company.

**Required implementation:**
1. Add `company` field to AllotmentItems (FK to CompanyModel)
2. Scope allocate_items endpoint to validate:
   - Caller can allocate to the selected company
   - Allocation doesn't exceed that company's permitted limit (once company limits are defined)
3. Allow manual selection of company per allocation line
4. Allow split across multiple companies in one request

---

## Risk

**Backward compatibility:**
- Existing AllotmentItems rows have no company (or implicitly inherit from allotment)
- Migration must backfill `company = allotment.company` for existing rows
- Queries must handle nullable company temporarily

**Authorization gap (F6):**
- Current allocate_items has no company authorization check
- Two concurrent issues:
  1. User can access any allotment (role-based only)
  2. Allocation has no company field, so can't tie it to a specific company

**Business decision needed:**
- Should each user/login be scoped to a specific company, or can they act on behalf of multiple companies?
- Should cross-company allocations be prevented or allowed?
- Who is responsible for validating company limits?

---

## Recommendation for Phase A

**Add company field to AllotmentItems:**
```python
company = models.ForeignKey(
    "core.CompanyModel",
    on_delete=models.PROTECT,
    related_name="allocation_items",
    null=True,  # During migration
    blank=True,
)
```

**Migration strategy:**
1. Add field with null=True
2. Backfill: `company = allotment.company` for all existing rows
3. Make field non-null

**API change:**
- Allow caller to specify company per allocation line
- Validate company is provided
- Validate caller has permission for that company (to be defined)

**No change to authorization model yet** — that's a separate decision (D1 business question above).
