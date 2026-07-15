from __future__ import annotations

from django.conf import settings
from django.db import models


class LicenseBalanceNotification(models.Model):
    """
    Tracks negative-balance exceptions on licenses (BD-003).

    Lifecycle: ACTIVE -> ACKNOWLEDGED -> RESOLVED

    Only ONE record per license is active at a time.
    When additional BOEs worsen the balance, the EXISTING active notification
    is updated (not replaced). Resolution is a deliberate business action only.

    Table: notifications_licensebalancenotification (managed=True — new table)
    """

    STATUS_ACTIVE = "active"
    STATUS_ACKNOWLEDGED = "acknowledged"
    STATUS_RESOLVED = "resolved"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_ACKNOWLEDGED, "Acknowledged"),
        (STATUS_RESOLVED, "Resolved"),
    ]

    # One active notification per license (enforced by unique_together + status filter in service)
    license = models.ForeignKey(
        "license.LicenseDetailsModel",
        on_delete=models.CASCADE,
        related_name="balance_notifications",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )

    # Balance snapshot at notification time
    balance_cif = models.DecimalField(max_digits=15, decimal_places=2)
    last_boe_reference = models.CharField(max_length=255, blank=True, default="")

    # Acknowledgement
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="acknowledged_balance_notifications",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_remarks = models.TextField(blank=True, default="")

    # Resolution
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_balance_notifications",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_remarks = models.TextField(blank=True, default="")

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notifications_licensebalancenotification"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["license", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"BalanceNotification[{self.license_id}] {self.status} {self.balance_cif}"

    @property
    def is_active(self) -> bool:
        return self.status == self.STATUS_ACTIVE
