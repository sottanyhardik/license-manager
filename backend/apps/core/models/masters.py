# core/models/masters.py
"""
All 23 master models for the License Manager core app.

IMPORTANT: Every model here uses managed=False — these tables are owned by
the legacy backend. Django will never create, alter, or drop these tables.
Field names and types must exactly match the legacy DB columns.

Reference: legacy/backend/apps/core/models.py
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

DEC_0 = Decimal("0")

ACCOUNT_TYPES = (
    ("current", "Current"),
    ("saving", "Saving"),
)


# ---------------------------------------------------------------------------
# Abstract bases (mirrors of legacy abstract models — NOT managed=False
# themselves, but all concrete subclasses set managed=False)
# ---------------------------------------------------------------------------

class AuditModel(models.Model):
    """
    Abstract base providing created_on / modified_on timestamps and
    created_by / modified_by FK columns. Mirrors the legacy AuditModel exactly.
    """

    created_on = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_created",
    )
    modified_on = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_updated",
    )

    class Meta:
        abstract = True


class SyncTimestampModel(models.Model):
    """
    Lightweight created/modified timestamps for bulk-imported masters that
    participate in delta sync. Mirrors the legacy SyncTimestampModel exactly.
    """

    created_on = models.DateTimeField(default=timezone.now, editable=False)
    modified_on = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Priority masters (used by other modules as foreign keys)
# ---------------------------------------------------------------------------

class CompanyModel(AuditModel):
    """
    Company / IEC holder master. Primary entity in the license management workflow.
    DB table: core_companymodel (owned by legacy).
    """

    iec = models.CharField(max_length=10, unique=True)
    pan = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{5}[0-9]{4}[A-Z]$",
                message="Enter a valid PAN number.",
            )
        ],
    )
    gst_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$",
                message="Enter a valid GST number.",
            )
        ],
    )
    name = models.CharField(max_length=255, blank=True, default="")
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address_line_1 = models.TextField(blank=True, default="")
    address_line_2 = models.TextField(blank=True, default="")
    # Branding / legal docs
    logo = models.ImageField(upload_to="companies/", null=True, blank=True)
    signature = models.ImageField(upload_to="companies/", null=True, blank=True)
    stamp = models.ImageField(upload_to="companies/", null=True, blank=True)
    bill_colour = models.CharField(max_length=20, default="#333")
    # Banking
    bank_account_number = models.CharField(max_length=30, null=True, blank=True)
    bank_name = models.CharField(max_length=255, null=True, blank=True)
    ifsc_code = models.CharField(
        max_length=11,
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{4}0[A-Z0-9]{6}$",
                message="Enter a valid IFSC code.",
            )
        ],
    )

    ACCOUNT_TYPE_CHOICES = [
        ("SAVINGS", "Savings"),
        ("CURRENT", "Current"),
        ("OD", "Overdraft"),
    ]
    account_type = models.CharField(
        max_length=20, choices=ACCOUNT_TYPE_CHOICES, null=True, blank=True
    )

    def __str__(self):
        return self.name if self.name else self.iec

    class Meta:
        managed = False
        db_table = "core_companymodel"
        ordering = ["name"]


class PortModel(AuditModel):
    """
    Port master. Used in license, bill-of-entry, and trade records.
    DB table: core_portmodel (owned by legacy).
    """

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"{self.code}"

    class Meta:
        managed = False
        db_table = "core_portmodel"
        ordering = ("code", "name")
        unique_together = ("name", "code")


class HSCodeModel(AuditModel):
    """
    Harmonised System Code master. Referenced by trade and SION import norms.
    DB table: core_hscodemodel (owned by legacy).
    """

    hs_code = models.CharField(max_length=8, unique=True)
    product_description = models.TextField(null=True, blank=True)
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    basic_duty = models.CharField(max_length=225, null=True, blank=True)
    unit = models.CharField(max_length=255, null=True, blank=True)
    policy = models.CharField(max_length=255, null=True, blank=True)
    note = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.hs_code}"

    class Meta:
        managed = False
        db_table = "core_hscodemodel"
        ordering = ("hs_code",)


class HeadSIONNormsModel(SyncTimestampModel):
    """
    Top-level SION norm heading. Groups SionNormClassModel records under a heading.
    DB table: core_headsionnormsmodel (owned by legacy).
    """

    uid = models.UUIDField(null=True, blank=True, unique=True, db_index=True, editable=False)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = "core_headsionnormsmodel"


class SionNormClassModel(AuditModel):
    """
    SION norm class. Links to HeadSIONNormsModel; groups export/import norms.
    Used by ItemNameModel and ItemHeadModel as FKs.
    DB table: core_sionnormclassmodel (owned by legacy).
    """

    head_norm = models.ForeignKey(
        "core.HeadSIONNormsModel",
        on_delete=models.CASCADE,
        related_name="sion_head",
    )
    description = models.CharField(max_length=255, null=True, blank=True)
    norm_class = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.norm_class}"

    class Meta:
        managed = False
        db_table = "core_sionnormclassmodel"


class ItemGroupModel(AuditModel):
    """
    Item group / category master. Parent for ItemNameModel.
    DB table: core_itemgroupmodel (owned by legacy).
    """

    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = "core_itemgroupmodel"
        ordering = ["name"]


class ItemNameModel(AuditModel):
    """
    Item name master. Each item belongs to an ItemGroupModel and optionally
    references a SionNormClassModel.
    DB table: core_itemnamemodel (owned by legacy).
    """

    group = models.ForeignKey(
        "core.ItemGroupModel",
        on_delete=models.CASCADE,
        related_name="items",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    sion_norm_class = models.ForeignKey(
        "core.SionNormClassModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
        help_text="SION norm class for restriction grouping (e.g., E1, E2)",
    )
    restriction_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
        help_text="Restriction percentage for this item (e.g., 2.00 for 2%)",
    )
    display_order = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Display order in reports (lower numbers appear first).",
    )

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = "core_itemnamemodel"
        ordering = ["display_order", "group__name", "name"]


class ExchangeRateModel(AuditModel):
    """
    Currency exchange rates. The active rate is the row with the latest date.
    DB table: core_exchangeratemodel (owned by legacy).
    """

    date = models.DateField(unique=True, help_text="Date of the exchange rate")
    usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(DEC_0)],
        help_text="USD to INR exchange rate",
    )
    euro = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(DEC_0)],
        help_text="Euro to INR exchange rate",
    )
    pound_sterling = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(DEC_0)],
        help_text="Pound Sterling to INR exchange rate",
    )
    chinese_yuan = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(DEC_0)],
        help_text="Chinese Yuan to INR exchange rate",
    )

    def __str__(self):
        return f"Exchange Rate - {self.date.strftime('%d-%m-%Y')}"

    @classmethod
    def get_active_rate(cls):
        """Return the most recent exchange rate (ordered by -date)."""
        return cls.objects.first()

    @classmethod
    def get_rate_for_date(cls, date):
        """Return the rate on or before *date*."""
        return cls.objects.filter(date__lte=date).first()

    class Meta:
        managed = False
        db_table = "core_exchangeratemodel"
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["-date"]),
        ]


# ---------------------------------------------------------------------------
# Secondary masters
# ---------------------------------------------------------------------------

class InvoiceEntity(models.Model):
    """
    Invoice-issuing entity (billing company). Used for PDF invoice generation.
    DB table: core_invoiceentity (owned by legacy).
    """

    name = models.CharField(max_length=255)
    address_line_1 = models.TextField()
    address_line_2 = models.TextField(blank=True)
    pan_number = models.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{5}[0-9]{4}[A-Z]$",
                message="Enter a valid PAN number.",
            )
        ],
    )
    gst_number = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$",
                message="Enter a valid GST number.",
            )
        ],
    )
    logo = models.ImageField(upload_to="entity_logos/", null=True, blank=True)
    bank_account_number = models.CharField(max_length=30)
    bank_name = models.CharField(max_length=100)
    ifsc_code = models.CharField(
        max_length=11,
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{4}0[A-Z0-9]{6}$",
                message="Enter a valid IFSC code.",
            )
        ],
    )
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)
    bill_colour = models.CharField(max_length=10, null=True, blank=True)
    signature = models.ImageField(upload_to="entity_signature/", null=True, blank=True)
    stamp = models.ImageField(upload_to="entity_stamp/", null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = "core_invoiceentity"


class SchemeCode(models.Model):
    """
    DGFT scheme codes (e.g., DFIA, MEIS). Used on license records.
    DB table: core_schemecode (owned by legacy).
    """

    code = models.CharField(max_length=10, unique=True)
    label = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.code} - {self.label}"

    class Meta:
        managed = False
        db_table = "core_schemecode"


class NotificationNumber(models.Model):
    """
    DGFT notification numbers. Referenced on licenses.
    DB table: core_notificationnumber (owned by legacy).
    """

    code = models.CharField(max_length=10, unique=True)
    label = models.CharField(max_length=100)

    def __str__(self):
        return self.label

    class Meta:
        managed = False
        db_table = "core_notificationnumber"


class PurchaseStatus(models.Model):
    """
    Purchase status codes for bill-of-entry line items.
    DB table: core_purchasestatus (owned by legacy).
    """

    code = models.CharField(max_length=2, unique=True)
    label = models.CharField(max_length=100)
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this purchase status is active and should be shown in UI",
    )
    display_order = models.IntegerField(
        default=0, help_text="Order for displaying in dropdowns"
    )

    def __str__(self):
        return self.label

    class Meta:
        managed = False
        db_table = "core_purchasestatus"
        ordering = ["display_order", "label"]
        verbose_name = "Purchase Status"
        verbose_name_plural = "Purchase Statuses"


class TransferLetterModel(AuditModel):
    """
    Transfer letter document store.
    DB table: core_transferlettermodel (owned by legacy).
    """

    name = models.CharField(max_length=255)
    tl = models.FileField(upload_to="tl")

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = "core_transferlettermodel"
        ordering = ["name", "id"]


class UnitPriceModel(AuditModel):
    """
    Unit price master for goods. Used in license and trade calculations.
    DB table: core_unitpricemodel (owned by legacy).
    """

    uid = models.UUIDField(null=True, blank=True, unique=True, db_index=True, editable=False)
    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    label = models.CharField(max_length=255, default="")

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = "core_unitpricemodel"


class ProductDescriptionModel(AuditModel):
    """
    Additional product descriptions linked to HS codes.
    DB table: core_productdescriptionmodel (owned by legacy).
    """

    uid = models.UUIDField(null=True, blank=True, unique=True, db_index=True, editable=False)
    hs_code = models.ForeignKey(
        "core.HSCodeModel",
        on_delete=models.PROTECT,
        related_name="product_descriptions",
    )
    product_description = models.TextField()

    def __str__(self):
        return self.product_description

    class Meta:
        managed = False
        db_table = "core_productdescriptionmodel"


class SIONExportModel(SyncTimestampModel):
    """
    SION export norm row. Each norm class can have multiple export items.
    DB table: core_sionexportmodel (owned by legacy).
    """

    uid = models.UUIDField(null=True, blank=True, unique=True, db_index=True, editable=False)
    norm_class = models.ForeignKey(
        "core.SionNormClassModel",
        on_delete=models.CASCADE,
        related_name="export_norm",
    )
    description = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    unit = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        if self.description:
            return f"{self.norm_class} | {self.description}"
        return f"{self.norm_class}"

    class Meta:
        managed = False
        db_table = "core_sionexportmodel"


class SIONImportModel(SyncTimestampModel):
    """
    SION import norm row. Each norm class can have multiple import items
    with serial numbers and optional HS code links.
    DB table: core_sionimportmodel (owned by legacy).
    """

    uid = models.UUIDField(null=True, blank=True, unique=True, db_index=True, editable=False)
    serial_number = models.IntegerField(default=0)
    norm_class = models.ForeignKey(
        "core.SionNormClassModel",
        on_delete=models.CASCADE,
        related_name="import_norm",
    )
    hsn_code = models.ForeignKey(
        "core.HSCodeModel",
        on_delete=models.SET_NULL,
        related_name="sion_imports",
        null=True,
        blank=True,
        db_column="hsn_code_id",
    )
    description = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    unit = models.CharField(max_length=255, null=True, blank=True)
    condition = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        if self.description:
            return f"{self.norm_class} | {self.description}"
        return f"{self.norm_class}"

    class Meta:
        managed = False
        db_table = "core_sionimportmodel"
        ordering = ["serial_number"]


class SionNormNote(AuditModel):
    """
    Supplementary notes attached to a SION norm class.
    DB table: core_sionnormnote (owned by legacy).
    """

    uid = models.UUIDField(null=True, blank=True, unique=True, db_index=True, editable=False)
    sion_norm = models.ForeignKey(
        "core.SionNormClassModel",
        on_delete=models.CASCADE,
        related_name="notes",
    )
    note_text = models.TextField()
    display_order = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.sion_norm.norm_class} - Note {self.display_order}"

    class Meta:
        managed = False
        db_table = "core_sionnormnote"
        ordering = ["display_order", "id"]
        verbose_name = "SION Norm Note"
        verbose_name_plural = "SION Norm Notes"


class SionNormCondition(AuditModel):
    """
    Conditions attached to a SION norm class (e.g., import conditions).
    DB table: core_sionnormcondition (owned by legacy).
    """

    uid = models.UUIDField(null=True, blank=True, unique=True, db_index=True, editable=False)
    sion_norm = models.ForeignKey(
        "core.SionNormClassModel",
        on_delete=models.CASCADE,
        related_name="conditions",
    )
    condition_text = models.TextField()
    display_order = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.sion_norm.norm_class} - Condition {self.display_order}"

    class Meta:
        managed = False
        db_table = "core_sionnormcondition"
        ordering = ["display_order", "id"]
        verbose_name = "SION Norm Condition"
        verbose_name_plural = "SION Norm Conditions"


# ---------------------------------------------------------------------------
# Deprecated model (kept for backward compatibility)
# ---------------------------------------------------------------------------

class ItemHeadModel(AuditModel):
    """
    DEPRECATED: Use ItemGroupModel instead.

    This model was superseded by ItemGroupModel. It is retained here with
    managed=False to support any legacy FK references or read paths that
    may still reference this table until they are migrated.

    Do NOT add new business logic referencing ItemHeadModel.
    DB table: core_itemheadmodel (owned by legacy).
    """

    name = models.CharField(max_length=255, unique=True)
    unit_rate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    is_restricted = models.BooleanField(default=False)
    restriction_norm = models.ForeignKey(
        "core.SionNormClassModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="restricted_heads",
        help_text="Norm class for restriction (e.g., E132)",
    )
    restriction_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
        help_text="Restriction percentage (e.g., 3.00 for 3%)",
    )
    dict_key = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = "core_itemheadmodel"
        verbose_name = "Item Head (Deprecated)"
        verbose_name_plural = "Item Heads (Deprecated)"


# ---------------------------------------------------------------------------
# System / ops models
# ---------------------------------------------------------------------------

class MasterChange(models.Model):
    """
    Append-only change feed for master/reference data.
    Powers delta-sync and delete propagation.
    DB table: core_masterchange (owned by legacy).
    """

    OP_CREATE = "create"
    OP_UPDATE = "update"
    OP_DELETE = "delete"
    OP_CHOICES = [
        (OP_CREATE, "create"),
        (OP_UPDATE, "update"),
        (OP_DELETE, "delete"),
    ]

    model_label = models.CharField(max_length=100, db_index=True)
    natural_key = models.CharField(max_length=255, db_index=True)
    op = models.CharField(max_length=10, choices=OP_CHOICES)
    at = models.DateTimeField(default=timezone.now, db_index=True)

    def __str__(self):
        return f"{self.op} {self.model_label}[{self.natural_key}] @ {self.at:%Y-%m-%d %H:%M:%S}"

    class Meta:
        managed = False
        db_table = "core_masterchange"
        ordering = ["at"]
        indexes = [
            models.Index(fields=["model_label", "at"]),
        ]


class CeleryTaskTracker(models.Model):
    """
    Tracks Celery task execution for monitoring and cleanup.
    DB table: core_celerytasktracker (owned by legacy).
    """

    STATUS_PENDING = "PENDING"
    STATUS_STARTED = "STARTED"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILURE = "FAILURE"
    STATUS_RETRY = "RETRY"
    STATUS_REVOKED = "REVOKED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_STARTED, "Started"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILURE, "Failure"),
        (STATUS_RETRY, "Retry"),
        (STATUS_REVOKED, "Revoked"),
    ]

    task_id = models.CharField(max_length=255, unique=True, db_index=True)
    task_name = models.CharField(max_length=255, db_index=True)
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    args = models.JSONField(default=list, blank=True)
    kwargs = models.JSONField(default=dict, blank=True)
    result = models.JSONField(null=True, blank=True)
    traceback = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    current = models.IntegerField(default=0)
    total = models.IntegerField(default=100)
    progress_message = models.TextField(blank=True)

    def __str__(self):
        return f"{self.task_name} ({self.task_id[:8]}) - {self.status}"

    @property
    def duration(self):
        """Task duration in seconds, or None if not completed."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    class Meta:
        managed = False
        db_table = "core_celerytasktracker"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "completed_at"]),
            models.Index(fields=["task_name", "status"]),
        ]


class ActivityLog(models.Model):
    """
    Records every significant user action for auditing purposes.
    DB table: core_activitylog (owned by legacy).
    """

    ACTION_LOGIN = "LOGIN"
    ACTION_LOGOUT = "LOGOUT"
    ACTION_VIEW = "VIEW"
    ACTION_CREATE = "CREATE"
    ACTION_UPDATE = "UPDATE"
    ACTION_DELETE = "DELETE"
    ACTION_DOWNLOAD = "DOWNLOAD"
    ACTION_UPLOAD = "UPLOAD"
    ACTION_EXPORT = "EXPORT"
    ACTION_SEARCH = "SEARCH"

    ACTION_CHOICES = [
        (ACTION_LOGIN, "Login"),
        (ACTION_LOGOUT, "Logout"),
        (ACTION_VIEW, "View"),
        (ACTION_CREATE, "Create"),
        (ACTION_UPDATE, "Update"),
        (ACTION_DELETE, "Delete"),
        (ACTION_DOWNLOAD, "Download"),
        (ACTION_UPLOAD, "Upload"),
        (ACTION_EXPORT, "Export"),
        (ACTION_SEARCH, "Search"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="core_activity_logs",
    )
    username = models.CharField(max_length=150, blank=True, db_index=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    module = models.CharField(max_length=60, blank=True, db_index=True)
    resource_id = models.CharField(max_length=60, blank=True)
    description = models.CharField(max_length=500, blank=True)
    endpoint = models.CharField(max_length=500, blank=True)
    method = models.CharField(max_length=10, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.username} | {self.action} | {self.module} | {self.timestamp:%Y-%m-%d %H:%M}"

    class Meta:
        managed = False
        db_table = "core_activitylog"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["module", "timestamp"]),
            models.Index(fields=["username", "timestamp"]),
        ]
