# bill_of_entry/serializers.py
from decimal import Decimal, ROUND_HALF_UP
from rest_framework import serializers

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT
from apps.license.services.effective_cif_mode import (
    INDIVIDUAL_ITEM,
    effective_source_row_cif_available,
    resolve_effective_cif_mode,
)


class RowDetailsSerializer(serializers.ModelSerializer):
    """Serializer for BOE row details (nested items) with decimal precision enforcement."""
    # Make id writable so it can be passed during updates
    id = serializers.IntegerField(required=False)

    # Enforce CIF INR to 2 decimal places
    cif_inr = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        coerce_to_string=False,
    )

    # Enforce CIF FC to 2 decimal places
    cif_fc = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        coerce_to_string=False,
    )

    # Enforce Quantity to 3 decimal places
    qty = serializers.DecimalField(
        max_digits=15,
        decimal_places=3,
        coerce_to_string=False,
    )

    license_number = serializers.CharField(source='sr_number.license.license_number', read_only=True)
    license_id = serializers.IntegerField(source='sr_number.license.id', read_only=True)
    item_description = serializers.CharField(source='sr_number.description', read_only=True)
    hs_code = serializers.CharField(source='sr_number.hs_code.hs_code', read_only=True)
    item_serial_number = serializers.IntegerField(source='sr_number.serial_number', read_only=True)
    condition_type = serializers.CharField(source='sr_number.condition_type', read_only=True)
    purchase_status = serializers.SerializerMethodField()
    source_row_id = serializers.IntegerField(source='sr_number_id', read_only=True)
    authoritative_available_cif = serializers.SerializerMethodField()

    def get_authoritative_available_cif(self, obj):
        item = obj.sr_number
        return str(effective_source_row_cif_available(
            licence=item.license,
            item=item,
            legacy_available=lambda: Decimal(str(item.available_value_calculated or 0)),
        ))

    def get_purchase_status(self, obj):
        """Get purchase status code safely"""
        if obj.sr_number and obj.sr_number.license and obj.sr_number.license.purchase_status:
            return obj.sr_number.license.purchase_status.code
        return None

    def validate_cif_inr(self, value):
        """Ensure CIF INR is rounded to 2 decimal places using ROUND_HALF_UP."""
        if value is not None:
            return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return value

    def validate_cif_fc(self, value):
        """Ensure CIF FC is rounded to 2 decimal places using ROUND_HALF_UP."""
        if value is not None:
            return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return value

    def validate_qty(self, value):
        """Ensure Quantity is rounded to 3 decimal places using ROUND_HALF_UP."""
        if value is not None:
            return value.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        return value

    def validate(self, attrs):
        # Planning target metadata belongs to the BOE header.  RowDetails
        # stopped storing these fields in migration 0009; adding them to this
        # nested payload makes Django reject a PDF-imported BOE at save time.
        item = attrs.get('sr_number') or getattr(self.instance, 'sr_number', None)
        requested_cif = attrs.get('cif_fc')
        if (
            item is not None
            and requested_cif is not None
            and resolve_effective_cif_mode(item.license) == INDIVIDUAL_ITEM
        ):
            # This guard is intentionally opt-in: legacy licences retain the
            # historical BOE validation path.  For individual mode, the
            # ceiling is the live ledger balance for this exact source row.
            # An edit gets its currently persisted debit back before comparing.
            ceiling = effective_source_row_cif_available(
                licence=item.license,
                item=item,
                legacy_available=lambda: Decimal(str(item.available_value_calculated or 0)),
            )
            if self.instance is not None:
                ceiling += Decimal(str(self.instance.cif_fc or 0))
            if requested_cif > ceiling:
                raise serializers.ValidationError({
                    'cif_fc': (
                        f'CIF {requested_cif} exceeds the available CIF {ceiling} '
                        f'for import source row {item.pk}.'
                    )
                })
        return attrs

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
            'license_id',
            'item_description',
            'hs_code',
            'item_serial_number',
            'condition_type',
            'purchase_status',
            'source_row_id',
            'authoritative_available_cif',
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
        decimal_places=2,
        read_only=True
    )
    planning_target_item_name = serializers.CharField(source="planning_target_item.name", read_only=True)

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
            'planning_target_item',
            'planning_target_item_name',
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

        # Add allotment information if available
        allotments = instance.allotment.all()
        if allotments:
            data['allotments'] = [
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
        planning_target_item = validated_data.pop("planning_target_item", serializers.empty)
        item_details_data = validated_data.pop('item_details', None)
        allotment_data = validated_data.pop('allotment', None)

        # Update BOE fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if planning_target_item is not serializers.empty:
            instance.planning_mapping_status = "MAPPED_EXPLICIT" if planning_target_item else "UNMAPPED_AMBIGUOUS"
            instance.planning_mapping_source = "USER_SELECTED" if planning_target_item else ""
            instance.save(update_fields=["planning_mapping_status", "planning_mapping_source", "modified_on"])

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
                from apps.allotment.models import AllotmentModel
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
                transaction_type = item_data.get('transaction_type', DEBIT)

                # Check if item has an id - if yes, update it; if no, use update_or_create
                item_id = item_data.get('id')

                # Prepare clean data
                # Nested payloads can include BOE-level planning metadata from
                # an annotated/read representation.  It belongs to the header,
                # not RowDetails; passing it to update_or_create raises a
                # FieldError when a row is created by `sr_number`.
                item_data_clean = {k: v for k, v in item_data.items()
                                  if k not in [
                                      'id', 'sr_number', 'license_number',
                                      'item_description', 'hs_code',
                                      'planning_mapping_status',
                                      'planning_mapping_source',
                                  ]}

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
