# license/serializers.py
from datetime import date, datetime, time
from typing import Any, Dict, Iterable

from rest_framework import serializers

from apps.core.models import ItemNameModel, ProductDescriptionModel, SchemeCode, NotificationNumber
from apps.core.serializers import HSCodeSerializer, SionNormClassNestedSerializer
from apps.core.serializers.fields import IndianDateField
from apps.license.serializers._license_write import LicenseWriteMixin  # write-path mixin
from apps.license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseDocumentModel,
    LicenseTransferModel,
    LicensePurchase,
    IncentiveLicense,
    LicenseBalance,
    LicenseFlags,
    LicenseNotes,
    LicenseOwnership,
    LicenseItemPlan,
)


def _nested_item_id(item: Dict[str, Any]) -> Any:
    """Best-effort int `id` from a nested `export_license`/`import_license`
    row dict, or `None` if absent/blank/non-numeric. Used to tell an
    existing child row (already validated when it was first created) apart
    from a genuinely new one in `LicenseDetailsSerializer.validate()`."""
    raw = item.get('id')
    if raw in (None, ''):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _safe_iso(val: Any) -> Any:
    if isinstance(val, datetime):
        try:
            return val.isoformat()
        except Exception:
            return str(val)
    if isinstance(val, date):
        return val.isoformat()
    return val


class SafeDateTimeField(serializers.DateTimeField):
    """
    DateTimeField that tolerates receiving a datetime.date (no time).
    It will coerce date -> datetime at midnight (naive) before the normal representation logic.
    This prevents `.utcoffset()` AttributeError when upstream code passes a date.
    """

    def to_representation(self, value):
        # If a plain date (not a datetime), convert to datetime at midnight
        if isinstance(value, date) and not isinstance(value, datetime):
            try:
                value = datetime.combine(value, time())

                # If this field expects timezone-aware datetimes and settings.USE_TZ is True,
                # DRF will handle conversion downstream where appropriate.
            except Exception:
                # fallback: use string representation to avoid crashing
                return str(value)
        return super().to_representation(value)


class PlanningOptionSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for planning options returned in import item details.
    Used by LicenseImportItemSerializer.planning_options to display all plan lines
    for a given import item without fetching the full LicenseItemPlanSerializer.
    """
    plan_line_id = serializers.IntegerField(source='id', read_only=True)
    item_name = serializers.CharField(source='item_name.name', read_only=True, allow_null=True)
    planned_quantity = serializers.DecimalField(max_digits=15, decimal_places=3, read_only=True)
    remaining_quantity = serializers.DecimalField(max_digits=15, decimal_places=3, read_only=True)
    planned_cif_fc = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    remaining_cif_fc = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = LicenseItemPlan
        fields = [
            'plan_line_id', 'item_name', 'planned_quantity', 'remaining_quantity',
            'planned_cif_fc', 'remaining_cif_fc'
        ]


class LicenseExportItemSerializer(serializers.ModelSerializer):
    norm_class_detail = SionNormClassNestedSerializer(source='norm_class', read_only=True)
    norm_class_label = serializers.SerializerMethodField()
    item_label = serializers.SerializerMethodField()
    unit = serializers.CharField(required=False, allow_blank=True, default='kg')

    class Meta:
        model = LicenseExportItemModel
        fields = ['id', 'license', 'description', 'item', 'norm_class', 'duty_type', 'net_quantity',
                  'old_quantity', 'unit', 'fob_fc', 'fob_inr', 'fob_exchange_rate', 'currency',
                  'value_addition', 'cif_fc', 'cif_inr',
                  'norm_class_detail', 'norm_class_label', 'item_label']

    def get_norm_class_label(self, obj):
        if obj.norm_class:
            return f"{obj.norm_class.norm_class} - {obj.norm_class.description}"
        return None

    def get_item_label(self, obj):
        if obj.item:
            return obj.item.name
        return None

    def validate_unit(self, value):
        """Ensure unit has a default value if not provided or empty"""
        if not value or value.strip() == '':
            return 'kg'  # Default unit
        return value

    def create(self, validated_data):
        # Ensure unit has default if not provided
        if 'unit' not in validated_data or not validated_data.get('unit'):
            validated_data['unit'] = 'kg'
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Ensure unit has default if not provided
        if 'unit' not in validated_data or not validated_data.get('unit'):
            validated_data['unit'] = 'kg'
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Add norm_class nested data for display
        if instance.norm_class:
            representation['norm_class_detail'] = {
                'id': instance.norm_class.id,
                'norm_class': instance.norm_class.norm_class,
                'description': instance.norm_class.description
            }
        return representation


class LicenseImportItemSerializer(serializers.ModelSerializer):
    @staticmethod
    def _cached_float(obj, key: str, calculator) -> float:
        """Run *calculator(obj)*, cache the result on the instance, return it as float."""
        if hasattr(obj, key):
            return getattr(obj, key)
        try:
            result = calculator(obj)
            value = float(result) if result is not None else 0.0
        except Exception:
            value = 0.0
        setattr(obj, key, value)
        return value

    items = serializers.PrimaryKeyRelatedField(many=True, queryset=ItemNameModel.objects.all(), required=False)
    items_detail = serializers.SerializerMethodField(read_only=True)
    license_number = serializers.CharField(source="license.license_number", read_only=True, allow_null=True)
    license_date = IndianDateField(source="license.license_date", read_only=True, allow_null=True)
    license_expiry_date = IndianDateField(source="license.license_expiry_date", read_only=True, allow_null=True)
    notification_number = serializers.SlugRelatedField(source="license.notification_number", slug_field="code", read_only=True)
    exporter_name = serializers.CharField(source="license.exporter.name", read_only=True, allow_null=True)
    notes = serializers.CharField(source="license.balance_report_notes", read_only=True, allow_null=True, allow_blank=True)
    hs_code_detail = HSCodeSerializer(source='hs_code', read_only=True)
    hs_code_label = serializers.SerializerMethodField()

    # Calculate at runtime instead of reading from database
    available_quantity = serializers.SerializerMethodField(read_only=True)
    available_value = serializers.SerializerMethodField(read_only=True)
    debited_quantity = serializers.SerializerMethodField(read_only=True)
    debited_value = serializers.SerializerMethodField(read_only=True)
    allotted_quantity = serializers.SerializerMethodField(read_only=True)
    allotted_value = serializers.SerializerMethodField(read_only=True)

    # Informational only — reuses the Planning module's own calculation
    # (`plan_reporting.plan_map_for_import_items`); never feeds into
    # Available Quantity (see that field's docstring in
    # `apps.core.scripts.calculate_balance.calculate_available_quantity`).
    planned_quantity = serializers.SerializerMethodField(read_only=True)

    balance_cif_fc = serializers.SerializerMethodField(read_only=True)

    # Sum of SALE trade lines for this import item where the parent trade has
    # NO BOE attached.  These amounts debit the licence balance without a
    # corresponding BOE, making the double-count visible in the UI.
    billed_no_boe = serializers.SerializerMethodField(read_only=True)

    # Planning options for this import item — all LicenseItemPlan rows split across
    # this item, each with its own remaining availability after allocations.
    planning_options = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = LicenseImportItemsModel
        fields = ['id', 'serial_number', 'license', 'hs_code', 'items', 'items_detail', 'description', 'quantity',
                  'old_quantity', 'unit', 'cif_fc', 'cif_inr', 'available_quantity', 'available_value',
                  'allotted_quantity', 'allotted_value', 'debited_quantity', 'debited_value', 'planned_quantity',
                  'license_number', 'license_date', 'license_expiry_date',
                  'notification_number', 'exporter_name', 'notes', 'hs_code_detail', 'hs_code_label', 'balance_cif_fc',
                  'is_restricted', 'condition_type', 'billed_no_boe', 'planning_options']
        # Allow partial updates and skip unique validation during deserialization
        # The update logic in the parent serializer handles uniqueness properly
        extra_kwargs = {
            'license': {'required': False},
            'serial_number': {'required': False},
            'balance_cif_fc': {'read_only': True}
        }

    def get_items_detail(self, obj):
        """
        Return detailed information about items including name, restriction percentage, and sion_norm_class.
        Similar to item pivot report display.
        """
        items_data = []
        for item in obj.items.all():
            item_info = {
                'id': item.id,
                'name': item.name,
                'is_active': item.is_active,
            }
            # Add sion_norm_class information if available
            if item.sion_norm_class:
                item_info['sion_norm_class'] = {
                    'id': item.sion_norm_class.id,
                    'norm_class': item.sion_norm_class.norm_class,
                    'description': item.sion_norm_class.description
                }
            else:
                item_info['sion_norm_class'] = None

            # Add restriction information if available
            if item.restriction_percentage and item.restriction_percentage > 0:
                item_info['restriction_percentage'] = float(item.restriction_percentage)
            else:
                item_info['restriction_percentage'] = None

            items_data.append(item_info)

        return items_data

    def get_hs_code_label(self, obj):
        if obj.hs_code:
            return f"{obj.hs_code.hs_code}"
        return None

    def get_available_quantity(self, obj):
        # Stored field is kept in sync by update_balance_values / the bulk
        # serializer flow; reading it avoids N round-trips per list response.
        return float(obj.available_quantity or 0)

    def get_available_value(self, obj):
        """
        Return the LIVE available value (same formula as
        `LicenseImportItemsModel.available_value_calculated` — see that
        property's docstring), not the stored `available_value` column.

        The stored column is only refreshed by `_update_all_import_items_
        available_value` on a save of this licence/BOE/allotment/item, so it
        can go stale between saves (e.g. after a licence's Balance CIF
        formula itself changes) — this is exactly the "Balance CIF is
        wrong on the Allotment License Selection screen" bug class this
        fixes. List callers should batch a `{item_id: Decimal}` map once via
        `condition_pool.available_value_bulk_map` and pass it in as
        `self.context['available_value_map']` — mirrors the `plan_map`
        pattern in `get_planned_quantity` above. Falls back to the live
        per-item property when no batch map is supplied (standalone usage),
        never to the stale stored column.
        """
        value_map = self.context.get('available_value_map')
        if value_map is not None:
            value = value_map.get(obj.id)
            return float(value) if value is not None else 0.0
        return float(obj.available_value_calculated or 0)

    # All balance read-outs use the stored fields (kept in sync by
    # update_balance_values + the bulk serializer flow). Reading from the
    # DB column is O(1) and avoids per-item SUM aggregations on every list
    # / detail response. Stored values are recomputed any time a BOE,
    # allotment, trade line, or licence item is saved.
    def get_debited_quantity(self, obj):
        return float(obj.debited_quantity or 0)

    def get_debited_value(self, obj):
        return float(obj.debited_value or 0)

    def get_allotted_quantity(self, obj):
        return float(obj.allotted_quantity or 0)

    def get_allotted_value(self, obj):
        return float(obj.allotted_value or 0)

    def get_planned_quantity(self, obj):
        """
        Reuses `plan_reporting.plan_map_for_import_items` — never a second
        planning calculation. `LicenseDetailsSerializer.to_representation`
        batches this ONCE for every import item on the licence (see
        `self.context['plan_map']`); a bare `LicenseImportItemSerializer`
        used standalone falls back to a single-item call so behaviour is
        unchanged outside the licence-detail response.
        """
        plan_map = self.context.get('plan_map')
        if plan_map is None:
            from apps.license.services.plan_reporting import plan_map_for_import_items
            plan_map = plan_map_for_import_items([obj.id])
        entry = plan_map.get(obj.id)
        return float(entry['total_planned_quantity']) if entry else 0.0

    def get_billed_no_boe(self, obj):
        """
        Total CIF from SALE trade lines for this import item where the parent
        trade has no BOE attached (trade.boes is empty).

        These amounts are counted in the licence balance calculation as trade
        debits but have no linked BOE, which can cause apparent double-counting
        when a separate BOE also debits the same item.  Surfacing this value in
        the UI lets operators spot and fix the missing BOE link.

        List callers should batch a `{item_id: Decimal}` map once via
        `item_usage.billed_no_boe_bulk_map` and pass it in as
        `self.context['billed_no_boe_map']` — same pattern as
        `get_available_value`'s `available_value_map` / `get_planned_
        quantity`'s `plan_map` — so a page of N items on M different
        licences issues one query instead of N. Falls back to the live
        per-item aggregate when no batch map is supplied (standalone usage).
        """
        billed_no_boe_map = self.context.get('billed_no_boe_map')
        if billed_no_boe_map is not None:
            return float(billed_no_boe_map.get(obj.id) or 0)
        try:
            from apps.trade.models import LicenseTradeLine
            from django.db.models import Sum, DecimalField
            from django.db.models.functions import Coalesce
            from django.db.models import Value
            from decimal import Decimal

            total = LicenseTradeLine.objects.filter(
                sr_number=obj,
                trade__direction='SALE',
                trade__boes__isnull=True,       # no BOE attached to this trade
            ).aggregate(
                t=Coalesce(Sum('cif_fc'), Value(Decimal('0')), output_field=DecimalField())
            )['t']
            return float(total or 0)
        except Exception:
            return 0.0

    def get_balance_cif_fc(self, obj):
        """
        ITEM-LEVEL available CIF FC. Under the new condition_type model the
        per-item balance is the same value as `available_value` — see
        `get_available_value`'s docstring for why this reads the LIVE value
        (via the same batched `available_value_map` context key) rather than
        the stale-prone stored `available_value` column.
        """
        value_map = self.context.get('available_value_map')
        if value_map is not None:
            value = value_map.get(obj.id)
            return float(value) if value is not None else 0.0
        return float(obj.available_value_calculated or 0)

    def get_planning_options(self, obj):
        """
        Return all LicenseItemPlan rows for this import item, formatted with the
        essential planning fields needed by the frontend to display planning options
        and enforce per-plan-line allocation caps.

        The related LicenseItemPlan objects are loaded via prefetch_related in the view
        (same pattern as `items`, `items_detail`, etc.), so this is O(1) per item.
        Falls back to a fresh query if no prefetch is present (e.g., standalone usage).
        """
        # utilization_plans is the related_name on LicenseItemPlan.import_item
        plans = obj.utilization_plans.all()
        serializer = PlanningOptionSerializer(plans, many=True)
        return serializer.data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Add hs_code nested data for display
        if instance.hs_code:
            representation['hs_code_detail'] = {
                'id': instance.hs_code.id,
                'hs_code': instance.hs_code.hs_code,
                'product_description': instance.hs_code.product_description
            }
        return representation


class LicenseDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LicenseDocumentModel
        fields = "__all__"


class LicenseTransferSerializer(serializers.ModelSerializer):
    transfer_date = IndianDateField(required=False, allow_null=True)
    transfer_initiation_date = serializers.DateTimeField(required=False, allow_null=True)
    transfer_acceptance_date = serializers.DateTimeField(required=False, allow_null=True)
    cbic_response_date = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = LicenseTransferModel
        fields = "__all__"


class LicensePurchaseSerializer(serializers.ModelSerializer):
    invoice_date = IndianDateField(required=False, allow_null=True)

    class Meta:
        model = LicensePurchase
        fields = "__all__"


class LicenseDetailsSerializer(LicenseWriteMixin, serializers.ModelSerializer):
    # Explicit DateFields for model.DateField columns
    license_date = IndianDateField(required=False, allow_null=True)
    license_expiry_date = IndianDateField(required=False, allow_null=True)
    registration_date = IndianDateField(required=False, allow_null=True)

    # FK lookups exposed as their string code (preserves the pre-FK API contract).
    scheme_code = serializers.SlugRelatedField(
        slug_field="code",
        queryset=SchemeCode.objects.all(),
        allow_null=True,
        required=False,
    )
    notification_number = serializers.SlugRelatedField(
        slug_field="code",
        queryset=NotificationNumber.objects.all(),
        allow_null=True,
        required=False,
    )

    # Fields that moved to OneToOne sub-tables after the 4-table split.
    # Declared here explicitly because they're no longer on LicenseDetailsModel
    # (fields="__all__" wouldn't pick them up). Read via the back-compat @property
    # accessors on the parent. Write paths route to the sub-table in `update()`
    # (see method override below).
    ledger_date = IndianDateField(required=False, allow_null=True)
    balance_cif = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    is_active = serializers.BooleanField(required=False)
    is_audit = serializers.BooleanField(required=False)
    is_mnm = serializers.BooleanField(required=False)
    is_not_registered = serializers.BooleanField(required=False)
    is_null = serializers.BooleanField(required=False)
    is_au = serializers.BooleanField(required=False)
    is_incomplete = serializers.BooleanField(required=False)
    is_expired = serializers.BooleanField(required=False)
    is_individual = serializers.BooleanField(required=False)
    current_owner = serializers.PrimaryKeyRelatedField(
        queryset=__import__("apps.core.models", fromlist=["CompanyModel"]).CompanyModel.objects.all(),
        allow_null=True,
        required=False,
    )
    file_transfer_status = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    last_ownership_fetch = serializers.DateTimeField(allow_null=True, required=False)
    user_comment = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    condition_sheet = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    user_restrictions = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    balance_report_notes = serializers.CharField(allow_blank=True, allow_null=True, required=False)

    # Annotated fields for FK display
    exporter_name = serializers.CharField(read_only=True, required=False)
    exporter_iec = serializers.CharField(read_only=True, required=False)
    port_name = serializers.CharField(read_only=True, required=False)
    purchase_status_code = serializers.SerializerMethodField()
    purchase_status_label = serializers.SerializerMethodField()

    # Property fields
    latest_transfer = serializers.CharField(read_only=True, required=False)
    get_norm_class = serializers.CharField(read_only=True, required=False)
    get_balance_cif = serializers.SerializerMethodField()
    has_tl = serializers.SerializerMethodField()
    has_copy = serializers.SerializerMethodField()
    has_condition_sheet = serializers.SerializerMethodField()
    is_manually_planned = serializers.SerializerMethodField()
    planning_state = serializers.SerializerMethodField()
    planning_revision = serializers.SerializerMethodField()

    # Nested serializers - separate for read/write to avoid validation issues
    export_license_read = LicenseExportItemSerializer(source='export_license', many=True, read_only=True)
    import_license_read = LicenseImportItemSerializer(source='import_license', many=True, read_only=True)

    export_license = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)
    import_license = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)

    # Separate read/write for license_documents to handle file uploads
    license_documents_read = LicenseDocumentSerializer(source='license_documents', many=True, read_only=True)
    license_documents = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)

    class Meta:
        model = LicenseDetailsModel
        fields = "__all__"
        read_only_fields = ("created_by", "modified_by", "created_on", "modified_on")

    def to_internal_value(self, data):
        """
        Override to parse FormData nested arrays.
        DRF doesn't automatically parse license_documents[0].type format from FormData.
        """
        import logging
        logger = logging.getLogger(__name__)

        # Parse nested arrays from FormData format (export_license[0].field, import_license[0].field, license_documents[0].field)
        if hasattr(data, 'getlist'):
            # It's MultiValueDict (FormData)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Parsing FormData for nested arrays")

            nested_dicts = {
                'export_license': {},
                'import_license': {},
                'license_documents': {},
            }
            for key in list(data.keys()):
                import re
                match = re.match(r'(export_license|import_license|license_documents)\[(\d+)\]\.(.+)', key)
                if match:
                    group = match.group(1)
                    index = int(match.group(2))
                    field_name = match.group(3)
                    if index not in nested_dicts[group]:
                        nested_dicts[group][index] = {}

                    if group == 'import_license' and field_name == 'items':
                        nested_dicts[group][index][field_name] = data.getlist(key)
                    else:
                        nested_dicts[group][index][field_name] = data.get(key)

            parsed_data = {}
            for key in data.keys():
                if not key.startswith(('export_license[', 'import_license[', 'license_documents[')):
                    parsed_data[key] = data.get(key)

            if nested_dicts['export_license']:
                parsed_data['export_license'] = [
                    nested_dicts['export_license'][i] for i in sorted(nested_dicts['export_license'].keys())
                ]
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Parsed %d export items from FormData", len(parsed_data['export_license']))

            if nested_dicts['import_license']:
                parsed_data['import_license'] = [
                    nested_dicts['import_license'][i] for i in sorted(nested_dicts['import_license'].keys())
                ]
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Parsed %d import items from FormData", len(parsed_data['import_license']))

            if nested_dicts['license_documents']:
                license_documents = [
                    nested_dicts['license_documents'][i] for i in sorted(nested_dicts['license_documents'].keys())
                ]
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Parsed %d documents from FormData", len(license_documents))
                    for i, doc in enumerate(license_documents):
                        logger.debug("Document %d: type=%s, file=%s", i, doc.get('type'), doc.get('file'))
                parsed_data['license_documents'] = license_documents

            data = parsed_data

        # Clean empty strings for boolean fields before validation
        self._clean_boolean_fields(data)

        return super().to_internal_value(data)

    def _clean_boolean_fields(self, data):
        """Convert string boolean values to actual booleans for FormData compatibility."""
        # Boolean fields in main license
        boolean_fields = ['is_audit', 'is_mnm', 'is_not_registered', 'is_null', 'is_au',
                         'is_active', 'is_incomplete', 'is_expired', 'is_individual']

        for field in boolean_fields:
            if field in data:
                value = data[field]
                if isinstance(value, str):
                    # Convert string booleans from FormData to actual booleans
                    if value == '' or value.lower() in ('false', '0', 'no'):
                        data[field] = False
                    elif value.lower() in ('true', '1', 'yes'):
                        data[field] = True

        # Boolean fields in import_license nested array
        if 'import_license' in data and isinstance(data['import_license'], list):
            for item in data['import_license']:
                if isinstance(item, dict) and 'is_restricted' in item:
                    value = item['is_restricted']
                    if isinstance(value, str):
                        if value == '' or value.lower() in ('false', '0', 'no'):
                            item['is_restricted'] = False
                        elif value.lower() in ('true', '1', 'yes'):
                            item['is_restricted'] = True

        return data

    def validate(self, data):
        """
        Object-level validation with specific error messages.
        """
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.exceptions import ValidationError
        import re

        errors = {}

        # Validate license_number format and sanitize
        if 'license_number' in data and data['license_number']:
            license_number = str(data['license_number']).strip().upper()

            # Sanitize: remove any characters not in allowed set
            sanitized = re.sub(r'[^A-Z0-9/-]', '', license_number)

            if sanitized != license_number:
                errors['license_number'] = ['License number contains invalid characters. Only uppercase letters, numbers, hyphens, and slashes are allowed.']
            else:
                # Update data with sanitized value
                data['license_number'] = sanitized

        # Validate license_number uniqueness (only if no format errors)
        if 'license_number' in data and data['license_number'] and 'license_number' not in errors:
            license_number = data['license_number']
            existing = LicenseDetailsModel.objects.filter(license_number=license_number)
            # Exclude current instance when updating
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                errors['license_number'] = ['License with this license number already exists']

        # Validate dates
        if data.get('license_date') and data.get('license_expiry_date'):
            if data['license_expiry_date'] <= data['license_date']:
                errors['license_expiry_date'] = ['License expiry date must be after license date']

        # Validate export items.
        #
        # Required-field checks below only apply to a row that is either
        # brand new (no `id`, or an `id` not among the license's current
        # export items) OR that is itself supplying the field being
        # checked. A row that already exists and is being patched for an
        # unrelated reason (e.g. the License Overview page's inline SION
        # Norm editor, which sends existing rows as bare `{id}` plus one
        # `{id, norm_class}` — see `LicenseWriteMixin.update()`, which
        # already only `setattr`s keys actually present in each dict) must
        # not be forced to re-supply every field just to change one of
        # them. Same "only validate what's actually new/changing" idea
        # already used for `license_documents` below.
        existing_export_ids = set()
        if self.instance is not None and 'export_license' in data:
            existing_export_ids = set(self.instance.export_license.values_list('id', flat=True))

        if 'export_license' in data and data['export_license']:
            export_errors = []
            for index, item in enumerate(data['export_license']):
                item_errors = {}
                is_existing = _nested_item_id(item) in existing_export_ids

                # HS Code is not required for export items (can be blank)
                # Removed: if not item.get('hs_code'):
                #     item_errors['hs_code'] = ['HS Code is required for export item']

                if 'description' in item or not is_existing:
                    if not item.get('description') or not item.get('description').strip():
                        item_errors['description'] = ['Description is required for export item']

                # Net quantity can be 0 or greater (including 0)
                if 'net_quantity' in item or not is_existing:
                    net_qty = item.get('net_quantity')
                    if net_qty is None or net_qty == '':
                        item_errors['net_quantity'] = ['Net quantity is required']
                    elif isinstance(net_qty, (int, float)) and net_qty < 0:
                        item_errors['net_quantity'] = ['Net quantity cannot be negative']

                # Unit is not required for export items (has default value 'kg' in model)

                if item_errors:
                    export_errors.append(item_errors)
                else:
                    export_errors.append(None)

            # Only add to errors if there are actual errors (not all None)
            if any(e for e in export_errors):
                errors['export_license'] = export_errors

        # Validate import items — same existing-row exemption as export items above.
        existing_import_ids = set()
        if self.instance is not None and 'import_license' in data:
            existing_import_ids = set(self.instance.import_license.values_list('id', flat=True))

        if 'import_license' in data and data['import_license']:
            import_errors = []
            for index, item in enumerate(data['import_license']):
                item_errors = {}
                is_existing = _nested_item_id(item) in existing_import_ids

                if 'hs_code' in item or not is_existing:
                    if not item.get('hs_code'):
                        item_errors['hs_code'] = ['HS Code is required for import item']

                if 'description' in item or not is_existing:
                    if not item.get('description') or not item.get('description').strip():
                        item_errors['description'] = ['Description is required for import item']

                if 'serial_number' in item or not is_existing:
                    serial_number = item.get('serial_number')
                    if serial_number is None or serial_number == '':
                        item_errors['serial_number'] = ['Serial number is required for import item']

                if 'unit' in item or not is_existing:
                    if not item.get('unit'):
                        item_errors['unit'] = ['Unit is required for import item']

                if item_errors:
                    import_errors.append(item_errors)
                else:
                    import_errors.append(None)

            # Only add to errors if there are actual errors (not all None)
            if any(e for e in import_errors):
                errors['import_license'] = import_errors

        # Validate documents
        if 'license_documents' in data and data['license_documents']:
            doc_errors = []
            for index, doc in enumerate(data['license_documents']):
                item_errors = {}

                # Only validate new documents (with file object)
                if doc.get('file') and not isinstance(doc.get('file'), str):
                    doc_type = doc.get('type')
                    # Check if type is missing, empty string, or whitespace only
                    if not doc_type or (isinstance(doc_type, str) and not doc_type.strip()):
                        item_errors['type'] = ['Document type is required']
                    # Validate type is one of the allowed choices
                    elif doc_type not in ['LICENSE COPY', 'TRANSFER LETTER', 'OTHER']:
                        item_errors['type'] = [f'Invalid document type: {doc_type}. Must be one of: LICENSE COPY, TRANSFER LETTER, OTHER']

                if item_errors:
                    doc_errors.append(item_errors)
                else:
                    doc_errors.append(None)

            # Only add to errors if there are actual errors (not all None)
            if any(e for e in doc_errors):
                errors['license_documents'] = doc_errors

        if errors:
            raise ValidationError(errors)

        return data

    def get_get_balance_cif(self, obj):
        """Return the LIVE balance for this license — same
        `LicenseBalanceCalculator` formula the License Overview page and the
        detail view use, so all three always agree. For list views, the
        viewset batch-computes this for the whole page in one shot
        (`LicenseBalanceCalculator.calculate_balance_for_licenses`, a fixed
        4 queries total, not 4×N — see `LicenseDetailsViewSet.
        get_serializer_context`) and passes it via `self.context
        ['live_balance_map']`; fall back to the stored column only if no
        batch map was supplied (e.g. this serializer used outside that
        viewset's `list`/`retrieve` flow). Clamp negatives to zero so this
        matches the live calculator's semantics exactly (it returns
        max(balance, 0)); the stored column can hold a negative-zero that
        would otherwise serialize as '-0.00'."""
        from decimal import Decimal
        live_map = self.context.get('live_balance_map')
        if live_map is not None:
            bal = live_map.get(obj.id)
        else:
            bal = obj.balance_cif
        if bal is None:
            return bal
        return bal if bal > 0 else Decimal('0.00')

    def __init__(self, *args, **kwargs):
        """
        Swap any DateTimeField in self.fields for SafeDateTimeField so that
        if underlying value is a date() it won't crash when DRF calls .utcoffset().
        Preserve common field attributes (format/input_formats/allow_null/required).

        Also optimize for list views by removing nested serializers.
        """
        super().__init__(*args, **kwargs)

        # Check if this is a list view - if so, remove nested serializers for performance
        request = self.context.get('request')
        is_list_view = request and hasattr(request, 'parser_context') and \
                       request.parser_context.get('view') and \
                       request.parser_context['view'].action == 'list'

        if is_list_view:
            # Remove nested serializers for list view to improve performance
            self.fields.pop('export_license_read', None)
            self.fields.pop('import_license_read', None)
            self.fields.pop('license_documents', None)

        for name, field in list(self.fields.items()):
            # only replace plain DateTimeField instances (not our SafeDateTimeField)
            if isinstance(field, serializers.DateTimeField) and not isinstance(field, SafeDateTimeField):
                # collect commonly used config values to preserve behavior
                fmt = getattr(field, "format", None)
                in_fmts = getattr(field, "input_formats", None)
                allow_null = getattr(field, "allow_null", False)
                required = getattr(field, "required", True)
                # instantiate a SafeDateTimeField with preserved settings
                self.fields[name] = SafeDateTimeField(format=fmt, input_formats=in_fmts, allow_null=allow_null,
                                                      required=required)

    def to_representation(self, instance) -> Dict[str, Any]:
        # Check if this is a list view
        request = self.context.get('request')
        is_list_view = request and hasattr(request, 'parser_context') and \
                       request.parser_context.get('view') and \
                       request.parser_context['view'].action == 'list'

        # Batch this licence's Planned Quantity map ONCE (not once per
        # import item) BEFORE nested serialization runs — same technique as
        # `live_balance_map` for Balance CIF list views, just injected here
        # since a single detail-view retrieve has no page_ids hook. List
        # views never reach `LicenseImportItemSerializer` at all (`import_
        # license_read` is popped in `__init__`), so this is skipped there.
        if not is_list_view and 'plan_map' not in self.context:
            from apps.license.services.plan_reporting import plan_map_for_import_items
            item_ids = [item.id for item in instance.import_license.all()]
            self.context['plan_map'] = plan_map_for_import_items(item_ids) if item_ids else {}

        # Same batching for the nested import items' live available_value /
        # balance_cif_fc (see `LicenseImportItemSerializer.get_available_value`)
        # — one shot for this licence's items instead of one live property
        # call per item.
        if not is_list_view and 'available_value_map' not in self.context:
            from apps.license.services.condition_pool import available_value_bulk_map
            self.context['available_value_map'] = available_value_bulk_map(instance.import_license.all())

        rep = super().to_representation(instance)

        if is_list_view:
            # For list view, add empty arrays for nested items (fields were removed in __init__)
            rep['export_license'] = []
            rep['import_license'] = []
            # For license_documents, emit at most one stub so the frontend can
            # display a merge link.  The queryset is prefetched by the viewset
            # for both list and retrieve actions, so reading .all() here hits the
            # prefetch cache — no per-row DB queries.
            _docs = list(instance.license_documents.all())
            rep['license_documents'] = [{'id': _docs[0].id}] if _docs else []
        else:
            # Detail view - rename the read-only fields back to their original names for frontend compatibility
            if 'export_license_read' in rep:
                rep['export_license'] = rep.pop('export_license_read')
            if 'import_license_read' in rep:
                rep['import_license'] = rep.pop('import_license_read')
            if 'license_documents_read' in rep:
                rep['license_documents'] = rep.pop('license_documents_read')

        # balance_cif: both DETAIL and LIST views now show the LIVE value —
        # same `LicenseBalanceCalculator` formula either way, so this field
        # always agrees with `get_balance_cif`/get_get_balance_cif() and with
        # the License Overview page. Detail view recomputes it directly
        # (single object, cheap); list view reads the viewset's batch-
        # computed `live_balance_map` (see `get_get_balance_cif`'s
        # docstring) to stay a fixed number of queries for the whole page.
        from decimal import Decimal

        def _clamp(value):
            # The live calculator can yield a negative-zero that serializes
            # as '-0.00' — clamp to a plain zero.
            if value is not None and value <= 0:
                return Decimal('0.00')
            return value

        if is_list_view:
            # `get_balance_cif` is already correct here — `get_get_balance_cif()`
            # (a SerializerMethodField, evaluated during `super().to_representation()`
            # above) reads the same `live_balance_map` itself. Only the plain
            # `balance_cif` field needs an explicit override, since it has no
            # custom getter and `super().to_representation()` populated it
            # from the model's stored-column property.
            live_map = self.context.get('live_balance_map')
            if live_map is not None:
                rep['balance_cif'] = _clamp(live_map.get(instance.id))
            # else: no batch map available (serializer used outside the
            # viewset's paginated `list` flow) — leave the stored-column
            # value `super().to_representation()` already produced.
        else:
            fresh = _clamp(instance.get_balance_cif)
            rep['balance_cif'] = fresh
            if 'get_balance_cif' in rep:
                rep['get_balance_cif'] = fresh

        def walk(obj):
            if isinstance(obj, dict):
                return {k: walk(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [walk(v) for v in obj]
            return _safe_iso(obj)

        return walk(rep)

    def get_is_manually_planned(self, obj):
        """True when the license has at least one manual utilization plan line.
        Uses the list-view annotation `_has_manual_plan` when present, else queries."""
        v = getattr(obj, '_has_manual_plan', None)
        if v is not None:
            return bool(v)
        return LicenseItemPlan.objects.filter(license=obj).exists()

    def get_planning_state(self, obj):
        """Expose freshness without making clients infer it from task rows.

        A matching source/applied revision is the only condition for CURRENT.
        For a stale plan, surface the active durable request state; a completed
        failure remains visibly non-current rather than being misreported as a
        usable plan.
        """
        if obj.planning_source_revision == obj.planning_applied_revision:
            return "CURRENT"
        request = obj.replan_requests.order_by("-requested_at", "-pk").first()
        if request is None:
            return "REPLAN_PENDING"
        if request.status == "running":
            return "REPLAN_RUNNING"
        if request.status in {"pending", "queued", "retry_pending"}:
            return "REPLAN_PENDING"
        return "REPLAN_FAILED"

    def get_planning_revision(self, obj):
        return {
            "source_revision": obj.planning_source_revision,
            "planned_revision": obj.planning_applied_revision,
            "is_current": obj.planning_source_revision == obj.planning_applied_revision,
        }

    def get_has_tl(self, obj):
        """Check if license has Transfer Letter documents.
        Uses the list-view annotation `_has_tl` when present, else queries."""
        v = getattr(obj, '_has_tl', None)
        if v is not None:
            return bool(v)
        return obj.license_documents.filter(type='TRANSFER LETTER').exists()

    def get_has_copy(self, obj):
        """Check if license has License Copy documents.
        Uses the list-view annotation `_has_copy` when present, else queries."""
        v = getattr(obj, '_has_copy', None)
        if v is not None:
            return bool(v)
        return obj.license_documents.filter(type='LICENSE COPY').exists()

    def get_has_condition_sheet(self, obj):
        return bool((obj.condition_sheet or "").strip())

    def get_purchase_status_code(self, obj):
        """Get purchase status code for display"""
        return obj.purchase_status.code if obj.purchase_status else None

    def get_purchase_status_label(self, obj):
        """Get purchase status label for display"""
        return obj.purchase_status.label if obj.purchase_status else None

    # helper for M2M items in import rows


# ============================================================================
# License Plan Presentation Serializers (read-only)
# ============================================================================

class PlanLinePresentationSerializer(serializers.Serializer):
    """
    Serializer for a single split plan line within a PlanRow.
    Represents one LicenseItemPlan instance in the split breakdown.
    """
    plan_line_id = serializers.IntegerField()
    item_name = serializers.CharField(allow_null=True)
    planned_quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    remaining_quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    planned_cif_fc = serializers.DecimalField(max_digits=15, decimal_places=2)
    remaining_cif_fc = serializers.DecimalField(max_digits=15, decimal_places=2)


class PlanRowSerializer(serializers.Serializer):
    """
    Serializer for one grouped plan row.
    Represents a set of import items with the same HSN + description + unit,
    presented as a single row with aggregated quantities and optional split breakdown.
    """
    group_id = serializers.IntegerField()
    import_item_ids = serializers.ListField(child=serializers.IntegerField())
    serials = serializers.ListField(child=serializers.IntegerField())
    description = serializers.CharField()
    hs_code = serializers.CharField(allow_null=True)

    # Aggregated quantities
    total_available_quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    total_available_cif_fc = serializers.DecimalField(max_digits=15, decimal_places=2)

    # Plan aggregates
    has_plan = serializers.BooleanField()
    planned_quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    planned_cif_fc = serializers.DecimalField(max_digits=15, decimal_places=2)

    # Usage aggregates
    used_quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    used_cif_fc = serializers.DecimalField(max_digits=15, decimal_places=2)

    # Derived
    remaining_quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    remaining_cif_fc = serializers.DecimalField(max_digits=15, decimal_places=2)
    uncommitted_quantity = serializers.DecimalField(max_digits=15, decimal_places=3)

    # Split breakdown
    split_lines = PlanLinePresentationSerializer(many=True, read_only=True)

    # Status flags
    is_feasible = serializers.BooleanField()
    is_short = serializers.BooleanField()


class LicensePlanPresentationSerializer(serializers.Serializer):
    """
    Complete plan presentation for one license.
    Single source of truth for aggregated license plan data.

    Semantics:
    - total_available_quantity: sum of import item quantities (from import)
    - total_planned_quantity: sum of plan line quantities (user-authored plans)
    - total_used_quantity: sum of allotment quantities (live consumption)
    - total_remaining_quantity: planned - used (planning headroom)
    - total_uncommitted_quantity: available - planned (unplanned headroom)
    """
    license_id = serializers.IntegerField()
    license_number = serializers.CharField()
    exporter_id = serializers.IntegerField(allow_null=True)
    exporter_name = serializers.CharField()

    # Rollup aggregates
    total_available_quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    total_available_cif_fc = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_planned_quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    total_planned_cif_fc = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_used_quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    total_used_cif_fc = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_remaining_quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    total_remaining_cif_fc = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_uncommitted_quantity = serializers.DecimalField(max_digits=15, decimal_places=3)

    # License-level semantics
    num_groups = serializers.IntegerField()
    num_items = serializers.IntegerField()
    has_any_plan = serializers.BooleanField()
    is_over_planned = serializers.BooleanField()

    # All rows (grouped, in serial order)
    rows = PlanRowSerializer(many=True, read_only=True)
