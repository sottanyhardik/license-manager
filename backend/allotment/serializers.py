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
    purchase_status = serializers.CharField(source='item.license.purchase_status', read_only=True)

    def get_ledger(self, obj):
        ledger = obj.ledger
        if isinstance(ledger, datetime):
            return ledger.date().strftime("%d-%m-%Y")
        elif isinstance(ledger, date):
            return ledger.strftime("%d-%m-%Y")
        return ledger

    def get_license_date(self, obj):
        license_date = obj.license_date
        if isinstance(license_date, datetime):
            return license_date.date().strftime("%d-%m-%Y")
        elif isinstance(license_date, date):
            return license_date.strftime("%d-%m-%Y")
        return license_date

    def get_license_expiry(self, obj):
        license_expiry = obj.license_expiry
        if isinstance(license_expiry, datetime):
            return license_expiry.date().strftime("%d-%m-%Y")
        elif isinstance(license_expiry, date):
            return license_expiry.strftime("%d-%m-%Y")
        return license_expiry

    def get_registration_date(self, obj):
        registration_date = obj.registration_date
        if isinstance(registration_date, datetime):
            return registration_date.date().strftime("%d-%m-%Y")
        elif isinstance(registration_date, date):
            return registration_date.strftime("%d-%m-%Y")
        return registration_date

    class Meta:
        model = AllotmentItems
        fields = [
            'id', 'item', 'allotment', 'cif_inr', 'cif_fc', 'qty', 'is_boe',
            'serial_number', 'ledger', 'product_description', 'license_number',
            'license_date', 'exporter', 'license_expiry', 'registration_number',
            'registration_date', 'notification_number', 'file_number', 'port_code',
            'purchase_status'
        ]


class AllotmentSerializer(serializers.ModelSerializer):
    # Nested serializer for read operations
    allotment_details_read = AllotmentItemSerializer(source='allotment_details', many=True, read_only=True)

    # Date field handling
    estimated_arrival_date = serializers.DateField(required=False, allow_null=True, format="%d-%m-%Y", input_formats=["%d-%m-%Y", "%Y-%m-%d"])
    created_on = serializers.SerializerMethodField()
    modified_on = serializers.SerializerMethodField()

    # Calculated at runtime instead of reading from database
    is_boe = serializers.SerializerMethodField(read_only=True)

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

    def get_is_boe(self, obj):
        """
        Calculate is_boe at runtime based on whether the allotment has a bill of entry.
        Returns True if allotment.bill_of_entry.exists(), else False.
        """
        try:
            return obj.bill_of_entry.exists()
        except Exception:
            return False

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
                return value.strftime("%d-%m-%Y %H:%M")
            elif isinstance(value, date):
                return value.strftime("%d-%m-%Y")
        return None

    def get_modified_on(self, obj):
        if obj.modified_on:
            value = obj.modified_on
            if isinstance(value, datetime):
                return value.strftime("%d-%m-%Y %H:%M")
            elif isinstance(value, date):
                return value.strftime("%d-%m-%Y")
        return None

    class Meta:
        model = AllotmentModel
        fields = [
            'id', 'company', 'type', 'required_quantity', 'unit_value_per_unit',
            'cif_fc', 'cif_inr', 'exchange_rate',
            'item_name', 'contact_person', 'contact_number', 'invoice',
            'estimated_arrival_date', 'bl_detail', 'port', 'related_company',
            'is_boe', 'is_approved', 'created_on', 'modified_on', 'created_by', 'modified_by',
            'required_value', 'dfia_list', 'balanced_quantity',
            'alloted_quantity', 'allotted_value', 'company_name', 'port_name',
            'related_company_name', 'display_label', 'allotment_details_read'
        ]

    def create(self, validated_data):
        """Set default values for type and exchange_rate if not provided"""
        # Set default type to 'AT' (Allotment) if not provided
        if 'type' not in validated_data or not validated_data['type']:
            validated_data['type'] = 'AT'  # ALLOTMENT

        # Set default exchange_rate to active USD rate if not provided
        if 'exchange_rate' not in validated_data or not validated_data.get('exchange_rate'):
            from core.models import ExchangeRateModel
            try:
                # Get the latest (active) exchange rate
                latest_rate = ExchangeRateModel.objects.order_by('-date').first()
                if latest_rate:
                    validated_data['exchange_rate'] = latest_rate.usd
            except Exception:
                pass  # If no exchange rate found, leave it as is

        return super().create(validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Rename nested field for frontend compatibility
        if 'allotment_details_read' in representation:
            representation['allotment_details'] = representation.pop('allotment_details_read')
        return representation
