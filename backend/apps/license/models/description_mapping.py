"""Saved licence import description → Item Name(s) mappings (owner spec 2026-11-19, "automatic licence item name mapping").

One mapping per *strictly* normalised original description (``description_key``; see
``services/product_intelligence/description_mapping.description_key``). It holds one or several existing Item Names
(``ItemNameModel``) and is applied — REPLACE semantics on ``LicenseImportItemsModel.items`` — to every existing import
item with that exact key, and automatically to future ones. ``ImportItemDescriptionMapping`` records, per import item,
which mapping version is applied (or why it was not: an HSN / SION conflict). Classification only: no quantity / CIF.
Never seeded automatically: every mapping is saved by a user.
"""
from django.conf import settings
from django.db import models


class ImportDescriptionMapping(models.Model):
    key_hash = models.CharField(max_length=64, unique=True, help_text="sha256 of description_key")
    description_key = models.TextField(help_text="Strictly normalised original description (identity)")
    description = models.TextField(help_text="An original wording with this key (display; sources are never changed)")
    items = models.ManyToManyField("core.ItemNameModel", related_name="+")
    is_active = models.BooleanField(default=True, db_index=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_on = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_on", "-pk")

    def __str__(self):
        return f"{self.description_key[:60]} v{self.version}"


class ImportDescriptionMappingVersion(models.Model):
    """Append-only history: every create / replace of a mapping (previous → new Item Name ids)."""
    CREATE, REPLACE = "CREATE", "REPLACE"
    ACTIONS = [(CREATE, "Created"), (REPLACE, "Replaced")]

    mapping = models.ForeignKey(ImportDescriptionMapping, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    action = models.CharField(max_length=8, choices=ACTIONS)
    item_ids = models.JSONField(default=list)
    previous_item_ids = models.JSONField(default=list)
    mapping_change = models.ForeignKey("license.MappingChange", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-pk",)


class ImportItemDescriptionMapping(models.Model):
    """Which mapping version is applied to one licence import item (APPLIED on save, AUTO for later records), or
    CONFLICT (HSN / SION incompatible — links left unchanged, flagged)."""
    APPLIED, AUTO, CONFLICT = "APPLIED", "AUTO", "CONFLICT"
    STATUSES = [(APPLIED, "Applied"), (AUTO, "Automatically mapped"), (CONFLICT, "Conflict")]

    import_item = models.OneToOneField("license.LicenseImportItemsModel", on_delete=models.CASCADE, related_name="description_mapping")
    mapping = models.ForeignKey(ImportDescriptionMapping, on_delete=models.PROTECT, related_name="applications")
    applied_version = models.PositiveIntegerField()
    status = models.CharField(max_length=8, choices=STATUSES, db_index=True)
    previous_item_ids = models.JSONField(default=list, help_text="Links before this mapping was first applied (audit)")
    detail = models.TextField(blank=True, default="")
    applied_on = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["mapping", "status"])]
