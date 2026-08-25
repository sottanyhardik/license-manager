# trade/serializers.py

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from .models import (
    LicenseTrade, LicenseTradeLine, IncentiveTradeLine, LicenseTradePayment, q2
)
from apps.license.services.effective_cif_mode import (
    INDIVIDUAL_ITEM,
    effective_source_row_cif_available,
    resolve_effective_cif_mode,
)


def _payment_total(instance):
    """Return the canonical settlement total without defeating list prefetches.

    ``LicenseTrade.paid_or_received`` deliberately remains the authoritative
    model property for callers that did not load payments.  On the trade list,
    however, the view has already fetched the exact payment rows required by
    the response.  Calling the property there used ``aggregate()`` once (and
    again through ``due_amount``) for every result, which turned a paginated
    list into an N+1 query path.  Summing the same prefetched Decimal values
    preserves the existing q2 rounding and null semantics.
    """
    payments = getattr(instance, '_prefetched_objects_cache', {}).get('payments')
    if payments is None:
        return instance.paid_or_received
    return q2(sum((payment.amount for payment in payments), Decimal('0')))


class PrefetchedPaymentTotalField(serializers.DecimalField):
    """A DecimalField with the legacy representation and prefetch-aware value."""

    def get_attribute(self, instance):
        return _payment_total(instance)


class PrefetchedDueAmountField(serializers.DecimalField):
    """The existing due calculation, without an extra aggregate per trade."""

    def get_attribute(self, instance):
        return q2(instance.total_amount) - q2(_payment_total(instance))


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
    source_row_id = serializers.IntegerField(source='sr_number_id', read_only=True)
    authoritative_available_cif = serializers.SerializerMethodField()

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
            'fob_inr', 'pct', 'amount_inr', 'computed_amount',
            'source_row_id', 'authoritative_available_cif',
        )

    def get_authoritative_available_cif(self, obj):
        item = obj.sr_number
        # The legacy list value is additive display metadata and is already
        # present on the line's selected import row.  Calling the canonical
        # selector for this branch would still build its individual-row audit
        # projection before selecting legacy mode, causing two ledger queries
        # per rendered line.  Individual-CIF mode continues through the
        # canonical source-row calculation below; write validation always does
        # so as well.  This read-only fast path therefore cannot authorise a
        # mutation or alter the null/false legacy calculation.
        if resolve_effective_cif_mode(item.license) != INDIVIDUAL_ITEM:
            return str(Decimal(str(item.available_value or 0)))
        return str(effective_source_row_cif_available(
            licence=item.license,
            item=item,
            # Additive list metadata must not turn the historic trade list
            # into an N+1 ledger calculation.  The legacy branch exposes the
            # already-selected/stored value; authoritative mutation checks
            # below still use the canonical live path when individual mode is
            # explicitly enabled.
            legacy_available=lambda: Decimal(str(item.available_value or 0)),
        ))

    def validate(self, attrs):
        item = attrs.get('sr_number') or getattr(self.instance, 'sr_number', None)
        requested_cif = attrs.get('cif_fc')
        # A paired purchase/sale is one commercial transfer: the counterpart
        # is created atomically by the parent serializer and retains the same
        # negotiated CIF.  It must not be rejected merely because a source
        # row's operational availability has already been consumed.  This is
        # deliberately limited to the explicit paired-create contract;
        # standalone trades continue to use the source-row ceiling below.
        raw_auto_pair = getattr(self.root, 'initial_data', {}).get('auto_create_paired', False)
        auto_pairing = raw_auto_pair is True or str(raw_auto_pair).strip().lower() in {'1', 'true', 'yes', 'on'}
        if (
            item is not None
            and requested_cif is not None
            and resolve_effective_cif_mode(item.license) == INDIVIDUAL_ITEM
            and not auto_pairing
        ):
            ceiling = effective_source_row_cif_available(
                licence=item.license,
                item=item,
                legacy_available=lambda: Decimal(str(item.available_value_calculated or 0)),
            )
            # A persisted line's current value remains available during edit.
            if self.instance is not None:
                ceiling += Decimal(str(self.instance.cif_fc or 0))
            if requested_cif > ceiling:
                raise serializers.ValidationError({
                    'cif_fc': f'CIF exceeds available source-row CIF {ceiling}.',
                })
        return attrs

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
    direction_label = serializers.CharField(source='get_direction_display', read_only=True)
    license_type_label = serializers.CharField(source='get_license_type_display', read_only=True)
    incentive_license = serializers.SerializerMethodField()

    # Computed fields
    paid_or_received = PrefetchedPaymentTotalField(max_digits=20, decimal_places=2, read_only=True)
    due_amount = PrefetchedDueAmountField(max_digits=20, decimal_places=2, read_only=True)

    # Linked trade fields
    auto_create_paired = serializers.BooleanField(write_only=True, required=False, default=False)
    linked_trade_info = serializers.SerializerMethodField(read_only=True)
    counterpart_info = serializers.SerializerMethodField(read_only=True)

    def get_counterpart_info(self, obj):
        counterpart = obj.counterpart
        if not counterpart:
            return None
        return {
            'id': counterpart.id,
            'type': counterpart.direction.lower(),
            'number': counterpart.invoice_number,
            'url': f'/api/trade/trades/{counterpart.id}/',
        }

    def get_linked_trade_info(self, obj):
        lt = obj.linked_trade
        if not lt:
            # ``first()`` issues a query even when the relation was prefetched
            # on several Django versions.  The prefetch retains the model's
            # declared ordering, so selecting its first cached value has the
            # same observable result as the previous call.
            paired_trades = getattr(obj, '_prefetched_objects_cache', {}).get('paired_trades')
            lt = paired_trades[0] if paired_trades else None
            if paired_trades is None:
                lt = obj.paired_trades.first()
        if not lt:
            return None
        return {
            'id': lt.id,
            'direction': lt.direction,
            'direction_label': lt.get_direction_display(),
            'invoice_number': lt.invoice_number,
            'total_amount': str(lt.total_amount),
            'paid_or_received': str(_payment_total(lt)),
            'due_amount': str(q2(lt.total_amount) - q2(_payment_total(lt))),
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
        for field in ['lines', 'incentive_lines', 'payments', 'boes']:
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

        # Replace BOE IDs with nested objects for frontend display
        data['boes'] = [
            {'id': b.id, 'bill_of_entry_number': b.bill_of_entry_number}
            for b in instance.boes.all()
        ]

        data['linked_trade_id'] = instance.linked_trade_id
        data['linked_trade_info'] = self.get_linked_trade_info(instance)

        return data

    @transaction.atomic
    def create(self, validated_data):
        """Create trade with nested lines and payments.

        Wrapped in a transaction so the header + lines + incentive lines + payments
        + BOE invoice_no update + the auto-created paired trade either all commit or
        all roll back. Previously a mid-loop failure left a partial trade with a
        half-computed balance."""
        import logging
        logger = logging.getLogger(__name__)

        lines_data = validated_data.pop('lines', [])
        incentive_lines_data = validated_data.pop('incentive_lines', [])
        payments_data = validated_data.pop('payments', [])
        auto_create_paired = validated_data.pop('auto_create_paired', False)
        # M2M fields can't be passed to .objects.create() (no PK yet) - set them
        # once the trade instance exists.
        boes_data = validated_data.pop('boes', [])

        # A BOE represents the physical quantity when one is attached.  In
        # the approved bypass workflow, however, a SALE line with no BOE is
        # itself final physical consumption and must fit the item's remaining
        # quantity.  Check the complete request cumulatively while holding
        # item locks so two concurrent direct sales cannot both over-consume.
        from collections import defaultdict
        from decimal import Decimal
        from rest_framework.exceptions import ValidationError
        from apps.license.models import LicenseImportItemsModel
        from apps.license.services.balance_calculator import ItemBalanceCalculator
        from apps.trade.models import LicenseTrade

        if validated_data.get('direction') == LicenseTrade.DIR_SALE and not boes_data:
            requested_by_item = defaultdict(lambda: Decimal('0'))
            for line_data in lines_data:
                requested_by_item[line_data['sr_number'].pk] += Decimal(str(line_data.get('qty_kg') or 0))
            for item_id in sorted(requested_by_item):
                item = LicenseImportItemsModel.objects.select_for_update().get(pk=item_id)
                requested = requested_by_item[item_id]
                available = ItemBalanceCalculator.calculate_available_quantity(item)
                if requested > available:
                    raise ValidationError({
                        'lines': (
                            f'SALE quantity {requested} exceeds available quantity '
                            f'{available} for import item {item_id}.'
                        ),
                    })

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

        # Link BOEs (M2M requires the trade to already have a PK)
        trade.boes.set(boes_data)

        # Update linked BOEs' invoice_no/invoice_date if this trade has an invoice
        if trade.invoice_number:
            for boe in trade.boes.all():
                boe.invoice_no = trade.invoice_number
                boe.invoice_date = trade.invoice_date
                boe.save(update_fields=['invoice_no', 'invoice_date'])

        # Legacy form compatibility: route this flag through the same locked,
        # idempotent domain service as the explicit copy endpoints.
        if auto_create_paired:
            from .services.trade_service import copy_purchase_to_sale, copy_sale_to_purchase
            if trade.direction == LicenseTrade.DIR_SALE:
                copy_sale_to_purchase(trade.pk, getattr(self.context.get('request'), 'user', None))
            elif trade.direction == LicenseTrade.DIR_PURCHASE:
                copy_purchase_to_sale(trade.pk, getattr(self.context.get('request'), 'user', None))

        return trade

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update trade with nested lines and payments.

        Wrapped in a transaction so header changes, nested line/payment syncs, the
        recompute, and both old/new BOE invoice_no updates commit atomically."""
        from apps.core.helpers import _sync_nested

        lines_data = validated_data.pop('lines', None)
        incentive_lines_data = validated_data.pop('incentive_lines', None)
        payments_data = validated_data.pop('payments', None)

        # Track old BOEs before update to clear invoice_no from ones that are removed
        old_boe_ids = set(instance.boes.values_list('id', flat=True))

        # M2M fields can't go through setattr - pop and apply separately once the
        # instance is saved. Use a sentinel to distinguish "not provided" (leave
        # existing BOEs untouched) from "explicitly provided as an empty list".
        _BOES_NOT_PROVIDED = object()
        new_boes = validated_data.pop('boes', _BOES_NOT_PROVIDED)

        # Update header fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if new_boes is not _BOES_NOT_PROVIDED:
            instance.boes.set(new_boes)

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
        new_boe_ids = set(instance.boes.values_list('id', flat=True))

        # BOEs removed from this trade: clear invoice_no/invoice_date if this
        # trade's invoice number is still the one stamped on them.
        removed_boe_ids = old_boe_ids - new_boe_ids
        if removed_boe_ids:
            from apps.bill_of_entry.models import BillOfEntryModel
            for boe in BillOfEntryModel.objects.filter(id__in=removed_boe_ids):
                if boe.invoice_no == instance.invoice_number:
                    boe.invoice_no = None
                    boe.invoice_date = None
                    boe.save(update_fields=['invoice_no', 'invoice_date'])

        # Stamp invoice_no/invoice_date on all BOEs currently linked to this trade
        from .services.trade_service import stamp_boe_invoice_from_trade
        for boe in instance.boes.all():
            stamp_boe_invoice_from_trade(instance, boe)

        return instance


class TradeLineSimpleSerializer(serializers.ModelSerializer):
    """Simple serializer for trade lines without nested data"""
    sr_number_label = serializers.CharField(source='sr_number.__str__', read_only=True)
    mode_label = serializers.CharField(source='get_mode_display', read_only=True)

    class Meta:
        model = LicenseTradeLine
        fields = '__all__'


# =============================================================================
