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
