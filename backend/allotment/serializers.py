# allotment/serializers.py
from rest_framework import serializers
from allotment.models import AllotmentModel, AllotmentItems


class AllotmentItemSerializer(serializers.ModelSerializer):
    # Read-only fields from cached properties
    serial_number = serializers.CharField(read_only=True, required=False)
    ledger = serializers.DateField(read_only=True, required=False)
    product_description = serializers.CharField(read_only=True, required=False)
    license_number = serializers.CharField(read_only=True, required=False)
    license_date = serializers.DateField(read_only=True, required=False)
    exporter = serializers.CharField(read_only=True, required=False, source='exporter.name')
    license_expiry = serializers.DateField(read_only=True, required=False)
    registration_number = serializers.CharField(read_only=True, required=False)
    registration_date = serializers.DateField(read_only=True, required=False)
    notification_number = serializers.CharField(read_only=True, required=False)
    file_number = serializers.CharField(read_only=True, required=False)
    port_code = serializers.CharField(read_only=True, required=False, source='port_code.name')

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

    class Meta:
        model = AllotmentModel
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Rename nested field for frontend compatibility
        if 'allotment_details_read' in representation:
            representation['allotment_details'] = representation.pop('allotment_details_read')
        return representation
