"""Standalone incentive-licence and utilization-plan serializers.

Split out of the former serializers.py (behaviour unchanged). These do not
reference the core licence serializers.
"""
from decimal import Decimal

from rest_framework import serializers

from apps.core.models import ItemNameModel
from apps.core.serializers.fields import IndianDateField
from apps.license.models import (
    IncentiveLicense, LicenseItemPlan, LicenseImportItemsModel, SionPlanningRule,
    SionPlanningUnitValueRow, SionPlanningPercentageRow,
)

DECIMAL_ZERO = Decimal("0.00")


class IncentiveLicenseSerializer(serializers.ModelSerializer):
    """
    Serializer for IncentiveLicense model (RODTEP/ROSTL/MEIS)
    """
    license_date = IndianDateField(required=True)
    license_expiry_date = IndianDateField(required=False, allow_null=True)

    # Read-only fields for display
    exporter_name = serializers.CharField(source="exporter.name", read_only=True, allow_null=True)
    port_name = serializers.CharField(source="port_code.name", read_only=True, allow_null=True)
    sold_value = serializers.SerializerMethodField()
    balance_value = serializers.SerializerMethodField()

    class Meta:
        model = IncentiveLicense
        fields = "__all__"
        read_only_fields = ("created_by", "modified_by", "created_on", "modified_on", "license_expiry_date")

    def get_sold_value(self, obj):
        """Get total sold value from SALE trades"""
        return float(obj.sold_value or DECIMAL_ZERO)

    def get_balance_value(self, obj):
        """Get remaining balance value"""
        return float(obj.balance_value or DECIMAL_ZERO)

    def get_sold_status(self, obj):
        """Get sold status: YES (fully sold), NO (not sold), PARTIAL (partially sold)"""
        sold_value = obj.sold_value or DECIMAL_ZERO
        balance_value = obj.balance_value or DECIMAL_ZERO

        if sold_value == DECIMAL_ZERO:
            return 'NO'
        if balance_value <= DECIMAL_ZERO:
            return 'YES'
        return 'PARTIAL'

    def to_representation(self, instance):
        """Add formatted dates and display names"""
        rep = super().to_representation(instance)

        # Add exporter and port details for frontend display
        if instance.exporter:
            rep['exporter_name'] = instance.exporter.name
            rep['exporter__name'] = instance.exporter.name  # For list_display consistency
        if instance.port_code:
            rep['port_name'] = instance.port_code.name
            rep['port_code__name'] = instance.port_code.name  # For list_display consistency

        # Add computed fields
        rep['sold_value'] = self.get_sold_value(instance)
        rep['balance_value'] = self.get_balance_value(instance)
        rep['sold_status'] = self.get_sold_status(instance)

        return rep


class LicenseItemPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for a utilization plan line (an item may have several split lines).

    Read-only context fields (item description / serial / available / total qty,
    item-name label) help the frontend render each split row. Capacity (Σ split
    quantity ≤ item capacity) and the CIF-pool cap (Σ planned_cif_fc ≤ licence
    balance) are cross-line checks and are validated in the viewset's
    ``bulk_upsert`` where all lines for the licence are known at once.
    """
    import_item = serializers.PrimaryKeyRelatedField(
        queryset=LicenseImportItemsModel.objects.all()
    )
    item_name = serializers.PrimaryKeyRelatedField(
        queryset=ItemNameModel.objects.all(), required=False, allow_null=True
    )
    item_name_label = serializers.CharField(source="item_name.name", read_only=True)
    planning_item_id = serializers.IntegerField(source="item_name_id", read_only=True)
    planning_item_name = serializers.CharField(source="item_name.name", read_only=True)
    item_description = serializers.CharField(source="import_item.description", read_only=True)
    serial_number = serializers.IntegerField(source="import_item.serial_number", read_only=True)
    item_available_quantity = serializers.DecimalField(
        source="import_item.available_quantity", max_digits=15, decimal_places=3, read_only=True
    )
    actual_item_available_qty = serializers.SerializerMethodField(read_only=True)
    actual_license_balance_cif = serializers.SerializerMethodField(read_only=True)
    item_total_quantity = serializers.DecimalField(
        source="import_item.quantity", max_digits=15, decimal_places=3, read_only=True
    )
    license_number = serializers.CharField(source="import_item.license.license_number", read_only=True)

    # Audit metadata — used by PlanningEditor to show "Last saved / By:" in
    # both the Plan tab and the Plan modal.
    modified_on = serializers.DateTimeField(read_only=True)
    modified_by_username = serializers.SerializerMethodField(read_only=True)
    planning_family = serializers.SerializerMethodField(read_only=True)
    boe_used_quantity = serializers.SerializerMethodField(read_only=True)
    boe_used_cif = serializers.SerializerMethodField(read_only=True)
    unlinked_allotment_quantity = serializers.SerializerMethodField(read_only=True)
    unlinked_allotment_cif = serializers.SerializerMethodField(read_only=True)
    effective_used_quantity = serializers.SerializerMethodField(read_only=True)
    effective_used_cif = serializers.SerializerMethodField(read_only=True)
    percentage_theoretical_quantity = serializers.SerializerMethodField(read_only=True)
    percentage_theoretical_cif = serializers.SerializerMethodField(read_only=True)
    theoretical_quantity = serializers.SerializerMethodField(read_only=True)
    theoretical_cif = serializers.SerializerMethodField(read_only=True)
    reconciled_planned_quantity = serializers.SerializerMethodField(read_only=True)
    reconciled_planned_cif = serializers.SerializerMethodField(read_only=True)
    remaining_quantity = serializers.SerializerMethodField(read_only=True)
    remaining_cif = serializers.SerializerMethodField(read_only=True)
    raw_remaining_quantity = serializers.SerializerMethodField(read_only=True)
    raw_remaining_cif = serializers.SerializerMethodField(read_only=True)
    available_balance_quantity = serializers.SerializerMethodField(read_only=True)
    effective_remaining_quantity = serializers.SerializerMethodField(read_only=True)
    effective_remaining_cif = serializers.SerializerMethodField(read_only=True)
    quantity_cap_applied = serializers.SerializerMethodField(read_only=True)
    excess_quantity = serializers.SerializerMethodField(read_only=True)
    excess_cif = serializers.SerializerMethodField(read_only=True)
    reconciliation_status = serializers.SerializerMethodField(read_only=True)
    planning_target_item_id = serializers.SerializerMethodField(read_only=True)
    mapping_status = serializers.SerializerMethodField(read_only=True)
    unmapped_actual_quantity = serializers.SerializerMethodField(read_only=True)
    unmapped_actual_cif = serializers.SerializerMethodField(read_only=True)
    status = serializers.SerializerMethodField(read_only=True)
    unmapped_usage = serializers.SerializerMethodField(read_only=True)
    needs_rebuild = serializers.SerializerMethodField(read_only=True)
    percentage_base_qty = serializers.SerializerMethodField(read_only=True)
    split_percentage = serializers.SerializerMethodField(read_only=True)
    theoretical_target_qty = serializers.SerializerMethodField(read_only=True)
    theoretical_target_cif = serializers.SerializerMethodField(read_only=True)
    new_planned_qty = serializers.DecimalField(source="planned_quantity", max_digits=15, decimal_places=3, read_only=True)
    new_planned_cif = serializers.DecimalField(source="planned_cif_fc", max_digits=15, decimal_places=2, read_only=True)
    unfilled_target_qty = serializers.SerializerMethodField(read_only=True)
    unfilled_target_cif = serializers.SerializerMethodField(read_only=True)
    adjusted_planned_cif = serializers.SerializerMethodField(read_only=True)
    effective_unit_price = serializers.SerializerMethodField(read_only=True)
    candidate_planned_qty = serializers.SerializerMethodField(read_only=True)
    effective_planned_qty = serializers.SerializerMethodField(read_only=True)
    configured_unit_price = serializers.SerializerMethodField(read_only=True)
    candidate_planned_cif = serializers.SerializerMethodField(read_only=True)
    cif_cap_adjustment = serializers.SerializerMethodField(read_only=True)
    effective_planned_cif = serializers.SerializerMethodField(read_only=True)
    remaining_entitlement_qty = serializers.SerializerMethodField(read_only=True)
    percentage_target_qty = serializers.SerializerMethodField(read_only=True)
    excess_other_item_qty = serializers.SerializerMethodField(read_only=True)
    excess_other_item_cif = serializers.SerializerMethodField(read_only=True)

    def _provenance_decimal(self, obj, key, fallback=0):
        return Decimal(str((obj.allocation_provenance or {}).get(key, fallback) or 0))

    def get_percentage_base_qty(self, obj):
        return f"{self._provenance_decimal(obj, 'percentage_base_qty'):.3f}"

    def get_split_percentage(self, obj):
        value = (obj.allocation_provenance or {}).get("percentage")
        return f"{Decimal(str(value)):.2f}" if value is not None else None

    def get_theoretical_target_qty(self, obj):
        return f"{self._provenance_decimal(obj, 'theoretical_quantity', obj.planned_quantity):.3f}"

    def get_theoretical_target_cif(self, obj):
        return f"{self._provenance_decimal(obj, 'percentage_target_cif', self._provenance_decimal(obj, 'theoretical_cif', obj.planned_cif_fc)):.2f}"

    def get_candidate_planned_qty(self, obj):
        return f"{self._provenance_decimal(obj, 'candidate_planned_quantity', obj.planned_quantity):.3f}"

    def get_effective_planned_qty(self, obj):
        return f"{self._provenance_decimal(obj, 'effective_planned_quantity', obj.planned_quantity):.3f}"

    def get_configured_unit_price(self, obj):
        return f"{self._provenance_decimal(obj, 'configured_max_unit_price', obj.unit_price):.2f}"

    def get_candidate_planned_cif(self, obj):
        return f"{self._provenance_decimal(obj, 'candidate_planned_cif', obj.planned_cif_fc):.2f}"

    def get_unfilled_target_qty(self, obj):
        return f"{max(self._provenance_decimal(obj, 'theoretical_quantity', obj.planned_quantity) - Decimal(obj.planned_quantity or 0), Decimal('0')):.3f}"

    def get_unfilled_target_cif(self, obj):
        return f"{max(self._provenance_decimal(obj, 'theoretical_cif', obj.planned_cif_fc) - Decimal(obj.planned_cif_fc or 0), Decimal('0')):.2f}"

    def get_adjusted_planned_cif(self, obj):
        value = self._reconciliation(obj)["plans"].get(obj.id, {}).get("adjusted_planned_cif")
        return f"{Decimal(value if value is not None else obj.planned_cif_fc or 0):.2f}"

    def get_effective_unit_price(self, obj):
        reconciled = self._reconciliation(obj)["plans"].get(obj.id, {})
        cif = Decimal(reconciled.get("adjusted_planned_cif", obj.planned_cif_fc or 0))
        qty = Decimal(obj.planned_quantity or 0)
        return f"{(cif / qty if qty else Decimal('0')):.9f}"

    def get_cif_cap_adjustment(self, obj):
        value = (obj.allocation_provenance or {}).get(
            "cif_cap_adjustment",
            self._reconciliation(obj)["plans"].get(obj.id, {}).get("cif_cap_adjustment", 0),
        )
        return f"{Decimal(value):.2f}"

    def get_effective_planned_cif(self, obj):
        return self.get_adjusted_planned_cif(obj)

    def get_percentage_target_qty(self, obj):
        return f"{self._provenance_decimal(obj, 'theoretical_target_qty', obj.planned_quantity):.3f}"

    def get_remaining_entitlement_qty(self, obj):
        # This is target minus actual mapped BOE/allotment exactly once.  It
        # is intentionally independent of any CIF-only price adjustment.
        provenance = obj.allocation_provenance or {}
        if 'audit_remaining_quantity' in provenance:
            value = Decimal(str(provenance['audit_remaining_quantity'])) - Decimal(str(provenance.get('excess_other_item_quantity', 0)))
            return f"{value:.3f}"
        value = provenance.get('remaining_percentage_capacity')
        if value is None:
            target = self._provenance_decimal(obj, 'theoretical_target_qty', obj.planned_quantity)
            actual = Decimal(self._reconciliation(obj)['plans'].get(obj.id, {}).get('effective_used_quantity', 0))
            value = max(target - actual, Decimal('0'))
        return f"{Decimal(value):.3f}"

    def get_excess_other_item_qty(self, obj):
        return f"{self._provenance_decimal(obj, 'excess_other_item_quantity'):.3f}"

    def get_excess_other_item_cif(self, obj):
        return f"{self._provenance_decimal(obj, 'excess_other_item_cif'):.2f}"

    def get_modified_by_username(self, obj):
        return obj.modified_by.username if obj.modified_by_id else None

    def get_actual_item_available_qty(self, obj):
        # The live, license-scoped source quantity; never a plan or Norm
        # Summary aggregate.
        return f"{Decimal(obj.import_item.available_quantity or 0):.3f}"

    def get_actual_license_balance_cif(self, obj):
        # Canonical financial balance after actual BOE/allotment utilization,
        # before future planning projections.
        return f"{Decimal(obj.license.get_balance_cif or 0):.2f}"

    def _reconciliation(self, obj):
        from apps.license.services.planning_usage_reconciliation import reconcile_license_plans

        cache = self.context.setdefault("planning_usage_reconciliation", {})
        license_id = obj.license_id or obj.import_item.license_id
        if license_id not in cache:
            cache[license_id] = reconcile_license_plans(license_id)
        return cache[license_id]

    def _reconciliation_value(self, obj, key, default="0"):
        value = self._reconciliation(obj)["plans"].get(obj.id, {}).get(key, default)
        if value is None:
            return None
        if key.endswith("quantity"):
            return f"{Decimal(value):.3f}"
        if key.endswith("cif"):
            return f"{Decimal(value):.2f}"
        return str(value)

    def get_planning_family(self, obj):
        return self._reconciliation_value(obj, "planning_family", None)

    def get_boe_used_quantity(self, obj):
        return self._reconciliation_value(obj, "boe_used_quantity")

    def get_boe_used_cif(self, obj):
        return self._reconciliation_value(obj, "boe_used_cif")

    def get_unlinked_allotment_quantity(self, obj):
        return self._reconciliation_value(obj, "unlinked_allotment_quantity")

    def get_unlinked_allotment_cif(self, obj):
        return self._reconciliation_value(obj, "unlinked_allotment_cif")

    def get_effective_used_quantity(self, obj):
        return self._reconciliation_value(obj, "effective_used_quantity")

    def get_effective_used_cif(self, obj):
        return self._reconciliation_value(obj, "effective_used_cif")

    def get_percentage_theoretical_quantity(self, obj):
        value = (obj.allocation_provenance or {}).get("theoretical_quantity", obj.planned_quantity)
        return f"{Decimal(value):.3f}"

    def get_percentage_theoretical_cif(self, obj):
        value = (obj.allocation_provenance or {}).get("theoretical_cif", obj.planned_cif_fc)
        return f"{Decimal(value):.2f}"

    def get_theoretical_quantity(self, obj):
        value = (obj.allocation_provenance or {}).get("theoretical_quantity", obj.planned_quantity)
        return f"{Decimal(value):.3f}"

    def get_theoretical_cif(self, obj):
        # Strategy-waterfall rows retain uncapped CIF in provenance while
        # planned_cif_fc is the operational CIF commitment.
        theoretical = (obj.allocation_provenance or {}).get("theoretical_cif")
        if theoretical is not None:
            return f"{Decimal(theoretical):.2f}"
        return self._reconciliation_value(obj, "theoretical_cif", obj.planned_cif_fc)

    def get_reconciled_planned_quantity(self, obj):
        return self._reconciliation_value(obj, "reconciled_planned_quantity", obj.planned_quantity)

    def get_reconciled_planned_cif(self, obj):
        return self._reconciliation_value(obj, "reconciled_planned_cif", obj.planned_cif_fc)

    def get_remaining_quantity(self, obj):
        return self._reconciliation_value(obj, "remaining_quantity", obj.planned_quantity)

    def get_remaining_cif(self, obj):
        return self._reconciliation_value(obj, "remaining_cif", obj.planned_cif_fc)

    def get_raw_remaining_quantity(self, obj):
        return self._reconciliation_value(obj, "raw_remaining_quantity", obj.planned_quantity)

    def get_raw_remaining_cif(self, obj):
        return self._reconciliation_value(obj, "raw_remaining_cif", obj.planned_cif_fc)

    def get_available_balance_quantity(self, obj):
        return self._reconciliation_value(obj, "available_balance_quantity", obj.import_item.available_quantity)

    def get_effective_remaining_quantity(self, obj):
        return self._reconciliation_value(obj, "effective_remaining_quantity", obj.planned_quantity)

    def get_effective_remaining_cif(self, obj):
        return self._reconciliation_value(obj, "effective_remaining_cif", obj.planned_cif_fc)

    def get_quantity_cap_applied(self, obj):
        return bool(self._reconciliation(obj)["plans"].get(obj.id, {}).get("quantity_cap_applied", False))

    def get_excess_quantity(self, obj):
        return self._reconciliation_value(obj, "excess_quantity")

    def get_excess_cif(self, obj):
        return self._reconciliation_value(obj, "excess_cif")

    def get_reconciliation_status(self, obj):
        return self._reconciliation_value(obj, "reconciliation_status", "NOT_USED")

    def get_planning_target_item_id(self, obj):
        return obj.item_name_id

    def get_mapping_status(self, obj):
        return self._reconciliation_value(obj, "mapping_status", "NO_ACTUAL_USAGE")

    def get_unmapped_actual_quantity(self, obj):
        return self._reconciliation_value(obj, "unmapped_actual_quantity")

    def get_unmapped_actual_cif(self, obj):
        return self._reconciliation_value(obj, "unmapped_actual_cif")

    def get_status(self, obj):
        return self.get_reconciliation_status(obj)

    def get_unmapped_usage(self, obj):
        rows = self._reconciliation(obj)["unmapped_usage"]
        return [{**row, "quantity": str(row["quantity"]), "cif_fc": str(row["cif_fc"])} for row in rows]

    def get_needs_rebuild(self, obj):
        """A saved plan is stale when its versioned rule has a newer active version."""
        if not obj.planning_rule_id:
            return False
        rule = obj.planning_rule
        # ``stable_key`` is not populated on older rules.  Filtering NULL
        # stable keys alone groups every unrelated active rule together and
        # makes every such plan permanently display "Needs Rebuild".
        candidates = SionPlanningRule.objects.filter(is_active=True)
        if rule.stable_key:
            candidates = candidates.filter(stable_key=rule.stable_key)
        else:
            candidates = candidates.filter(
                sion_id=rule.sion_id, name=rule.name,
                priority=rule.priority, strategy=rule.strategy,
            )
        return candidates.exclude(pk=obj.planning_rule_id).exists()

    class Meta:
        model = LicenseItemPlan
        fields = [
            "id", "import_item", "item_name", "item_name_label",
            "planning_item_id", "planning_item_name", "license",
            "planned_quantity", "unit_price", "planned_cif_fc", "planned_cif_inr", "note",
            "item_description", "serial_number", "license_number",
            "item_available_quantity", "item_total_quantity", "actual_item_available_qty",
            "actual_license_balance_cif",
            "modified_on", "modified_by_username",
            "planning_family", "boe_used_quantity", "boe_used_cif",
            "unlinked_allotment_quantity", "unlinked_allotment_cif",
            "effective_used_quantity", "effective_used_cif",
            "percentage_theoretical_quantity", "percentage_theoretical_cif",
            "theoretical_quantity", "theoretical_cif",
            "reconciled_planned_quantity", "reconciled_planned_cif",
            "remaining_quantity", "remaining_cif", "excess_quantity", "excess_cif",
            "raw_remaining_quantity", "raw_remaining_cif", "available_balance_quantity",
            "effective_remaining_quantity", "effective_remaining_cif", "quantity_cap_applied",
            "reconciliation_status", "status", "unmapped_usage", "needs_rebuild",
            "percentage_base_qty", "split_percentage", "theoretical_target_qty", "theoretical_target_cif",
            "new_planned_qty", "new_planned_cif", "unfilled_target_qty", "unfilled_target_cif",
            "adjusted_planned_cif", "effective_unit_price",
            "candidate_planned_qty", "effective_planned_qty", "configured_unit_price",
            "candidate_planned_cif", "cif_cap_adjustment", "effective_planned_cif",
            "percentage_target_qty", "remaining_entitlement_qty",
            "excess_other_item_qty", "excess_other_item_cif",
            "planning_target_item_id", "mapping_status", "unmapped_actual_quantity", "unmapped_actual_cif",
        ]
        read_only_fields = ["license"]


class SionPlanningUnitValueRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = SionPlanningUnitValueRow
        fields = ("id", "import_item", "min_unit_price", "max_unit_price", "preferred_unit_price", "priority")

    def validate(self, data):
        minimum = data.get("min_unit_price")
        maximum = data.get("max_unit_price")
        # A range must contain a positive-width interval.  Decimal fields and
        # model validators enforce non-negative values; do not use truthiness
        # here because Decimal("0") is an intentional valid value.
        if minimum is not None and maximum is not None and maximum <= minimum:
            raise serializers.ValidationError(
                {"max_unit_price": "Must be greater than min_unit_price."}
            )
        return data


class SionPlanningPercentageRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = SionPlanningPercentageRow
        fields = ("id", "import_item", "percentage", "unit_price", "max_quantity", "priority")


class SionPlanningRuleSerializer(serializers.ModelSerializer):
    unit = serializers.CharField(max_length=10)
    sion_code = serializers.CharField(source="sion.norm_class", read_only=True)
    standard_item_name = serializers.CharField(source="import_item.name", read_only=True, allow_null=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    modified_by_username = serializers.CharField(source="modified_by.username", read_only=True)
    unit_value_rows = SionPlanningUnitValueRowSerializer(many=True, required=False)
    percentage_rows = SionPlanningPercentageRowSerializer(many=True, required=False)

    class Meta:
        model = SionPlanningRule
        fields = (
            "id", "sion", "sion_code", "name", "version", "expression",
            "max_unit_price", "unit", "priority", "is_active", "execution_output",
            "strategy", "import_item", "standard_item_name", "unit_value_rows", "percentage_rows",
            "percentage_constraint", "rule_type",
            "created_on", "created_by_username", "modified_on",
            "modified_by_username",
        )
        read_only_fields = (
            "version", "priority", "created_on", "created_by_username", "modified_on",
            "modified_by_username", "standard_item_name",
        )

    def validate_expression(self, value):
        from apps.license.services.sion_rule_engine import normalize_expression, validate_expression
        try:
            value = normalize_expression(value)
            validate_expression(value)
        except Exception as exc:
            raise serializers.ValidationError(getattr(exc, "messages", [str(exc)])) from exc
        return value

    def validate_unit(self, value):
        from apps.core.constants import UNIT_CHOICES
        normalized = str(value).strip().lower()
        if normalized not in {code for code, _label in UNIT_CHOICES}:
            raise serializers.ValidationError("Unsupported planning unit.")
        return normalized

    def validate(self, data):
        strategy = data.get("strategy")
        sion = data.get("sion") or (self.instance.sion if self.instance else None)

        # Reject old "output_item" key
        if "output_item" in self.initial_data or "output_item_id" in self.initial_data:
            raise serializers.ValidationError(
                "output_item is deprecated. Use import_item (STANDARD strategy), "
                "unit_value_rows, or percentage_rows instead."
            )

        if not strategy:
            # Legacy dispatch path — no validation needed
            return data

        # STANDARD: require import_item (1:1), reject other rows
        if strategy == "STANDARD":
            import_item = data.get("import_item")
            if not import_item:
                raise serializers.ValidationError(
                    {"strategy": "STANDARD strategy requires import_item."}
                )
            if not (import_item.norms.filter(pk=sion.id).exists() or import_item.sion_norm_class_id == sion.id):
                raise serializers.ValidationError(
                    {"import_item": "Import item does not belong to this SION."},
                    code="IMPORT_ITEM_NOT_ALLOWED_FOR_SION",
                )
            if data.get("unit_value_rows") or data.get("percentage_rows"):
                raise serializers.ValidationError(
                    {"strategy": "STANDARD strategy does not use unit_value_rows or percentage_rows."}
                )

        # SPLIT_BY_UNIT_VALUE: require ≥1 rows, validate SION + bounds
        elif strategy == "SPLIT_BY_UNIT_VALUE":
            unit_value_rows = data.get("unit_value_rows") or []
            if not unit_value_rows:
                raise serializers.ValidationError(
                    {"unit_value_rows": "SPLIT_BY_UNIT_VALUE requires at least one row."}
                )
            for row_data in unit_value_rows:
                import_item = row_data.get("import_item")
                if import_item and not (import_item.norms.filter(pk=sion.id).exists() or import_item.sion_norm_class_id == sion.id):
                    raise serializers.ValidationError(
                        {"unit_value_rows": f"Import item '{import_item.name}' does not belong to this SION."},
                        code="IMPORT_ITEM_NOT_ALLOWED_FOR_SION",
                    )
            item_ids = [row["import_item"].pk for row in unit_value_rows if row.get("import_item")]
            if len(item_ids) != len(set(item_ids)):
                raise serializers.ValidationError(
                    {"unit_value_rows": "Each import item may only be selected once."}
                )
            # Input price bands are evaluated low-to-high.  A touching
            # boundary is deterministic: it belongs to the lower band, while
            # the next band is previous_max < price <= max.  Validate a sorted
            # copy so visual/form row order does not affect save behaviour.
            ordered_rows = sorted(unit_value_rows, key=lambda row: row["min_unit_price"])
            for lower, upper in zip(ordered_rows, ordered_rows[1:]):
                if upper["min_unit_price"] < lower["max_unit_price"]:
                    raise serializers.ValidationError(
                        {"unit_value_rows": "Price ranges overlap."}
                    )

        # SPLIT_BY_PERCENT: require ≥1 rows, total==100, validate SION
        elif strategy == "SPLIT_BY_PERCENT":
            percentage_rows = data.get("percentage_rows") or []
            if not percentage_rows:
                raise serializers.ValidationError(
                    {"percentage_rows": "SPLIT_BY_PERCENT requires at least one row."}
                )
            total_pct = sum(Decimal(str(row.get("percentage", 0))) for row in percentage_rows)
            if total_pct != Decimal("100"):
                raise serializers.ValidationError(
                    {"percentage_rows": f"Percentages must sum to 100.00 (got {total_pct})."}
                )
            for row_data in percentage_rows:
                import_item = row_data.get("import_item")
                if import_item and not (import_item.norms.filter(pk=sion.id).exists() or import_item.sion_norm_class_id == sion.id):
                    raise serializers.ValidationError(
                        {"percentage_rows": f"Import item '{import_item.name}' does not belong to this SION."},
                        code="IMPORT_ITEM_NOT_ALLOWED_FOR_SION",
                    )
            item_ids = [row["import_item"].pk for row in percentage_rows if row.get("import_item")]
            if len(item_ids) != len(set(item_ids)):
                raise serializers.ValidationError(
                    {"percentage_rows": "Each import item may only be selected once."}
                )

        return data

    def create(self, validated_data):
        unit_value_rows = validated_data.pop("unit_value_rows", [])
        percentage_rows = validated_data.pop("percentage_rows", [])

        instance = super().create(validated_data)

        # Create nested rows
        for row_data in unit_value_rows:
            SionPlanningUnitValueRow.objects.create(rule=instance, **row_data)
        for row_data in percentage_rows:
            SionPlanningPercentageRow.objects.create(rule=instance, **row_data)

        return instance

    def update(self, instance, validated_data):
        unit_value_rows = validated_data.pop("unit_value_rows", None)
        percentage_rows = validated_data.pop("percentage_rows", None)

        # Update main fields (but not via super, since we're in version-append workflow)
        # The view handles version-append; serializer just saves the core fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Replace row sets entirely (delete-then-recreate)
        if unit_value_rows is not None:
            instance.unit_value_rows.all().delete()
            for row_data in unit_value_rows:
                SionPlanningUnitValueRow.objects.create(rule=instance, **row_data)
        if percentage_rows is not None:
            instance.percentage_rows.all().delete()
            for row_data in percentage_rows:
                SionPlanningPercentageRow.objects.create(rule=instance, **row_data)

        return instance


class LicenseIdOnlySerializer(serializers.Serializer):
    """Single-license planning request."""

    license_id = serializers.IntegerField(required=True, min_value=1)
    mode = serializers.ChoiceField(
        choices=("NEW", "ALL"),
        required=False,
        default="NEW",
    )


class BulkLicensePlanningSerializer(serializers.Serializer):
    """Bulk-license planning request."""

    license_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=True,
        allow_empty=False,
    )
    mode = serializers.ChoiceField(
        choices=("NEW", "ALL"),
        required=False,
        default="NEW",
    )
