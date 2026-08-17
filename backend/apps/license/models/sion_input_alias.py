"""SION percentage-rule input classification via Product Name aliases.

Maps BOE/Allotment product names (case-insensitive) to canonical SION inputs
for percentage-constrained allocation rules (E126, E132, etc.).
"""
from django.db import models
from apps.core.models import AuditModel


class SionCanonicalInput(AuditModel):
    """Canonical SION input for percentage rule allocation."""
    code = models.CharField(
        max_length=50, unique=True,
        help_text="Canonical code (e.g., PKO, OLIVE_OIL, CHEESE)"
    )
    display_name = models.CharField(
        max_length=255,
        help_text="Human-readable name (e.g., Palm Kernel Oil)"
    )
    is_active = models.BooleanField(
        default=True, db_index=True,
        help_text="Inactive inputs are not matched against product names"
    )

    class Meta:
        ordering = ("code",)
        indexes = [models.Index(fields=["is_active", "code"])]

    def __str__(self):
        return f"{self.code} ({self.display_name})"


class SionInputAlias(AuditModel):
    """Product name alias mapping to canonical SION input."""
    canonical_input = models.ForeignKey(
        SionCanonicalInput, on_delete=models.CASCADE,
        related_name="aliases"
    )
    alias = models.CharField(
        max_length=255,
        help_text="Raw product name variant (e.g., 'PALM KERNEL OIL', 'PKO', 'palm kernel oil')"
    )
    normalized_alias = models.CharField(
        max_length=255, db_index=True,
        help_text="Normalized form for case-insensitive matching (UPPERCASE, single spaces)"
    )

    class Meta:
        ordering = ("canonical_input", "alias")
        constraints = [
            models.UniqueConstraint(
                fields=["normalized_alias"],
                name="uniq_normalized_alias"
            ),
        ]
        indexes = [models.Index(fields=["normalized_alias"])]

    def __str__(self):
        return f"{self.alias} → {self.canonical_input.code}"
