"""Licence documents, workflow lookup models, inward/outward and transfers.

Split verbatim from core.py; behaviour unchanged.
"""
from __future__ import annotations


from django.conf import settings
from django.db import models
from django.utils.functional import cached_property


def license_path(instance, filename):
    """
    Upload path with naming convention:
    - LICENSE COPY -> licenses/<license_number>/<license_number> Copy.ext
    - TRANSFER LETTER -> licenses/<license_number>/<license_number> TL.ext
    - OTHER -> licenses/<license_number>/<license_number> Other.ext
    """
    import os
    import logging
    logger = logging.getLogger(__name__)

    # Safely get license number with fallback
    try:
        if not instance.license:
            logger.error(f"license_path called with instance.license=None, filename={filename}")
            license_number = 'temp'
        else:
            license_number = instance.license.license_number or 'unknown'
    except Exception as e:
        logger.error(f"Error in license_path: {e}, instance={instance}, filename={filename}")
        license_number = 'temp'

    file_ext = os.path.splitext(filename)[1]  # Get original extension

    # Map document type to suffix
    type_suffix_map = {
        'LICENSE COPY': 'Copy',
        'TRANSFER LETTER': 'TL',
        'OTHER': 'Other',
    }

    # Safely get type with fallback
    doc_type = getattr(instance, 'type', 'OTHER')
    suffix = type_suffix_map.get(doc_type, 'Document')

    return f"licenses/{license_number}/{license_number} {suffix}{file_ext}"


# -----------------------------
# Documents
# -----------------------------
class LicenseDocumentModel(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ('LICENSE COPY', 'LICENSE COPY'),
        ('TRANSFER LETTER', 'TRANSFER LETTER'),
        ('OTHER', 'OTHER'),
    ]

    license = models.ForeignKey("license.LicenseDetailsModel", on_delete=models.CASCADE,
                                related_name="license_documents")
    type = models.CharField(max_length=255, choices=DOCUMENT_TYPE_CHOICES)
    file = models.FileField(upload_to=license_path)

    def __str__(self) -> str:
        return f"{self.type} - {getattr(self.license, 'license_number', 'N/A')}"


# -----------------------------
# Status / Workflow Models
# -----------------------------
class StatusModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


class OfficeModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


class AlongWithModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


class DateModel(models.Model):
    date = models.DateField()

    def __str__(self) -> str:
        return str(self.date)


class LicenseInwardOutwardModel(models.Model):
    date = models.ForeignKey("license.DateModel", on_delete=models.CASCADE, related_name="license_status")
    license = models.ForeignKey("license.LicenseDetailsModel", on_delete=models.CASCADE,
                                related_name="license_status",
                                null=True, blank=True)
    status = models.ForeignKey("license.StatusModel", on_delete=models.CASCADE, related_name="license_status")
    office = models.ForeignKey("license.OfficeModel", on_delete=models.CASCADE, related_name="license_status")

    description = models.TextField(null=True, blank=True)
    amd_sheets_number = models.CharField(max_length=100, null=True, blank=True)
    copy = models.BooleanField(default=False)
    annexure = models.BooleanField(default=False)
    tl = models.BooleanField(default=False)
    aro = models.BooleanField(default=False)
    along_with = models.ForeignKey("license.AlongWithModel", on_delete=models.CASCADE,
                                   related_name="license_status",
                                   null=True, blank=True)

    def __str__(self) -> str:
        parts = []
        if self.license:
            parts.append(str(self.license))
        if self.copy:
            parts.append("copy")
        if self.amd_sheets_number:
            parts.append(f"amendment sheet: {self.amd_sheets_number}")
        if self.annexure:
            parts.append("& annexure")
        if self.status:
            parts.append(f"has been {self.status.name}")
        if self.office:
            parts.append(f"sent to {self.office.name}")
        if self.description:
            parts.append(f"for {self.description}")
        if self.along_with:
            parts.append(f"along with {self.along_with.name}")
        return " ".join(parts)

    @cached_property
    def ge_file_number(self):
        return self.license.ge_file_number if self.license else 0


# -----------------------------
# Transfers
# -----------------------------
class LicenseTransferModel(models.Model):
    license = models.ForeignKey("license.LicenseDetailsModel", on_delete=models.CASCADE,
                                related_name="transfers")
    transfer_date = models.DateField(null=True, blank=True)

    from_company = models.ForeignKey("core.CompanyModel", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="transfers_from")
    to_company = models.ForeignKey("core.CompanyModel", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="transfers_to")

    transfer_status = models.CharField(max_length=50)
    transfer_initiation_date = models.DateTimeField(null=True, blank=True)
    transfer_acceptance_date = models.DateTimeField(null=True, blank=True)

    cbic_status = models.CharField(max_length=100, null=True, blank=True)
    cbic_response_date = models.DateTimeField(null=True, blank=True)

    user_id_transfer_initiation = models.CharField(max_length=100, null=True, blank=True)
    user_id_acceptance = models.CharField(max_length=100, null=True, blank=True)

    # Expand phase: proper FK columns replacing the CharField ID copies above.
    # Backfilled by data migration 0XXX_backfill_transfer_user_fks.
    transfer_initiation_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='transfer_initiations',
    )
    acceptance_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='transfer_acceptances',
    )

    def __str__(self) -> str:
        fd = self.transfer_date or (self.transfer_initiation_date.date() if self.transfer_initiation_date else None)
        fd_str = str(fd) if fd else "N/A"
        return (
            f"{self.transfer_status} from "
            f"{self.from_company.name if self.from_company else 'N/A'} to "
            f"{self.to_company.name if self.to_company else 'N/A'} on {fd_str}"
        )

    def from_company_name(self):
        return self.from_company.name if self.from_company else "-"

    from_company_name.short_description = "From Company"

    def to_company_name(self):
        return self.to_company.name if self.to_company else "-"

    to_company_name.short_description = "To Company"
