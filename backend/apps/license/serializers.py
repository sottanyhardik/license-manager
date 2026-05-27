# license/serializers.py
from datetime import date, datetime, time
from typing import Any, Dict, Iterable

from rest_framework import serializers

from apps.core.models import ItemNameModel, ProductDescriptionModel, SchemeCode, NotificationNumber
from apps.core.serializers import HSCodeSerializer, SionNormClassNestedSerializer
from apps.core.serializers.fields import IndianDateField
from apps.license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseDocumentModel,
    LicenseTransferModel,
    LicensePurchase,
    IncentiveLicense,
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
    license_number = serializers.CharField(source="license.license_number", read_only=True)
    license_date = IndianDateField(source="license.license_date", read_only=True)
    license_expiry_date = IndianDateField(source="license.license_expiry_date", read_only=True)
    notification_number = serializers.SlugRelatedField(source="license.notification_number", slug_field="code", read_only=True)
    exporter_name = serializers.CharField(source="license.exporter.name", read_only=True)
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


class LicenseDetailsSerializer(serializers.ModelSerializer):
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
        """Return balance_cif field directly instead of computing it."""
        # Use the model field directly, not the computed property
        # The property runs expensive queries which causes performance issues in list views
        return obj.balance_cif

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
            # For license_documents, check if any exist to show merge link in frontend
            rep['license_documents'] = [{'id': doc.id} for doc in instance.license_documents.all()[:1]] if instance.license_documents.exists() else []
        else:
            # Detail view - rename the read-only fields back to their original names for frontend compatibility
            if 'export_license_read' in rep:
                rep['export_license'] = rep.pop('export_license_read')
            if 'import_license_read' in rep:
                rep['import_license'] = rep.pop('import_license_read')
            if 'license_documents_read' in rep:
                rep['license_documents'] = rep.pop('license_documents_read')

        # Replace the stale balance_cif database field with fresh calculated value
        if 'get_balance_cif' in rep:
            rep['balance_cif'] = rep['get_balance_cif']

        def walk(obj):
            if isinstance(obj, dict):
                return {k: walk(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [walk(v) for v in obj]
            return _safe_iso(obj)

        return walk(rep)

    def get_get_balance_cif(self, obj):
        """Get fresh balance_cif (always calculated from property, not cached field)"""
        return obj.get_balance_cif

    def get_has_tl(self, obj):
        """Check if license has Transfer Letter documents"""
        return obj.license_documents.filter(type='TRANSFER LETTER').exists()

    def get_has_copy(self, obj):
        """Check if license has License Copy documents"""
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
    def _calculate_import_quantity(self, license_inst, hs_code_id):
        """
        Calculate import item quantity based on formula:
        Import Quantity = Export Net Quantity × SION Norm Quantity
        """
        from decimal import Decimal
        from apps.core.models import SIONImportModel

        # Get all export items for this license
        export_items = license_inst.export_license.all()

        if not export_items.exists():
            return Decimal('0')

        # Get the first export item's net quantity and norm class
        first_export = export_items.first()
        net_quantity = Decimal(str(first_export.net_quantity or 0))
        norm_class = first_export.norm_class

        if not norm_class or net_quantity == 0:
            return Decimal('0')

        # Find matching SION import norm based on HS code and norm class
        try:
            sion_import = SIONImportModel.objects.filter(
                norm_class=norm_class,
                hsn_code_id=hs_code_id
            ).first()

            if sion_import:
                norm_quantity = Decimal(str(sion_import.quantity or 0))
                # SION norms are per MT (1000 kg), so multiply by 1000 to get per kg
                calculated_quantity = net_quantity * norm_quantity * Decimal('1000')
                return calculated_quantity
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Failed to calculate import quantity: %s", str(e))

        return Decimal('0')

    def _create_import_item(self, license_inst, payload):
        from apps.license.signals import update_license_on_import_item_change

        items = payload.pop("items", [])
        description = payload.get("description")
        hs_code = payload.get("hs_code")

        # Remove fields that don't exist in LicenseImportItemsModel
        payload.pop('duty_type', None)  # This field only exists in export items
        if 'id' in payload and payload['id'] == '':
            payload.pop('id')

        # Auto-calculate quantity if not provided or is 0
        if hs_code and (not payload.get('quantity') or payload.get('quantity') == 0 or payload.get('quantity') == ''):
            calculated_qty = self._calculate_import_quantity(license_inst, hs_code)
            if calculated_qty > 0:
                payload['quantity'] = calculated_qty

        # Convert empty strings and None to 0 for required NOT NULL fields
        for field in ['serial_number', 'quantity']:
            if field in payload and (payload[field] == '' or payload[field] is None):
                payload[field] = 0

        # Convert empty strings to None for optional decimal fields
        for field in ['cif_fc', 'cif_inr']:
            if field in payload and payload[field] == '':
                payload[field] = None

        # Handle foreign key fields - convert IDs to model instances
        if 'hs_code' in payload and payload['hs_code']:
            from apps.core.models import HSCodeModel
            if isinstance(payload['hs_code'], (int, str)):
                try:
                    payload['hs_code'] = HSCodeModel.objects.get(id=payload['hs_code'])
                except (ValueError, HSCodeModel.DoesNotExist):
                    payload['hs_code'] = None

        obj = LicenseImportItemsModel.objects.create(license=license_inst, **payload)
        if isinstance(items, Iterable):
            # Only set items if the import item has no items linked yet
            if not obj.items.exists():
                obj.items.set(items)

        # Save description to ProductDescriptionModel if both description and hs_code exist
        # Use the converted hs_code from payload (which is now a model instance)
        if description and payload.get('hs_code'):
            ProductDescriptionModel.objects.get_or_create(
                hs_code=payload['hs_code'],
                product_description=description
            )

        # Manually trigger signal to ensure ItemNameModel items are linked
        # This ensures items are properly linked based on description matching
        try:
            update_license_on_import_item_change(
                sender=LicenseImportItemsModel,
                instance=obj,
                created=True,
                raw=False
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error("Failed to auto-link items in _create_import_item for %d: %s", obj.id, str(e))

        return obj

    def create(self, validated_data):
        from django.db import transaction
        from apps.license.signals import suspend_license_flag_recalc, update_license_flags
        from apps.license.utils.item_matcher import bulk_auto_link_license_items

        exports = validated_data.pop("export_license", [])
        imports = validated_data.pop("import_license", [])
        docs = validated_data.pop("license_documents", [])
        transfers = validated_data.pop("transfers", [])
        purchases = validated_data.pop("purchases", [])

        # Wrap entire license creation in atomic transaction
        # If any error occurs, the entire license creation will be rolled back
        with transaction.atomic(), suspend_license_flag_recalc():
            instance = LicenseDetailsModel.objects.create(**validated_data)

            for e in exports:
                # Remove form-only fields and empty id fields
                e.pop('start_serial_number', None)
                e.pop('end_serial_number', None)
                if 'id' in e and e['id'] == '':
                    e.pop('id')

                # Convert empty strings and None to 0 for required NOT NULL fields
                for field in ['net_quantity', 'old_quantity']:
                    if field in e and (e[field] == '' or e[field] is None):
                        e[field] = 0

                # Convert empty strings to None for optional decimal fields
                for field in ['fob_fc', 'fob_inr', 'fob_exchange_rate', 'value_addition', 'cif_fc', 'cif_inr']:
                    if field in e and e[field] == '':
                        e[field] = None

                # Handle foreign key fields - convert IDs to model instances
                if 'norm_class' in e and e['norm_class']:
                    from apps.core.models import SionNormClassModel
                    if isinstance(e['norm_class'], (int, str)):
                        try:
                            e['norm_class'] = SionNormClassModel.objects.get(id=e['norm_class'])
                        except (ValueError, SionNormClassModel.DoesNotExist):
                            e['norm_class'] = None

                if 'hs_code' in e and e['hs_code']:
                    from apps.core.models import HSCodeModel
                    if isinstance(e['hs_code'], (int, str)):
                        try:
                            e['hs_code'] = HSCodeModel.objects.get(id=e['hs_code'])
                        except (ValueError, HSCodeModel.DoesNotExist):
                            e['hs_code'] = None

                # Ensure unit field has default value if not provided or empty
                if 'unit' not in e or not e.get('unit') or (isinstance(e.get('unit'), str) and e.get('unit').strip() == ''):
                    e['unit'] = 'kg'

                LicenseExportItemModel.objects.create(license=instance, **e)

            # Create import items - signal is called inside _create_import_item
            for i in imports:
                self._create_import_item(instance, i)

            for d in docs:
                # Validate required fields - ensure type is not empty and file is present
                doc_type = d.get('type', '').strip() if d.get('type') else None
                if doc_type and d.get('file'):
                    # Ensure type is set properly
                    d['type'] = doc_type
                    LicenseDocumentModel.objects.create(license=instance, **d)
            for t in transfers:
                LicenseTransferModel.objects.create(license=instance, **t)
            for p in purchases:
                LicensePurchase.objects.create(license=instance, **p)

        # Bulk auto-link ItemNames in O(M) queries instead of O(N×M).
        bulk_auto_link_license_items(instance)
        # For a fresh licence, available_quantity = quantity (no debits yet).
        # Bulk-set in one query instead of letting the on_commit hook fire
        # update_balance_values 38× post-commit.
        from django.db.models import F
        LicenseImportItemsModel.objects.filter(
            license=instance, available_quantity=0
        ).update(available_quantity=F("quantity"))
        # Final balance / is_null / is_expired recalc + pool-based
        # available_value (single pass).
        update_license_flags(instance)
        return instance

    def update(self, instance, validated_data):
        from django.db import transaction
        from apps.license.signals import suspend_license_flag_recalc, update_license_flags
        from apps.license.utils.item_matcher import bulk_auto_link_license_items
        import logging
        logger = logging.getLogger(__name__)

        # Log what we receive
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("="*50)
            logger.debug("UPDATE called with validated_data keys: %s", list(validated_data.keys()))

        exports = validated_data.pop("export_license", None)
        imports = validated_data.pop("import_license", None)
        docs = validated_data.pop("license_documents", None)
        transfers = validated_data.pop("transfers", None)
        purchases = validated_data.pop("purchases", None)

        # Log license_documents
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("license_documents extracted: %s", docs)
            if docs:
                logger.debug("Number of documents: %s", len(docs))
                for i, doc in enumerate(docs):
                    logger.debug("Document %s: keys=%s, type=%s, file=%s", i, list(doc.keys()), doc.get('type'), doc.get('file'))

        # Use atomic transaction with row-level locking to prevent race conditions.
        # Suspend per-item balance recalcs — we flush them once at the end.
        with transaction.atomic(), suspend_license_flag_recalc():
            # Lock the license record for update to prevent concurrent modifications
            locked_instance = LicenseDetailsModel.objects.select_for_update().get(pk=instance.pk)

            # Update the main license fields
            for k, v in validated_data.items():
                setattr(locked_instance, k, v)
            locked_instance.save()

            # Update instance reference to use locked instance
            instance = locked_instance

        if exports is not None:
            with transaction.atomic():
                # Lock and get all existing export items to prevent race conditions
                existing_items = {item.id: item for item in instance.export_license.select_for_update().all()}
                processed_ids = set()

                # Update or create export items
                for e in exports:
                    item_id = e.get('id')

                    # Remove form-only fields and nested read-only fields that are not part of the model
                    e.pop('start_serial_number', None)
                    e.pop('end_serial_number', None)
                    e.pop('norm_class_label', None)
                    e.pop('item_label', None)

                    # Remove nested detail objects (norm_class_detail.*, item_detail.*)
                    keys_to_remove = [k for k in e.keys() if '.' in k or k.endswith('_detail')]
                    for key in keys_to_remove:
                        e.pop(key, None)

                    # Convert empty strings and None to 0 for required NOT NULL fields
                    for field in ['net_quantity', 'old_quantity']:
                        if field in e and (e[field] == '' or e[field] is None):
                            e[field] = 0

                    # Convert empty strings to None for optional decimal fields
                    for field in ['fob_fc', 'fob_inr', 'fob_exchange_rate', 'value_addition', 'cif_fc', 'cif_inr']:
                        if field in e and e[field] == '':
                            e[field] = None

                    # Ensure unit field has default value if not provided or empty
                    if 'unit' not in e or not e.get('unit') or (isinstance(e.get('unit'), str) and e.get('unit').strip() == ''):
                        e['unit'] = 'kg'

                    if item_id and item_id in existing_items:
                        # Update existing item by ID
                        obj = existing_items[item_id]
                        for key, value in e.items():
                            if key not in ('id', 'license', 'start_serial_number', 'end_serial_number'):
                                # Handle foreign keys by using _id suffix
                                if key in ('norm_class', 'item') and value is not None:
                                    setattr(obj, f"{key}_id", value)
                                else:
                                    setattr(obj, key, value)
                        obj.save()
                        processed_ids.add(item_id)
                    else:
                        # Create new item
                        e.pop('id', None)  # Remove ID if present
                        e.pop('license', None)  # Remove license field - we use instance

                        # Handle foreign keys - convert to _id format for direct assignment
                        if 'norm_class' in e and e['norm_class'] is not None:
                            e['norm_class_id'] = e.pop('norm_class')
                        if 'item' in e and e['item'] is not None:
                            e['item_id'] = e.pop('item')

                        obj = LicenseExportItemModel.objects.create(license=instance, **e)
                        processed_ids.add(obj.id)

                # Only delete items if we actually received export data in the payload
                # This prevents accidental deletion when frontend doesn't send nested data
                if len(exports) > 0:
                    from django.db.models import ProtectedError
                    from rest_framework.exceptions import ValidationError
                    import logging
                    logger = logging.getLogger(__name__)

                    protected_items = []
                    deleted_count = 0

                    # Delete items that are no longer in the payload
                    for item_id, item in existing_items.items():
                        if item_id not in processed_ids:
                            try:
                                if logger.isEnabledFor(logging.DEBUG):
                                    logger.debug("Attempting to delete export item ID=%d", item_id)
                                item.delete()
                                deleted_count += 1
                                if logger.isEnabledFor(logging.DEBUG):
                                    logger.debug("Successfully deleted export item ID=%d", item_id)
                            except ProtectedError as e:
                                logger.warning("Cannot delete export item ID=%d: %s", item_id, str(e))
                                protected_items.append({
                                    'id': item.id,
                                    'description': item.description or str(item.norm_class) if item.norm_class else 'Unknown'
                                })

                    logger.info("Deleted %d export items successfully", deleted_count)

                    # If any items couldn't be deleted due to protection, raise validation error
                    if protected_items:
                        error_msg = "Cannot delete the following export items because they are referenced elsewhere:\n"
                        for protected in protected_items:
                            error_msg += f"  - {protected['description']}\n"
                        error_msg += "Please remove references first, or keep them in the license."

                        logger.error("Protected export items preventing deletion: %s", protected_items)
                        raise ValidationError({
                            'export_license': error_msg
                        })

        if imports is not None:
            from apps.license.signals import update_license_on_import_item_change

            # Use transaction to ensure atomicity
            with transaction.atomic():
                # Lock and get all existing import items to prevent race conditions
                existing_items = list(instance.import_license.select_for_update().all())
                existing_items_by_id = {item.id: item for item in existing_items}
                existing_items_by_serial = {item.serial_number: item for item in existing_items}
                processed_ids = set()
                processed_serials = set()

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Existing items by ID: %s", list(existing_items_by_id.keys()))
                    logger.debug("Existing items by serial: %s", list(existing_items_by_serial.keys()))
                    logger.debug("Incoming imports count: %d", len(imports))

                # Update or create import items
                for idx, i in enumerate(imports):
                    item_id = i.get('id')
                    # Convert item_id to int for proper matching
                    if item_id:
                        try:
                            item_id = int(item_id)
                        except (ValueError, TypeError):
                            item_id = None

                    serial_number = i.get('serial_number')
                    # Convert serial_number to int for proper matching
                    if serial_number:
                        try:
                            serial_number = int(serial_number)
                        except (ValueError, TypeError):
                            pass

                    items_list = i.pop('items', [])
                    description = i.get('description')
                    hs_code = i.get('hs_code')

                    # Remove fields that don't exist in LicenseImportItemsModel
                    i.pop('duty_type', None)  # This field only exists in export items
                    i.pop('license_number', None)
                    i.pop('license_date', None)
                    i.pop('license_expiry', None)
                    i.pop('license_expiry_date', None)
                    i.pop('notification_number', None)
                    i.pop('exporter_name', None)

                    # Remove read-only computed properties that have no setter
                    i.pop('balance_cif_fc', None)
                    i.pop('allotted_quantity', None)
                    i.pop('allotted_value', None)

                    # Remove nested detail objects and read-only fields with dots or array brackets
                    keys_to_remove = [k for k in i.keys() if '.' in k or '[' in k or k.endswith('_detail') or k.endswith('_label')]
                    for key in keys_to_remove:
                        i.pop(key, None)

                    obj = None

                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("Processing import #%d: id=%s, serial=%s", idx, item_id, serial_number)

                    # First, try to match by ID
                    if item_id and item_id in existing_items_by_id:
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("  -> Matched by ID %s", item_id)
                        # Update existing item by ID
                        obj = existing_items_by_id[item_id]

                        # Auto-calculate quantity if not provided or is 0
                        hs_code = i.get('hs_code')
                        if hs_code and (not i.get('quantity') or i.get('quantity') == 0 or i.get('quantity') == ''):
                            calculated_qty = self._calculate_import_quantity(instance, hs_code)
                            if calculated_qty > 0:
                                i['quantity'] = calculated_qty

                        for key, value in i.items():
                            if key not in ('id', 'license', 'license_date', 'license_expiry', 'balance_cif_fc',
                                           'license_number', 'notification_number', 'exporter_name', 'hs_code_detail',
                                           'hs_code_label', 'allotted_quantity', 'allotted_value'):
                                # Handle foreign keys by using _id suffix
                                if key == 'hs_code' and value is not None:
                                    setattr(obj, 'hs_code_id', value)
                                else:
                                    setattr(obj, key, value)
                        obj.save()

                        # Update M2M relationship - only if items is empty
                        if isinstance(items_list, list):
                            # Only update items if no items are currently linked
                            if not obj.items.exists():
                                obj.items.set(items_list)

                        # Trigger signal to ensure ItemNameModel items are linked
                        try:
                            update_license_on_import_item_change(
                                sender=LicenseImportItemsModel,
                                instance=obj,
                                created=False,
                                raw=False
                            )
                        except Exception as e:
                            logger.error("Failed to auto-link items for import item %d: %s", obj.id, str(e))

                        processed_ids.add(obj.id)
                        processed_serials.add(obj.serial_number)
                    # If no ID match, try to match by serial_number (for items without ID or wrong ID)
                    elif serial_number and serial_number in existing_items_by_serial:
                        # Check if this serial was already processed (avoid duplicates in same batch)
                        if serial_number in processed_serials:
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug("  -> Skipping: serial %s already processed", serial_number)
                            continue
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("  -> Matched by serial %s", serial_number)

                        # Update existing item by serial_number
                        obj = existing_items_by_serial[serial_number]

                        # Auto-calculate quantity if not provided or is 0
                        hs_code = i.get('hs_code')
                        if hs_code and (not i.get('quantity') or i.get('quantity') == 0 or i.get('quantity') == ''):
                            calculated_qty = self._calculate_import_quantity(instance, hs_code)
                            if calculated_qty > 0:
                                i['quantity'] = calculated_qty

                        for key, value in i.items():
                            if key not in ('id', 'license', 'license_date', 'license_expiry', 'balance_cif_fc',
                                           'license_number', 'notification_number', 'exporter_name', 'hs_code_detail',
                                           'hs_code_label', 'allotted_quantity', 'allotted_value'):
                                # Handle foreign keys by using _id suffix
                                if key == 'hs_code' and value is not None:
                                    setattr(obj, 'hs_code_id', value)
                                else:
                                    setattr(obj, key, value)
                        obj.save()

                        # Update M2M relationship - only if items is empty
                        if isinstance(items_list, list):
                            # Only update items if no items are currently linked
                            if not obj.items.exists():
                                obj.items.set(items_list)

                        # Trigger signal to ensure ItemNameModel items are linked
                        try:
                            update_license_on_import_item_change(
                                sender=LicenseImportItemsModel,
                                instance=obj,
                                created=False,
                                raw=False
                            )
                        except Exception as e:
                            logger.error("Failed to auto-link items for import item %d: %s", obj.id, str(e))

                        processed_ids.add(obj.id)
                        processed_serials.add(obj.serial_number)
                    else:
                        # Check if this serial was already processed (avoid duplicates in same batch)
                        if serial_number and serial_number in processed_serials:
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug("  -> Skipping: creating duplicate serial %s", serial_number)
                            continue

                        # Double-check: if serial_number exists in DB, update it instead of creating
                        if serial_number and serial_number in existing_items_by_serial:
                            logger.warning("Found existing item by serial %s in fallback check, updating instead", serial_number)
                            obj = existing_items_by_serial[serial_number]

                            # Auto-calculate quantity if not provided or is 0
                            hs_code = i.get('hs_code')
                            if hs_code and (not i.get('quantity') or i.get('quantity') == 0 or i.get('quantity') == ''):
                                calculated_qty = self._calculate_import_quantity(instance, hs_code)
                                if calculated_qty > 0:
                                    i['quantity'] = calculated_qty

                            for key, value in i.items():
                                if key not in ('id', 'license', 'license_date', 'license_expiry', 'balance_cif_fc',
                                               'license_number', 'notification_number', 'exporter_name', 'hs_code_detail',
                                               'hs_code_label', 'allotted_quantity', 'allotted_value'):
                                    # Handle foreign keys by using _id suffix
                                    if key == 'hs_code' and value is not None:
                                        setattr(obj, 'hs_code_id', value)
                                    else:
                                        setattr(obj, key, value)
                            obj.save()

                            # Update M2M relationship - only if items is empty
                            if isinstance(items_list, list):
                                if not obj.items.exists():
                                    obj.items.set(items_list)

                            processed_ids.add(obj.id)
                            processed_serials.add(obj.serial_number)
                        else:
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug("  -> Creating new item with serial %s", serial_number)
                            # Create new item only if serial_number doesn't exist
                            i.pop('id', None)  # Remove ID if present
                            i.pop('license', None)  # Remove license field - we use instance
                            i.pop('license_date', None)  # Remove read-only fields
                            i.pop('license_expiry', None)  # Remove read-only fields

                            # Handle foreign keys - convert to _id format for direct assignment
                            if 'hs_code' in i and i['hs_code'] is not None:
                                i['hs_code_id'] = i.pop('hs_code')

                            i['items'] = items_list
                            obj = self._create_import_item(instance, i)
                            processed_ids.add(obj.id)
                            if obj.serial_number:
                                processed_serials.add(obj.serial_number)
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug("  -> Created item with ID %d", obj.id)

                    # Save description to ProductDescriptionModel
                    if description and hs_code:
                        ProductDescriptionModel.objects.get_or_create(
                            hs_code_id=hs_code if isinstance(hs_code, int) else hs_code,
                            product_description=description
                        )

                # Only delete items if we actually received import data in the payload
                # This prevents accidental deletion when frontend doesn't send nested data
                if len(imports) > 0:
                    # Delete items that are no longer in the payload
                    items_to_delete = [item for item in existing_items if item.id not in processed_ids]

                    # SAFETY CHECK: Warn if there's a mismatch (frontend didn't send all items)
                    if items_to_delete:
                        logger.warning("Import items mismatch detected:")
                        logger.warning("  - Processed %d items from payload", len(processed_ids))
                        logger.warning("  - %d items exist in database", len(existing_items))
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("  - Processed IDs: %s", sorted(processed_ids))
                            logger.debug("  - Existing IDs: %s", sorted([item.id for item in existing_items]))
                            logger.debug("  - Items marked for deletion: %s", [{'id': item.id, 'serial': item.serial_number} for item in items_to_delete])

                    if items_to_delete:
                        logger.info("Attempting to delete %d import items not in payload", len(items_to_delete))
                        from django.db.models import ProtectedError
                        from rest_framework.exceptions import ValidationError

                        protected_items = []
                        deleted_count = 0

                        for item in items_to_delete:
                            try:
                                if logger.isEnabledFor(logging.DEBUG):
                                    logger.debug("Attempting to delete import item ID=%d, serial=%s", item.id, item.serial_number)
                                item.delete()
                                deleted_count += 1
                                if logger.isEnabledFor(logging.DEBUG):
                                    logger.debug("Successfully deleted import item ID=%d", item.id)
                            except ProtectedError as e:
                                logger.warning("Cannot delete import item ID=%d: %s", item.id, str(e))
                                protected_items.append({
                                    'id': item.id,
                                    'serial_number': item.serial_number,
                                    'description': item.description
                                })

                        logger.info("Deleted %d import items successfully", deleted_count)

                        # If any items couldn't be deleted due to protection, raise validation error
                        if protected_items:
                            error_msg = f"Cannot delete {len(protected_items)} import item(s) because they are used in trades or bills of entry:\n\n"
                            for protected in protected_items:
                                error_msg += f"  • Serial #{protected['serial_number']}: {protected['description']} (ID: {protected['id']})\n"
                            error_msg += f"\nThese items are currently being used and cannot be removed from the license. "
                            error_msg += f"To delete them, first remove their usage from trades or bills of entry, "
                            error_msg += f"or include them in your save to keep them."

                            logger.error("Protected items preventing deletion: %s", protected_items)
                            raise ValidationError({
                                'import_license': error_msg,
                                'non_field_errors': [f"Cannot delete {len(protected_items)} import item(s) - they are being used in trades/BOEs"]
                            })
                    else:
                        logger.info("No import items to delete - all existing items were updated or are in payload")

                logger.info("Import items update complete. Processed %d items, deleted %d items", len(processed_ids), len(items_to_delete) if len(imports) > 0 else 0)

        if docs is not None:
            with transaction.atomic():
                # Lock and get all existing documents to prevent race conditions
                existing_items = {item.id: item for item in instance.license_documents.select_for_update().all()}
                processed_ids = set()

                # Process documents from payload
                for idx, d in enumerate(docs):
                    item_id = d.get('id')
                    # Convert item_id to int if it's a string
                    if item_id:
                        try:
                            item_id = int(item_id)
                        except (ValueError, TypeError):
                            item_id = None

                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("Processing document %d: id=%s, type=%s, file type=%s", idx, item_id, d.get('type'), type(d.get('file')).__name__)

                    if item_id and item_id in existing_items:
                        # Keep existing document - mark as processed so it won't be deleted
                        obj = existing_items[item_id]
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("Found existing document ID=%s", item_id)

                        changed = False

                        # Update type if changed (and not empty)
                        new_type = d.get('type', '').strip() if d.get('type') else None
                        if new_type and new_type != obj.type:
                            obj.type = new_type
                            changed = True
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug("Updated type to '%s'", new_type)

                        # Update file only if new File object provided (not a URL string)
                        file_value = d.get('file')
                        if file_value and not isinstance(file_value, str):
                            obj.file = file_value
                            changed = True
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug("Updated file")
                        elif isinstance(file_value, str) and logger.isEnabledFor(logging.DEBUG):
                            logger.debug("Skipping file update (URL string)")

                        # Only save if something actually changed
                        if changed:
                            obj.save()
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug("Saved changes to document ID=%s", item_id)
                        elif logger.isEnabledFor(logging.DEBUG):
                            logger.debug("No changes to document ID=%s, skipping save", item_id)

                        processed_ids.add(item_id)
                    else:
                        # Create new document
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("Creating new document")
                        d.pop('id', None)
                        d.pop('license', None)

                        # Only create if type and file are present (and file is a File object, not URL string)
                        file_obj = d.get('file')
                        doc_type = d.get('type', '').strip() if d.get('type') else None
                        has_type = bool(doc_type)
                        is_file_obj = file_obj and not isinstance(file_obj, str)

                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug("Validation: has_type=%s, doc_type=%s, is_file_obj=%s", has_type, doc_type, is_file_obj)

                        if has_type and is_file_obj:
                            # Ensure type is set properly
                            d['type'] = doc_type
                            obj = LicenseDocumentModel.objects.create(license=instance, **d)
                            processed_ids.add(obj.id)
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug("Created new document with ID=%d", obj.id)
                        elif logger.isEnabledFor(logging.DEBUG):
                            logger.debug("Skipped creating document: type=%s, file type=%s", d.get('type'), type(file_obj).__name__)

                # Only delete documents if we actually received document data in the payload
                # This prevents accidental deletion when frontend doesn't send nested data
                if len(docs) > 0:
                    # Delete documents that were removed from the form (not in payload)
                    for item_id, item in existing_items.items():
                        if item_id not in processed_ids:
                            item.delete()

        if transfers is not None:
            with transaction.atomic():
                # Lock and get all existing transfers to prevent race conditions
                existing_items = {item.id: item for item in instance.transfers.select_for_update().all()}
                processed_ids = set()

                # Update or create transfers
                for t in transfers:
                    item_id = t.get('id')

                    if item_id and item_id in existing_items:
                        # Update existing item by ID
                        obj = existing_items[item_id]
                        for key, value in t.items():
                            if key not in ('id', 'license'):
                                setattr(obj, key, value)
                        obj.save()
                        processed_ids.add(item_id)
                    else:
                        # Create new item
                        t.pop('id', None)  # Remove ID if present
                        t.pop('license', None)  # Remove license field
                        obj = LicenseTransferModel.objects.create(license=instance, **t)
                        processed_ids.add(obj.id)

                # Delete items that are no longer in the payload
                for item_id, item in existing_items.items():
                    if item_id not in processed_ids:
                        item.delete()

        if purchases is not None:
            with transaction.atomic():
                # Lock and get all existing purchases to prevent race conditions
                existing_items = {item.id: item for item in instance.purchases.select_for_update().all()}
                processed_ids = set()

                # Update or create purchases
                for p in purchases:
                    item_id = p.get('id')

                    if item_id and item_id in existing_items:
                        # Update existing item by ID
                        obj = existing_items[item_id]
                        for key, value in p.items():
                            if key not in ('id', 'license'):
                                setattr(obj, key, value)
                        obj.save()
                        processed_ids.add(item_id)
                    else:
                        # Create new item
                        p.pop('id', None)  # Remove ID if present
                        p.pop('license', None)  # Remove license field
                        obj = LicensePurchase.objects.create(license=instance, **p)
                        processed_ids.add(obj.id)

                # Delete items that are no longer in the payload
                for item_id, item in existing_items.items():
                    if item_id not in processed_ids:
                        item.delete()

        # Bulk auto-link ItemNames + single recalc pass.
        bulk_auto_link_license_items(instance)
        update_license_flags(instance)
        return instance


class IncentiveLicenseSerializer(serializers.ModelSerializer):
    """
    Serializer for IncentiveLicense model (RODTEP/ROSTL/MEIS)
    """
    license_date = IndianDateField(required=True)
    license_expiry_date = IndianDateField(required=False, allow_null=True)

    # Read-only fields for display
    exporter_name = serializers.CharField(source="exporter.name", read_only=True)
    port_name = serializers.CharField(source="port_code.name", read_only=True)
    sold_value = serializers.SerializerMethodField()
    balance_value = serializers.SerializerMethodField()

    class Meta:
        model = IncentiveLicense
        fields = "__all__"
        read_only_fields = ("created_by", "modified_by", "created_on", "modified_on", "license_expiry_date")

    def get_sold_value(self, obj):
        """Get total sold value from SALE trades"""
        return float(obj.get_sold_value())

    def get_balance_value(self, obj):
        """Get remaining balance value"""
        return float(obj.get_balance_value())

    def get_sold_status(self, obj):
        """Get sold status: YES (fully sold), NO (not sold), PARTIAL (partially sold)"""
        from decimal import Decimal
        sold_value = obj.get_sold_value()
        balance_value = obj.get_balance_value()

        if sold_value == Decimal('0.00') or sold_value is None:
            return 'NO'
        elif balance_value <= Decimal('0.00'):
            return 'YES'
        else:
            return 'PARTIAL'

    def to_representation(self, instance):
        """Add formatted dates and display names"""
        rep = super().to_representation(instance)

        # Add exporter and port details for frontend display
        if instance.exporter:
            rep['exporter_name'] = instance.exporter.name
            rep['exporter__name'] = instance.exporter.name  # For list_display consistency
        if instance.port_code:
            rep['port_name'] = instance.port_code.name
            rep['port_code__name'] = instance.port_code.name  # For list_display consistency

        # Add computed fields
        rep['sold_value'] = self.get_sold_value(instance)
        rep['balance_value'] = self.get_balance_value(instance)
        rep['sold_status'] = self.get_sold_status(instance)

        return rep
