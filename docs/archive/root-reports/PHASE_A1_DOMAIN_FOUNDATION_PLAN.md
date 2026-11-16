# PHASE A.1 IMPLEMENTATION PLAN — Domain Foundation

**Status:** READY FOR EXECUTION (next context)

**Scope:** Add lifecycle, company, versioning, and audit models to support allocation/planning specification.

**Estimated effort:** 4-6 hours

**Order of execution:**
1. Create migrations (non-destructive)
2. Modify AllotmentItems model
3. Create AuditEvent model
4. Create Shortfall model
5. Create AllocationVersion model
6. Backfill existing data
7. Run tests

---

## 1. MIGRATION: Add Fields to AllotmentItems

**File:** `backend/apps/allotment/migrations/000X_add_allocation_lifecycle.py`

**Changes to AllotmentItems:**

Add fields (null=True initially for migration safety):

```python
# Company assignment (D1)
company = models.ForeignKey(
    "core.CompanyModel",
    on_delete=models.PROTECT,
    related_name="allocation_items",
    null=True,
    blank=True,
    db_index=True,
)

# Lifecycle state (Req 7)
status = models.CharField(
    max_length=20,
    choices=[
        ('CREATED', 'Created'),
        ('RELEASED', 'Released'),
        ('REACTIVATED', 'Reactivated'),
        ('COMPLETED', 'Completed'),
    ],
    default='CREATED',
    db_index=True,
)

# Release tracking (Req 8)
released_quantity = models.DecimalField(
    max_digits=15,
    decimal_places=3,
    default=DEC_000,
    null=True,
    blank=True,
)
released_date = models.DateTimeField(null=True, blank=True)
release_reason = models.CharField(max_length=500, null=True, blank=True)

# Reactivation tracking (Req 9-10)
reactivated_quantity = models.DecimalField(
    max_digits=15,
    decimal_places=3,
    default=DEC_000,
    null=True,
    blank=True,
)
reactivated_date = models.DateTimeField(null=True, blank=True)
reactivated_from_company = models.ForeignKey(
    "core.CompanyModel",
    on_delete=models.SET_NULL,
    related_name="reactivated_from_allocations",
    null=True,
    blank=True,
)

# Version history (Req 7)
previous_version = models.ForeignKey(
    'self',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='next_version',
)
```

**Backfill logic in migration:**
```python
# Set company = allotment.company for all existing rows
AllotmentItems.objects.all().update(
    company_id=F('allotment__company_id')
)

# Set status = 'CREATED' for all existing rows
AllotmentItems.objects.all().update(status='CREATED')
```

---

## 2. Model Changes: Update AllotmentItems

**File:** `backend/apps/allotment/models.py`

**Class location:** AllotmentItems (line ~209)

**Add properties/methods:**

```python
class AllotmentItems(AuditModel):
    # ... existing fields ...
    company = ... (added by migration)
    status = ... (added by migration)
    released_quantity = ... (added by migration)
    released_date = ... (added by migration)
    release_reason = ... (added by migration)
    reactivated_quantity = ... (added by migration)
    reactivated_date = ... (added by migration)
    reactivated_from_company = ... (added by migration)
    previous_version = ... (added by migration)
    
    class Meta:
        ordering = ["qty"]
        unique_together = ("item", "allotment")
        indexes = [
            # Existing indexes
            models.Index(fields=['company']),
            models.Index(fields=['status']),
        ]
    
    @property
    def is_released(self):
        return self.status in ['RELEASED', 'COMPLETED']
    
    @property
    def is_reactivated(self):
        return self.status == 'REACTIVATED'
    
    def create_version(self):
        """Create a new version by copying current state."""
        new_version = AllotmentItems.objects.create(
            item=self.item,
            allotment=self.allotment,
            company=self.company,
            qty=self.qty,
            cif_fc=self.cif_fc,
            cif_inr=self.cif_inr,
            is_boe=self.is_boe,
            status='CREATED',
            previous_version=self,
        )
        return new_version
```

---

## 3. New Model: AuditEvent

**File:** `backend/apps/allotment/models/audit_event.py` (new file)

```python
from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import AuditModel
from decimal import Decimal

User = get_user_model()

class AuditEvent(AuditModel):
    """
    Detailed audit trail for all allocation mutations.
    
    Combines multiple changes into a single audit event with reason.
    Preserves full mutation history for compliance and troubleshooting.
    """
    
    ALLOCATION = 'ALLOCATION'
    RELEASE = 'RELEASE'
    REVERSAL = 'REVERSAL'
    REACTIVATION = 'REACTIVATION'
    BOE_RECONCILIATION = 'BOE_RECONCILIATION'
    COMPANY_CHANGE = 'COMPANY_CHANGE'
    SHORTFALL_FULFILLMENT = 'SHORTFALL_FULFILLMENT'
    
    ACTION_CHOICES = [
        (ALLOCATION, 'Allocation Created'),
        (RELEASE, 'Allocation Released'),
        (REVERSAL, 'Release Reversed'),
        (REACTIVATION, 'Allocation Reactivated'),
        (BOE_RECONCILIATION, 'BOE Reconciliation'),
        (COMPANY_CHANGE, 'Company Changed'),
        (SHORTFALL_FULFILLMENT, 'Shortfall Fulfilled'),
    ]
    
    allocation_item = models.ForeignKey(
        'allotment.AllotmentItems',
        on_delete=models.PROTECT,
        related_name='audit_events',
        null=True,
        blank=True,
    )
    
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, db_index=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Change details
    quantity_before = models.DecimalField(max_digits=15, decimal_places=3, null=True, blank=True)
    quantity_after = models.DecimalField(max_digits=15, decimal_places=3, null=True, blank=True)
    
    cif_before = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    cif_after = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    company_before = models.ForeignKey(
        'core.CompanyModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events_from',
    )
    company_after = models.ForeignKey(
        'core.CompanyModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events_to',
    )
    
    # Reason/context
    reason = models.CharField(max_length=500, null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)  # Arbitrary context data
    
    class Meta:
        indexes = [
            models.Index(fields=['allocation_item', '-created_on']),
            models.Index(fields=['action', '-created_on']),
            models.Index(fields=['actor', '-created_on']),
        ]
    
    def __str__(self):
        return f"{self.get_action_display()} on {self.allocation_item} by {self.actor}"
```

---

## 4. New Model: Shortfall

**File:** `backend/apps/allotment/models/shortfall.py` (new file)

```python
from django.db import models
from apps.core.models import AuditModel
from decimal import Decimal

class Shortfall(AuditModel):
    """
    Saved shortfall from automatic planning.
    
    When allocation cannot fulfill requested quantity (insufficient availability),
    the shortfall is saved and automatically fulfilled when new balance becomes
    available (FIFO ordering).
    """
    
    PENDING = 'PENDING'
    PARTIALLY_FULFILLED = 'PARTIALLY_FULFILLED'
    FULFILLED = 'FULFILLED'
    
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (PARTIALLY_FULFILLED, 'Partially Fulfilled'),
        (FULFILLED, 'Fulfilled'),
    ]
    
    # Reference to the allocation context (may be planning, may be direct request)
    license = models.ForeignKey(
        'license.LicenseDetailsModel',
        on_delete=models.CASCADE,
        related_name='shortfalls',
    )
    
    # The actual amounts
    required_quantity = models.DecimalField(max_digits=15, decimal_places=3)
    required_cif = models.DecimalField(max_digits=15, decimal_places=2)
    
    allocated_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=Decimal('0.000'),
    )
    allocated_cif = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    
    # Status and fulfillment history
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=PENDING,
        db_index=True,
    )
    
    fulfilled_on = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['license', 'status']),
            models.Index(fields=['created_on']),  # FIFO ordering
        ]
        ordering = ['created_on']  # FIFO: oldest first
    
    def shortfall_quantity(self):
        """Remaining shortfall."""
        return self.required_quantity - self.allocated_quantity
    
    def shortfall_cif(self):
        """Remaining CIF shortfall."""
        return self.required_cif - self.allocated_cif
    
    def is_fulfilled(self):
        return self.shortfall_quantity() <= Decimal('0.000')
    
    def __str__(self):
        return f"Shortfall on {self.license}: {self.shortfall_quantity()} qty, {self.shortfall_cif()} CIF"
```

---

## 5. New Model: AllocationVersion

**File:** `backend/apps/allotment/models/allocation_version.py` (new file)

```python
from django.db import models
from apps.core.models import AuditModel

class AllocationVersion(AuditModel):
    """
    Historical version record for allocations.
    
    Immutable snapshot of allocation state at each mutation point.
    Linked via AllotmentItems.previous_version for full lifecycle traceability.
    """
    
    allocation_item = models.ForeignKey(
        'allotment.AllotmentItems',
        on_delete=models.PROTECT,
        related_name='versions',
    )
    
    # Snapshot state
    status = models.CharField(
        max_length=20,
        choices=[
            ('CREATED', 'Created'),
            ('RELEASED', 'Released'),
            ('REACTIVATED', 'Reactivated'),
            ('COMPLETED', 'Completed'),
        ],
    )
    
    quantity = models.DecimalField(max_digits=15, decimal_places=3)
    cif_fc = models.DecimalField(max_digits=15, decimal_places=2)
    company = models.ForeignKey('core.CompanyModel', on_delete=models.SET_NULL, null=True)
    
    # What changed
    change_reason = models.CharField(max_length=500, null=True, blank=True)
    
    class Meta:
        indexes = [models.Index(fields=['allocation_item', '-created_on'])]
        ordering = ['-created_on']
    
    def __str__(self):
        return f"Version of {self.allocation_item}: {self.status} ({self.quantity} qty)"
```

---

## 6. Update Imports

**File:** `backend/apps/allotment/models/__init__.py` (create if needed)

```python
from .allotment import AllotmentModel, AllotmentItems
from .audit_event import AuditEvent
from .shortfall import Shortfall
from .allocation_version import AllocationVersion

__all__ = [
    'AllotmentModel',
    'AllotmentItems',
    'AuditEvent',
    'Shortfall',
    'AllocationVersion',
]
```

---

## 7. Backfill Strategy

After migrations run:

```python
# management/commands/backfill_allocations.py
from django.core.management.base import BaseCommand
from django.db.models import F
from allotment.models import AllotmentItems

class Command(BaseCommand):
    def handle(self, *args, **options):
        # Set company for all existing allocations
        count = AllotmentItems.objects.filter(company__isnull=True).update(
            company_id=F('allotment__company_id')
        )
        self.stdout.write(f"Backfilled {count} allocations with company")
```

---

## 8. Testing (A.1 Phase Only)

**File:** `backend/apps/allotment/tests/test_a1_domain_models.py`

```python
import pytest
from decimal import Decimal
from allotment.models import AllotmentItems, AuditEvent, Shortfall, AllocationVersion

@pytest.mark.django_db
def test_allocation_has_company():
    """Verify AllotmentItems requires company."""
    # ... test that allocation must have company
    
@pytest.mark.django_db
def test_allocation_status_lifecycle():
    """Verify allocation status transitions."""
    # CREATED → RELEASED → COMPLETED
    
@pytest.mark.django_db
def test_shortfall_fifo_ordering():
    """Verify shortfalls are ordered FIFO."""
    # created_on ordering
    
@pytest.mark.django_db
def test_audit_event_creation():
    """Verify audit events log mutations."""
    # ... test that events are created on allocation changes
```

---

## Execution Checklist

- [ ] Create migration file
- [ ] Modify AllotmentItems model
- [ ] Create AuditEvent model
- [ ] Create Shortfall model
- [ ] Create AllocationVersion model
- [ ] Update __init__.py
- [ ] Run `python manage.py makemigrations`
- [ ] Run `python manage.py migrate`
- [ ] Run backfill command
- [ ] Run A.1 tests
- [ ] Verify database schema
- [ ] Commit with appropriate message

---

## Next Context: Phase A.2

After A.1 completes, proceed with Phase A.2 (Canonical Domain Services):
- EligibilityService
- AutomaticPriorityService
- ManualAllocationService
- AutomaticPlanningService
- ShortfallFulfillmentService
- BOEReconciliationService
- ReleaseService
- ConcurrencyService
