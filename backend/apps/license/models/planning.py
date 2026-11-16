"""Utilization planning models (replan requests, item plans, SION planning).

Split verbatim from core.py; behaviour unchanged.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.constants import DEC_0, DEC_000, UNIT_CHOICES
from apps.core.models import AuditModel


# -----------------------------
# Utilization Planning
# -----------------------------
class LicenseReplanRequest(models.Model):
    """Durable, coalesced request to rebuild one licence's plan asynchronously.

    This is intentionally a request ledger, not a second planning authority.
    The worker delegates to the same SION rule engine as the explicit
    ``auto-plan`` API after the triggering transaction has committed.
    """
    STATUS_PENDING = "pending"
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_RETRY_PENDING = "retry_pending"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_SUPERSEDED = "superseded"
    # Compatibility alias for the initial implementation.
    STATUS_RETRY = STATUS_RETRY_PENDING
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_RETRY_PENDING, "Retry pending"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SUPERSEDED, "Superseded"),
    )
    SCOPE_LICENSE = "LICENSE"
    SCOPE_SION = "SION"
    SCOPE_CHOICES = ((SCOPE_LICENSE, "Licence"), (SCOPE_SION, "SION"))

    license = models.ForeignKey(
        "license.LicenseDetailsModel", on_delete=models.CASCADE,
        related_name="replan_requests", db_index=True,
    )
    reason = models.CharField(max_length=100)
    # The worker command scope is explicit.  ``license`` remains the durable
    # per-licence work item used by the sequential SION batch.
    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES, default=SCOPE_LICENSE)
    sion_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    source_model = models.CharField(max_length=128, blank=True, default="")
    source_pk = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    source_revision = models.PositiveBigIntegerField(default=0)
    planned_revision = models.PositiveBigIntegerField(null=True, blank=True)
    started_source_revision = models.PositiveBigIntegerField(null=True, blank=True)
    requested_at = models.DateTimeField(default=timezone.now, db_index=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    trigger_count = models.PositiveIntegerField(default=1)
    retry_count = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True)
    task_id = models.CharField(max_length=255, blank=True, default="")
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    result = models.JSONField(default=dict, blank=True)
    last_error = models.TextField(blank=True, default="")
    last_error_code = models.CharField(max_length=100, blank=True, default="")
    last_error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-requested_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=["license"],
                condition=models.Q(status__in=["pending", "queued", "running", "retry_pending"]),
                name="one_active_replan_request_per_license",
            ),
        ]

    def __str__(self):
        return f"Replan {self.license_id} ({self.status})"


class LicenseItemPlan(AuditModel):
    """
    User-authored utilization plan line for an import item.

    An import item's total quantity can be SPLIT into several plan lines, each
    optionally tagged with an item name (e.g. milk → WPC / SWP / DWP) and priced
    with a unit price. Each line records planned quantity, unit price and CIF-FC.

    At allotment time (`allocate_items`) the SUM of an item's plan lines acts as
    a CAP: cumulative allotment for the item may not exceed the total planned
    quantity / CIF-FC. Items without any plan line keep the default
    availability-based behavior.

    This is distinct from the norm-derived "planned CIF" produced by the
    E1/E5 waterfall (`services/e1_plan.py` / `e5_plan.py`), which is read-only.
    """
    import_item = models.ForeignKey(
        "license.LicenseImportItemsModel",
        on_delete=models.CASCADE,
        related_name="utilization_plans",
        db_index=True,
    )
    # Optional split label — one of the item's attached item names.
    item_name = models.ForeignKey(
        "core.ItemNameModel",
        on_delete=models.SET_NULL,
        related_name="plan_lines",
        null=True,
        blank=True,
    )
    # Denormalized for fast per-license querying and shared-pool validation.
    license = models.ForeignKey(
        "license.LicenseDetailsModel",
        on_delete=models.CASCADE,
        related_name="item_plans",
        null=True,
        blank=True,
        db_index=True,
    )
    planned_quantity = models.DecimalField(
        max_digits=15, decimal_places=3, default=DEC_000,
        validators=[MinValueValidator(DEC_000)],
    )
    unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    planned_cif_fc = models.DecimalField(
        max_digits=15, decimal_places=2, default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    planned_cif_inr = models.DecimalField(
        max_digits=15, decimal_places=2, default=DEC_0, null=True, blank=True,
    )
    # Legacy denormalized snapshots retained for migration/reporting
    # compatibility.  They are NOT allocation authority: a plan line's live
    # residual is immutable planned capacity minus `AllotmentItems` ledger
    # debits linked by `plan_line`.  Keeping those values out of validation
    # avoids drift on amend/delete/reopen and prevents a two-decimal plan
    # price from overwriting the canonical allocation CIF.
    remaining_quantity = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True,
        validators=[MinValueValidator(DEC_000)],
    )
    remaining_cif_fc = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(DEC_0)],
    )
    note = models.CharField(max_length=500, blank=True, null=True)

    # Snapshot of the group's ALL-TIME live-allotted qty/CIF, taken the
    # moment this line was created (see
    # `plan_enforcement.save_plan_lines_for_license`). `plan_status_for`
    # subtracts this from the CURRENT all-time live-allotted total to get
    # "used since this plan was saved" — deliberately NOT derived from
    # AllotmentItems.created_on, because `allocate_items` "amends" an
    # existing AllotmentItems row in place (qty += ...) when an item is
    # re-allotted into the same allotment, which never advances that row's
    # created_on. A timestamp filter would silently miss any such amendment
    # made after a re-plan; this snapshot doesn't care how the live total
    # changed, only that it did.
    baseline_used_quantity = models.DecimalField(
        max_digits=15, decimal_places=3, default=DEC_000,
    )
    baseline_used_cif_fc = models.DecimalField(
        max_digits=15, decimal_places=2, default=DEC_0,
    )
    planning_rule = models.ForeignKey(
        "license.SionPlanningRule", on_delete=models.PROTECT,
        related_name="generated_plan_lines", null=True, blank=True,
    )
    planning_rule_version = models.PositiveIntegerField(null=True, blank=True)
    planning_rule_priority = models.PositiveIntegerField(null=True, blank=True)
    allocation_provenance = models.JSONField(default=dict, blank=True)
    # Lifecycle state is explicit.  An allocation route must never infer an
    # active plan from its target item, a positive quantity, or a stale cache.
    # Existing plans predate lifecycle tracking and are backfilled as active
    # by the additive migration; later cancellation/supersession is recorded
    # without deleting audit history.
    is_active = models.BooleanField(default=True, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    is_cancelled = models.BooleanField(default=False, db_index=True)

    def clean(self):
        super().clean()
        if self.is_active and (self.is_deleted or self.is_cancelled):
            raise ValidationError({
                "is_active": "A deleted or cancelled plan line cannot be active.",
            })

    class Meta:
        indexes = [models.Index(fields=["license"]), models.Index(fields=["import_item"])]
        constraints = [
            models.CheckConstraint(
                condition=~(Q(is_active=True) & (Q(is_deleted=True) | Q(is_cancelled=True))),
                name="license_item_plan_active_not_deleted_or_cancelled",
            ),
        ]

    def save(self, *args, **kwargs):
        # Keep the denormalized license in sync with the item's license.
        if self.import_item_id and not self.license_id:
            self.license_id = self.import_item.license_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Plan item={self.import_item_id}: qty={self.planned_quantity} cif_fc={self.planned_cif_fc}"


class SionPlanningRule(AuditModel):
    """Versioned, data-driven rule used to select SION planning lines.

    ``expression`` is interpreted only by the bounded evaluator in
    ``services.sion_rule_engine``; it is never evaluated as Python/SQL.
    Historical versions remain rows for auditability, while only active rules
    participate in planning.
    """
    sion = models.ForeignKey(
        "core.SionNormClassModel", on_delete=models.PROTECT,
        related_name="planning_rules", db_index=True,
    )
    stable_key = models.CharField(max_length=120, null=True, blank=True, db_index=True)
    execution_output = models.CharField(
        max_length=120, blank=True, default="",
        help_text="Legacy execution bucket supplied by the SION planning profile/UI.",
    )
    import_item = models.ForeignKey(
        "core.ItemNameModel", on_delete=models.PROTECT, null=True, blank=True,
        related_name="sion_planning_rules",
        help_text="Import item this rule plans (STANDARD strategy)",
    )
    name = models.CharField(max_length=255)
    version = models.PositiveIntegerField(default=1)
    expression = models.JSONField(default=dict)
    max_unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(DEC_0)],
    )
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES)
    priority = models.IntegerField(default=100, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    percentage_constraint = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(DEC_0), MaxValueValidator(Decimal("100"))],
        help_text="Percentage cap for this input under the parent SION norm (e.g., 50.00 for E126 PKO)",
    )
    rule_type = models.CharField(
        max_length=50,
        choices=[
            ('PERCENTAGE_CAP', 'Master percentage cap'),
            ('SPLIT_BY_PERCENTAGE', 'Split by percentage'),
            ('QUANTITY_CAP', 'Quantity cap'),
        ],
        default='PERCENTAGE_CAP',
        help_text='Type of rule: master percentage cap or transaction split strategy'
    )
    rule_group_id = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        db_index=True,
        help_text='Identifier for grouping related rules (e.g., "E126_50_50_split")'
    )
    strategy = models.CharField(
        max_length=30,
        choices=[
            ('STANDARD', 'Standard'),
            ('SPLIT_BY_UNIT_VALUE', 'Split by Unit Value'),
            ('SPLIT_BY_PERCENT', 'Split by %'),
        ],
        null=True,
        blank=True,
        db_index=True,
        help_text='Planning strategy for this rule (null = legacy dispatch path)',
    )
    cif_restriction_percentage = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(DEC_0), MaxValueValidator(Decimal("100"))],
        help_text="Max CIF % of each matched import item's total CIF that can be planned "
                  "(debited + allotted). Allowed values: 2, 3, 5, 10, or NULL (no restriction).",
    )

    class Meta:
        ordering = ("sion_id", "priority", "name", "-version")
        constraints = [
            models.UniqueConstraint(
                fields=("sion", "stable_key", "version"),
                condition=models.Q(stable_key__isnull=False),
                name="uniq_sion_rule_stable_key_version",
            ),
            models.UniqueConstraint(
                fields=("sion", "name", "version"),
                name="uniq_sion_planning_rule_version",
            ),
            models.CheckConstraint(
                condition=models.Q(max_unit_price__gte=DEC_0),
                name="sion_rule_nonnegative_max_price",
            ),
            models.UniqueConstraint(
                fields=("sion", "priority"), condition=models.Q(is_active=True),
                name="uniq_active_sion_rule_priority",
            ),
        ]
        indexes = [models.Index(fields=("sion", "is_active", "priority"))]

    def __str__(self):
        return f"{self.sion.norm_class}: {self.name} v{self.version}"


class SionPlanningUnitValueRow(AuditModel):
    """Unit-Value allocation row: one import item with min/max/preferred price band."""
    rule = models.ForeignKey(
        SionPlanningRule, on_delete=models.CASCADE, related_name="unit_value_rows"
    )
    import_item = models.ForeignKey(
        "core.ItemNameModel", on_delete=models.PROTECT, related_name="+"
    )
    min_unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(DEC_0)]
    )
    max_unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(DEC_0)]
    )
    preferred_unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(DEC_0)]
    )
    cif_restriction_percentage = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(DEC_0), MaxValueValidator(Decimal("100"))],
        help_text="Max CIF % of this import item's total CIF that can be planned. "
                  "Allowed values: 2, 3, 5, 10, or NULL (inherit from rule).",
    )
    priority = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("rule_id", "priority", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("rule", "import_item"), name="uniq_unit_value_row_per_item"
            ),
            models.CheckConstraint(
                condition=models.Q(max_unit_price__gte=models.F("min_unit_price")),
                name="unit_value_max_gte_min",
            ),
            # Preferred price is an optional planning/output value.  Zero is
            # the established explicit sentinel for "no preferred price" and
            # is valid even where the row's matching price band starts above
            # zero.  Band membership applies to the input price, not this
            # optional output value.
            models.CheckConstraint(
                condition=models.Q(preferred_unit_price__gte=DEC_0),
                name="unit_value_preferred_non_negative",
            ),
        ]


class SionPlanningPercentageRow(AuditModel):
    """Percentage allocation row: one import item with percentage + unit price."""
    rule = models.ForeignKey(
        SionPlanningRule, on_delete=models.CASCADE, related_name="percentage_rows"
    )
    import_item = models.ForeignKey(
        "core.ItemNameModel", on_delete=models.PROTECT, related_name="+"
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(DEC_0), MaxValueValidator(Decimal("100"))],
    )
    unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(DEC_0)]
    )
    max_quantity = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True,
        validators=[MinValueValidator(DEC_000)],
        help_text="Optional theoretical quantity ceiling applied after the percentage split.",
    )
    cif_restriction_percentage = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(DEC_0), MaxValueValidator(Decimal("100"))],
        help_text="Max CIF % of this import item's total CIF that can be planned. "
                  "Allowed values: 2, 3, 5, 10, or NULL (inherit from rule).",
    )
    priority = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("rule_id", "priority", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("rule", "import_item"), name="uniq_percentage_row_per_item"
            ),
        ]


class SionInputAliasConfig(AuditModel):
    """Maps raw product names to canonical input codes for SION rules.

    Allows different norms/output items to classify products differently while
    maintaining a central definition of canonical input names and their aliases.
    """
    canonical_input_code = models.CharField(
        max_length=100, db_index=True,
        help_text="Canonical code (e.g., 'PKO', 'OLIVE_OIL', 'CHEESE', or custom for extended norms)"
    )
    alias_normalized = models.CharField(
        max_length=255, db_index=True, unique=True,
        help_text="Normalized alias for exact matching (uppercase, normalized whitespace)"
    )
    sion = models.ForeignKey(
        'core.SionNormClassModel', on_delete=models.CASCADE,
        null=True, blank=True, related_name='input_aliases',
        help_text="If set, this alias applies only to this SION norm"
    )
    output_item = models.ForeignKey(
        'core.ItemNameModel', on_delete=models.CASCADE,
        null=True, blank=True, related_name='sion_input_aliases',
        help_text="If set, this alias applies only to this output item within the SION"
    )
    source_description = models.TextField(
        blank=True,
        help_text="Source or reason for this mapping (e.g., 'From E126 specification')"
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ('canonical_input_code', 'alias_normalized')
        indexes = [
            models.Index(fields=('sion', 'output_item', 'canonical_input_code')),
            models.Index(fields=('sion', 'alias_normalized')),
            models.Index(fields=('alias_normalized', 'is_active')),
        ]

    def __str__(self):
        scope = ""
        if self.sion and self.output_item:
            scope = f" ({self.sion.norm_class}/{self.output_item.name})"
        elif self.sion:
            scope = f" ({self.sion.norm_class})"
        return f"{self.alias_normalized} → {self.canonical_input_code}{scope}"


PLANNING_ACTION_TYPES = (
    ("MATCH", "Match"), ("PRICE", "Price"), ("GROUP", "Group"),
    ("ALLOCATE", "Allocate"), ("SPLIT", "Split"),
    ("REBALANCE", "Rebalance"), ("ROUND", "Round"),
    ("MAP_OUTPUT", "Map output"),
)


def _validate_planning_json(value, label):
    """Reject executable/ambiguous configuration at the model boundary."""
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be a JSON object.")
    forbidden = {"python", "javascript", "sql", "eval", "exec", "script"}
    allowed_formula_ops = {
        "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "MIN", "MAX",
        "WEIGHTED_AVERAGE",
    }

    def walk(node):
        if isinstance(node, dict):
            for key, child in node.items():
                if str(key).lower() in forbidden:
                    raise ValidationError(f"Unsafe configuration key: {key}.")
                walk(child)
            if "operation" in node and str(node["operation"]).upper() not in allowed_formula_ops:
                raise ValidationError("Unsupported structured formula operation.")
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)


class SionPlanningProfile(AuditModel):
    """Versioned, SION-neutral description of how planning is executed."""
    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sion = models.ForeignKey(
        "core.SionNormClassModel", on_delete=models.PROTECT,
        related_name="planning_profiles",
    )
    stable_key = models.CharField(max_length=100, unique=True)
    strategy_type = models.CharField(max_length=50, default="ACTION_PIPELINE")
    config = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ("sion_id", "-is_active", "-version")
        constraints = [
            models.UniqueConstraint(
                fields=("sion",), condition=models.Q(is_active=True),
                name="uniq_active_sion_planning_profile",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="sion_profile_version_gte_1",
            ),
        ]

    admin_list_display = ("stable_key", "sion", "strategy_type", "version", "is_active", "modified_on")
    admin_search_fields = ("stable_key", "sion__norm_class")
    list_filter = ("strategy_type", "is_active")

    def clean(self):
        super().clean()
        _validate_planning_json(self.config, "Profile config")
        has_active_actions = self.pk and self.actions.filter(is_active=True).exists()
        if self.is_active and not has_active_actions:
            raise ValidationError({"is_active": "An active profile requires an active action."})

    def __str__(self):
        return f"{self.sion.norm_class}: {self.stable_key} v{self.version}"


class SionPlanningAction(AuditModel):
    """One generic, ordered stage in a planning profile pipeline."""
    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    profile = models.ForeignKey(
        SionPlanningProfile, on_delete=models.PROTECT, related_name="actions",
    )
    stable_key = models.CharField(max_length=100)
    action_type = models.CharField(max_length=20, choices=PLANNING_ACTION_TYPES)
    priority = models.PositiveIntegerField(default=1)
    config = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("profile_id", "priority", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("profile", "stable_key"), name="uniq_profile_action_key",
            ),
            models.UniqueConstraint(
                fields=("profile", "priority"), condition=models.Q(is_active=True),
                name="uniq_active_profile_action_priority",
            ),
            models.CheckConstraint(
                condition=models.Q(priority__gte=1), name="sion_action_priority_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="sion_action_version_gte_1",
            ),
        ]

    admin_list_display = ("stable_key", "profile", "action_type", "priority", "version", "is_active")
    admin_search_fields = ("stable_key", "profile__stable_key")
    list_filter = ("action_type", "is_active")

    def clean(self):
        super().clean()
        _validate_planning_json(self.config, "Action config")

    def __str__(self):
        return f"{self.profile.stable_key}: {self.priority} {self.action_type}"


class SionPlanningOutputMapping(AuditModel):
    """Data-owned mapping from a match/rule to a canonical output item."""
    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    profile = models.ForeignKey(
        SionPlanningProfile, on_delete=models.PROTECT, related_name="output_mappings",
    )
    stable_key = models.CharField(max_length=100)
    source_rule = models.ForeignKey(
        SionPlanningRule, on_delete=models.PROTECT, related_name="output_mappings",
        null=True, blank=True,
    )
    output_item = models.ForeignKey(
        "core.ItemNameModel", on_delete=models.PROTECT,
        related_name="sion_planning_output_mappings", null=True, blank=True,
    )
    conversion_factor = models.DecimalField(
        max_digits=20, decimal_places=8, default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    rate = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES)
    priority = models.PositiveIntegerField(default=1)
    config = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("profile_id", "priority", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("profile", "stable_key"), name="uniq_profile_output_mapping_key",
            ),
            models.CheckConstraint(
                condition=models.Q(conversion_factor__gte=0), name="sion_mapping_factor_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(rate__isnull=True) | models.Q(rate__gte=0),
                name="sion_mapping_rate_nonnegative",
            ),
            models.UniqueConstraint(
                fields=("profile", "priority"), condition=models.Q(is_active=True),
                name="uniq_active_profile_mapping_priority",
            ),
            models.CheckConstraint(
                condition=models.Q(priority__gte=1), name="sion_mapping_priority_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="sion_mapping_version_gte_1",
            ),
        ]

    admin_list_display = (
        "stable_key", "profile", "output_item", "conversion_factor", "rate",
        "unit", "priority", "version", "is_active",
    )
    admin_search_fields = ("stable_key", "profile__stable_key", "output_item__name")
    list_filter = ("unit", "is_active")

    def clean(self):
        super().clean()
        _validate_planning_json(self.config, "Output mapping config")
        if self.source_rule_id and self.profile_id and self.source_rule.sion_id != self.profile.sion_id:
            raise ValidationError({"source_rule": "Rule and profile must belong to the same SION."})


class SionPlanningRun(AuditModel):
    """Immutable configuration/result audit envelope for one planner execution."""
    STATUS_CHOICES = (
        ("PENDING", "Pending"), ("RUNNING", "Running"),
        ("COMPLETED", "Completed"), ("FAILED", "Failed"),
        ("SHADOW", "Shadow"),
    )
    run_uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    profile = models.ForeignKey(
        SionPlanningProfile, on_delete=models.PROTECT, related_name="runs",
    )
    sion = models.ForeignKey(
        "core.SionNormClassModel", on_delete=models.PROTECT,
        related_name="planning_runs",
    )
    profile_version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="PENDING", db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    config_snapshot = models.JSONField(default=dict)
    result_summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_on",)
        indexes = [models.Index(fields=("sion", "status", "created_on"))]

    admin_list_display = (
        "run_uid", "sion", "profile", "profile_version", "status",
        "started_at", "completed_at",
    )
    admin_search_fields = ("run_uid", "profile__stable_key", "sion__norm_class")
    list_filter = ("status",)

    def clean(self):
        super().clean()
        _validate_planning_json(self.config_snapshot, "Config snapshot")
        _validate_planning_json(self.result_summary, "Result summary")
        if self.profile_id and self.sion_id and self.profile.sion_id != self.sion_id:
            raise ValidationError({"sion": "Run SION must match its profile SION."})
        if self.profile_id and self.profile_version != self.profile.version:
            raise ValidationError({"profile_version": "Profile version must match at run creation."})
        if self.completed_at and not self.started_at:
            raise ValidationError({"completed_at": "A completed run requires started_at."})
