"""
MDS master models — the authoritative copies of the 17 shared masters.

Design notes:
- Every master carries sync timestamps (created_on/modified_on) via MasterModel.
- Each master has a NATURAL_KEY_FIELD: its unique business key where one exists
  (iec, code, hs_code, norm_class, name, date), or a synthetic `uid` UUID for the
  keyless models (the SION norm rows, notes/conditions, product descriptions,
  unit prices) — per ADR-001 Decision 6.
- Media (company logo/signature/stamp) is stored as an object-storage KEY
  (CharField); django-storages wiring is a later phase, so the service boots
  without external infra.
- Inter-master FKs live in the same DB, so they are ordinary Django FKs.
- MASTER_REGISTRY at the bottom drives serializers, viewsets, routing, the change
  feed, and admin so adding a master is one entry.
"""

import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

DEC0 = Decimal("0")

PAN = RegexValidator(regex=r"^[A-Z]{5}[0-9]{4}[A-Z]$", message="Enter a valid PAN number.")
GST = RegexValidator(
    regex=r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$",
    message="Enter a valid GST number.",
)
IFSC = RegexValidator(regex=r"^[A-Z]{4}0[A-Z0-9]{6}$", message="Enter a valid IFSC code.")


class MasterModel(models.Model):
    """Abstract base: sync timestamps + a natural-key contract."""

    NATURAL_KEY_FIELD = None

    created_on = models.DateTimeField(default=timezone.now, editable=False)
    modified_on = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True

    @property
    def natural_key_value(self) -> str:
        return str(getattr(self, self.NATURAL_KEY_FIELD))


class SyntheticKeyMixin(models.Model):
    """A stable synthetic natural key for masters lacking a business key."""

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        abstract = True


# --- entities --------------------------------------------------------------

class Company(MasterModel):
    NATURAL_KEY_FIELD = "iec"

    ACCOUNT_TYPE_CHOICES = [("SAVINGS", "Savings"), ("CURRENT", "Current"), ("OD", "Overdraft")]

    iec = models.CharField(max_length=10, unique=True)
    pan = models.CharField(max_length=50, null=True, blank=True, validators=[PAN])
    gst_number = models.CharField(max_length=50, null=True, blank=True, validators=[GST])
    name = models.CharField(max_length=255, blank=True, default="")
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address_line_1 = models.TextField(blank=True, default="")
    address_line_2 = models.TextField(blank=True, default="")
    # media as object-storage keys (django-storages later)
    logo = models.CharField(max_length=512, blank=True, default="")
    signature = models.CharField(max_length=512, blank=True, default="")
    stamp = models.CharField(max_length=512, blank=True, default="")
    bill_colour = models.CharField(max_length=20, default="#333")
    bank_account_number = models.CharField(max_length=30, null=True, blank=True)
    bank_name = models.CharField(max_length=255, null=True, blank=True)
    ifsc_code = models.CharField(max_length=11, null=True, blank=True, validators=[IFSC])
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name or self.iec


class Port(MasterModel):
    NATURAL_KEY_FIELD = "code"

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ("code", "name")
        unique_together = ("name", "code")

    def __str__(self):
        return self.code


class ItemHead(MasterModel):
    """Deprecated in the source app (use ItemGroup); mirrored for completeness."""

    NATURAL_KEY_FIELD = "name"

    name = models.CharField(max_length=255, unique=True)
    unit_rate = models.DecimalField(max_digits=15, decimal_places=2, default=DEC0, validators=[MinValueValidator(DEC0)])
    is_restricted = models.BooleanField(default=False)
    restriction_norm = models.ForeignKey(
        "SIONNormClass", on_delete=models.SET_NULL, null=True, blank=True, related_name="restricted_heads"
    )
    restriction_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=DEC0, validators=[MinValueValidator(DEC0)]
    )
    dict_key = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class ItemGroup(MasterModel):
    NATURAL_KEY_FIELD = "name"

    name = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ItemName(MasterModel):
    NATURAL_KEY_FIELD = "name"

    group = models.ForeignKey("ItemGroup", on_delete=models.CASCADE, related_name="items", null=True, blank=True)
    name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    sion_norm_class = models.ForeignKey(
        "SIONNormClass", on_delete=models.SET_NULL, null=True, blank=True, related_name="items"
    )
    restriction_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=DEC0, validators=[MinValueValidator(DEC0)]
    )
    display_order = models.IntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["display_order", "group__name", "name"]

    def __str__(self):
        return self.name


class HSCode(MasterModel):
    NATURAL_KEY_FIELD = "hs_code"

    hs_code = models.CharField(max_length=8, unique=True)
    product_description = models.TextField(null=True, blank=True)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=DEC0, validators=[MinValueValidator(DEC0)])
    basic_duty = models.CharField(max_length=225, null=True, blank=True)
    unit = models.CharField(max_length=255, null=True, blank=True)
    policy = models.CharField(max_length=255, null=True, blank=True)
    note = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ("hs_code",)

    def __str__(self):
        return self.hs_code


class HeadSIONNorm(SyntheticKeyMixin, MasterModel):
    NATURAL_KEY_FIELD = "uid"

    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class SIONNormClass(MasterModel):
    NATURAL_KEY_FIELD = "norm_class"

    head_norm = models.ForeignKey("HeadSIONNorm", on_delete=models.CASCADE, related_name="sion_head")
    description = models.CharField(max_length=255, null=True, blank=True)
    norm_class = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.norm_class


class SIONExport(SyntheticKeyMixin, MasterModel):
    NATURAL_KEY_FIELD = "uid"

    norm_class = models.ForeignKey("SIONNormClass", on_delete=models.CASCADE, related_name="export_norm")
    description = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.DecimalField(max_digits=15, decimal_places=2, default=DEC0, validators=[MinValueValidator(DEC0)])
    unit = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.norm_class_id} | {self.description or ''}"


class SIONImport(SyntheticKeyMixin, MasterModel):
    NATURAL_KEY_FIELD = "uid"

    serial_number = models.IntegerField(default=0)
    norm_class = models.ForeignKey("SIONNormClass", on_delete=models.CASCADE, related_name="import_norm")
    hsn_code = models.ForeignKey(
        "HSCode", on_delete=models.SET_NULL, related_name="sion_imports", null=True, blank=True
    )
    description = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.DecimalField(max_digits=15, decimal_places=2, default=DEC0, validators=[MinValueValidator(DEC0)])
    unit = models.CharField(max_length=255, null=True, blank=True)
    condition = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ["serial_number"]

    def __str__(self):
        return f"{self.norm_class_id} | {self.description or ''}"


class SIONNormNote(SyntheticKeyMixin, MasterModel):
    NATURAL_KEY_FIELD = "uid"

    sion_norm = models.ForeignKey("SIONNormClass", on_delete=models.CASCADE, related_name="notes")
    note_text = models.TextField()
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"note {self.display_order}"


class SIONNormCondition(SyntheticKeyMixin, MasterModel):
    NATURAL_KEY_FIELD = "uid"

    sion_norm = models.ForeignKey("SIONNormClass", on_delete=models.CASCADE, related_name="conditions")
    condition_text = models.TextField()
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"condition {self.display_order}"


class ProductDescription(SyntheticKeyMixin, MasterModel):
    NATURAL_KEY_FIELD = "uid"

    hs_code = models.ForeignKey("HSCode", on_delete=models.PROTECT, related_name="product_descriptions")
    product_description = models.TextField()

    def __str__(self):
        return self.product_description


class UnitPrice(SyntheticKeyMixin, MasterModel):
    NATURAL_KEY_FIELD = "uid"

    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=DEC0, validators=[MinValueValidator(DEC0)])
    label = models.CharField(max_length=255, default="")

    def __str__(self):
        return self.name


class SchemeCode(MasterModel):
    NATURAL_KEY_FIELD = "code"

    code = models.CharField(max_length=10, unique=True)
    label = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.code} - {self.label}"


class NotificationNumber(MasterModel):
    NATURAL_KEY_FIELD = "code"

    code = models.CharField(max_length=10, unique=True)
    label = models.CharField(max_length=100)

    def __str__(self):
        return self.label


class ExchangeRate(MasterModel):
    NATURAL_KEY_FIELD = "date"

    date = models.DateField(unique=True)
    usd = models.DecimalField(max_digits=10, decimal_places=4, validators=[MinValueValidator(DEC0)])
    euro = models.DecimalField(max_digits=10, decimal_places=4, validators=[MinValueValidator(DEC0)])
    pound_sterling = models.DecimalField(max_digits=10, decimal_places=4, validators=[MinValueValidator(DEC0)])
    chinese_yuan = models.DecimalField(max_digits=10, decimal_places=4, validators=[MinValueValidator(DEC0)])

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date}: USD {self.usd}"


# --- change feed -----------------------------------------------------------

class MasterChange(models.Model):
    """Append-only change feed powering delta-sync webhooks and delete
    propagation (deletes are invisible to an `updated_since` pull)."""

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


# --- registry: single source of truth for API + feed + admin ---------------
# (model, natural_key_field, url_endpoint)
MASTER_REGISTRY = [
    (Company, "iec", "companies"),
    (Port, "code", "ports"),
    (ItemHead, "name", "item-heads"),
    (ItemGroup, "name", "item-groups"),
    (ItemName, "name", "item-names"),
    (HSCode, "hs_code", "hs-codes"),
    (HeadSIONNorm, "uid", "head-sion-norms"),
    (SIONNormClass, "norm_class", "sion-norm-classes"),
    (SIONExport, "uid", "sion-exports"),
    (SIONImport, "uid", "sion-imports"),
    (SIONNormNote, "uid", "sion-norm-notes"),
    (SIONNormCondition, "uid", "sion-norm-conditions"),
    (ProductDescription, "uid", "product-descriptions"),
    (UnitPrice, "uid", "unit-prices"),
    (SchemeCode, "code", "scheme-codes"),
    (NotificationNumber, "code", "notification-numbers"),
    (ExchangeRate, "date", "exchange-rates"),
]

TRACKED_MODELS = tuple(model for model, _, _ in MASTER_REGISTRY)
