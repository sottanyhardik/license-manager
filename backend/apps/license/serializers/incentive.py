"""Standalone incentive-licence and utilization-plan serializers.

Split out of the former serializers.py (behaviour unchanged). These do not
reference the core licence serializers.
"""
from decimal import Decimal

from rest_framework import serializers

from apps.core.models import ItemNameModel
from apps.core.serializers.fields import IndianDateField
from apps.license.models import IncentiveLicense, LicenseItemPlan, LicenseImportItemsModel

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
            "id", "import_item", "item_name", "item_name_label", "license",
            "planned_quantity", "unit_price", "planned_cif_fc", "planned_cif_inr", "note",
            "item_description", "serial_number", "license_number",
            "item_available_quantity", "item_total_quantity",
            "modified_on", "modified_by_username",
        ]
        read_only_fields = ["license"]
