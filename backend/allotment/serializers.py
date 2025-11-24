# allotment/serializers.py
from rest_framework import serializers
from allotment.models import AllotmentModel, AllotmentItems
from datetime import datetime, date


class AllotmentItemSerializer(serializers.ModelSerializer):
    # Read-only fields from cached properties
    serial_number = serializers.CharField(read_only=True, required=False)
    ledger = serializers.SerializerMethodField()
    product_description = serializers.CharField(read_only=True, required=False)
    license_number = serializers.CharField(read_only=True, required=False)
    license_date = serializers.SerializerMethodField()
    exporter = serializers.CharField(read_only=True, required=False, source='exporter.name')
    license_expiry = serializers.SerializerMethodField()
    registration_number = serializers.CharField(read_only=True, required=False)
    registration_date = serializers.SerializerMethodField()
    notification_number = serializers.CharField(read_only=True, required=False)
    file_number = serializers.CharField(read_only=True, required=False)
    port_code = serializers.CharField(read_only=True, required=False, source='port_code.name')

    def get_ledger(self, obj):
        ledger = obj.ledger
        if isinstance(ledger, datetime):
            return ledger.date().isoformat()
        elif isinstance(ledger, date):
            return ledger.isoformat()
        return ledger

    def get_license_date(self, obj):
        license_date = obj.license_date
        if isinstance(license_date, datetime):
            return license_date.date().isoformat()
        elif isinstance(license_date, date):
            return license_date.isoformat()
        return license_date

    def get_license_expiry(self, obj):
        license_expiry = obj.license_expiry
        if isinstance(license_expiry, datetime):
            return license_expiry.date().isoformat()
        elif isinstance(license_expiry, date):
            return license_expiry.isoformat()
        return license_expiry

    def get_registration_date(self, obj):
        registration_date = obj.registration_date
        if isinstance(registration_date, datetime):
            return registration_date.date().isoformat()
        elif isinstance(registration_date, date):
            return registration_date.isoformat()
        return registration_date

    class Meta:
        model = AllotmentItems
        fields = [
            'id', 'item', 'allotment', 'cif_inr', 'cif_fc', 'qty', 'is_boe',
            'serial_number', 'ledger', 'product_description', 'license_number',
            'license_date', 'exporter', 'license_expiry', 'registration_number',
            'registration_date', 'notification_number', 'file_number', 'port_code'
        ]


class AllotmentSerializer(serializers.ModelSerializer):
    # Nested serializer for read operations
    allotment_details_read = AllotmentItemSerializer(source='allotment_details', many=True, read_only=True)

    # Date field handling
    estimated_arrival_date = serializers.DateField(required=False, allow_null=True, format="%Y-%m-%d")
    created_on = serializers.SerializerMethodField()
    modified_on = serializers.SerializerMethodField()

    # Cached property fields
    required_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    dfia_list = serializers.CharField(read_only=True, required=False)
    balanced_quantity = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    alloted_quantity = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    allotted_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    # Foreign key display fields
    company_name = serializers.CharField(source='company.name', read_only=True, required=False)
    port_name = serializers.CharField(source='port.name', read_only=True, required=False)
    related_company_name = serializers.CharField(source='related_company.name', read_only=True, required=False)

    # Custom label field for dropdown display
    display_label = serializers.SerializerMethodField(read_only=True)

    def get_display_label(self, obj):
        """Generate display label: Company Name - Invoice - Required Qty"""
        parts = []
        if obj.company:
            parts.append(obj.company.name)
        if obj.invoice:
            parts.append(f"Inv: {obj.invoice}")
        if obj.required_quantity:
            parts.append(f"Qty: {obj.required_quantity}")
        return " | ".join(parts) if parts else obj.item_name

    def get_created_on(self, obj):
        if obj.created_on:
            value = obj.created_on
            if isinstance(value, datetime):
                return value.date().isoformat()
            elif isinstance(value, date):
                return value.isoformat()
        return None

    def get_modified_on(self, obj):
        if obj.modified_on:
            value = obj.modified_on
            if isinstance(value, datetime):
                return value.date().isoformat()
            elif isinstance(value, date):
                return value.isoformat()
        return None

    class Meta:
        model = AllotmentModel
        fields = [
            'id', 'company', 'type', 'required_quantity', 'unit_value_per_unit',
            'cif_fc', 'cif_inr', 'exchange_rate',
            'item_name', 'contact_person', 'contact_number', 'invoice',
            'estimated_arrival_date', 'bl_detail', 'port', 'related_company',
            'is_boe', 'created_on', 'modified_on', 'created_by', 'modified_by',
            'required_value', 'dfia_list', 'balanced_quantity',
            'alloted_quantity', 'allotted_value', 'company_name', 'port_name',
            'related_company_name', 'display_label', 'allotment_details_read'
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Rename nested field for frontend compatibility
        if 'allotment_details_read' in representation:
            representation['allotment_details'] = representation.pop('allotment_details_read')
        return representation
