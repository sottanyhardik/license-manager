"""Ledger package job / item / artifact / audit models.

Split verbatim from core.py; behaviour unchanged.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .header import LicenseDetailsModel


class LicenseLedgerPackageJob(models.Model):
    """Durable, owner-scoped request for asynchronously built ledger PDFs.

    Binary data deliberately lives in configured Django storage.  The database
    only contains opaque storage keys and audit/status metadata, so a worker
    may safely run on a different host from the web process.
    """
    STATUS_QUEUED = "queued"
    STATUS_GENERATING = "generating"
    STATUS_VALIDATING_SOURCES = "validating_sources"
    STATUS_MERGING = "merging"
    # This is a server-side state only.  A browser may subsequently record
    # ``downloading``/``downloaded`` in its durable local-save journal, but a
    # worker must never claim that a client has saved a file.
    STATUS_SERVER_READY = "server_ready"
    STATUS_FAILED = "failed"
    STATUS_PARTIAL_FAILED = "partial_failed"  # legacy failed-job reporting
    STATUS_DISPATCH_FAILED = "dispatch_failed"
    STATUS_CHOICES = [(v, v.replace("_", " ").title()) for v in (
        STATUS_QUEUED, STATUS_GENERATING, STATUS_VALIDATING_SOURCES, STATUS_MERGING,
        STATUS_SERVER_READY, STATUS_FAILED, STATUS_PARTIAL_FAILED, STATUS_DISPATCH_FAILED,
    )]

    key = models.CharField(max_length=64, unique=True, db_index=True)
    # Public UUID is intentionally separate from the compact human key.  The
    # latter remains compatible with the original download-package API.
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name="license_ledger_package_jobs")
    idempotency_key = models.CharField(max_length=255, blank=True, default="", db_index=True)
    requested_ids = models.JSONField(default=list)
    manifest_key = models.CharField(max_length=512, blank=True, default="")
    archive_key = models.CharField(max_length=512, blank=True, default="")
    archive_filename = models.CharField(max_length=255, blank=True, default="")
    archive_size = models.BigIntegerField(default=0)
    archive_checksum = models.CharField(max_length=64, blank=True, default="")
    root_task_id = models.CharField(max_length=255, blank=True, default="")
    requested_count = models.PositiveIntegerField(default=0)
    queued_count = models.PositiveIntegerField(default=0)
    processing_count = models.PositiveIntegerField(default=0)
    server_ready_count = models.PositiveIntegerField(default=0)
    blocked_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, default="")

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["requested_by", "idempotency_key", "created_at"], name="license_led_request_4ab8f8_idx")]


class LicenseLedgerPackageItem(models.Model):
    """One idempotent work item in a :class:`LicenseLedgerPackageJob`."""
    STATUS_QUEUED = LicenseLedgerPackageJob.STATUS_QUEUED
    STATUS_GENERATING = LicenseLedgerPackageJob.STATUS_GENERATING
    STATUS_VALIDATING_SOURCES = LicenseLedgerPackageJob.STATUS_VALIDATING_SOURCES
    STATUS_MERGING = LicenseLedgerPackageJob.STATUS_MERGING
    STATUS_SERVER_READY = LicenseLedgerPackageJob.STATUS_SERVER_READY
    STATUS_FAILED = LicenseLedgerPackageJob.STATUS_FAILED
    # Data blockers are operationally distinct from renderer/task failures and
    # may be re-queued automatically after an audited correction.
    STATUS_BLOCKED_MISSING_PURCHASE_DOCUMENT = "blocked_missing_purchase_document"
    STATUS_BLOCKED_UNKNOWN_SALES_CLASSIFICATION = "blocked_unknown_sales_classification"
    STATUS_BLOCKED_MULTIPLE_REASONS = "blocked_multiple_reasons"
    STATUS_BLOCKED_MISSING_FINAL_PARTY_SALES_INVOICE = "blocked_missing_final_party_sales_invoice"
    STATUS_CHOICES = [(v, v.replace('_', ' ').title()) for v in (
        STATUS_QUEUED, STATUS_GENERATING, STATUS_VALIDATING_SOURCES,
        STATUS_MERGING, STATUS_SERVER_READY, STATUS_FAILED,
        STATUS_BLOCKED_MISSING_PURCHASE_DOCUMENT, STATUS_BLOCKED_UNKNOWN_SALES_CLASSIFICATION,
        STATUS_BLOCKED_MULTIPLE_REASONS, STATUS_BLOCKED_MISSING_FINAL_PARTY_SALES_INVOICE,
    )]

    job = models.ForeignKey(LicenseLedgerPackageJob, on_delete=models.CASCADE, related_name="items")
    license = models.ForeignKey(LicenseDetailsModel, on_delete=models.PROTECT,
                                related_name="ledger_package_items")
    licence_number = models.CharField(max_length=100)  # immutable display/audit snapshot
    request_order = models.PositiveIntegerField(default=0)
    readiness_status = models.CharField(max_length=48, blank=True, default="queued")
    processing_status = models.CharField(max_length=48, blank=True, default="queued")
    purchase_expected_count = models.PositiveIntegerField(default=0)
    purchase_included_count = models.PositiveIntegerField(default=0)
    sales_expected_count = models.PositiveIntegerField(default=0)
    sales_included_count = models.PositiveIntegerField(default=0)
    interlinked_sales_excluded_count = models.PositiveIntegerField(default=0)
    unknown_sales_count = models.PositiveIntegerField(default=0)
    blocking_reason_codes = models.JSONField(default=list)
    status = models.CharField(max_length=48, choices=STATUS_CHOICES, default=STATUS_QUEUED, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    section_manifest = models.JSONField(default=dict)
    output_key = models.CharField(max_length=512, blank=True, default="")
    output_checksum = models.CharField(max_length=128, blank=True, default="")
    output_size = models.BigIntegerField(default=0)
    output_page_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["job", "license"], name="uniq_ledger_package_item_license")]
        indexes = [models.Index(fields=["job", "status"], name="license_led_job_id_9940d0_idx")]


# Public domain names for the durable download workflow.  They deliberately
# share the established tables so in-flight legacy jobs survive this upgrade.
LicensePackageRequest = LicenseLedgerPackageJob
LicensePackageRequestItem = LicenseLedgerPackageItem


class LicensePackageArtifact(models.Model):
    """Checksum-verified component or final output belonging to one request."""
    KIND_CHOICES = [(value, value) for value in (
        "01-custom-ledger", "02-financial-ledger", "03-main-purchase-invoices",
        "04-final-party-sales-invoices", "FINAL_MERGED_PDF", "FINAL_ZIP",
    )]
    request = models.ForeignKey(LicenseLedgerPackageJob, on_delete=models.CASCADE, related_name="artifacts")
    item = models.ForeignKey(LicenseLedgerPackageItem, null=True, blank=True, on_delete=models.CASCADE, related_name="artifacts")
    kind = models.CharField(max_length=48, choices=KIND_CHOICES)
    document_ids = models.JSONField(default=list)
    storage_key = models.CharField(max_length=512)
    checksum = models.CharField(max_length=64)
    size = models.BigIntegerField(default=0)
    page_count = models.PositiveIntegerField(default=0)
    page_range_start = models.PositiveIntegerField(null=True, blank=True)
    page_range_end = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["request", "item", "kind"])]


class LicensePackageAuditEvent(models.Model):
    request = models.ForeignKey(LicenseLedgerPackageJob, on_delete=models.CASCADE, related_name="audit_events")
    item = models.ForeignKey(LicenseLedgerPackageItem, null=True, blank=True, on_delete=models.CASCADE, related_name="audit_events")
    event = models.CharField(max_length=64)
    detail = models.JSONField(default=dict)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["request", "created_at"])]


class LicenseLedgerRecoveryAudit(models.Model):
    """Append-only evidence for a supplier-document recovery decision.

    The original object is never moved or altered: this row records why a
    configured-storage copy was attached to one exact purchase trade.
    """
    trade = models.ForeignKey("trade.LicenseTrade", on_delete=models.PROTECT, related_name="ledger_recovery_audits")
    source_storage_key = models.CharField(max_length=512)
    source_checksum = models.CharField(max_length=64)
    linked_document_key = models.CharField(max_length=512, blank=True, default="")
    evidence = models.JSONField(default=dict)
    matching_rule = models.CharField(max_length=128)
    recovery_method = models.CharField(max_length=32, default="ORPHAN_LINK")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["trade", "created_at"])]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Recovery audit records are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Recovery audit records are immutable.")
