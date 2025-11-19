# bill_of_entry/serializers.py
from rest_framework import serializers
from bill_of_entry.models import BillOfEntryModel, RowDetails


class RowDetailsSerializer(serializers.ModelSerializer):
    """Serializer for BOE row details (nested items)"""
    license_number = serializers.CharField(source='sr_number.license.license_number', read_only=True)
    item_description = serializers.CharField(source='sr_number.description', read_only=True)
    hs_code = serializers.CharField(source='sr_number.hs_code.hs_code', read_only=True)

    class Meta:
        model = RowDetails
        fields = [
            'id',
            'row_type',
            'sr_number',
            'transaction_type',
            'cif_inr',
            'cif_fc',
            'qty',
            'license_number',
            'item_description',
            'hs_code',
        ]


class BillOfEntrySerializer(serializers.ModelSerializer):
    """Serializer for Bill of Entry with nested items"""
    item_details = RowDetailsSerializer(many=True, read_only=False, required=False)

    # Read-only computed fields
    total_inr = serializers.DecimalField(
        source='get_total_inr',
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    total_fc = serializers.DecimalField(
        source='get_total_fc',
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    total_quantity = serializers.DecimalField(
        source='get_total_quantity',
        max_digits=15,
        decimal_places=3,
        read_only=True
    )
    licenses = serializers.CharField(source='get_licenses', read_only=True)
    unit_price = serializers.DecimalField(
        source='get_unit_price',
        max_digits=15,
        decimal_places=3,
        read_only=True
    )

    # Display fields for foreign keys
    port_name = serializers.CharField(source='port.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = BillOfEntryModel
        fields = [
            'id',
            'company',
            'company_name',
            'bill_of_entry_number',
            'bill_of_entry_date',
            'port',
            'port_name',
            'exchange_rate',
            'product_name',
            'invoice_no',
            'invoice_date',
            'is_fetch',
            'failed',
            'appraisement',
            'ooc_date',
            'cha',
            'comments',
            'item_details',
            'total_inr',
            'total_fc',
            'total_quantity',
            'licenses',
            'unit_price',
            'created_on',
            'modified_on',
            'created_by',
            'modified_by',
        ]
        read_only_fields = ['created_on', 'modified_on', 'created_by', 'modified_by']

    def create(self, validated_data):
        """Create BOE with nested item details"""
        item_details_data = validated_data.pop('item_details', [])

        # Create the BOE instance
        boe = BillOfEntryModel.objects.create(**validated_data)

        # Create nested item details
        for item_data in item_details_data:
            RowDetails.objects.create(bill_of_entry=boe, **item_data)

        return boe

    def update(self, instance, validated_data):
        """Update BOE with nested item details"""
        item_details_data = validated_data.pop('item_details', None)

        # Update BOE fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update nested item details if provided
        if item_details_data is not None:
            # Get existing items
            existing_items = {item.id: item for item in instance.item_details.all()}

            # Track which items were updated
            updated_ids = set()

            for item_data in item_details_data:
                item_id = item_data.get('id')

                if item_id and item_id in existing_items:
                    # Update existing item
                    item_instance = existing_items[item_id]
                    for attr, value in item_data.items():
                        if attr != 'id':
                            setattr(item_instance, attr, value)
                    item_instance.save()
                    updated_ids.add(item_id)
                else:
                    # Create new item
                    new_item = RowDetails.objects.create(bill_of_entry=instance, **item_data)
                    updated_ids.add(new_item.id)

            # Delete items that weren't in the update
            for item_id, item in existing_items.items():
                if item_id not in updated_ids:
                    item.delete()

        return instance

    def to_representation(self, instance):
        """Add computed fields to representation"""
        representation = super().to_representation(instance)

        # Add allotment information if available
        allotments = instance.allotment.all()
        if allotments:
            representation['allotments'] = [
                {
                    'id': allot.id,
                    'item_name': allot.item_name,
                    'invoice': allot.invoice,
                    'required_quantity': str(allot.required_quantity),
                    'estimated_arrival_date': allot.estimated_arrival_date,
                    'company': allot.company.name if allot.company else None,
                }
                for allot in allotments
            ]

        return representation
