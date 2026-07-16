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

    balance_cif_fc = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = LicenseImportItemsModel
        fields = ['id', 'serial_number', 'license', 'hs_code', 'items', 'items_detail', 'description', 'quantity',
                  'old_quantity', 'unit', 'cif_fc', 'cif_inr', 'available_quantity', 'available_value',
                  'allotted_quantity', 'allotted_value', 'debited_quantity', 'debited_value',
                  'license_number', 'license_date', 'license_expiry_date',
                  'notification_number', 'exporter_name', 'notes', 'hs_code_detail', 'hs_code_label', 'balance_cif_fc',
                  'is_restricted', 'condition_type']
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
        Return calculated available value based on restriction logic.

        Reads the stored `available_value` field rather than re-computing the
        pool model on every read — the pool is recalculated on every save by
        `_update_all_import_items_available_value`, so the stored field is
        authoritative. Avoids O(N) compute_condition_pools calls per list view.
        """
        return float(obj.available_value or 0)

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

    def get_balance_cif_fc(self, obj):
        """
        ITEM-LEVEL available CIF FC. Under the new condition_type model the
        per-item balance is the same value we store in `available_value` —
        return the stored field to keep this O(1).
        """
        return float(obj.available_value or 0)

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

        # Validate export items
        if 'export_license' in data and data['export_license']:
            export_errors = []
            for index, item in enumerate(data['export_license']):
                item_errors = {}

                # HS Code is not required for export items (can be blank)
                # Removed: if not item.get('hs_code'):
                #     item_errors['hs_code'] = ['HS Code is required for export item']

                if not item.get('description') or not item.get('description').strip():
                    item_errors['description'] = ['Description is required for export item']

                # Net quantity can be 0 or greater (including 0)
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

        # Validate import items
        if 'import_license' in data and data['import_license']:
            import_errors = []
            for index, item in enumerate(data['import_license']):
                item_errors = {}

                if not item.get('hs_code'):
                    item_errors['hs_code'] = ['HS Code is required for import item']

                if not item.get('description') or not item.get('description').strip():
                    item_errors['description'] = ['Description is required for import item']

                serial_number = item.get('serial_number')
                if serial_number is None or serial_number == '':
                    item_errors['serial_number'] = ['Serial number is required for import item']

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
        """Return the stored balance_cif column directly (O(1)) instead of the
        expensive live property, which runs 4 aggregate queries per row and kills
        list-view performance. Clamp negatives to zero so this matches the live
        calculator's semantics exactly (it returns max(balance, 0)); the stored
        column can hold a negative-zero that would otherwise serialize as '-0.00'."""
        from decimal import Decimal
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
        rep = super().to_representation(instance)

        # Check if this is a list view
        request = self.context.get('request')
        is_list_view = request and hasattr(request, 'parser_context') and \
                       request.parser_context.get('view') and \
                       request.parser_context['view'].action == 'list'

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

        # balance_cif: the DETAIL view recomputes the live value (single object, cheap,
        # and keeps the "fresh" guarantee); the LIST view keeps the stored column, which
        # signals keep in sync and which avoids N balance-aggregate queries per row.
        # (The stored column is what get_get_balance_cif() returns.)
        if not is_list_view:
            from decimal import Decimal
            fresh = instance.get_balance_cif
            # Clamp to match the list path (stored column) so both views agree; the
            # live calculator can yield a negative-zero that serializes as '-0.00'.
            if fresh is not None and fresh <= 0:
                fresh = Decimal('0.00')
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
