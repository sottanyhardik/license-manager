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

            # Add restriction information if available
            if item.restriction_percentage and item.restriction_percentage > 0:
                item_info['restriction_percentage'] = float(item.restriction_percentage)
            else:
                item_info['restriction_percentage'] = None

            # Add sion_norm_class information if available
            if item.sion_norm_class:
                item_info['sion_norm_class'] = {
                    'id': item.sion_norm_class.id,
                    'norm_class': item.sion_norm_class.norm_class,
                    'description': item.sion_norm_class.description
                }
            else:
                item_info['sion_norm_class'] = None

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
        CENTRALIZED available_value calculation - uses available_value_calculated property.

        This is the SINGLE SOURCE OF TRUTH for available value.
        The property handles:
        - is_restricted = True OR items have restriction_percentage > 0:
          Uses restriction-based calculation (2%, 3%, 5%, 10% etc.)
          Formula: (License Export CIF × restriction_percentage / 100) - (debits + allotments)
        - Otherwise: Uses license.balance_cif (shared across all non-restricted items)

        DO NOT add custom calculation logic here - always delegate to the model property.
        """
        return obj.available_value_calculated

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

    # Nested serializers - separate for read/write to avoid validation issues
    export_license_read = LicenseExportItemSerializer(source='export_license', many=True, read_only=True)
    import_license_read = LicenseImportItemSerializer(source='import_license', many=True, read_only=True)

    export_license = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)
    import_license = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)

    license_documents = LicenseDocumentSerializer(many=True, required=False)

    class Meta:
        model = LicenseDetailsModel
        fields = "__all__"
        read_only_fields = ("created_by", "modified_by", "created_on", "modified_on")

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
            rep['license_documents'] = []
        else:
            # Detail view - rename the read-only fields back to their original names for frontend compatibility
            if 'export_license_read' in rep:
                rep['export_license'] = rep.pop('export_license_read')
            if 'import_license_read' in rep:
                rep['import_license'] = rep.pop('import_license_read')

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

    # helper for M2M items in import rows
    def _create_import_item(self, license_inst, payload):
        items = payload.pop("items", [])
        description = payload.get("description")
        hs_code = payload.get("hs_code")

        # Convert empty strings to None for decimal/numeric fields
        for field in ['serial_number', 'quantity', 'cif_fc', 'cif_inr']:
            if field in payload and payload[field] == '':
                payload[field] = None

        obj = LicenseImportItemsModel.objects.create(license=license_inst, **payload)
        if isinstance(items, Iterable):
            obj.items.set(items)

        # Save description to ProductDescriptionModel if both description and hs_code exist
        if description and hs_code:
            ProductDescriptionModel.objects.get_or_create(
                hs_code=hs_code,
                product_description=description
            )

        return obj

    def create(self, validated_data):
        exports = validated_data.pop("export_license", [])
        imports = validated_data.pop("import_license", [])
        docs = validated_data.pop("license_documents", [])
        transfers = validated_data.pop("transfers", [])
        purchases = validated_data.pop("purchases", [])

        instance = LicenseDetailsModel.objects.create(**validated_data)

        for e in exports:
            # Remove form-only fields that are not part of the model
            e.pop('start_serial_number', None)
            e.pop('end_serial_number', None)

            # Convert empty strings to None for decimal/numeric fields
            for field in ['net_quantity', 'fob_fc', 'fob_inr', 'fob_exchange_rate', 'value_addition', 'cif_fc', 'cif_inr', 'old_quantity']:
                if field in e and e[field] == '':
                    e[field] = None

            LicenseExportItemModel.objects.create(license=instance, **e)
        for i in imports:
            self._create_import_item(instance, i)
        for d in docs:
            LicenseDocumentModel.objects.create(license=instance, **d)
        for t in transfers:
            LicenseTransferModel.objects.create(license=instance, **t)
        for p in purchases:
            LicensePurchase.objects.create(license=instance, **p)

        return instance

    def update(self, instance, validated_data):
        exports = validated_data.pop("export_license", None)
        imports = validated_data.pop("import_license", None)
        docs = validated_data.pop("license_documents", None)
        transfers = validated_data.pop("transfers", None)
        purchases = validated_data.pop("purchases", None)

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

                    # Convert empty strings to None for decimal/numeric fields
                    for field in ['net_quantity', 'fob_fc', 'fob_inr', 'fob_exchange_rate', 'value_addition', 'cif_fc', 'cif_inr', 'old_quantity']:
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

                    obj = None

                    logger.debug(f"Processing import #{idx}: id={item_id}, serial={serial_number}")

                    # First, try to match by ID
                    if item_id and item_id in existing_items_by_id:
                        logger.debug(f"  -> Matched by ID {item_id}")
                        # Update existing item by ID
                        obj = existing_items_by_id[item_id]
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

                # Update or create documents
                for d in docs:
                    item_id = d.get('id')

                    if item_id and item_id in existing_items:
                        # Update existing item by ID
                        obj = existing_items[item_id]
                        for key, value in d.items():
                            if key not in ('id', 'license'):
                                setattr(obj, key, value)
                        obj.save()
                        processed_ids.add(item_id)
                    else:
                        # Create new item
                        d.pop('id', None)  # Remove ID if present
                        d.pop('license', None)  # Remove license field
                        obj = LicenseDocumentModel.objects.create(license=instance, **d)
                        processed_ids.add(obj.id)

                # Delete items that are no longer in the payload
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
