"""Audited product-matching decisions (Item Pivot product consolidation).

One row per user decision on a suggested match between unlinked / ambiguous
licence import items and a master item (``ItemNameModel``). An APPROVED
decision links those import items to the chosen master item (owner decision
2026-11-18) and records the links before and after; source descriptions, HSN
codes and transactions are never modified. REJECTED / DIFFERENT decisions are
reused so the same suggestion is not offered again.
"""
from django.conf import settings
from django.db import models


class ProductMatchDecision(models.Model):
    APPROVED, REJECTED, DIFFERENT = "APPROVED", "REJECTED", "DIFFERENT"
    DECISIONS = [(APPROVED, "Approved"), (REJECTED, "Rejected"), (DIFFERENT, "Different products")]

    source_key = models.CharField(max_length=600, db_index=True, help_text="normalised description | HSN | SION")
    source_description = models.TextField(blank=True, default="")
    normalized_description = models.CharField(max_length=500, blank=True, default="")
    hsn_code = models.CharField(max_length=20, blank=True, default="")
    sion = models.ForeignKey("core.SionNormClassModel", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    import_item_ids = models.JSONField(default=list)
    suggested_item = models.ForeignKey("core.ItemNameModel", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    chosen_item = models.ForeignKey("core.ItemNameModel", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    confidence = models.PositiveSmallIntegerField(default=0)
    explanation = models.TextField(blank=True, default="")
    checks = models.JSONField(default=dict, blank=True)
    matcher = models.CharField(max_length=40, default="deterministic-v1")
    decision = models.CharField(max_length=12, choices=DECISIONS, db_index=True)
    previous_links = models.JSONField(default=dict, blank=True, help_text="{import_item_id: [item_name_id, …]} before")
    new_links = models.JSONField(default=dict, blank=True, help_text="{import_item_id: [item_name_id, …]} after")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    decided_on = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-decided_on", "-pk")
        indexes = [models.Index(fields=["source_key", "decision"])]

    def __str__(self):
        return f"{self.decision} {self.source_key} -> {self.chosen_item_id or self.suggested_item_id}"


class ProductTextEmbedding(models.Model):
    """Persisted embedding of one prepared text (computed once per model version + text hash)."""
    SOURCE, MASTER = "SOURCE", "MASTER"
    model_version = models.CharField(max_length=120)
    kind = models.CharField(max_length=8, choices=[(SOURCE, "Source description"), (MASTER, "Master item")])
    text_hash = models.CharField(max_length=64)
    ref = models.CharField(max_length=600, blank=True, default="", help_text="source key or master item id")
    vector = models.BinaryField()
    dim = models.PositiveSmallIntegerField(default=384)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["model_version", "kind", "text_hash"], name="uniq_product_text_embedding")]


class ProductMatchingJob(models.Model):
    """One background classification run (Celery queue ``matching``)."""
    QUEUED, RUNNING, PAUSED, DONE, FAILED = "QUEUED", "RUNNING", "PAUSED", "DONE", "FAILED"
    STATUSES = [(s, s.title()) for s in (QUEUED, RUNNING, PAUSED, DONE, FAILED)]
    status = models.CharField(max_length=10, choices=STATUSES, default=QUEUED, db_index=True)
    filters = models.JSONField(default=dict, blank=True)
    model_version = models.CharField(max_length=120, blank=True, default="")
    batch_size = models.PositiveSmallIntegerField(default=4)
    total = models.PositiveIntegerField(default=0)
    processed = models.PositiveIntegerField(default=0)
    pause_requested = models.BooleanField(default=False)
    metrics = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_on = models.DateTimeField(auto_now_add=True)
    started_on = models.DateTimeField(null=True, blank=True)
    finished_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_on", "-pk")


class ProductMatchSuggestion(models.Model):
    """Latest machine suggestion for a source group — kept separate from human ProductMatchDecision rows."""
    source_key = models.CharField(max_length=600)
    model_version = models.CharField(max_length=120)
    job = models.ForeignKey(ProductMatchingJob, on_delete=models.SET_NULL, null=True, blank=True, related_name="suggestions")
    semantic_item = models.ForeignKey("core.ItemNameModel", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    similarity = models.FloatField(null=True, blank=True)
    semantic_candidates = models.JSONField(default=list, blank=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source_key", "model_version"], name="uniq_product_match_suggestion")]
