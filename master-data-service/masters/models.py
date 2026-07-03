"""
MDS master models — the authoritative copies.

This skeleton implements a representative slice (Company, Port, ExchangeRate)
that proves the full pattern: a natural-key contract + sync timestamps that the
generic API and the change feed rely on. The remaining 14 masters are added the
same way (subclass MasterModel, set NATURAL_KEY_FIELD, register a ViewSet).
See docs/architecture/ADR-001-master-data-service.md.
"""

from django.db import models
from django.utils import timezone


class MasterModel(models.Model):
    """Abstract base: every master carries sync timestamps + a natural key."""

    #: name of the field holding the business/natural key (unique per model)
    NATURAL_KEY_FIELD = None

    created_on = models.DateTimeField(default=timezone.now, editable=False)
    modified_on = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True

    @property
    def natural_key_value(self) -> str:
        return str(getattr(self, self.NATURAL_KEY_FIELD))


class Company(MasterModel):
    NATURAL_KEY_FIELD = "iec"

    iec = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, default="")
    # Media as object-storage keys (django-storages wired in a later phase).
    logo = models.CharField(max_length=512, blank=True, default="")
    signature = models.CharField(max_length=512, blank=True, default="")
    stamp = models.CharField(max_length=512, blank=True, default="")

    def __str__(self):
        return f"{self.name} ({self.iec})"


class Port(MasterModel):
    NATURAL_KEY_FIELD = "code"

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.name} [{self.code}]"


class ExchangeRate(MasterModel):
    NATURAL_KEY_FIELD = "date"

    date = models.DateField(unique=True)
    currency = models.CharField(max_length=8, default="USD")
    rate = models.DecimalField(max_digits=12, decimal_places=4)

    def __str__(self):
        return f"{self.date}: {self.currency} {self.rate}"


class MasterChange(models.Model):
    """
    Append-only change feed powering delta-sync webhooks and delete propagation
    (deletes are invisible to an `updated_since` pull). One row per create/update
    /delete on any master, keyed by the master's natural key.
    """

    OP_CREATE = "create"
    OP_UPDATE = "update"
    OP_DELETE = "delete"
    OP_CHOICES = [(OP_CREATE, "create"), (OP_UPDATE, "update"), (OP_DELETE, "delete")]

    model_label = models.CharField(max_length=100, db_index=True)
    natural_key = models.CharField(max_length=255, db_index=True)
    op = models.CharField(max_length=10, choices=OP_CHOICES)
    at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["at"]
        indexes = [models.Index(fields=["model_label", "at"])]

    def __str__(self):
        return f"{self.op} {self.model_label}[{self.natural_key}] @ {self.at:%Y-%m-%d %H:%M:%S}"
