# bill_of_entry/serializers.py
from rest_framework import serializers

from bill_of_entry.models import BillOfEntryModel, RowDetails


class RowDetailsSerializer(serializers.ModelSerializer):
    """Serializer for BOE row details (nested items)"""
    # Make id writable so it can be passed during updates
    id = serializers.IntegerField(required=False)
    license_number = serializers.CharField(source='sr_number.license.license_number', read_only=True)
    item_description = serializers.CharField(source='sr_number.description', read_only=True)
    hs_code = serializers.CharField(source='sr_number.hs_code.hs_code', read_only=True)
    item_serial_number = serializers.IntegerField(source='sr_number.serial_number', read_only=True)
    condition_type = serializers.CharField(source='sr_number.condition_type', read_only=True)
    purchase_status = serializers.SerializerMethodField()

    def get_purchase_status(self, obj):
        """Get purchase status code safely"""
        if obj.sr_number and obj.sr_number.license and obj.sr_number.license.purchase_status:
            return obj.sr_number.license.purchase_status.code
        return None

    class Meta:
        model = RowDetails
        fields = [
            'id',
            'sr_number',
            'cif_inr',
            'cif_fc',
            'qty',
            'is_frozen',
            'is_dispute',
            'license_number',
            'item_description',
            'hs_code',
            'item_serial_number',
            'condition_type',
            'purchase_status',
        ]
        read_only_fields = ['is_frozen', 'is_dispute']


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
            'allotment',
            'exchange_rate',
            'product_name',
            'invoice_no',
            'invoice_date',
            'is_fetch',
            'boe_pdf_copy',
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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Auto-calculate exchange_rate from row totals when stored value is 0 or null
        exc = data.get('exchange_rate')
        if not exc or float(exc) == 0:
            total_fc = float(data.get('total_fc') or 0)
            total_inr = float(data.get('total_inr') or 0)
            if total_fc > 0:
                data['exchange_rate'] = round(total_inr / total_fc, 4)
        return data

    def to_internal_value(self, data):
        """Parse JSON strings or flattened FormData from multipart/form-data"""
        import json
        import re

        # Create a mutable copy of the data
        data = data.copy() if hasattr(data, 'copy') else dict(data)

        # Handle JSON string format (when frontend sends JSON.stringify for nested arrays)
        if 'item_details' in data and isinstance(data['item_details'], str):
            try:
                data['item_details'] = json.loads(data['item_details'])
            except (json.JSONDecodeError, TypeError):
                pass

        # Handle flattened FormData format (item_details[0][field])
        if hasattr(data, 'getlist'):
            nested_items = {}
            for key in list(data.keys()):
                match = re.match(r'item_details\[(\d+)\]\.(.+)', key)
                if match:
                    index = int(match.group(1))
                    field_name = match.group(2)
                    if index not in nested_items:
                        nested_items[index] = {}
                    nested_items[index][field_name] = data[key]

            if nested_items:
                data['item_details'] = [nested_items[i] for i in sorted(nested_items.keys())]

        return super().to_internal_value(data)

    def create(self, validated_data):
        """Create BOE with nested item details"""
        item_details_data = validated_data.pop('item_details', [])
        allotment_data = validated_data.pop('allotment', [])

        # Use update_or_create to avoid IntegrityError on the unique_together
        # constraint (bill_of_entry_number, bill_of_entry_date, port).
        boe_number = validated_data.pop('bill_of_entry_number')
        boe_date = validated_data.pop('bill_of_entry_date', None)
        port = validated_data.pop('port', None)
        boe, _ = BillOfEntryModel.objects.update_or_create(
            bill_of_entry_number=boe_number,
            bill_of_entry_date=boe_date,
            port=port,
            defaults=validated_data,
        )

        # Set many-to-many allotment field
        if allotment_data:
            boe.allotment.set(allotment_data)

            # Mark all associated allotments as having BOE
            for allotment in allotment_data:
                allotment.is_boe = True
                allotment.save()

        # Create nested item details
        for item_data in item_details_data:
            RowDetails.objects.create(bill_of_entry=boe, **item_data)

        return boe

    def update(self, instance, validated_data):
        """Update BOE with nested item details"""
        item_details_data = validated_data.pop('item_details', None)
        allotment_data = validated_data.pop('allotment', None)

        # Update BOE fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update many-to-many allotment field only if explicitly provided with values
        if allotment_data is not None and len(allotment_data) > 0:
            # Get old allotments before updating
            old_allotment_ids = set(instance.allotment.values_list('id', flat=True))

            # Set new allotments
            instance.allotment.set(allotment_data)

            # Get new allotment IDs
            new_allotment_ids = set([a.id for a in allotment_data])

            # Mark new allotments as having BOE
            for allotment in allotment_data:
                if allotment.id not in old_allotment_ids:
                    allotment.is_boe = True
                    allotment.save()

            # Find removed allotments
            removed_allotment_ids = old_allotment_ids - new_allotment_ids
            if removed_allotment_ids:
                from allotment.models import AllotmentModel
                for allotment_id in removed_allotment_ids:
                    allotment = AllotmentModel.objects.get(id=allotment_id)
                    # Check if this allotment is used in other BOEs (excluding current instance)
                    if not allotment.bill_of_entry.exclude(id=instance.id).exists():
                        allotment.is_boe = False
                        allotment.save()

        # Update nested item details if provided
        if item_details_data is not None:
            # Track IDs of items that should exist after update
            updated_item_ids = []

            for item_data in item_details_data:
                # Get sr_number - handle both object and ID
                sr_number = item_data.get('sr_number')
                if isinstance(sr_number, dict):
                    sr_number_id = sr_number.get('id')
                elif hasattr(sr_number, 'id'):
                    sr_number_id = sr_number.id
                else:
                    sr_number_id = sr_number

                if not sr_number_id:
                    continue

                # Get transaction_type (default to 'D' for DFIA)
                transaction_type = item_data.get('transaction_type', 'D')

                # Check if item has an id - if yes, update it; if no, use update_or_create
                item_id = item_data.get('id')

                # Prepare clean data
                item_data_clean = {k: v for k, v in item_data.items()
                                  if k not in ['id', 'sr_number', 'license_number', 'item_description', 'hs_code']}

                if item_id:
                    # Update existing item
                    try:
                        item_instance = RowDetails.objects.get(id=item_id, bill_of_entry=instance)
                        # Skip frozen rows — they come from ledger and cannot be edited
                        if item_instance.is_frozen:
                            updated_item_ids.append(item_id)
                            continue
                        # Update all fields
                        for key, value in item_data_clean.items():
                            setattr(item_instance, key, value)
                        # Update sr_number separately
                        item_instance.sr_number_id = sr_number_id
                        item_instance.save()
                        updated_item_ids.append(item_id)
                    except RowDetails.DoesNotExist:
                        # If item doesn't exist, use update_or_create to avoid duplicates
                        item_data_clean['sr_number_id'] = sr_number_id
                        item_instance, created = RowDetails.objects.update_or_create(
                            bill_of_entry=instance,
                            sr_number_id=sr_number_id,
                            transaction_type=transaction_type,
                            defaults=item_data_clean
                        )
                        updated_item_ids.append(item_instance.id)
                else:
                    # No ID provided - use update_or_create to handle duplicates
                    # Check if existing row is frozen before overwriting
                    existing = RowDetails.objects.filter(
                        bill_of_entry=instance,
                        sr_number_id=sr_number_id,
                        transaction_type=transaction_type,
                    ).first()
                    if existing and existing.is_frozen:
                        updated_item_ids.append(existing.id)
                        continue
                    item_data_clean['sr_number_id'] = sr_number_id
                    item_instance, created = RowDetails.objects.update_or_create(
                        bill_of_entry=instance,
                        sr_number_id=sr_number_id,
                        transaction_type=transaction_type,
                        defaults=item_data_clean
                    )
                    updated_item_ids.append(item_instance.id)

            # Delete items that were not in the update list
            RowDetails.objects.filter(
                bill_of_entry=instance
            ).exclude(
                id__in=updated_item_ids
            ).delete()

            # Clear cached properties to force recalculation
            if hasattr(instance, 'item_details_cached'):
                delattr(instance, 'item_details_cached')
            if hasattr(instance, 'get_licenses'):
                delattr(instance, 'get_licenses')

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
