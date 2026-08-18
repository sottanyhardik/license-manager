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
    item_total_quantity = serializers.DecimalField(
        source="import_item.quantity", max_digits=15, decimal_places=3, read_only=True
    )
    license_number = serializers.CharField(source="import_item.license.license_number", read_only=True)

    # Audit metadata — used by PlanningEditor to show "Last saved / By:" in
    # both the Plan tab and the Plan modal.
    modified_on = serializers.DateTimeField(read_only=True)
    modified_by_username = serializers.SerializerMethodField(read_only=True)

    def get_modified_by_username(self, obj):
        return obj.modified_by.username if obj.modified_by_id else None

    class Meta:
        model = LicenseItemPlan
        fields = [
            "id", "import_item", "item_name", "item_name_label",
            "planning_item_id", "planning_item_name", "license",
            "planned_quantity", "unit_price", "planned_cif_fc", "planned_cif_inr", "note",
            "item_description", "serial_number", "license_number",
            "item_available_quantity", "item_total_quantity",
            "modified_on", "modified_by_username",
        ]
        read_only_fields = ["license"]


class SionPlanningUnitValueRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = SionPlanningUnitValueRow
        fields = ("id", "import_item", "min_unit_price", "max_unit_price", "preferred_unit_price", "priority")

    def validate(self, data):
        if data.get("max_unit_price") and data.get("min_unit_price"):
            if data["max_unit_price"] < data["min_unit_price"]:
                raise serializers.ValidationError(
                    {"max_unit_price": "Must be >= min_unit_price."}
                )
        if data.get("preferred_unit_price"):
            if data.get("min_unit_price") and data["preferred_unit_price"] < data["min_unit_price"]:
                raise serializers.ValidationError(
                    {"preferred_unit_price": "Must be >= min_unit_price."}
                )
            if data.get("max_unit_price") and data["preferred_unit_price"] > data["max_unit_price"]:
                raise serializers.ValidationError(
                    {"preferred_unit_price": "Must be <= max_unit_price."}
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
            if import_item.sion_norm_class_id != sion.id:
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
                if import_item and import_item.sion_norm_class_id != sion.id:
                    raise serializers.ValidationError(
                        {"unit_value_rows": f"Import item '{import_item.name}' does not belong to this SION."},
                        code="IMPORT_ITEM_NOT_ALLOWED_FOR_SION",
                    )
            item_ids = [row["import_item"].pk for row in unit_value_rows if row.get("import_item")]
            if len(item_ids) != len(set(item_ids)):
                raise serializers.ValidationError(
                    {"unit_value_rows": "Each import item may only be selected once."}
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
                if import_item and import_item.sion_norm_class_id != sion.id:
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
