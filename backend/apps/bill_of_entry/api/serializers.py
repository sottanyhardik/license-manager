# bill_of_entry/serializers.py
import logging
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
from django.db import transaction
from django.db.models import ProtectedError
from rest_framework import serializers

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails, genuinely_hidden_boe_ids
from apps.core.constants import DEBIT, DEC_0
from apps.license.services.effective_cif_mode import (
    INDIVIDUAL_ITEM,
    effective_source_row_cif_available,
    resolve_effective_cif_mode,
)

logger = logging.getLogger(__name__)

DEC_CENT = Decimal('0.01')
DEC_MILLI = Decimal('0.001')

# Financial fields of a RowDetails row and the precision the nested serializer
# accepts them at.  A frozen (ledger-imported) row is compared at this precision
# so a client that echoes the row back exactly as it was serialized never trips
# the D3 "frozen rows are immutable" guard.
FROZEN_ROW_FIELD_PRECISION = {
    'cif_fc': DEC_CENT,
    'cif_inr': DEC_CENT,
    'qty': DEC_MILLI,
}


def _item_pk(value):
    """Primary key of a nested `sr_number` value (model instance, dict or id)."""
    if isinstance(value, dict):
        return value.get('id')
    if hasattr(value, 'pk'):
        return value.pk
    return value


def _frozen_row_changes(payload_row: dict, frozen_row: RowDetails) -> list[str]:
    """Field names whose payload value differs from the stored frozen row."""
    changed = []
    sr_number = payload_row.get('sr_number')
    if sr_number is not None and _item_pk(sr_number) != frozen_row.sr_number_id:
        changed.append('sr_number')
    for field, precision in FROZEN_ROW_FIELD_PRECISION.items():
        if field not in payload_row or payload_row[field] is None:
            continue
        # Same rounding as the read path (DRF DecimalField default,
        # ROUND_HALF_EVEN) so an echoed serialization compares equal.
        requested = Decimal(str(payload_row[field])).quantize(precision, rounding=ROUND_HALF_EVEN)
        stored = Decimal(str(getattr(frozen_row, field) or 0)).quantize(precision, rounding=ROUND_HALF_EVEN)
        if requested != stored:
            changed.append(field)
    return changed


def _resolve_payload_target(payload_row: dict, existing_by_id: dict, existing_by_key: dict):
    """The persisted BOE row a nested payload row will write to, mirroring
    `BillOfEntrySerializer.update`: by `id` when it belongs to this BOE, else by
    the (sr_number, DEBIT) upsert key.  None means a brand-new row."""
    row_id = payload_row.get('id')
    if row_id and row_id in existing_by_id:
        return existing_by_id[row_id]
    transaction_type = payload_row.get('transaction_type', DEBIT)
    return existing_by_key.get((_item_pk(payload_row.get('sr_number')), transaction_type))


def _ceiling_scope(item) -> tuple[str, int]:
    """Which persisted rows debit `item`'s live ledger.

    Mirrors the branch in `ItemBalanceCalculator.calculate_item_credit_debit`
    (read-only reuse; the math is not re-derived): an item with no CIF of its
    own is debited licence-wide, otherwise only by rows on that exact item.
    """
    if not item.cif_fc or item.cif_fc == 0:
        return ('licence', item.license_id)
    return ('item', item.pk)


def _row_in_scope(item, scope: tuple[str, int]) -> bool:
    kind, pk = scope
    if kind == 'licence':
        return item.license_id == pk
    return item.pk == pk


def check_individual_item_cif_ceiling(boe, item_rows, *, lock: bool) -> None:
    """INDIVIDUAL_ITEM CIF ceiling for a whole nested `item_details` payload
    (owner decisions D12/D13).

    For every import item X referenced by a writable payload row whose licence
    is in INDIVIDUAL_ITEM mode, the post-write total of this BOE's DEBIT rows in
    X's ledger scope must fit in X's live ledger balance with this BOE's own
    currently-counted debit in that scope added back:

        new_total(scope) <= credit(X) - debit(X) + own_counted(scope)

    * own_counted only includes rows the ledger counts today (DEBIT, not
      frozen, BOE not genuinely hidden).  A row moved to another item/licence
      gets no credit on its new item: its old debit is not in the new scope.
    * Frozen rows are excluded on both sides: they are never written by this
      form (D3) and stay in the ledger unchanged.
    * Multiple payload rows on the same scope are summed.
    * A write that does not increase this BOE's consumption of the scope
      (new_total <= current raw total) never fails, so an unchanged or
      decreased row is accepted even when the item is already over-utilised.

    `lock=True` (inside the save transaction) takes SELECT ... FOR UPDATE on
    the import items (and licence, for licence-wide scopes) before reading the
    ledger, so two concurrent BOE writes on the same item are serialised and the
    second one re-checks against the first one's committed debit.
    """
    from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
    from apps.license.services.balance_calculator import ItemBalanceCalculator

    if not item_rows:
        return

    existing_rows = []
    if boe is not None and boe.pk:
        existing_rows = list(
            RowDetails.objects.filter(bill_of_entry=boe).select_related('sr_number')
        )
    existing_by_id = {row.pk: row for row in existing_rows}
    existing_by_key = {(row.sr_number_id, row.transaction_type): row for row in existing_rows}

    # (payload index, item, cif_fc) for every row the update will actually write.
    writable = []
    for index, payload_row in enumerate(item_rows):
        # Only DEBIT rows debit the ledger; other transaction types are not
        # part of the ceiling.
        if payload_row.get('transaction_type', DEBIT) != DEBIT:
            continue
        target = _resolve_payload_target(payload_row, existing_by_id, existing_by_key)
        if target is not None and (target.is_frozen or target.transaction_type != DEBIT):
            continue
        # The nested update only writes keys present in the payload, so a row
        # that targets an existing row without sr_number/cif_fc keeps the stored
        # value: count it at that stored value (otherwise new_total is
        # understated and the ceiling can be bypassed in a licence-wide scope).
        item_id = _item_pk(payload_row.get('sr_number'))
        if not item_id and target is not None:
            item_id = target.sr_number_id
        cif = payload_row.get('cif_fc')
        if cif is None and target is not None:
            cif = target.cif_fc
        if not item_id or cif is None:
            continue
        writable.append((index, item_id, Decimal(str(cif))))
    if not writable:
        return

    item_ids = sorted({item_id for _, item_id, _ in writable})
    items = {
        item.pk: item
        for item in LicenseImportItemsModel.objects.filter(pk__in=item_ids).select_related('license')
    }
    individual_ids = sorted(
        pk for pk, item in items.items()
        if resolve_effective_cif_mode(item.license) == INDIVIDUAL_ITEM
    )
    if not individual_ids:
        return

    if lock:
        # Licences before items, each in pk order, to avoid lock-order deadlocks.
        licence_ids = sorted({
            items[pk].license_id for pk in individual_ids if _ceiling_scope(items[pk])[0] == 'licence'
        })
        if licence_ids:
            list(LicenseDetailsModel.objects.select_for_update().filter(pk__in=licence_ids).order_by('pk'))
        locked = LicenseImportItemsModel.objects.select_for_update().filter(pk__in=individual_ids).order_by('pk')
        for item in locked:
            # Re-read under the lock; keep the already-loaded licence object.
            item.license = items[item.pk].license
            items[item.pk] = item

    boe_hidden = bool(boe is not None and boe.pk and boe.pk in genuinely_hidden_boe_ids(boe_ids=[boe.pk]))
    old_rows = [
        row for row in existing_rows
        if not row.is_frozen and row.transaction_type == DEBIT
    ]

    errors: dict[int, str] = {}
    for item_pk in individual_ids:
        item = items[item_pk]
        scope = _ceiling_scope(item)
        scoped_new = [
            (index, cif) for index, row_item_id, cif in writable
            if row_item_id in items and _row_in_scope(items[row_item_id], scope)
        ]
        new_total = sum((cif for _, cif in scoped_new), DEC_0)
        old_raw = sum(
            (Decimal(str(row.cif_fc or 0)) for row in old_rows if _row_in_scope(row.sr_number, scope)),
            DEC_0,
        )
        if new_total <= old_raw:
            continue
        own_counted = DEC_0 if boe_hidden else old_raw
        credit, debit = ItemBalanceCalculator.calculate_item_credit_debit(item)
        available = credit - debit + own_counted
        if new_total <= available:
            continue
        shown = max(available, DEC_0)
        prefix = 'Combined CIF' if len(scoped_new) > 1 else 'CIF'
        message = (
            f'{prefix} {new_total} exceeds the available CIF {shown} '
            f'for import source row {item.pk}.'
        )
        for index, _ in scoped_new:
            errors.setdefault(index, message)

    if errors:
        raise serializers.ValidationError({
            'item_details': [
                {'cif_fc': [errors[index]]} if index in errors else {}
                for index in range(len(item_rows))
            ]
        })


def _protected_row_ids(protected_objects, candidate_row_ids) -> list[int]:
    """Ids of the RowDetails in `candidate_row_ids` that `protected_objects`
    (from a ProtectedError) point at through any FK to RowDetails."""
    row_ids: set[int] = set()
    for obj in protected_objects:
        for field in obj._meta.concrete_fields:
            if field.is_relation and field.related_model is RowDetails:
                value = getattr(obj, field.attname)
                if value in candidate_row_ids:
                    row_ids.add(value)
    return sorted(row_ids)


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

    HIDDEN_INVOICE_NO_MESSAGE = (
        'This bill of entry is hidden; its invoice number cannot be changed here. '
        'Restore the bill of entry (restore-boe) first.'
    )

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
        if boe is None or not boe.pk or invoice_no == boe.invoice_no:
            return False
        return boe.pk in genuinely_hidden_boe_ids(boe_ids=[boe.pk])

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

    def _reject_null_date_collision(self, boe_number, boe_date, exclude_pk=None) -> None:
        """D7: a create without `bill_of_entry_date` must not silently overwrite
        (same port) or duplicate (other port) an existing BOE with the same
        number.  Dated duplicates are still rejected by DRF's
        UniqueTogetherValidator before this point.  Raised from `create` (not
        `validate`) so `existing_boe_id` is returned as a plain integer; the
        caller already holds BOE create permission, which implies BOE read."""
        if boe_date is not None:
            return
        existing_qs = BillOfEntryModel.objects.filter(bill_of_entry_number=boe_number)
        if exclude_pk is not None:
            existing_qs = existing_qs.exclude(pk=exclude_pk)
        existing_id = (
            existing_qs
            .order_by('pk').values_list('pk', flat=True).first()
        )
        if existing_id is None:
            return
        exc = serializers.ValidationError({
            'bill_of_entry_date': [
                'Bill of entry date is required: a bill of entry with this number '
                'already exists.'
            ],
        })
        exc.detail['existing_boe_id'] = existing_id
        raise exc

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
        """Create BOE with nested item details"""
        # Atomic (a savepoint under perform_create) so the row locks taken by
        # the CIF ceiling re-check are held until the rows are written.
        with transaction.atomic():
            return self._create(validated_data)

    def _create(self, validated_data):
        item_details_data = validated_data.pop('item_details', [])
        allotment_data = validated_data.pop('allotment', [])

        # Use update_or_create to avoid IntegrityError on the unique_together
        # constraint (bill_of_entry_number, bill_of_entry_date, port).
        boe_number = validated_data.pop('bill_of_entry_number')
        boe_date = validated_data.pop('bill_of_entry_date', None)
        port = validated_data.pop('port', None)
        self._reject_null_date_collision(boe_number, boe_date)
        check_individual_item_cif_ceiling(None, item_details_data, lock=True)
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
        # Atomic (a savepoint under perform_update) so the BOE / item row locks
        # taken by the re-checks below are held until the write is done.
        with transaction.atomic():
            return self._update(instance, validated_data)

    def _update(self, instance, validated_data):
        planning_target_item = validated_data.pop("planning_target_item", serializers.empty)
        item_details_data = validated_data.pop('item_details', None)
        allotment_data = validated_data.pop('allotment', None)

        # D7 on update: an effectively undated BOE must not share its number
        # with another BOE (excluding itself).
        effective_date = validated_data.get('bill_of_entry_date', instance.bill_of_entry_date)
        if effective_date is None:
            self._reject_null_date_collision(
                validated_data.get('bill_of_entry_number', instance.bill_of_entry_number),
                effective_date,
                exclude_pk=instance.pk,
            )

        if 'invoice_no' in validated_data and validated_data['invoice_no'] != instance.invoice_no:
            # D1 re-check under the BOE row lock: the hidden state may have
            # changed between validation and save.
            locked = BillOfEntryModel.objects.select_for_update().only('pk', 'invoice_no').get(pk=instance.pk)
            if self._invoice_no_change_blocked(locked, validated_data['invoice_no']):
                raise serializers.ValidationError({'invoice_no': self.HIDDEN_INVOICE_NO_MESSAGE})

        if item_details_data:
            check_individual_item_cif_ceiling(instance, item_details_data, lock=True)

        # Update BOE fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if planning_target_item is not serializers.empty:
            # D14: persist the FK itself (it used to be popped and dropped,
            # leaving MAPPED_EXPLICIT with a NULL target).
            instance.planning_target_item = planning_target_item
            instance.planning_mapping_status = "MAPPED_EXPLICIT" if planning_target_item else "UNMAPPED_AMBIGUOUS"
            instance.planning_mapping_source = "USER_SELECTED" if planning_target_item else ""
            instance.save(update_fields=[
                "planning_target_item", "planning_mapping_status", "planning_mapping_source", "modified_on",
            ])

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

            # Delete items that were not in the update list.  Rows still
            # referenced by a PROTECT FK (e.g. reconciliation allocations)
            # raise ProtectedError; surface that as a 400 instead of a 500.
            # The savepoint keeps the outer perform_update transaction usable;
            # raising rolls the whole update back.
            # D3: frozen (ledger-imported) rows are never deleted by a form
            # update, even when the client leaves them out of the payload.
            orphan_rows = RowDetails.objects.filter(
                bill_of_entry=instance
            ).exclude(
                id__in=updated_item_ids
            ).exclude(
                is_frozen=True
            )
            try:
                with transaction.atomic():
                    orphan_rows.delete()
            except ProtectedError as exc:
                orphan_ids = set(orphan_rows.values_list('id', flat=True))
                protected_row_ids = _protected_row_ids(exc.protected_objects, orphan_ids) or sorted(orphan_ids)
                # Model labels are logged, not returned, so internal app/model
                # names are not exposed to API clients.
                logger.info(
                    "BOE %s update blocked: rows %s referenced by %s",
                    instance.pk, protected_row_ids,
                    sorted({obj._meta.label for obj in exc.protected_objects}),
                )
                raise serializers.ValidationError({
                    'item_details': (
                        "Cannot remove item row(s) "
                        f"{', '.join(str(row_id) for row_id in protected_row_ids)}: "
                        "still referenced by existing reconciliation/allocation records. "
                        "Resolve those references first."
                    )
                }) from exc

            # Clear cached properties to force recalculation
            if hasattr(instance, 'item_details_cached'):
                delattr(instance, 'item_details_cached')
            if hasattr(instance, 'get_licenses'):
                delattr(instance, 'get_licenses')

        return instance
