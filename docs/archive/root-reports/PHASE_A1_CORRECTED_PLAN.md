# PHASE A.1 CORRECTED PLAN — Domain Foundation (D1 Correction Applied)

**CRITICAL CHANGE:** Company field is NOT added to AllotmentItems.

Company relationship remains at Allotment level (already exists).

---

## MIGRATION: Add Lifecycle Fields to AllotmentItems

**Remove from plan:**
- ~~`company` FK~~

**Keep in plan:**
- `status` (lifecycle: CREATED, RELEASED, REACTIVATED, COMPLETED)
- `released_quantity`, `released_date`, `release_reason`
- `reactivated_quantity`, `reactivated_date`, `reactivated_from_company` (for audit only, not FK)
- `previous_version` (FK to self for version history)

---

## AllotmentItems Model Changes (CORRECTED)

```python
class AllotmentItems(AuditModel):
    # ... existing fields (item, allotment, qty, cif_fc, cif_inr, is_boe) ...
    
    # ❌ DO NOT ADD: company field
    # Company is inherited from allotment: allotment.company
    
    # ✅ ADD: Lifecycle and history
    status = models.CharField(...)  # CREATED, RELEASED, REACTIVATED, COMPLETED
    released_quantity = models.DecimalField(...)
    released_date = models.DateTimeField(...)
    release_reason = models.CharField(...)
    
    reactivated_quantity = models.DecimalField(...)
    reactivated_date = models.DateTimeField(...)
    reactivated_from_company = models.CharField(...) # Audit label, NOT FK
    
    previous_version = models.ForeignKey('self', ...) # Version chain
```

---

## Other Models (UNCHANGED)

- AuditEvent: create as planned
- Shortfall: create as planned
- AllocationVersion: create as planned

---

## Company Validation

Company authorization moves to **Allotment create/update boundary**, NOT to AllotmentItems.

When allocating items to an allotment:
1. Allotment.company is already set
2. Validate user is authorized for that company (existing auth mechanism)
3. Present eligible licenses filtered by expiry cutoff
4. Order by automatic priority (expiry → issue_date → license_number)
5. User may split across licenses, but NOT across companies

---

## Phase A.1 Corrected Checklist

- [ ] Create migration: Add lifecycle fields to AllotmentItems (NO company field)
- [ ] Modify AllotmentItems model
- [ ] Create AuditEvent model
- [ ] Create Shortfall model
- [ ] Create AllocationVersion model
- [ ] Run `python manage.py makemigrations`
- [ ] Run `python manage.py migrate`
- [ ] Run backfill (set status='CREATED' for existing rows)
- [ ] Unit tests
- [ ] Verify schema

---

## Authorization Implementation (Later Phase)

Company authorization will be implemented in Phase A.2/A.3 at:
- AllotmentViewSet.create() — validate user.company_id (or multi-company list)
- ManualAllocationService — validate company remains same as allotment.company

No changes to model permissions needed.

---

**CRITICAL:** This is a DATA MODEL correction. The business rule remains:

> Users can manage multiple Allotments for different authorized companies.

But the implementation is:
- Separate Allotments per company (not per-item company assignment)
- Company validation at Allotment boundary (not AllotmentItems)

Next context: Execute this corrected Phase A.1 plan.
