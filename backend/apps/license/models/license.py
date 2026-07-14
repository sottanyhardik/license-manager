# license/models/license.py
"""
All License domain models.

Every model uses managed=False — these tables already exist in the legacy
PostgreSQL database. Django will never CREATE, ALTER, or DROP them.

Field names, types, and db_table values match the legacy schema exactly.
Cross-app FKs that reference apps not yet built (bill_of_entry, allotment,
trade) are expressed as string references so they resolve lazily at runtime.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models.masters import AuditModel

# ---------------------------------------------------------------------------
# Local constants
# ---------------------------------------------------------------------------
DEC_0 = Decimal("0")

UNIT_CHOICES = (
    ("KGS", "KGS"),
    ("MTS", "MTS"),
    ("NOS", "NOS"),
    ("PCS", "PCS"),
    ("LTR", "LTR"),
    ("MTR", "MTR"),
    ("SQM", "SQM"),
    ("SET", "SET"),
    ("DZN", "DZN"),
    ("PAR", "PAR"),
    ("OTH", "OTH"),
)

CURRENCY_CHOICES = (
    ("USD", "USD"),
    ("EUR", "EUR"),
    ("GBP", "GBP"),
    ("JPY", "JPY"),
    ("CNY", "CNY"),
    ("INR", "INR"),
    ("AUD", "AUD"),
    ("CAD", "CAD"),
    ("SGD", "SGD"),
    ("CHF", "CHF"),
    ("AED", "AED"),
    ("HKD", "HKD"),
    ("SEK", "SEK"),
    ("NZD", "NZD"),
    ("OTH", "OTH"),
)

DOCUMENT_TYPE_CHOICES = (
    ("LICENSE COPY", "LICENSE COPY"),
    ("TRANSFER LETTER", "TRANSFER LETTER"),
    ("OTHER", "OTHER"),
)

INCENTIVE_LICENSE_TYPE_CHOICES = (
    ("RODTEP", "RODTEP"),
    ("ROSTL", "ROSTL"),
    ("MEIS", "MEIS"),
)

SOLD_STATUS_CHOICES = (
    ("NO", "NO"),
    ("PARTIAL", "PARTIAL"),
    ("YES", "YES"),
)

PURCHASE_MODE_CHOICES = (
    ("AMOUNT", "Amount-based"),
    ("QTY", "Quantity-based"),
)

PURCHASE_AMOUNT_SOURCE_CHOICES = (
    ("FOB_INR", "FOB (INR)"),
    ("CIF_INR", "CIF (INR)"),
    ("CIF_USD", "CIF (USD)"),
)

BILLING_MODE_CHOICES = (
    ("kg", "kg"),
    ("cif", "cif"),
    ("fob", "fob"),
)


# ---------------------------------------------------------------------------
# Core license models
# ---------------------------------------------------------------------------

class LicenseDetailsModel(AuditModel):
    """
    Central license record — one row per Advance Licence.

    All financial and administrative sub-data hangs off this via
    OneToOne or FK relations (balance, flags, notes, ownership, items).
    """

    purchase_status = models.ForeignKey(
        "core.PurchaseStatus",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="licenses",
    )
    scheme_code = models.ForeignKey(
        "core.SchemeCode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="licenses",
    )
    notification_number = models.ForeignKey(
        "core.NotificationNumber",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="licenses",
    )
    exporter = models.ForeignKey(
        "core.CompanyModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="licenses",
    )
    port = models.ForeignKey(
        "core.PortModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="licenses",
    )

    license_number = models.CharField(max_length=255, unique=True)
    license_date = models.DateField(null=True, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    file_number = models.CharField(max_length=255, blank=True, default="")
    registration_number = models.CharField(max_length=255, blank=True, default="")
    registration_date = models.DateField(null=True, blank=True)
    ge_file_number = models.IntegerField(null=True, blank=True)
    archived_exporter_name = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        managed = False
        db_table = "license_licensedetailsmodel"
        ordering = ("license_expiry_date", "license_date")

    def __str__(self):
        return self.license_number


class LicenseExportItemModel(models.Model):
    """Export items attached to a license (the credit side)."""

    license = models.ForeignKey(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        related_name="export_license",
    )
    item = models.ForeignKey(
        "core.ItemNameModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="license_export_items",
    )
    norm_class = models.ForeignKey(
        "core.SionNormClassModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="license_export_items",
    )

    description = models.CharField(max_length=2000, blank=True, default="")
    duty_type = models.CharField(max_length=50, blank=True, default="")
    net_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    old_quantity = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, blank=True, default="")
    fob_fc = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    fob_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    fob_exchange_rate = models.DecimalField(max_digits=15, decimal_places=6, default=DEC_0)
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, blank=True, default="")
    value_addition = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    cif_fc = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    cif_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)

    class Meta:
        managed = False
        db_table = "license_licenseexportitemmodel"

    def __str__(self):
        return f"Export item {self.pk} for license {self.license_id}"


class LicenseImportItemsModel(models.Model):
    """
    Import items on the license (the debit side).

    available_quantity / available_value are denormalized convenience fields
    kept in sync by balance_service.recompute_license_balance().
    """

    license = models.ForeignKey(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        related_name="import_license",
    )
    hs_code = models.ForeignKey(
        "core.HSCodeModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="license_import_items",
    )
    items = models.ManyToManyField(
        "core.ItemNameModel",
        blank=True,
        related_name="license_import_item",
    )

    serial_number = models.IntegerField()
    description = models.CharField(max_length=2000, blank=True, default="")
    quantity = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_0)
    old_quantity = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_0)
    unit = models.CharField(max_length=10, blank=True, default="")
    cif_fc = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    cif_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    available_quantity = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_0)
    available_value = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    debited_quantity = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_0)
    debited_value = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    allotted_quantity = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_0)
    allotted_value = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    is_restricted = models.BooleanField(default=False)
    condition_type = models.CharField(max_length=8, blank=True, default="")
    comment = models.TextField(blank=True, default="")

    class Meta:
        managed = False
        db_table = "license_licenseimportitemsmodel"
        unique_together = (("license", "serial_number"),)

    def __str__(self):
        return f"Import item {self.serial_number} for license {self.license_id}"


# ---------------------------------------------------------------------------
# OneToOne satellite models hanging off LicenseDetailsModel
# ---------------------------------------------------------------------------

class LicenseBalance(models.Model):
    """Running CIF balance for a license, refreshed asynchronously."""

    license = models.OneToOneField(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        related_name="balance",
        primary_key=True,
    )
    balance_cif = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    ledger_date = models.DateField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "license_licensebalance"

    def __str__(self):
        return f"Balance {self.balance_cif} for license {self.license_id}"


class LicenseFlags(models.Model):
    """Boolean flag bag for a license — status indicators."""

    license = models.OneToOneField(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        related_name="flags",
        primary_key=True,
    )
    is_active = models.BooleanField(default=True)
    is_audit = models.BooleanField(default=False)
    is_mnm = models.BooleanField(default=False)
    is_not_registered = models.BooleanField(default=False)
    is_null = models.BooleanField(default=False)
    is_au = models.BooleanField(default=False)
    is_incomplete = models.BooleanField(default=False)
    is_expired = models.BooleanField(default=False)
    is_individual = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "license_licenseflags"

    def __str__(self):
        return f"Flags for license {self.license_id}"


class LicenseNotes(models.Model):
    """Free-text notes associated with a license."""

    license = models.OneToOneField(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        related_name="notes",
        primary_key=True,
    )
    user_comment = models.TextField(blank=True, default="")
    condition_sheet = models.TextField(blank=True, default="")
    user_restrictions = models.TextField(blank=True, default="")
    balance_report_notes = models.TextField(blank=True, default="")

    class Meta:
        managed = False
        db_table = "license_licensenotes"

    def __str__(self):
        return f"Notes for license {self.license_id}"


class LicenseOwnership(models.Model):
    """Tracks the current owner of a license (may differ from exporter)."""

    license = models.OneToOneField(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        related_name="ownership",
        primary_key=True,
    )
    current_owner = models.ForeignKey(
        "core.CompanyModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_licenses",
    )
    file_transfer_status = models.TextField(blank=True, default="")
    last_ownership_fetch = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "license_licenseownership"

    def __str__(self):
        return f"Ownership for license {self.license_id}"


# ---------------------------------------------------------------------------
# Document / transfer / plan / purchase models
# ---------------------------------------------------------------------------

class LicenseDocumentModel(models.Model):
    """File attachments linked to a license."""

    license = models.ForeignKey(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        related_name="license_documents",
    )
    type = models.CharField(max_length=50, choices=DOCUMENT_TYPE_CHOICES, blank=True, default="")
    file = models.FileField(upload_to="license_documents/", null=True, blank=True)

    class Meta:
        managed = False
        db_table = "license_licensedocumentmodel"

    def __str__(self):
        return f"Document ({self.type}) for license {self.license_id}"


class LicenseTransferModel(models.Model):
    """Records a license ownership transfer between two companies."""

    license = models.ForeignKey(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        related_name="transfers",
    )
    from_company = models.ForeignKey(
        "core.CompanyModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="outgoing_transfers",
    )
    to_company = models.ForeignKey(
        "core.CompanyModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incoming_transfers",
    )
    transfer_initiation_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="initiated_transfers",
    )
    acceptance_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accepted_transfers",
    )

    transfer_date = models.DateField(null=True, blank=True)
    transfer_status = models.CharField(max_length=50, blank=True, default="")
    transfer_initiation_date = models.DateTimeField(null=True, blank=True)
    transfer_acceptance_date = models.DateTimeField(null=True, blank=True)
    cbic_status = models.CharField(max_length=255, blank=True, default="")
    cbic_response_date = models.DateTimeField(null=True, blank=True)
    user_id_transfer_initiation = models.CharField(max_length=255, blank=True, default="")
    user_id_acceptance = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        managed = False
        db_table = "license_licensetransfermodel"

    def __str__(self):
        return f"Transfer for license {self.license_id} → status={self.transfer_status}"


class LicenseItemPlan(AuditModel):
    """
    Planned utilization of an import item — used for forward planning before
    a Bill of Entry is raised.
    """

    import_item = models.ForeignKey(
        LicenseImportItemsModel,
        on_delete=models.CASCADE,
        related_name="utilization_plans",
    )
    item_name = models.ForeignKey(
        "core.ItemNameModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="license_item_plans",
    )
    license = models.ForeignKey(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        related_name="item_plans",
    )

    planned_quantity = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_0)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    planned_cif_fc = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    planned_cif_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    note = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        managed = False
        db_table = "license_licenseitemplan"

    def __str__(self):
        return f"ItemPlan {self.pk} for license {self.license_id}"


class LicensePurchase(AuditModel):
    """Records a market purchase of an advance license."""

    license = models.ForeignKey(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        related_name="purchases",
    )
    purchasing_entity = models.ForeignKey(
        "core.CompanyModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="license_purchases",
    )
    supplier = models.ForeignKey(
        "core.CompanyModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="license_supplied",
    )

    supplier_pan = models.CharField(max_length=20, blank=True, default="")
    supplier_gst = models.CharField(max_length=20, blank=True, default="")
    invoice_number = models.CharField(max_length=100, blank=True, default="")
    invoice_date = models.DateField(null=True, blank=True)
    invoice_copy = models.FileField(upload_to="license_purchase_invoices/", null=True, blank=True)
    mode = models.CharField(max_length=20, choices=PURCHASE_MODE_CHOICES, blank=True, default="")
    amount_source = models.CharField(
        max_length=20, choices=PURCHASE_AMOUNT_SOURCE_CHOICES, blank=True, default=""
    )
    fob_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    cif_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    cif_usd = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=6, default=DEC_0)
    markup_pct = models.DecimalField(max_digits=15, decimal_places=6, default=DEC_0)
    product_name = models.CharField(max_length=500, blank=True, default="")
    quantity_kg = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_0)
    rate_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    amount_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)

    class Meta:
        managed = False
        db_table = "license_licensepurchase"

    def __str__(self):
        return f"Purchase {self.invoice_number} for license {self.license_id}"


# ---------------------------------------------------------------------------
# Incentive license (RODTEP / ROSTL / MEIS)
# ---------------------------------------------------------------------------

class IncentiveLicense(AuditModel):
    """
    Incentive scheme licenses (RODTEP / ROSTL / MEIS).

    Separate from advance licenses — simpler balance tracking via
    sold_value / balance_value fields.
    """

    exporter = models.ForeignKey(
        "core.CompanyModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incentive_licenses",
    )
    port_code = models.ForeignKey(
        "core.PortModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incentive_licenses",
    )

    license_type = models.CharField(
        max_length=10, choices=INCENTIVE_LICENSE_TYPE_CHOICES, blank=True, default=""
    )
    license_number = models.CharField(max_length=255, unique=True)
    license_date = models.DateField(null=True, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    license_value = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    sold_value = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    balance_value = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    sold_status = models.CharField(max_length=10, choices=SOLD_STATUS_CHOICES, blank=True, default="NO")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        managed = False
        db_table = "license_incentivelicense"

    def __str__(self):
        return f"{self.license_type} {self.license_number}"


# ---------------------------------------------------------------------------
# Invoice models
# ---------------------------------------------------------------------------

class Invoice(models.Model):
    """
    Invoice raised against a Bill of Entry for license sale.

    billing_mode controls how line items are priced (by kg, CIF, or FOB).
    """

    bills_of_entry = models.ForeignKey(
        "bill_of_entry.BillOfEntryModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices",
    )
    from_entity = models.ForeignKey(
        "core.InvoiceEntity",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices",
    )

    to_company_name = models.TextField(blank=True, default="")
    to_company_pan = models.TextField(blank=True, default="")
    to_company_gst_number = models.TextField(blank=True, default="")
    to_company_address_line_1 = models.TextField(blank=True, default="")
    to_company_address_line_2 = models.TextField(blank=True, default="")
    invoice_number = models.CharField(max_length=255, unique=True)
    invoice_date = models.DateField(null=True, blank=True)
    billing_mode = models.CharField(max_length=10, choices=BILLING_MODE_CHOICES, blank=True, default="")
    total_qty = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_0)
    total_cif_fc = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    total_cif_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    total_fob_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    total_amount_in_words = models.TextField(blank=True, default="")
    sale_type = models.CharField(max_length=50, blank=True, default="")

    class Meta:
        managed = False
        db_table = "license_invoice"

    def __str__(self):
        return f"Invoice {self.invoice_number}"


class InvoiceItem(models.Model):
    """One line item on an Invoice."""

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
    )
    sr_number = models.ForeignKey(
        LicenseImportItemsModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoice_items",
    )

    license_no = models.CharField(max_length=255, blank=True, default="")
    hs_code = models.CharField(max_length=50, blank=True, default="")
    qty = models.DecimalField(max_digits=15, decimal_places=3, default=DEC_0)
    cif_fc = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    cif_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    fob_inr = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)
    rate = models.DecimalField(max_digits=15, decimal_places=6, default=DEC_0)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=DEC_0)

    class Meta:
        managed = False
        db_table = "license_invoiceitem"

    def __str__(self):
        return f"InvoiceItem {self.pk} on invoice {self.invoice_id}"


# ---------------------------------------------------------------------------
# Inward / outward tracking models
# ---------------------------------------------------------------------------

class StatusModel(models.Model):
    """Lookup table for inward/outward status values."""

    name = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = "license_statusmodel"

    def __str__(self):
        return self.name


class OfficeModel(models.Model):
    """Lookup table for customs offices used in inward/outward tracking."""

    name = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = "license_officemodel"

    def __str__(self):
        return self.name


class AlongWithModel(models.Model):
    """Lookup — documents submitted along with inward/outward docket."""

    name = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = "license_alongwithmodel"

    def __str__(self):
        return self.name


class DateModel(models.Model):
    """Date dimension used by LicenseInwardOutwardModel."""

    date = models.DateField()

    class Meta:
        managed = False
        db_table = "license_datemodel"

    def __str__(self):
        return str(self.date)


class LicenseInwardOutwardModel(models.Model):
    """
    Tracks the physical movement of a license file to/from customs offices
    (inward = received back; outward = dispatched).
    """

    date = models.ForeignKey(
        DateModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inward_outward_entries",
    )
    license = models.ForeignKey(
        LicenseDetailsModel,
        on_delete=models.CASCADE,
        related_name="inward_outward_entries",
    )
    status = models.ForeignKey(
        StatusModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inward_outward_entries",
    )
    office = models.ForeignKey(
        OfficeModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inward_outward_entries",
    )
    along_with = models.ForeignKey(
        AlongWithModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inward_outward_entries",
    )

    description = models.TextField(blank=True, default="")
    amd_sheets_number = models.CharField(max_length=50, blank=True, default="")
    copy = models.BooleanField(default=False)
    annexure = models.BooleanField(default=False)
    tl = models.BooleanField(default=False)
    aro = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "license_licenseinwardoutwardmodel"

    def __str__(self):
        return f"InwardOutward {self.pk} for license {self.license_id}"
