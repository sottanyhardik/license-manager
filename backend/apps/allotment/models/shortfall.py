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

    # Reference to the allocation context
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
            models.Index(fields=['created_on']),
        ]
        ordering = ['created_on']

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
