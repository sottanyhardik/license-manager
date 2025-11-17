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
    license_number = serializers.CharField(source="license.license_number", read_only=True)
    license_date = serializers.DateField(source="license.license_date", read_only=True, format="%Y-%m-%d")
    license_expiry_date = serializers.DateField(source="license.license_expiry_date", read_only=True, format="%Y-%m-%d")
    exporter_name = serializers.CharField(source="license.exporter.name", read_only=True)
    hs_code_detail = HSCodeSerializer(source='hs_code', read_only=True)
    hs_code_label = serializers.SerializerMethodField()
    balance_cif_fc = serializers.SerializerMethodField()

    class Meta:
        model = LicenseImportItemsModel
        fields = ['id', 'serial_number', 'license', 'hs_code', 'items', 'description', 'quantity',
                  'old_quantity', 'unit', 'cif_fc', 'cif_inr', 'available_quantity', 'available_value',
                  'debited_quantity', 'debited_value', 'license_number', 'license_date', 'license_expiry_date',
                  'exporter_name', 'hs_code_detail', 'hs_code_label', 'balance_cif_fc']
        # Allow partial updates and skip unique validation during deserialization
        # The update logic in the parent serializer handles uniqueness properly
        extra_kwargs = {
            'license': {'required': False},
            'serial_number': {'required': False}
        }

    def get_hs_code_label(self, obj):
        if obj.hs_code:
            return f"{obj.hs_code.hs_code}"
        return None

    def get_balance_cif_fc(self, obj):
        """Get fresh balance_cif_fc (now a regular property, always fresh)"""
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

    def __init__(self, *args, **kwargs):
        """
        Swap any DateTimeField in self.fields for SafeDateTimeField so that
        if underlying value is a date() it won't crash when DRF calls .utcoffset().
        Preserve common field attributes (format/input_formats/allow_null/required).
        """
        super().__init__(*args, **kwargs)

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

        # Rename the read-only fields back to their original names for frontend compatibility
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

                    if item_id and item_id in existing_items:
                        # Update existing item by ID
                        obj = existing_items[item_id]
                        for key, value in e.items():
                            if key not in ('id', 'license'):
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
                            if key not in ('id', 'license', 'license_date', 'license_expiry'):
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
                            if key not in ('id', 'license', 'license_date', 'license_expiry'):
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
