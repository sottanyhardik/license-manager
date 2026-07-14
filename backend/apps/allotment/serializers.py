# allotment/serializers.py
"""
Serializers for the Allotment module.

AllotmentItemSerializer  — line item with read-only annotated helpers from
                           AllotmentItems.cached_property accessors.
AllotmentSerializer      — header with nested items, computed balance
                           properties, and display helpers.
"""
from rest_framework import serializers

from apps.allotment.models import AllotmentItems, AllotmentModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_date(value):
    """Format a date/datetime as dd-mm-yyyy, or return '' if falsy."""
    if value is None:
        return ""
    try:
        return value.strftime("%d-%m-%Y")
    except AttributeError:
        return str(value)


# ---------------------------------------------------------------------------
# AllotmentItemSerializer
# ---------------------------------------------------------------------------

class AllotmentItemSerializer(serializers.ModelSerializer):
    # Annotated read-only fields sourced from cached_property on the model
    serial_number = serializers.ReadOnlyField()
    product_description = serializers.ReadOnlyField()
    license_number = serializers.ReadOnlyField()
    hs_code = serializers.ReadOnlyField()
    registration_number = serializers.ReadOnlyField()
    notification_number = serializers.ReadOnlyField()
    file_number = serializers.ReadOnlyField()

    # Date fields formatted as dd-mm-yyyy
    license_date = serializers.SerializerMethodField()
    license_expiry = serializers.SerializerMethodField()

    # Nested object sources exposed as name strings
    exporter = serializers.SerializerMethodField()
    port_code = serializers.SerializerMethodField()

    class Meta:
        model = AllotmentItems
        fields = [
            "id",
            "item",
            "allotment",
            "cif_inr",
            "cif_fc",
            "qty",
            "is_boe",
            # annotated
            "serial_number",
            "product_description",
            "license_number",
            "license_date",
            "license_expiry",
            "hs_code",
            "exporter",
            "registration_number",
            "notification_number",
            "file_number",
            "port_code",
        ]

    def get_license_date(self, obj):
        return _fmt_date(obj.license_date)

    def get_license_expiry(self, obj):
        return _fmt_date(obj.license_expiry)

    def get_exporter(self, obj):
        exporter = obj.exporter
        if exporter is None:
            return None
        return getattr(exporter, "name", str(exporter))

    def get_port_code(self, obj):
        port_code = obj.port_code
        if port_code is None:
            return None
        return getattr(port_code, "name", str(port_code))


# ---------------------------------------------------------------------------
# AllotmentSerializer
# ---------------------------------------------------------------------------

class AllotmentSerializer(serializers.ModelSerializer):
    # Nested items (read-only; items are managed via their own endpoints)
    allotment_details = AllotmentItemSerializer(
        source="allotment_details",
        many=True,
        read_only=True,
    )

    # Computed balance properties (read-only)
    required_value = serializers.ReadOnlyField()
    alloted_quantity = serializers.ReadOnlyField()
    allotted_value = serializers.ReadOnlyField()
    balanced_quantity = serializers.ReadOnlyField()
    dfia_list = serializers.ReadOnlyField()

    # Display helpers sourced from related objects
    company_name = serializers.CharField(source="company.name", read_only=True)
    port_name = serializers.SerializerMethodField()
    related_company_name = serializers.SerializerMethodField()

    # Date input/output
    estimated_arrival_date = serializers.DateField(
        input_formats=["%Y-%m-%d"],
        required=False,
        allow_null=True,
    )
    created_on = serializers.SerializerMethodField()
    modified_on = serializers.SerializerMethodField()

    # Display label convenience field
    display_label = serializers.SerializerMethodField()

    # is_boe override: check bill_of_entry reverse relation safely
    is_boe = serializers.SerializerMethodField()

    class Meta:
        model = AllotmentModel
        fields = [
            "id",
            "company",
            "company_name",
            "type",
            "required_quantity",
            "unit_value_per_unit",
            "cif_fc",
            "cif_inr",
            "exchange_rate",
            "item_name",
            "contact_person",
            "contact_number",
            "invoice",
            "estimated_arrival_date",
            "bl_detail",
            "port",
            "port_name",
            "related_company",
            "related_company_name",
            "is_boe",
            "is_allotted",
            "is_approved",
            # computed
            "required_value",
            "alloted_quantity",
            "allotted_value",
            "balanced_quantity",
            "dfia_list",
            # nested
            "allotment_details",
            # audit
            "created_on",
            "modified_on",
            # display helpers
            "display_label",
        ]

    def get_created_on(self, obj):
        return _fmt_date(obj.created_on)

    def get_modified_on(self, obj):
        return _fmt_date(obj.modified_on)

    def get_port_name(self, obj):
        port = obj.port
        if port is None:
            return None
        return getattr(port, "name", str(port))

    def get_related_company_name(self, obj):
        rc = obj.related_company
        if rc is None:
            return None
        return getattr(rc, "name", str(rc))

    def get_display_label(self, obj):
        company_name = getattr(obj.company, "name", "") if obj.company else ""
        invoice = obj.invoice or ""
        qty = obj.required_quantity or 0
        return f"{company_name} | Inv: {invoice} | Qty: {qty}"

    def get_is_boe(self, obj):
        """Check if any BillOfEntry records exist via reverse relation."""
        try:
            # Use .all() to hit the prefetch_related cache without re-querying
            return obj.bill_of_entry.all().exists()
        except AttributeError:
            # Reverse relation may not exist yet (license app not wired)
            return obj.is_boe
