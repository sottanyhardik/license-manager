from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import AuditModel

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
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['allocation_item', '-created_on']),
            models.Index(fields=['action', '-created_on']),
            models.Index(fields=['actor', '-created_on']),
        ]

    def __str__(self):
        return f"{self.get_action_display()} on {self.allocation_item} by {self.actor}"
