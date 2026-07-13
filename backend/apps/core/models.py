# core/models.py
"""
Core models (clean, Decimal-safe) that import shared choices from core/constants.py.
Replace your existing core/models.py with this file (backup first).
"""

import uuid
from threading import local

from django.conf import settings
from django.core.validators import RegexValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from .constants import (
    DEC_0,
)

# Canonical deterministic-uid recipe shared with MDS export/load (ADR-001).
# Imported lazily-tolerant: if the mds_client package is not installed in this
# environment, a byte-identical inline fallback is used so core.models still
# imports (the mirror sync just won't be active). See mds_client/keys.py.
try:
    from mds_client.keys import (
        synthetic_uid as _mds_synthetic_uid,
        sig_head_sion_norm as _sig_head_sion_norm,
        sig_sion_export as _sig_sion_export,
        sig_sion_import as _sig_sion_import,
        sig_sion_norm_note as _sig_sion_norm_note,
        sig_sion_norm_condition as _sig_sion_norm_condition,
        sig_product_description as _sig_product_description,
        sig_unit_price as _sig_unit_price,
    )
except ImportError:  # pragma: no cover - fallback keeps core importable w/o client
    from datetime import date as _date, datetime as _datetime
    from decimal import Decimal as _Decimal

    _MDS_NS = uuid.UUID("6f1a9d2e-0c4b-5a7e-8b3f-2d9c1e4a7b60")

    def _mds_ss(v):
        if v is None:
            return ""
        if isinstance(v, (_datetime, _date)):
            return v.isoformat()
        if isinstance(v, _Decimal):
            return str(v)
        return str(v)

    def _mds_synthetic_uid(label, parent_nk, sig):
        return str(uuid.uuid5(_MDS_NS, f"{label}|{parent_nk or ''}|{sig or ''}"))

    def _sig_head_sion_norm(name):
        return _mds_ss(name)

    def _sig_sion_export(description, quantity, unit):
        return "|".join([_mds_ss(description), _mds_ss(quantity), _mds_ss(unit)])

    def _sig_sion_import(serial_number, description, quantity, unit, condition, hs_code):
        return "|".join([str(serial_number), _mds_ss(description), _mds_ss(quantity),
                         _mds_ss(unit), _mds_ss(condition), _mds_ss(hs_code)])

    def _sig_sion_norm_note(display_order, note_text):
        return "|".join([str(display_order), _mds_ss(note_text)])

    def _sig_sion_norm_condition(display_order, condition_text):
        return "|".join([str(display_order), _mds_ss(condition_text)])

    def _sig_product_description(product_description):
        return _mds_ss(product_description)

    def _sig_unit_price(name, unit_price, label):
        return "|".join([_mds_ss(name), _mds_ss(unit_price), _mds_ss(label)])

alpha = RegexValidator(r'^[a-zA-Z ]*$', 'Only alpha characters are allowed.')


def company_upload_path(instance, filename):
    # Store company files under companies/<id>/
    return f"companies/{instance.id}/{filename}"


# Thread-local storage to hold the current user during a request
_user = local()


def set_current_user(user):
    """Store the current user in thread-local context for model save hooks."""
    _user.value = user


def get_current_user():
    """Safely get the current user from thread-local context."""
    return getattr(_user, "value", None)


class AuditModel(models.Model):
    """
    Abstract base with automatic created/modified auditing.
    - created_on / modified_on timestamps
    - created_by / modified_by FK auto-filled from current user
    """

    created_on = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created",
    )
    modified_on = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_updated",
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Automatically set created_by and modified_by
        from the thread-local current user (if available).
        """
        user = get_current_user()
        if user and getattr(user, "is_authenticated", False):
            if not self.pk and not self.created_by_id:
                # New object — set both created_by and modified_by
                self.created_by = user
                self.modified_by = user
            else:
                # Existing object — update only modified_by
                self.modified_by = user

        super().save(*args, **kwargs)


class SyncTimestampModel(models.Model):
    """
    Lightweight created/modified timestamps for masters that are bulk-imported
    (no per-user auditing) but must participate in delta sync (`updated_since`).

    Nullable + defaulted so the field can be added to existing tables without a
    one-off-default prompt; existing rows are backfilled by the migration.
    See docs/architecture/ADR-001-master-data-service.md (Phase 1).
    """

    created_on = models.DateTimeField(default=timezone.now, editable=False)
    modified_on = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        abstract = True


class SyntheticUidMixin(models.Model):
    """Adds a deterministic synthetic natural key (`uid`) to a KEYLESS master so
    it can converge across servers via the MDS mirror sync (ADR-001 Decision 6).

    The `uid` is a uuid5 derived from the row's identifying content using the
    SAME canonical recipe as the MDS export/load (mds_client.keys), so the same
    logical row gets the SAME uid on every server — the mirror sync then upserts
    by `uid` and never creates duplicates.

    Nullable + unique + indexed so it can be added additively to existing tables;
    existing rows are backfilled by a data migration, and `save()` fills it in
    for any new/blank row. Subclasses implement `compute_uid()`.
    """

    uid = models.UUIDField(null=True, blank=True, unique=True, db_index=True, editable=False)

    class Meta:
        abstract = True

    def compute_uid(self):  # pragma: no cover - overridden by each subclass
        """Return the deterministic uid string for this row. Subclasses override."""
        raise NotImplementedError

    def save(self, *args, **kwargs):
        if not self.uid:
            try:
                self.uid = self.compute_uid()
            except Exception:  # noqa: BLE001 - never block a save on uid computation
                # A row that can't yet compute its uid (e.g. an unsaved required
                # FK) is saved without one; the backfill / a later save fills it.
                self.uid = None
        super().save(*args, **kwargs)


class MasterChange(models.Model):
    """
    Append-only change feed for master/reference data.

    Powers delta-sync webhooks and — crucially — **delete propagation**: deletes
    are invisible to an `updated_since` pull, so every create/update/delete on a
    master appends a row here keyed by the master's natural (business) key.
    See docs/architecture/ADR-001-master-data-service.md (Decision 4).
    """

    OP_CREATE = "create"
    OP_UPDATE = "update"
    OP_DELETE = "delete"
    OP_CHOICES = [
        (OP_CREATE, "create"),
        (OP_UPDATE, "update"),
        (OP_DELETE, "delete"),
    ]

    model_label = models.CharField(max_length=100, db_index=True)  # e.g. "core.CompanyModel"
    natural_key = models.CharField(max_length=255, db_index=True)  # business-key value
    op = models.CharField(max_length=10, choices=OP_CHOICES)
    at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["at"]
        indexes = [
            models.Index(fields=["model_label", "at"]),
        ]

    def __str__(self):
        return f"{self.op} {self.model_label}[{self.natural_key}] @ {self.at:%Y-%m-%d %H:%M:%S}"


class CompanyModel(AuditModel):
    iec = models.CharField(max_length=10, unique=True)
    pan = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        validators=[
            RegexValidator(regex=r'^[A-Z]{5}[0-9]{4}[A-Z]$', message="Enter a valid PAN number.")
        ]
    )
    gst_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        validators=[
            RegexValidator(regex=r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$',
                           message="Enter a valid GST number.")
        ]
    )
    name = models.CharField(max_length=255, blank=True, default='')
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address_line_1 = models.TextField(blank=True, default='')
    address_line_2 = models.TextField(blank=True, default='')
    # Branding / Legal Docs
    logo = models.ImageField(upload_to=company_upload_path, null=True, blank=True)
    signature = models.ImageField(upload_to=company_upload_path, null=True, blank=True)
    stamp = models.ImageField(upload_to=company_upload_path, null=True, blank=True)
    bill_colour = models.CharField(max_length=20, default="#333")
    # Banking fields
    bank_account_number = models.CharField(max_length=30, null=True, blank=True)
    bank_name = models.CharField(max_length=255, null=True, blank=True)
    ifsc_code = models.CharField(
        max_length=11,
        null=True,
        blank=True,
        validators=[
            RegexValidator(regex=r'^[A-Z]{4}0[A-Z0-9]{6}$', message="Enter a valid IFSC code.")
        ]
    )

    ACCOUNT_TYPE_CHOICES = [
        ("SAVINGS", "Savings"),
        ("CURRENT", "Current"),
        ("OD", "Overdraft"),
    ]
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, null=True, blank=True)

    def __str__(self):
        return self.name if self.name else self.iec

    def get_absolute_url(self):
        return reverse('masters:companymodel-list')

    def full_address(self):
        parts = [self.address_line_1, self.address_line_2]
        return " ".join(p for p in parts if p).strip()

    class Meta:
        ordering = ['name']


class PortModel(AuditModel):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ('code', 'name')
        unique_together = ('name', 'code')

    def __str__(self):
        return f"{self.code}"


class ItemHeadModel(AuditModel):
    """Deprecated: Use ItemGroupModel instead"""
    name = models.CharField(max_length=255, unique=True)
    unit_rate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    is_restricted = models.BooleanField(default=False)
    restriction_norm = models.ForeignKey(
        'core.SionNormClassModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='restricted_heads',
        help_text="Norm class for restriction (e.g., E132)"
    )
    restriction_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
        help_text="Restriction percentage (e.g., 3.00 for 3%)"
    )
    dict_key = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Item Head (Deprecated)"
        verbose_name_plural = "Item Heads (Deprecated)"


class ItemGroupModel(AuditModel):
    """Group model for categorizing items"""
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class ItemNameModel(AuditModel):
    group = models.ForeignKey('core.ItemGroupModel', on_delete=models.CASCADE, related_name='items', null=True,
                              blank=True)
    name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    sion_norm_class = models.ForeignKey(
        'core.SionNormClassModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items',
        help_text="SION norm class for restriction grouping (e.g., E1, E2)"
    )
    restriction_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
        help_text="Restriction percentage for this item (e.g., 2.00 for 2%, 10.00 for 10%)"
    )
    display_order = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Display order in reports (lower numbers appear first). Must be unique per norm class."
    )

    class Meta:
        ordering = ['display_order', 'group__name', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('masters:itemnamemodel-list')


class HSCodeModel(AuditModel):
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
    search_fields = ('hs_code', 'product_description')

    def __str__(self):
        return f"{self.hs_code}"

    class Meta:
        ordering = ('hs_code',)


class HeadSIONNormsModel(SyntheticUidMixin, SyncTimestampModel):
    name = models.CharField(max_length=255)

    def compute_uid(self):
        return _mds_synthetic_uid("HeadSIONNorm", "", _sig_head_sion_norm(self.name))

    def __str__(self):
        return self.name


class SionNormClassModel(AuditModel):
    head_norm = models.ForeignKey('core.HeadSIONNormsModel', on_delete=models.CASCADE, related_name='sion_head')
    description = models.CharField(max_length=255, null=True, blank=True)
    norm_class = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.norm_class}"

    def get_absolute_url(self):
        return reverse('masters:sionnormclassmodel-detail', kwargs={'pk': self.pk})


class SIONExportModel(SyntheticUidMixin, SyncTimestampModel):
    norm_class = models.ForeignKey('core.SionNormClassModel', on_delete=models.CASCADE, related_name='export_norm')
    description = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    unit = models.CharField(max_length=255, null=True, blank=True)

    def compute_uid(self):
        parent_nk = self.norm_class.norm_class if self.norm_class_id else ""
        return _mds_synthetic_uid(
            "SIONExport", parent_nk,
            _sig_sion_export(self.description, self.quantity, self.unit),
        )

    def __str__(self):
        return f"{self.norm_class} | {self.description}" if self.description else f"{self.norm_class}"


class SIONImportModel(SyntheticUidMixin, SyncTimestampModel):
    serial_number = models.IntegerField(default=0)
    norm_class = models.ForeignKey('core.SionNormClassModel', on_delete=models.CASCADE, related_name='import_norm')
    hsn_code = models.ForeignKey(HSCodeModel, on_delete=models.SET_NULL, related_name='sion_imports', null=True,
                                 blank=True, db_column='hsn_code_id')
    description = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    unit = models.CharField(max_length=255, null=True, blank=True)
    condition = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ['serial_number']

    def compute_uid(self):
        parent_nk = self.norm_class.norm_class if self.norm_class_id else ""
        hs = self.hsn_code.hs_code if self.hsn_code_id else ""
        return _mds_synthetic_uid(
            "SIONImport", parent_nk,
            _sig_sion_import(
                self.serial_number, self.description, self.quantity,
                self.unit, self.condition, hs,
            ),
        )

    def __str__(self):
        return f"{self.norm_class} | {self.description}" if self.description else f"{self.norm_class}"


class SionNormNote(SyntheticUidMixin, AuditModel):
    """Multiple notes per SION norm"""
    sion_norm = models.ForeignKey('SionNormClassModel', on_delete=models.CASCADE, related_name='notes')
    note_text = models.TextField()
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = "SION Norm Note"
        verbose_name_plural = "SION Norm Notes"

    def compute_uid(self):
        parent_nk = self.sion_norm.norm_class if self.sion_norm_id else ""
        return _mds_synthetic_uid(
            "SIONNormNote", parent_nk,
            _sig_sion_norm_note(self.display_order, self.note_text),
        )

    def __str__(self):
        return f"{self.sion_norm.norm_class} - Note {self.display_order}"


class SionNormCondition(SyntheticUidMixin, AuditModel):
    """Multiple conditions per SION norm"""
    sion_norm = models.ForeignKey('SionNormClassModel', on_delete=models.CASCADE, related_name='conditions')
    condition_text = models.TextField()
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = "SION Norm Condition"
        verbose_name_plural = "SION Norm Conditions"

    def compute_uid(self):
        parent_nk = self.sion_norm.norm_class if self.sion_norm_id else ""
        return _mds_synthetic_uid(
            "SIONNormCondition", parent_nk,
            _sig_sion_norm_condition(self.display_order, self.condition_text),
        )

    def __str__(self):
        return f"{self.sion_norm.norm_class} - Condition {self.display_order}"


class ProductDescriptionModel(SyntheticUidMixin, AuditModel):
    hs_code = models.ForeignKey('core.HSCodeModel', on_delete=models.PROTECT, related_name='product_descriptions')
    product_description = models.TextField()

    def compute_uid(self):
        parent_nk = self.hs_code.hs_code if self.hs_code_id else ""
        return _mds_synthetic_uid(
            "ProductDescription", parent_nk,
            _sig_product_description(self.product_description),
        )

    def __str__(self):
        return self.product_description


class TransferLetterModel(AuditModel):
    name = models.CharField(max_length=255)
    tl = models.FileField(upload_to='tl')

    class Meta:
        ordering = ['name', 'id']

    def __str__(self):
        return self.name


class UnitPriceModel(SyntheticUidMixin, AuditModel):
    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    label = models.CharField(max_length=255, default='')

    def compute_uid(self):
        return _mds_synthetic_uid(
            "UnitPrice", "",
            _sig_unit_price(self.name, self.unit_price, self.label),
        )

    def __str__(self):
        return self.name


ACCOUNT_TYPES = (
    ('current', 'Current'),
    ('saving', 'Saving'),
)


class InvoiceEntity(models.Model):
    name = models.CharField(max_length=255)
    address_line_1 = models.TextField()
    address_line_2 = models.TextField(blank=True)
    pan_number = models.CharField(
        max_length=10,
        validators=[RegexValidator(regex=r'^[A-Z]{5}[0-9]{4}[A-Z]$', message="Enter a valid PAN number.")]
    )
    gst_number = models.CharField(
        max_length=15,
        validators=[RegexValidator(regex=r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$',
                                   message="Enter a valid GST number.")]
    )
    logo = models.ImageField(upload_to='entity_logos/', null=True, blank=True)

    bank_account_number = models.CharField(max_length=30)
    bank_name = models.CharField(max_length=100)
    ifsc_code = models.CharField(
        max_length=11,
        validators=[RegexValidator(regex=r'^[A-Z]{4}0[A-Z0-9]{6}$', message="Enter a valid IFSC code.")]
    )
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)
    bill_colour = models.CharField(max_length=10, null=True, blank=True)
    signature = models.ImageField(upload_to='entity_signature/', null=True, blank=True)
    stamp = models.ImageField(upload_to='entity_stamp/', null=True, blank=True)

    def __str__(self):
        return self.name


class SchemeCode(models.Model):
    code = models.CharField(max_length=10, unique=True)
    label = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.code} - {self.label}"


class NotificationNumber(models.Model):
    code = models.CharField(max_length=10, unique=True)
    label = models.CharField(max_length=100)

    def __str__(self):
        return self.label


class PurchaseStatus(models.Model):
    code = models.CharField(max_length=2, unique=True)
    label = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True, help_text="Whether this purchase status is active and should be shown in UI")
    display_order = models.IntegerField(default=0, help_text="Order for displaying in dropdowns")

    class Meta:
        ordering = ['display_order', 'label']
        verbose_name = "Purchase Status"
        verbose_name_plural = "Purchase Statuses"

    def __str__(self):
        return self.label


class ExchangeRateModel(AuditModel):
    """
    Exchange Rate model to store currency exchange rates.
    The active exchange rate is the latest one based on the date field.
    """
    date = models.DateField(unique=True, help_text="Date of the exchange rate")
    usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(DEC_0)],
        help_text="USD to INR exchange rate"
    )
    euro = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(DEC_0)],
        help_text="Euro to INR exchange rate"
    )
    pound_sterling = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(DEC_0)],
        help_text="Pound Sterling to INR exchange rate"
    )
    chinese_yuan = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(DEC_0)],
        help_text="Chinese Yuan to INR exchange rate"
    )

    class Meta:
        ordering = ['-date']  # Latest date first
        verbose_name = "Exchange Rate"
        verbose_name_plural = "Exchange Rates"
        indexes = [
            models.Index(fields=['-date']),  # Index for getting latest rate
        ]

    def __str__(self):
        return f"Exchange Rate - {self.date.strftime('%d-%m-%Y')}"

    @classmethod
    def get_active_rate(cls):
        """
        Get the most recent (active) exchange rate based on date.
        Returns the ExchangeRateModel instance with the latest date.
        """
        return cls.objects.first()  # Already ordered by -date

    @classmethod
    def get_rate_for_date(cls, date):
        """
        Get the exchange rate for a specific date.
        If no rate exists for that date, returns the most recent rate before that date.
        """
        return cls.objects.filter(date__lte=date).first()

    def save(self, *args, **kwargs):
        """Override save to ensure date uniqueness"""
        super().save(*args, **kwargs)


class CeleryTaskTracker(models.Model):
    """
    Track all Celery tasks for monitoring and cleanup.
    Automatically records task start, completion, and results.
    """
    task_id = models.CharField(max_length=255, unique=True, db_index=True)
    task_name = models.CharField(max_length=255, db_index=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ('PENDING', 'Pending'),
            ('STARTED', 'Started'),
            ('SUCCESS', 'Success'),
            ('FAILURE', 'Failure'),
            ('RETRY', 'Retry'),
            ('REVOKED', 'Revoked'),
        ],
        default='PENDING',
        db_index=True
    )

    # Task metadata
    args = models.JSONField(default=list, blank=True)
    kwargs = models.JSONField(default=dict, blank=True)
    result = models.JSONField(null=True, blank=True)
    traceback = models.TextField(null=True, blank=True)

    # Timing
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Progress tracking
    current = models.IntegerField(default=0)
    total = models.IntegerField(default=100)
    progress_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'completed_at']),
            models.Index(fields=['task_name', 'status']),
        ]

    def __str__(self):
        return f"{self.task_name} ({self.task_id[:8]}) - {self.status}"

    @property
    def duration(self):
        """Calculate task duration in seconds"""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


# ── Activity / Audit Log ──────────────────────────────────────────────────────

class ActivityLog(models.Model):
    """
    Records every significant user action in the system for auditing purposes.
    Written by ActivityLogMiddleware for all authenticated API requests plus
    explicit entries for login/logout.
    """
    ACTION_LOGIN    = 'LOGIN'
    ACTION_LOGOUT   = 'LOGOUT'
    ACTION_VIEW     = 'VIEW'
    ACTION_CREATE   = 'CREATE'
    ACTION_UPDATE   = 'UPDATE'
    ACTION_DELETE   = 'DELETE'
    ACTION_DOWNLOAD = 'DOWNLOAD'
    ACTION_UPLOAD   = 'UPLOAD'
    ACTION_EXPORT   = 'EXPORT'
    ACTION_SEARCH   = 'SEARCH'

    ACTION_CHOICES = [
        (ACTION_LOGIN,    'Login'),
        (ACTION_LOGOUT,   'Logout'),
        (ACTION_VIEW,     'View'),
        (ACTION_CREATE,   'Create'),
        (ACTION_UPDATE,   'Update'),
        (ACTION_DELETE,   'Delete'),
        (ACTION_DOWNLOAD, 'Download'),
        (ACTION_UPLOAD,   'Upload'),
        (ACTION_EXPORT,   'Export'),
        (ACTION_SEARCH,   'Search'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='activity_logs',
    )
    username    = models.CharField(max_length=150, blank=True, db_index=True)
    action      = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    module      = models.CharField(max_length=60, blank=True, db_index=True)
    resource_id = models.CharField(max_length=60, blank=True)
    description = models.CharField(max_length=500, blank=True)
    endpoint    = models.CharField(max_length=500, blank=True)
    method      = models.CharField(max_length=10, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.CharField(max_length=400, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    extra       = models.JSONField(default=dict, blank=True)
    timestamp   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['module', 'timestamp']),
            models.Index(fields=['username', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.username} | {self.action} | {self.module} | {self.timestamp:%Y-%m-%d %H:%M}"

