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


class ImportItemNameOverride(models.Model):
    """Row-level Item Name correction on one licence import item (Licence Detail -> Import Items; owner decision
    2026-11-20). The M2M ``LicenseImportItemsModel.items`` stays the source of truth; this row is a protection flag
    (saved description mappings never re-apply to an overridden row) plus an audit snapshot. ``item_ids == []`` is a
    deliberate "Not Mapped". Classification only: never quantity / CIF / debits / balances."""
    import_item = models.OneToOneField("license.LicenseImportItemsModel", on_delete=models.CASCADE, related_name="item_name_override")
    item_ids = models.JSONField(default=list, help_text="Links set by the override ([] = deliberately Not Mapped)")
    previous_item_ids = models.JSONField(default=list, help_text="Links before the first override (audit)")
    reason = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)


class ImportItemMappingApproval(models.Model):
    """Global, approved Description + HSN -> Item Name decision (owner amendment 2026-11-20). Identity is
    ``(description_key, hsn_code)``: the strict description key plus the trimmed HSN code ("" = no HSN, its own value).
    ``USER_APPROVED`` links every matching import item (all licences) to ``item``; ``USER_APPROVED_CLEAR`` deliberately
    leaves them without an Item Name. Revoke = ``is_active=False`` (history kept). Precedence: row override > this >
    ``ImportDescriptionMapping`` > automatic writers. Classification only: never quantity / CIF / debits / balances."""
    USER_APPROVED, USER_APPROVED_CLEAR = "USER_APPROVED", "USER_APPROVED_CLEAR"
    STATUSES = [(USER_APPROVED, "Approved"), (USER_APPROVED_CLEAR, "Approved - no Item Name")]
    LICENCE_DETAIL, MAPPING_WORKSPACE, CONSOLIDATION = "LICENCE_DETAIL", "MAPPING_WORKSPACE", "CONSOLIDATION"
    SOURCES = [(LICENCE_DETAIL, "Licence Detail"), (MAPPING_WORKSPACE, "Mapping workspace"), (CONSOLIDATION, "Consolidation")]

    description_key = models.TextField(help_text="Strictly normalised original description (identity, with hsn_code)")
    key_hash = models.CharField(max_length=64, help_text="sha256 of description_key")
    hsn_code = models.CharField(max_length=20, blank=True, default="", help_text="Trimmed HSN code; '' = no HSN")
    description = models.TextField(help_text="An original wording with this key (display; sources are never changed)")
    item = models.ForeignKey("core.ItemNameModel", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    status = models.CharField(max_length=20, choices=STATUSES)
    source = models.CharField(max_length=20, choices=SOURCES, default=LICENCE_DETAIL)
    is_active = models.BooleanField(default=True, db_index=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_on", "-pk")
        constraints = [models.UniqueConstraint(fields=["key_hash", "hsn_code"], name="uniq_import_item_approval_key_hsn")]

    def __str__(self):
        return f"{self.description_key[:50]} / {self.hsn_code or '-'} v{self.version}"


class ImportItemMappingApprovalVersion(models.Model):
    """Append-only history of one approval: every create / revise / clear / revoke / reactivate / consolidation re-point."""
    CREATE, REVISE, CLEAR, REVOKE, REACTIVATE, CONSOLIDATION = "CREATE", "REVISE", "CLEAR", "REVOKE", "REACTIVATE", "CONSOLIDATION"
    ACTIONS = [(a, a.title()) for a in (CREATE, REVISE, CLEAR, REVOKE, REACTIVATE, CONSOLIDATION)]

    approval = models.ForeignKey(ImportItemMappingApproval, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    action = models.CharField(max_length=16, choices=ACTIONS)
    item_id = models.PositiveIntegerField(null=True, blank=True, help_text="Item Name id of this version (null = cleared)")
    previous_item_id = models.PositiveIntegerField(null=True, blank=True)
    previous_status = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(max_length=20, blank=True, default="")
    records = models.PositiveIntegerField(default=0)
    licences = models.PositiveIntegerField(default=0)
    mapping_change = models.ForeignKey("license.MappingChange", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_on = models.DateTimeField(auto_now_add=True)
    detail = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-pk",)


class SourceNameMapping(models.Model):
    """Saved BOE Product Name / Allotment Item Name → Planning Target Item mapping (owner spec 2026-11-19, "BOE &
    allotment item to planning target mapping"). One mapping per (source kind, strictly normalised name); BOE and
    allotment identities never mix with each other or with licence import descriptions. The target is the existing
    canonical planning target master (``core.ItemNameModel`` — the ``planning_target_item`` FK of both headers, a single
    target per record). Applied to every existing record with that exact name and automatically to future ones."""
    BOE, ALLOTMENT = "BOE", "ALLOTMENT"
    KINDS = [(BOE, "BOE Product Name"), (ALLOTMENT, "Allotment Item Name")]

    kind = models.CharField(max_length=9, choices=KINDS)
    key_hash = models.CharField(max_length=64, help_text="sha256 of name_key")
    name_key = models.TextField(help_text="Strictly normalised source name (identity within its kind)")
    name = models.TextField(help_text="An original wording with this key (display; sources are never changed)")
    target = models.ForeignKey("core.ItemNameModel", on_delete=models.PROTECT, related_name="+")
    is_active = models.BooleanField(default=True, db_index=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_on = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_on", "-pk")
        constraints = [models.UniqueConstraint(fields=["kind", "key_hash"], name="uniq_source_name_mapping_kind_key")]

    def __str__(self):
        return f"{self.kind} {self.name_key[:60]} v{self.version}"


class SourceNameMappingVersion(models.Model):
    """Append-only history: every create / replace of a source name mapping (previous → new target)."""
    CREATE, REPLACE = "CREATE", "REPLACE"
    ACTIONS = [(CREATE, "Created"), (REPLACE, "Replaced")]

    mapping = models.ForeignKey(SourceNameMapping, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    action = models.CharField(max_length=8, choices=ACTIONS)
    target_id_value = models.PositiveIntegerField(help_text="Planning Target Item id of this version")
    previous_target_id = models.PositiveIntegerField(null=True, blank=True)
    mapping_change = models.ForeignKey("license.MappingChange", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-pk",)


class SourceNameMappingRecord(models.Model):
    """Which mapping version is applied to one BOE / allotment header: APPLIED (saved by a user) or AUTO (future record),
    optionally ``verified=False`` (no licence debit yet, or no planning rule configured for its licence — the target is
    kept but planning keeps treating the record as unmapped), or CONFLICT (the target is not legitimate under the
    record's SION rules / the record keeps another valid target — left unchanged). ``previous_*`` = the header's
    planning-target fields before a name mapping first touched it (audit + restore on conflict)."""
    APPLIED, AUTO, CONFLICT = "APPLIED", "AUTO", "CONFLICT"
    STATUSES = [(APPLIED, "Applied"), (AUTO, "Automatically mapped"), (CONFLICT, "Conflict")]

    kind = models.CharField(max_length=9, choices=SourceNameMapping.KINDS)
    record_id = models.PositiveIntegerField(help_text="BillOfEntryModel / AllotmentModel id")
    mapping = models.ForeignKey(SourceNameMapping, on_delete=models.PROTECT, related_name="applications")
    applied_version = models.PositiveIntegerField()
    status = models.CharField(max_length=8, choices=STATUSES, db_index=True)
    verified = models.BooleanField(default=True)
    previous_target_id = models.PositiveIntegerField(null=True, blank=True)
    previous_status = models.CharField(max_length=32, blank=True, default="")
    previous_source = models.CharField(max_length=32, blank=True, default="")
    detail = models.TextField(blank=True, default="")
    applied_on = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["kind", "record_id"], name="uniq_source_name_mapping_record")]
        indexes = [models.Index(fields=["mapping", "status"])]
