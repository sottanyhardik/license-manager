# bill_of_entry/serializers.py
import logging
from decimal import Decimal, ROUND_HALF_UP
from rest_framework import serializers

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.bill_of_entry.services import boe_service
# Re-exported: the write-path guards moved to the service layer (ADR-003);
# existing imports of these names from this module keep working.
from apps.bill_of_entry.services.boe_service import (  # noqa: F401
    DEC_CENT,
    DEC_MILLI,
    FROZEN_ROW_FIELD_PRECISION,
    _ceiling_scope,
    _frozen_row_changes,
    _item_pk,
    _protected_row_ids,
    _resolve_payload_target,
    _row_in_scope,
    check_individual_item_cif_ceiling,
)
from apps.core.constants import DEBIT
from apps.license.services.effective_cif_mode import (
    INDIVIDUAL_ITEM,
    effective_source_row_cif_available,
    resolve_effective_cif_mode,
)

logger = logging.getLogger(__name__)



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
        if self.parent is not None:
            # Nested under BillOfEntrySerializer.item_details: the child has no
            # instance, so it cannot add back the row's own persisted debit.
            # The parent checks the whole payload instead (D12/D13,
            # `check_individual_item_cif_ceiling`).
            return attrs
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

    HIDDEN_INVOICE_NO_MESSAGE = boe_service.HIDDEN_INVOICE_NO_MESSAGE

    # ------------------------------------------------------------------ #
    # Validation (owner decisions D1, D3, D12/D13, D14)
    # ------------------------------------------------------------------ #
    def validate_planning_target_item(self, value):
        """D14: an explicit planning target must be an active item name.  The
        currently stored target is accepted even if it was deactivated later,
        so re-sending an unchanged form never fails."""
        if value is None:
            return value
        current_id = getattr(self.instance, 'planning_target_item_id', None)
        if value.pk != current_id and not getattr(value, 'is_active', True):
            raise serializers.ValidationError('Planning target item is inactive.')
        return value

    def validate_boe_pdf_copy(self, value):
        """Fresh uploads get the same content/size checks as parse-pdf.
        None / an unchanged stored file (not an UploadedFile) passes."""
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.core.files.uploadedfile import UploadedFile
        from apps.bill_of_entry.services.boe_documents import validate_boe_pdf

        if isinstance(value, UploadedFile):
            try:
                validate_boe_pdf(value)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.messages) from exc
        return value

    def _invoice_no_change_blocked(self, boe, invoice_no) -> bool:
        """D1: True when `invoice_no` would change a genuinely hidden BOE."""
        return boe_service.invoice_no_change_blocked(boe, invoice_no)

    def _validate_frozen_rows(self, item_rows) -> None:
        """D3: a nested payload may echo a frozen (ledger) row back, but must not
        change it.  Changes used to be dropped silently; they are now a 400
        naming the row, so the client learns its edit was not applied."""
        if self.instance is None or not self.instance.pk:
            return
        frozen_rows = list(RowDetails.objects.filter(bill_of_entry=self.instance, is_frozen=True))
        if not frozen_rows:
            return
        frozen_by_id = {row.pk: row for row in frozen_rows}
        frozen_by_key = {(row.sr_number_id, row.transaction_type): row for row in frozen_rows}
        all_ids = set(
            RowDetails.objects.filter(bill_of_entry=self.instance).values_list('pk', flat=True)
        )
        errors = {}
        for index, payload_row in enumerate(item_rows):
            row_id = payload_row.get('id')
            if row_id and row_id in all_ids:
                frozen_row = frozen_by_id.get(row_id)
            else:
                frozen_row = frozen_by_key.get((_item_pk(payload_row.get('sr_number')), DEBIT))
            if frozen_row is None:
                continue
            changed = _frozen_row_changes(payload_row, frozen_row)
            if changed:
                errors[index] = (
                    f'Row {frozen_row.pk} is frozen (ledger-imported) and cannot be modified '
                    f'({", ".join(changed)}).'
                )
        if errors:
            raise serializers.ValidationError({
                'item_details': [
                    {'non_field_errors': [errors[index]]} if index in errors else {}
                    for index in range(len(item_rows))
                ]
            })

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if 'invoice_no' in attrs and self._invoice_no_change_blocked(self.instance, attrs['invoice_no']):
            raise serializers.ValidationError({'invoice_no': self.HIDDEN_INVOICE_NO_MESSAGE})
        item_rows = attrs.get('item_details')
        if item_rows:
            self._validate_frozen_rows(item_rows)
            # Early, unlocked feedback; re-checked under row locks in save.
            check_individual_item_cif_ceiling(self.instance, item_rows, lock=False)
        return attrs

    @staticmethod
    def _seed_totals_from_prefetch(instance):
        """List view: derive the per-BOE totals from the prefetched rows.

        `get_total_inr/fc/quantity` are cached_properties that each run a
        SUM() query over the BOE's rows (3 queries per BOE).  Decimal columns
        sum exactly, so summing the already-loaded rows (same default-manager
        row set, NULLs ignored like SQL SUM, same quantize) is identical.
        """
        from apps.bill_of_entry.models import DEC_0, DEC_000

        rows = list(instance.item_details.all())

        def _total(attr, default):
            vals = [getattr(r, attr) for r in rows if getattr(r, attr) is not None]
            total = sum(vals, Decimal(0)) if vals else default
            return total.quantize(default)

        instance.__dict__.setdefault('get_total_inr', _total('cif_inr', DEC_0))
        instance.__dict__.setdefault('get_total_fc', _total('cif_fc', DEC_0))
        instance.__dict__.setdefault('get_total_quantity', _total('qty', DEC_000))

    def to_representation(self, instance):
        request = self.context.get('request')
        view = getattr(request, 'parser_context', {}).get('view') if request is not None else None
        if (
            getattr(view, 'action', None) == 'list'
            and 'item_details' in getattr(instance, '_prefetched_objects_cache', {})
        ):
            self._seed_totals_from_prefetch(instance)
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
        """Create BOE with nested item details (orchestration: boe_service)."""
        item_rows = validated_data.pop('item_details', [])
        allotments = validated_data.pop('allotment', [])
        return boe_service.save_boe_with_rows(
            validated_data=validated_data, item_rows=item_rows, allotments=allotments,
        )

    def update(self, instance, validated_data):
        """Update BOE with nested item details (orchestration: boe_service)."""
        item_rows = validated_data.pop('item_details', None)
        allotments = validated_data.pop('allotment', None)
        return boe_service.save_boe_with_rows(
            instance=instance, validated_data=validated_data,
            item_rows=item_rows, allotments=allotments,
        )
