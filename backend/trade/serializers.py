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
    condition_type = serializers.CharField(source='sr_number.condition_type', read_only=True, allow_blank=True, default='')
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
            'id', 'sr_number', 'sr_number_label', 'condition_type', 'description', 'hsn_code', 'mode',
            'qty_kg', 'rate_inr_per_kg', 'cif_fc', 'exc_rate', 'cif_inr',
            'fob_inr', 'pct', 'amount_inr', 'computed_amount'
        )

    def get_sr_number_label(self, obj):
        """Return license number and SR number, using prefetch cache where possible."""
        if obj.sr_number:
            license_number = obj.sr_number.license.license_number if obj.sr_number.license else 'Unknown'
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

    # Linked trade fields
    auto_create_paired = serializers.BooleanField(write_only=True, required=False, default=False)
    linked_trade_info = serializers.SerializerMethodField(read_only=True)

    def get_linked_trade_info(self, obj):
        lt = obj.linked_trade
        if not lt:
            lt = obj.paired_trades.first()
        if not lt:
            return None
        return {
            'id': lt.id,
            'direction': lt.direction,
            'direction_label': lt.get_direction_display(),
            'invoice_number': lt.invoice_number,
            'total_amount': str(lt.total_amount),
            'paid_or_received': str(lt.paid_or_received),
            'due_amount': str(lt.due_amount),
        }

    def to_internal_value(self, data):
        """Parse JSON strings OR flattened FormData from multipart/form-data"""
        import json
        import re
        import logging
        logger = logging.getLogger(__name__)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("to_internal_value called. Data keys: %s", list(data.keys()))

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
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Field '%s' found. Type: %s", field, type(data[field]).__name__)

                # Format 1: JSON string (from TradeForm)
                if isinstance(data[field], str):
                    try:
                        parsed = json.loads(data[field])
                        data[field] = parsed
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("Parsed %s from JSON string: %d items", field, len(parsed))
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.error("Failed to parse %s as JSON: %s", field, str(e))
                        raise serializers.ValidationError({
                            field: f"Invalid JSON format: {str(e)}"
                        })
                elif logger.isEnabledFor(logging.DEBUG):
                    logger.debug("%s already parsed as %s", field, type(data[field]).__name__)
            elif logger.isEnabledFor(logging.DEBUG):
                logger.debug("Field '%s' NOT in data - checking for flattened format", field)

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
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("Found flattened field: %s -> %s[%d].%s", key, field_name, index, sub_field)

            # Convert flattened format to list format
            for field_name, items in nested_fields.items():
                if items:
                    data[field_name] = [items[i] for i in sorted(items.keys())]
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("Reconstructed %s from flattened format: %d items", field_name, len(data[field_name]))

        return super().to_internal_value(data)

    def validate(self, data):
        """Validate that at least one line (regular or incentive) is present"""
        import logging
        logger = logging.getLogger(__name__)

        lines = data.get('lines', [])
        incentive_lines = data.get('incentive_lines', [])

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("VALIDATE: lines type=%s, length=%s", type(lines).__name__, len(lines) if hasattr(lines, '__len__') else 'N/A')
            logger.debug("VALIDATE: incentive_lines type=%s, length=%s", type(incentive_lines).__name__, len(incentive_lines) if hasattr(incentive_lines, '__len__') else 'N/A')
            logger.debug("VALIDATE: All data keys: %s", list(data.keys()))

        # Check if both are empty
        if not lines and not incentive_lines:
            logger.error("VALIDATION FAILED: No lines present")
            raise serializers.ValidationError({
                "lines": "At least one trade line or incentive line must be defined.",
                "incentive_lines": "At least one trade line or incentive line must be defined."
            })

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("VALIDATION PASSED: lines=%d, incentive_lines=%d", len(lines), len(incentive_lines))
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

        data['linked_trade_id'] = instance.linked_trade_id
        data['linked_trade_info'] = self.get_linked_trade_info(instance)

        return data

    def create(self, validated_data):
        """Create trade with nested lines and payments"""
        import logging
        logger = logging.getLogger(__name__)

        lines_data = validated_data.pop('lines', [])
        incentive_lines_data = validated_data.pop('incentive_lines', [])
        payments_data = validated_data.pop('payments', [])
        auto_create_paired = validated_data.pop('auto_create_paired', False)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("CREATE: lines=%d, incentive=%d, payments=%d", len(lines_data), len(incentive_lines_data), len(payments_data))

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

        # Auto-create the paired counterpart trade (Sale↔Purchase)
        if auto_create_paired and trade.direction in ('PURCHASE', 'SALE', 'COMMISSION_PURCHASE', 'COMMISSION_SALE'):
            from trade.models import get_next_invoice_number
            direction_map = {
                'PURCHASE': 'SALE', 'SALE': 'PURCHASE',
                'COMMISSION_PURCHASE': 'COMMISSION_SALE', 'COMMISSION_SALE': 'COMMISSION_PURCHASE',
            }
            paired_direction = direction_map[trade.direction]
            paired_from = trade.to_company
            paired_to = trade.from_company

            paired_invoice = get_next_invoice_number(
                direction=paired_direction,
                company_name=paired_from.name if paired_from else '',
                invoice_date=trade.invoice_date,
            )

            paired_trade = LicenseTrade.objects.create(
                direction=paired_direction,
                license_type=trade.license_type,
                incentive_license=trade.incentive_license,
                boe=trade.boe,
                from_company=paired_from,
                to_company=paired_to,
                invoice_number=paired_invoice,
                invoice_date=trade.invoice_date,
                remarks=trade.remarks,
                linked_trade=trade,
                created_by=trade.created_by,
            )
            paired_trade.snapshot_parties()

            for line in trade.lines.all():
                LicenseTradeLine.objects.create(
                    trade=paired_trade,
                    sr_number=line.sr_number,
                    description=line.description,
                    hsn_code=line.hsn_code,
                    mode=line.mode,
                    qty_kg=line.qty_kg,
                    rate_inr_per_kg=line.rate_inr_per_kg,
                    cif_fc=line.cif_fc,
                    exc_rate=line.exc_rate,
                    cif_inr=line.cif_inr,
                    fob_inr=line.fob_inr,
                    pct=line.pct,
                    amount_inr=line.amount_inr,
                )

            for line in trade.incentive_lines.all():
                IncentiveTradeLine.objects.create(
                    trade=paired_trade,
                    incentive_license=line.incentive_license,
                    license_value=line.license_value,
                    rate_pct=line.rate_pct,
                    amount_inr=line.amount_inr,
                )

            paired_trade.recompute_totals()
            paired_trade.refresh_from_db()

            # Link primary trade back to the paired trade
            LicenseTrade.objects.filter(pk=trade.pk).update(linked_trade=paired_trade)
            trade.refresh_from_db()

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
