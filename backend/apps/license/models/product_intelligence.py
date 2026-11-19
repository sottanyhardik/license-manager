"""Product Intelligence registry (owner spec 2026-11-19: our own database-trained engine).

* ``ProductAlias`` — approved alias registry for product matching only. It maps a
  normalised description (optionally SION-scoped) to a master item. It is NOT the
  planning-rule ``SionInputAliasConfig`` (that one feeds Auto Plan input codes and is
  never written by matching). Aliases are created from approved decisions or by an
  authorised reviewer; they produce *suggestions*, never automatic merges.
* ``ProductIntelDataset`` — one versioned, reproducible extraction (artifact on disk,
  sha256 recorded). Financial fields are never part of a dataset.
* ``ProductIntelModel`` — one trained pair classifier (artifact on disk + metrics).
  Exactly one may be ACTIVE; promotion and rollback are explicit, audited actions.
* ``ProductIntelAuditEvent`` — every administrative action (dataset, train,
  evaluate, promote, rollback, alias create/deactivate).
"""
from django.conf import settings
from django.db import models


class ProductAlias(models.Model):
    DECISION, REVIEWER = "DECISION", "REVIEWER"
    SOURCES = [(DECISION, "Approved matching decision"), (REVIEWER, "Added by reviewer")]

    alias_text = models.CharField(max_length=500, help_text="Alias as entered / first seen (display)")
    normalized_alias = models.CharField(max_length=500, db_index=True)
    item = models.ForeignKey("core.ItemNameModel", on_delete=models.PROTECT, related_name="+")
    sion = models.ForeignKey("core.SionNormClassModel", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                             help_text="Empty = valid for every SION where the master item is legitimate")
    source = models.CharField(max_length=10, choices=SOURCES, default=REVIEWER)
    decision = models.ForeignKey("license.ProductMatchDecision", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_on = models.DateTimeField(auto_now_add=True)
    deactivated_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("normalized_alias", "pk")
        constraints = [
            models.UniqueConstraint(fields=["normalized_alias", "item", "sion"], name="uniq_product_alias"),
            # Postgres treats NULL SIONs as distinct: a second constraint keeps global aliases unique too.
            models.UniqueConstraint(fields=["normalized_alias", "item"], condition=models.Q(sion__isnull=True), name="uniq_product_alias_any_sion"),
        ]

    def __str__(self):
        return f"{self.normalized_alias} → {self.item_id} ({self.sion_id or 'any'})"


class ProductIntelDataset(models.Model):
    version = models.CharField(max_length=40, unique=True)
    artifact_path = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    observation_count = models.PositiveIntegerField(default=0)
    unique_description_count = models.PositiveIntegerField(default=0)
    label_count = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_on", "-pk")


class ProductIntelModel(models.Model):
    CANDIDATE, ACTIVE, RETIRED, REJECTED, INSUFFICIENT = "CANDIDATE", "ACTIVE", "RETIRED", "REJECTED", "INSUFFICIENT_LABELS"
    STATUSES = [(s, s.replace("_", " ").title()) for s in (CANDIDATE, ACTIVE, RETIRED, REJECTED, INSUFFICIENT)]

    version = models.CharField(max_length=40, unique=True)
    dataset = models.ForeignKey(ProductIntelDataset, on_delete=models.PROTECT, related_name="models")
    algorithm = models.CharField(max_length=40, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUSES, default=CANDIDATE, db_index=True)
    artifact_path = models.CharField(max_length=500, blank=True, default="")
    sha256 = models.CharField(max_length=64, blank=True, default="")
    feature_names = models.JSONField(default=list, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    comparison = models.JSONField(default=dict, blank=True, help_text="Holdout metrics of the model ACTIVE at training time")
    notes = models.TextField(blank=True, default="")
    trained_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    trained_on = models.DateTimeField(auto_now_add=True)
    promoted_on = models.DateTimeField(null=True, blank=True)
    retired_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-trained_on", "-pk")
        constraints = [models.UniqueConstraint(fields=["status"], condition=models.Q(status="ACTIVE"), name="one_active_product_intel_model")]


class ProductIntelAuditEvent(models.Model):
    action = models.CharField(max_length=40, db_index=True)
    detail = models.JSONField(default=dict, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_on = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_on", "-pk")


class ProductMatchSelection(models.Model):
    """One reviewer decision for ONE product detected in a multi-product source description.

    A multi-product licence record has a single shared quantity / CIF, so approving its products records
    a *classification* only: the import items' master links (which feed Auto Plan) are not changed and no
    quantity is attributed to any product (owner spec 2026-11-19 §6 — allocation must be verified first).
    The set of APPROVED rows for a source key is the record's final approved classification.
    """
    APPROVED, REVOKED = "APPROVED", "REVOKED"
    STATUSES = [(APPROVED, "Approved"), (REVOKED, "Revoked (deselected later)")]

    source_key = models.CharField(max_length=600, db_index=True)
    import_item_ids = models.JSONField(default=list, help_text="Source licence import-item ids (provenance)")
    source_description = models.TextField(blank=True, default="")
    hsn_code = models.CharField(max_length=20, blank=True, default="")
    detected_phrase = models.CharField(max_length=500, help_text="Product phrase as detected / entered")
    normalized_phrase = models.CharField(max_length=500)
    segment_index = models.SmallIntegerField(null=True, blank=True, help_text="Detected segment; null = added manually")
    item = models.ForeignKey("core.ItemNameModel", on_delete=models.PROTECT, related_name="+")
    confidence = models.PositiveSmallIntegerField(default=0)
    sion = models.ForeignKey("core.SionNormClassModel", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    entitlement = models.CharField(max_length=120, blank=True, default="", help_text="Entitlement required for the phrase, if any")
    checks = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default=APPROVED, db_index=True)
    previous_mapping = models.JSONField(default=list, blank=True, help_text="Approved [item ids] for this source before the decision")
    new_mapping = models.JSONField(default=list, blank=True, help_text="Approved [item ids] for this source after the decision")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    decided_on = models.DateTimeField(auto_now_add=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    revoked_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("source_key", "segment_index", "pk")
        constraints = [models.UniqueConstraint(fields=["source_key", "normalized_phrase", "item"], condition=models.Q(status="APPROVED"),
                                               name="uniq_approved_product_selection")]


class MappingChange(models.Model):
    """One version of an approved product / debit-item mapping change and its downstream propagation (Part 15).

    The version number is the primary key. ``before`` archives the affected licences' complete plan lines and
    canonical CIF before re-planning (the existing re-plan engine REPLACEs generated lines); ``after`` is captured
    once every affected licence has re-planned. Status is derived from the existing ``LicenseReplanRequest``
    pipeline: PROPAGATING → PUBLISHED, or FAILED (retryable). Item-Pivot-only changes are NO_PLANNING_IMPACT.
    """
    MATCH_DECISION, MULTI_PRODUCT, CONSOLIDATION, CONSOLIDATION_REVERT, BOE_TARGET, ALLOTMENT_TARGET = (
        "MATCH_DECISION", "MULTI_PRODUCT", "CONSOLIDATION", "CONSOLIDATION_REVERT", "BOE_TARGET", "ALLOTMENT_TARGET")
    KINDS = [(k, k.replace("_", " ").title()) for k in (MATCH_DECISION, MULTI_PRODUCT, CONSOLIDATION, CONSOLIDATION_REVERT, BOE_TARGET, ALLOTMENT_TARGET)]
    PROPAGATING, PUBLISHED, FAILED, NO_PLANNING_IMPACT = "PROPAGATING", "PUBLISHED", "FAILED", "NO_PLANNING_IMPACT"
    STATUSES = [(s, s.replace("_", " ").title()) for s in (PROPAGATING, PUBLISHED, FAILED, NO_PLANNING_IMPACT)]

    kind = models.CharField(max_length=24, choices=KINDS, db_index=True)
    source_model = models.CharField(max_length=80, blank=True, default="")
    source_refs = models.JSONField(default=list, blank=True, help_text="Ids of the decisions / selections / BOEs / allotments")
    detail = models.JSONField(default=dict, blank=True, help_text="Previous → new mapping summary")
    import_item_ids = models.JSONField(default=list, blank=True)
    license_ids = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default=PROPAGATING, db_index=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    retries = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-pk",)
