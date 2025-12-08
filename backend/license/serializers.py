# license/serializers.py
from datetime import date, datetime, time
from typing import Any, Dict, Iterable

from rest_framework import serializers

from core.models import ItemNameModel, ProductDescriptionModel
from core.serializers import HSCodeSerializer, SionNormClassNestedSerializer
from license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseDocumentModel,
    LicenseTransferModel,
    LicensePurchase,
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

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
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
    items = serializers.PrimaryKeyRelatedField(many=True, queryset=ItemNameModel.objects.all(), required=False)
    items_detail = serializers.SerializerMethodField(read_only=True)
    license_number = serializers.CharField(source="license.license_number", read_only=True)
    license_date = serializers.DateField(source="license.license_date", read_only=True, format="%Y-%m-%d")
    license_expiry_date = serializers.DateField(source="license.license_expiry_date", read_only=True, format="%Y-%m-%d")
    notification_number = serializers.CharField(source="license.notification_number", read_only=True)
    exporter_name = serializers.CharField(source="license.exporter.name", read_only=True)
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
                  'notification_number', 'exporter_name', 'hs_code_detail', 'hs_code_label', 'balance_cif_fc',
                  'is_restricted']
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
        """
        Calculate available quantity at runtime.
        Formula: quantity - debited_quantity - allotted_quantity
        """
        from core.scripts.calculate_balance import calculate_available_quantity
        try:
            result = calculate_available_quantity(obj)
            return float(result) if result is not None else 0.0
        except Exception as e:
            # Fallback: Manual calculation if helper function fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"calculate_available_quantity failed for item {obj.id}: {str(e)}")

            try:
                quantity = float(obj.quantity or 0)
                debited = self.get_debited_quantity(obj)
                allotted = self.get_allotted_quantity(obj)
                available = quantity - debited - allotted
                return max(available, 0.0)
            except Exception:
                return 0.0

    def get_available_value(self, obj):
        """
        Return calculated available value based on restriction logic.

        This ensures available_value in the API response matches balance_cif_fc.
        Both use the same underlying calculation (available_value_calculated).
        """
        return obj.available_value_calculated

    def get_debited_quantity(self, obj):
        """
        Calculate debited quantity at runtime.
        Includes BOE debits + ARO allotments (treated as debits).
        """
        from core.scripts.calculate_balance import calculate_debited_quantity
        try:
            result = calculate_debited_quantity(obj)
            return float(result) if result is not None else 0.0
        except Exception:
            return 0.0

    def get_debited_value(self, obj):
        """
        Calculate debited value at runtime.
        Includes BOE debits + ARO allotments (treated as debits).
        """
        from core.scripts.calculate_balance import calculate_debited_value
        try:
            result = calculate_debited_value(obj)
            return float(result) if result is not None else 0.0
        except Exception:
            return 0.0

    def get_allotted_quantity(self, obj):
        """
        Calculate allotted quantity at runtime.
        Only includes AT allotments without BOE.
        """
        from core.scripts.calculate_balance import calculate_allotted_quantity
        try:
            result = calculate_allotted_quantity(obj)
            return float(result) if result is not None else 0.0
        except Exception:
            return 0.0

    def get_allotted_value(self, obj):
        """
        Calculate allotted value at runtime.
        Only includes AT allotments without BOE.
        """
        from core.scripts.calculate_balance import calculate_allotted_value
        try:
            result = calculate_allotted_value(obj)
            return float(result) if result is not None else 0.0
        except Exception:
            return 0.0

    def get_balance_cif_fc(self, obj):
        """
        ITEM-LEVEL available CIF FC calculation.

        Uses balance_cif_fc property which calculates:
        - For restricted items: restriction-based calculation
        - For special rows (CIF 0/0.01/0.1): license-level calculation
        - For regular items: item-level calculation (item_credit - item_debit - item_allotment)

        This is different from available_value which uses license-level balance for non-restricted items.
        """
        return obj.balance_cif_fc

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
    transfer_date = serializers.DateField(required=False, allow_null=True, format="%Y-%m-%d",
                                          input_formats=["%Y-%m-%d"])
    transfer_initiation_date = serializers.DateTimeField(required=False, allow_null=True)
    transfer_acceptance_date = serializers.DateTimeField(required=False, allow_null=True)
    cbic_response_date = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = LicenseTransferModel
        fields = "__all__"


class LicensePurchaseSerializer(serializers.ModelSerializer):
    invoice_date = serializers.DateField(required=False, allow_null=True, format="%Y-%m-%d", input_formats=["%Y-%m-%d"])

    class Meta:
        model = LicensePurchase
        fields = "__all__"


class LicenseDetailsSerializer(serializers.ModelSerializer):
    # Explicit DateFields for model.DateField columns
    license_date = serializers.DateField(required=False, allow_null=True, format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    license_expiry_date = serializers.DateField(required=False, allow_null=True, format="%Y-%m-%d",
                                                input_formats=["%Y-%m-%d"])
    registration_date = serializers.DateField(required=False, allow_null=True, format="%Y-%m-%d",
                                              input_formats=["%Y-%m-%d"])
    ledger_date = serializers.DateField(required=False, allow_null=True, format="%Y-%m-%d", input_formats=["%Y-%m-%d"])

    # Annotated fields for FK display
    exporter_name = serializers.CharField(read_only=True, required=False)
    port_name = serializers.CharField(read_only=True, required=False)

    # Property fields
    latest_transfer = serializers.CharField(read_only=True, required=False)
    get_norm_class = serializers.CharField(read_only=True, required=False)
    get_balance_cif = serializers.SerializerMethodField()
    has_tl = serializers.SerializerMethodField()
    has_copy = serializers.SerializerMethodField()

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

        # Parse nested arrays from FormData format (license_documents[0].type)
        if hasattr(data, 'getlist'):
            # It's MultiValueDict (FormData)
            logger.info("Parsing FormData for nested arrays")

            # Extract license_documents from FormData
            doc_dict = {}
            for key in list(data.keys()):
                if key.startswith('license_documents['):
                    # Extract index and field name
                    # Format: license_documents[0].type or license_documents[0].file
                    import re
                    match = re.match(r'license_documents\[(\d+)\]\.(.+)', key)
                    if match:
                        index = int(match.group(1))
                        field_name = match.group(2)

                        if index not in doc_dict:
                            doc_dict[index] = {}

                        doc_dict[index][field_name] = data.get(key)

            # Convert dict to list and create regular dict with parsed data
            if doc_dict:
                license_documents = [doc_dict[i] for i in sorted(doc_dict.keys())]
                logger.info("Parsed %d documents from FormData", len(license_documents))
                for i, doc in enumerate(license_documents):
                    logger.info("Document %d: type=%s, file=%s", i, doc.get('type'), doc.get('file'))

                # Convert MultiValueDict to regular dict for processing
                parsed_data = {}
                for key in data.keys():
                    # Skip the old FormData format keys
                    if not key.startswith('license_documents['):
                        parsed_data[key] = data.get(key)

                # Add parsed license_documents as list
                parsed_data['license_documents'] = license_documents
                data = parsed_data

        # Clean empty strings for boolean fields before validation
        self._clean_boolean_fields(data)

        return super().to_internal_value(data)

    def _clean_boolean_fields(self, data):
        """Convert empty strings to False for boolean fields in nested data."""
        # Boolean fields in main license
        boolean_fields = ['is_audit', 'is_mnm', 'is_not_registered', 'is_null', 'is_au',
                         'is_active', 'is_incomplete', 'is_expired', 'is_individual']

        for field in boolean_fields:
            if field in data and data[field] == '':
                data[field] = False

        # Boolean fields in import_license nested array
        if 'import_license' in data and isinstance(data['import_license'], list):
            for item in data['import_license']:
                if isinstance(item, dict) and 'is_restricted' in item and item['is_restricted'] == '':
                    item['is_restricted'] = False

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

    # helper for M2M items in import rows
    def _calculate_import_quantity(self, license_inst, hs_code_id):
        """
        Calculate import item quantity based on formula:
        Import Quantity = Export Net Quantity × SION Norm Quantity
        """
        from decimal import Decimal
        from core.models import SIONImportModel

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
            logger.warning(f"Failed to calculate import quantity: {str(e)}")

        return Decimal('0')

    def _create_import_item(self, license_inst, payload):
        from license.signals import update_license_on_import_item_change

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
            from core.models import HSCodeModel
            if isinstance(payload['hs_code'], (int, str)):
                try:
                    payload['hs_code'] = HSCodeModel.objects.get(id=payload['hs_code'])
                except (ValueError, HSCodeModel.DoesNotExist):
                    payload['hs_code'] = None

        obj = LicenseImportItemsModel.objects.create(license=license_inst, **payload)
        if isinstance(items, Iterable):
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
            logger.error(f"Failed to auto-link items in _create_import_item for {obj.id}: {str(e)}")

        return obj

    def create(self, validated_data):
        from django.db import transaction

        exports = validated_data.pop("export_license", [])
        imports = validated_data.pop("import_license", [])
        docs = validated_data.pop("license_documents", [])
        transfers = validated_data.pop("transfers", [])
        purchases = validated_data.pop("purchases", [])

        # Wrap entire license creation in atomic transaction
        # If any error occurs, the entire license creation will be rolled back
        with transaction.atomic():
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
                    from core.models import SionNormClassModel
                    if isinstance(e['norm_class'], (int, str)):
                        try:
                            e['norm_class'] = SionNormClassModel.objects.get(id=e['norm_class'])
                        except (ValueError, SionNormClassModel.DoesNotExist):
                            e['norm_class'] = None

                if 'hs_code' in e and e['hs_code']:
                    from core.models import HSCodeModel
                    if isinstance(e['hs_code'], (int, str)):
                        try:
                            e['hs_code'] = HSCodeModel.objects.get(id=e['hs_code'])
                        except (ValueError, HSCodeModel.DoesNotExist):
                            e['hs_code'] = None

                LicenseExportItemModel.objects.create(license=instance, **e)

            # Create import items - signal is called inside _create_import_item
            for i in imports:
                self._create_import_item(instance, i)

            for d in docs:
                # Validate required fields
                if d.get('type') and d.get('file'):
                    LicenseDocumentModel.objects.create(license=instance, **d)
            for t in transfers:
                LicenseTransferModel.objects.create(license=instance, **t)
            for p in purchases:
                LicensePurchase.objects.create(license=instance, **p)

        return instance

    def update(self, instance, validated_data):
        # DEBUG: Log what we receive
        import logging
        logger = logging.getLogger(__name__)
        logger.info("="*50)
        logger.info("UPDATE called with validated_data keys: %s", list(validated_data.keys()))

        exports = validated_data.pop("export_license", None)
        imports = validated_data.pop("import_license", None)
        docs = validated_data.pop("license_documents", None)
        transfers = validated_data.pop("transfers", None)
        purchases = validated_data.pop("purchases", None)

        # DEBUG: Log license_documents
        logger.info("license_documents extracted: %s", docs)
        if docs:
            logger.info("Number of documents: %s", len(docs))
            for i, doc in enumerate(docs):
                logger.info("Document %s: keys=%s, type=%s, file=%s", i, list(doc.keys()), doc.get('type'), doc.get('file'))

        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()

        if exports is not None:
            from django.db import transaction

            with transaction.atomic():
                # Build mapping of ID to existing export items
                existing_items = {item.id: item for item in instance.export_license.all()}
                processed_ids = set()

                # Update or create export items
                for e in exports:
                    item_id = e.get('id')

                    # Remove form-only fields that are not part of the model
                    e.pop('start_serial_number', None)
                    e.pop('end_serial_number', None)

                    # Convert empty strings and None to 0 for required NOT NULL fields
                    for field in ['net_quantity', 'old_quantity']:
                        if field in e and (e[field] == '' or e[field] is None):
                            e[field] = 0

                    # Convert empty strings to None for optional decimal fields
                    for field in ['fob_fc', 'fob_inr', 'fob_exchange_rate', 'value_addition', 'cif_fc', 'cif_inr']:
                        if field in e and e[field] == '':
                            e[field] = None

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

                # Delete items that are no longer in the payload
                for item_id, item in existing_items.items():
                    if item_id not in processed_ids:
                        item.delete()

        if imports is not None:
            from django.db import transaction
            from license.signals import update_license_on_import_item_change
            import logging
            logger = logging.getLogger(__name__)

            # Use transaction to ensure atomicity
            with transaction.atomic():
                # Get all existing import items
                existing_items = list(instance.import_license.all())
                existing_items_by_id = {item.id: item for item in existing_items}
                existing_items_by_serial = {item.serial_number: item for item in existing_items}
                processed_ids = set()
                processed_serials = set()

                logger.debug(f"Existing items by ID: {list(existing_items_by_id.keys())}")
                logger.debug(f"Existing items by serial: {list(existing_items_by_serial.keys())}")
                logger.debug(f"Incoming imports count: {len(imports)}")

                # Update or create import items
                for idx, i in enumerate(imports):
                    item_id = i.get('id')
                    serial_number = i.get('serial_number')
                    items_list = i.pop('items', [])
                    description = i.get('description')
                    hs_code = i.get('hs_code')

                    # Remove fields that don't exist in LicenseImportItemsModel
                    i.pop('duty_type', None)  # This field only exists in export items

                    obj = None

                    logger.debug(f"Processing import #{idx}: id={item_id}, serial={serial_number}")

                    # First, try to match by ID
                    if item_id and item_id in existing_items_by_id:
                        logger.debug(f"  -> Matched by ID {item_id}")
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

                        # Update M2M relationship
                        if isinstance(items_list, list):
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
                            logger.error(f"Failed to auto-link items for import item {obj.id}: {str(e)}")

                        processed_ids.add(obj.id)
                        processed_serials.add(obj.serial_number)
                    # If no ID match, try to match by serial_number (for items without ID or wrong ID)
                    elif serial_number and serial_number in existing_items_by_serial:
                        # Check if this serial was already processed (avoid duplicates in same batch)
                        if serial_number in processed_serials:
                            logger.debug(f"  -> Skipping: serial {serial_number} already processed")
                            continue
                        logger.debug(f"  -> Matched by serial {serial_number}")

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

                        # Update M2M relationship
                        if isinstance(items_list, list):
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
                            logger.error(f"Failed to auto-link items for import item {obj.id}: {str(e)}")

                        processed_ids.add(obj.id)
                        processed_serials.add(obj.serial_number)
                    else:
                        # Check if this serial was already processed (avoid duplicates in same batch)
                        if serial_number and serial_number in processed_serials:
                            logger.debug(f"  -> Skipping: creating duplicate serial {serial_number}")
                            continue

                        logger.debug(f"  -> Creating new item with serial {serial_number}")
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
                        logger.debug(f"  -> Created item with ID {obj.id}")

                    # Save description to ProductDescriptionModel
                    if description and hs_code:
                        ProductDescriptionModel.objects.get_or_create(
                            hs_code_id=hs_code if isinstance(hs_code, int) else hs_code,
                            product_description=description
                        )

                # Delete items that are no longer in the payload
                for item in existing_items:
                    if item.id not in processed_ids:
                        item.delete()

        if docs is not None:
            from django.db import transaction

            with transaction.atomic():
                # Build mapping of ID to existing documents
                existing_items = {item.id: item for item in instance.license_documents.all()}
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

                    logger.info(f"Processing document {idx}: id={item_id}, type={d.get('type')}, file type={type(d.get('file'))}, file={d.get('file')}")

                    if item_id and item_id in existing_items:
                        # Keep existing document - mark as processed so it won't be deleted
                        obj = existing_items[item_id]
                        logger.info(f"  -> Updating existing document ID={item_id}")

                        # Update type if changed
                        if 'type' in d and d['type']:
                            obj.type = d['type']
                            logger.info(f"  -> Updated type to {d['type']}")

                        # Update file only if new File object provided
                        if 'file' in d and d['file'] and not isinstance(d['file'], str):
                            obj.file = d['file']
                            logger.info(f"  -> Updated file to {d['file']}")

                        obj.save()
                        processed_ids.add(item_id)
                    else:
                        # Create new document
                        logger.info(f"  -> Creating new document")
                        d.pop('id', None)
                        d.pop('license', None)

                        # Only create if type and file are present (and file is a File object, not URL string)
                        file_obj = d.get('file')
                        has_type = bool(d.get('type'))
                        has_file = bool(file_obj)
                        is_file_obj = has_file and not isinstance(file_obj, str)

                        logger.info(f"  -> Validation: has_type={has_type}, has_file={has_file}, is_file_obj={is_file_obj}")

                        if d.get('type') and d.get('file') and not isinstance(d.get('file'), str):
                            obj = LicenseDocumentModel.objects.create(license=instance, **d)
                            processed_ids.add(obj.id)
                            logger.info(f"  -> Created new document with ID={obj.id}")
                        else:
                            logger.warning(f"  -> Skipped creating document: validation failed")

                # Delete documents that were removed from the form (not in payload)
                for item_id, item in existing_items.items():
                    if item_id not in processed_ids:
                        item.delete()

        if transfers is not None:
            from django.db import transaction

            with transaction.atomic():
                # Build mapping of ID to existing transfers
                existing_items = {item.id: item for item in instance.transfers.all()}
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
            from django.db import transaction

            with transaction.atomic():
                # Build mapping of ID to existing purchases
                existing_items = {item.id: item for item in instance.purchases.all()}
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

        return instance
