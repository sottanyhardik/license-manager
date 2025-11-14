"""
Refactored `models.py` for YOUR_APP — merged, cleaned, and improved version as requested.
Features:
 - AuditModel abstract base for created/modified tracking
 - company file upload path helper
 - PAN/GST/IFSC validators
 - more explicit/typed fields and sensible defaults
 - consistent related_name usage
 - kept behavior compatible with your provided snippets

Drop this file into your app (e.g. core/models.py), run `makemigrations` and `migrate`,
then run tests and review admin displays.
"""
from decimal import Decimal
from threading import local

from django.conf import settings
from django.core.validators import RegexValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property

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
    name = models.CharField(max_length=255, null=True, blank=True)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    address_line_1 = models.TextField(null=True, blank=True)
    address_line_2 = models.TextField(null=True, blank=True)
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
        return reverse('company-list')

    def full_address(self):
        if self.address_line_1 and self.address_line_2:
            return f"{self.address_line_1} {self.address_line_2}"
        return self.address or ""

    class Meta:
        ordering = ['name']


class PortModel(AuditModel):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ('code', 'name')
        unique_together = ('name', 'code')

    def __str__(self):
        return f"{self.code}"


class ItemHeadModel(AuditModel):
    name = models.CharField(max_length=255, unique=True)
    unit_rate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    is_restricted = models.BooleanField(default=False)
    dict_key = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class ItemNameModel(AuditModel):
    head = models.ForeignKey('core.ItemHeadModel', on_delete=models.CASCADE, related_name='items', null=True,
                             blank=True)
    name = models.CharField(max_length=255, unique=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('item-list')


class HSCodeModel(AuditModel):
    hs_code = models.CharField(max_length=8, unique=True)
    product_description = models.TextField(null=True, blank=True)
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
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


class HeadSIONNormsModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class SionNormClassModel(AuditModel):
    head_norm = models.ForeignKey('core.HeadSIONNormsModel', on_delete=models.CASCADE, related_name='sion_head')
    description = models.CharField(max_length=255, null=True, blank=True)
    norm_class = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return f"{self.norm_class}"

    def get_absolute_url(self):
        return reverse('Sion-detail', kwargs={'pk': self.pk})


class SIONExportModel(models.Model):
    norm_class = models.ForeignKey('core.SionNormClassModel', on_delete=models.CASCADE, related_name='export_norm')
    description = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    unit = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.norm_class} | {self.description}" if self.description else f"{self.norm_class}"


class SIONImportModel(models.Model):
    sr_no = models.IntegerField(default=0)
    norm_class = models.ForeignKey('core.SionNormClassModel', on_delete=models.CASCADE, related_name='import_norm')
    hsn_code = models.ForeignKey(HSCodeModel, on_delete=models.SET_NULL, related_name='sion_imports', null=True,
                                 blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    unit = models.CharField(max_length=255, null=True, blank=True)
    condition = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ['sr_no']

    def __str__(self):
        return f"{self.norm_class} | {self.description}" if self.description else f"{self.norm_class}"


class HSCodeDutyModel(AuditModel):
    hs_code = models.CharField(max_length=8, unique=True)
    basic_custom_duty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    additional_duty_of_customs = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    custom_health_CESS = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    social_welfare_surcharge = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    additional_CVD = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    IGST_levy = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    compensation_cess = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    total_duty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    sample_on_lakh = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    is_fetch = models.BooleanField(default=False)
    is_fetch_xls = models.BooleanField(default=False)
    list_filter = ('is_fetch', 'is_fetch_xls')
    admin_search_fields = ('hs_code',)

    def __str__(self):
        return self.hs_code

    @cached_property
    def product_description(self):
        return '\n'.join(
            [pd['product_description'] for pd in self.product_descriptions.all().values('product_description')])


class ProductDescriptionModel(AuditModel):
    hs_code = models.ForeignKey('core.HSCodeDutyModel', on_delete=models.PROTECT, related_name='product_descriptions')
    product_description = models.TextField()

    def __str__(self):
        return self.product_description


class TransferLetterModel(AuditModel):
    name = models.CharField(max_length=255)
    tl = models.FileField(upload_to='tl')

    def __str__(self):
        return self.name


class UnitPriceModel(AuditModel):
    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    label = models.CharField(max_length=255, default='')

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
    pan_number = models.CharField(max_length=10)
    gst_number = models.CharField(max_length=15)
    logo = models.ImageField(upload_to='entity_logos/', null=True, blank=True)

    bank_account_number = models.CharField(max_length=30)
    bank_name = models.CharField(max_length=100)
    ifsc_code = models.CharField(max_length=11)
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

    def __str__(self):
        return self.label
