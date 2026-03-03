# trade/serializers.py

from rest_framework import serializers

from .models import (
    LicenseTrade, LicenseTradeLine, IncentiveTradeLine, LicenseTradePayment
)


class LicenseTradePaymentSerializer(serializers.ModelSerializer):
    """Serializer for payment settlements"""
    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = LicenseTradePayment
        fields = ('id', 'date', 'amount', 'note')


class LicenseTradeLineSerializer(serializers.ModelSerializer):
    """Serializer for trade line items"""
    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    sr_number_label = serializers.SerializerMethodField()
    computed_amount = serializers.SerializerMethodField()

    def to_internal_value(self, data):
        """Remove empty string fields to prevent overwriting existing values with zeros"""
        # Create a copy to avoid modifying the original data
        data = data.copy() if hasattr(data, 'copy') else dict(data)

        # Extract sr_number ID if it's an object (from frontend HybridSelect)
        if 'sr_number' in data and isinstance(data['sr_number'], dict):
            data['sr_number'] = data['sr_number'].get('id') or data['sr_number'].get('pk')

        # Remove fields with empty strings so they don't override existing values
        fields_to_check = ['qty_kg', 'rate_inr_per_kg', 'cif_fc', 'exc_rate', 'cif_inr', 'fob_inr', 'pct', 'amount_inr']
        for field in fields_to_check:
            if field in data and data[field] == '':
                del data[field]

        return super().to_internal_value(data)

    class Meta:
        model = LicenseTradeLine
        fields = (
            'id', 'sr_number', 'sr_number_label', 'description', 'hsn_code', 'mode',
            'qty_kg', 'rate_inr_per_kg', 'cif_fc', 'exc_rate', 'cif_inr',
            'fob_inr', 'pct', 'amount_inr', 'computed_amount'
        )

    def get_sr_number_label(self, obj):
        """Return license number, SR number, and description"""
        if obj.sr_number:
            # Get license number
            license_number = obj.sr_number.license.license_number if obj.sr_number.license else 'Unknown'

            # Use description if available, otherwise get first item name from ManyToMany
            if obj.sr_number.description:
                item_desc = obj.sr_number.description
            else:
                # Get first item from ManyToMany items field
                first_item = obj.sr_number.items.first()
                item_desc = first_item.name if first_item else 'Unknown'

            return f"{license_number} - SR {obj.sr_number.serial_number}"
        return None

    def get_computed_amount(self, obj):
        """Return computed amount based on mode"""
        return float(obj.compute_amount())


class IncentiveTradeLineSerializer(serializers.ModelSerializer):
    """Serializer for incentive trade line items"""
    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    incentive_license_label = serializers.SerializerMethodField()

    class Meta:
        model = IncentiveTradeLine
        fields = ('id', 'incentive_license', 'incentive_license_label', 'license_value', 'rate_pct', 'amount_inr')

    def get_incentive_license_label(self, obj):
        """Return formatted incentive license label"""
        if obj.incentive_license:
            return f"{obj.incentive_license.license_type} - {obj.incentive_license.license_number}"
        return None


class LicenseTradeSerializer(serializers.ModelSerializer):
    """Nested serializer for LicenseTrade with lines and payments"""
    lines = LicenseTradeLineSerializer(many=True, required=False)
    incentive_lines = IncentiveTradeLineSerializer(many=True, required=False)
    payments = LicenseTradePaymentSerializer(many=True, required=False)

    # Display fields
    from_company_label = serializers.CharField(source='from_company.name', read_only=True)
    to_company_label = serializers.CharField(source='to_company.name', read_only=True)
    boe_label = serializers.CharField(source='boe.boe_number', read_only=True, allow_null=True)
    direction_label = serializers.CharField(source='get_direction_display', read_only=True)
    license_type_label = serializers.CharField(source='get_license_type_display', read_only=True)
    incentive_license = serializers.SerializerMethodField()

    # Computed fields
    paid_or_received = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    due_amount = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)

    def to_internal_value(self, data):
        """Parse JSON strings OR flattened FormData from multipart/form-data"""
        import json
        import re
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"🔍 to_internal_value called. Data keys: {list(data.keys())}")

        # Create a mutable copy of the data.
        # For QueryDict, convert to a plain dict to avoid string-coercion on assignment.
        raw_data = data
        if hasattr(data, 'getlist'):
            data = {key: raw_data.get(key) for key in raw_data.keys()}
        else:
            data = data.copy() if hasattr(data, 'copy') else dict(data)

        # Handle both JSON string format AND flattened FormData format
        for field in ['lines', 'incentive_lines', 'payments']:
            if field in data:
                logger.info(f"🔍 Field '{field}' found. Type: {type(data[field])}, Value: {str(data[field])[:100]}")

                # Format 1: JSON string (from TradeForm)
                if isinstance(data[field], str):
                    try:
                        parsed = json.loads(data[field])
                        data[field] = parsed
                        logger.info(f"✅ Parsed {field} from JSON string: {len(parsed)} items")
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.error(f"❌ Failed to parse {field} as JSON: {str(e)}")
                        pass
                else:
                    logger.info(f"ℹ️  {field} already parsed as {type(data[field])}, length: {len(data[field]) if hasattr(data[field], '__len__') else 'N/A'}")
            else:
                logger.warning(f"⚠️  Field '{field}' NOT in data - checking for flattened format")

        # Format 2: Flattened FormData format (from MasterForm)
        # Check if data has flattened keys like "lines[0].field"
        if hasattr(raw_data, 'keys'):
            nested_fields = {
                'lines': {},
                'incentive_lines': {},
                'payments': {}
            }

            for key in list(raw_data.keys()):
                for field_name in nested_fields.keys():
                    # Match patterns like "lines[0].sr_number" or "lines[0][sr_number]"
                    match = re.match(rf'{field_name}\[(\d+)\][\.\[](.+?)[\]\.]?$', key)
                    if match:
                        index = int(match.group(1))
                        sub_field = match.group(2).replace(']', '').replace('[', '.')

                        if index not in nested_fields[field_name]:
                            nested_fields[field_name][index] = {}

                        nested_fields[field_name][index][sub_field] = raw_data[key]
                        logger.info(f"🔍 Found flattened field: {key} -> {field_name}[{index}].{sub_field}")

            # Convert flattened format to list format
            for field_name, items in nested_fields.items():
                if items:
                    data[field_name] = [items[i] for i in sorted(items.keys())]
                    logger.info(f"✅ Reconstructed {field_name} from flattened format: {len(data[field_name])} items")

        return super().to_internal_value(data)

    def validate(self, data):
        """Validate that at least one line (regular or incentive) is present"""
        import logging
        logger = logging.getLogger(__name__)

        lines = data.get('lines', [])
        incentive_lines = data.get('incentive_lines', [])

        logger.info(f"🔍 VALIDATE: lines type={type(lines)}, length={len(lines) if hasattr(lines, '__len__') else 'N/A'}, value={str(lines)[:200]}")
        logger.info(f"🔍 VALIDATE: incentive_lines type={type(incentive_lines)}, length={len(incentive_lines) if hasattr(incentive_lines, '__len__') else 'N/A'}")
        logger.info(f"🔍 VALIDATE: All data keys: {list(data.keys())}")

        # Check if both are empty
        if not lines and not incentive_lines:
            logger.error(f"❌ VALIDATION FAILED: No lines present! lines={lines}, incentive_lines={incentive_lines}")
            raise serializers.ValidationError({
                "lines": "At least one trade line or incentive line must be defined.",
                "incentive_lines": "At least one trade line or incentive line must be defined."
            })

        logger.info(f"✅ VALIDATION PASSED: lines={len(lines)}, incentive_lines={len(incentive_lines)}")
        return data

    def get_incentive_license(self, obj):
        """Return all license numbers (DFIA and Incentive) comma-separated"""
        license_numbers = set()

        # Get DFIA license numbers from trade lines
        for line in obj.lines.all():
            if line.sr_number and line.sr_number.license:
                license_numbers.add(line.sr_number.license.license_number)

        # Get Incentive license numbers from incentive_lines
        for line in obj.incentive_lines.all():
            if line.incentive_license:
                license_numbers.add(line.incentive_license.license_number)

        return ', '.join(sorted(license_numbers)) if license_numbers else None

    class Meta:
        model = LicenseTrade
        fields = '__all__'

    def to_representation(self, instance):
        """Customize output representation to include nested company and BOE objects"""
        data = super().to_representation(instance)

        # Replace company IDs with nested objects for frontend display
        if instance.from_company:
            data['from_company'] = {
                'id': instance.from_company.id,
                'name': instance.from_company.name,
            }

        if instance.to_company:
            data['to_company'] = {
                'id': instance.to_company.id,
                'name': instance.to_company.name,
            }

        # Replace BOE ID with nested object for frontend display
        if instance.boe:
            data['boe'] = {
                'id': instance.boe.id,
                'bill_of_entry_number': instance.boe.bill_of_entry_number,
            }

        return data

    def create(self, validated_data):
        """Create trade with nested lines and payments"""
        import logging
        logger = logging.getLogger(__name__)

        lines_data = validated_data.pop('lines', [])
        incentive_lines_data = validated_data.pop('incentive_lines', [])
        payments_data = validated_data.pop('payments', [])

        logger.info(f"🔥 CREATE: lines={len(lines_data)}, incentive={len(incentive_lines_data)}, payments={len(payments_data)}")

        # Create trade header
        trade = LicenseTrade.objects.create(**validated_data)

        # Snapshot party details
        trade.snapshot_parties()

        # Create lines (DFIA)
        for line_data in lines_data:
            line_data.pop('id', None)  # Remove temp ID
            LicenseTradeLine.objects.create(trade=trade, **line_data)

        # Create incentive lines (RODTEP/ROSTL/MEIS)
        for line_data in incentive_lines_data:
            line_data.pop('id', None)  # Remove temp ID
            IncentiveTradeLine.objects.create(trade=trade, **line_data)

        # Create payments
        for payment_data in payments_data:
            payment_data.pop('id', None)  # Remove temp ID
            LicenseTradePayment.objects.create(trade=trade, **payment_data)

        # Recompute totals
        trade.recompute_totals()
        trade.refresh_from_db()

        # Update BOE invoice_no if BOE is linked
        if trade.boe and trade.invoice_number:
            trade.boe.invoice_no = trade.invoice_number
            trade.boe.save(update_fields=['invoice_no'])

        return trade

    def update(self, instance, validated_data):
        """Update trade with nested lines and payments"""
        from core.helpers import _sync_nested

        lines_data = validated_data.pop('lines', None)
        incentive_lines_data = validated_data.pop('incentive_lines', None)
        payments_data = validated_data.pop('payments', None)

        # Track old BOE before update to clear invoice_no if BOE changes
        old_boe = instance.boe

        # Update header fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Snapshot party details if companies changed
        instance.snapshot_parties()

        # Sync nested lines if provided (DFIA)
        if lines_data is not None:
            _sync_nested(
                instance,
                LicenseTradeLine,
                lines_data,
                fk_field='trade',
                treat_empty_list_as_delete=False
            )

        # Sync nested incentive lines if provided (RODTEP/ROSTL/MEIS)
        if incentive_lines_data is not None:
            _sync_nested(
                instance,
                IncentiveTradeLine,
                incentive_lines_data,
                fk_field='trade',
                treat_empty_list_as_delete=False
            )

        # Sync nested payments if provided
        if payments_data is not None:
            _sync_nested(
                instance,
                LicenseTradePayment,
                payments_data,
                fk_field='trade',
                treat_empty_list_as_delete=False
            )

        # Recompute totals
        instance.recompute_totals()
        instance.refresh_from_db()

        # Handle BOE invoice_no updates
        # If BOE changed, clear invoice_no from old BOE
        if old_boe and old_boe != instance.boe:
            # Only clear if this trade's invoice is still on the old BOE
            if old_boe.invoice_no == instance.invoice_number:
                old_boe.invoice_no = None
                old_boe.save(update_fields=['invoice_no'])

        # Update new BOE with invoice_no if BOE is linked
        if instance.boe and instance.invoice_number:
            instance.boe.invoice_no = instance.invoice_number
            instance.boe.save(update_fields=['invoice_no'])

        return instance


class TradeLineSimpleSerializer(serializers.ModelSerializer):
    """Simple serializer for trade lines without nested data"""
    sr_number_label = serializers.CharField(source='sr_number.__str__', read_only=True)
    mode_label = serializers.CharField(source='get_mode_display', read_only=True)

    class Meta:
        model = LicenseTradeLine
        fields = '__all__'


# =============================================================================
