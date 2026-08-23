"""Write path for LicenseDetailsSerializer (create/update + item helpers).

Extracted verbatim from the 1.2k-LOC LicenseDetailsSerializer class into a mixin
to shrink it. Inherited first in the MRO, so method resolution — and therefore
behaviour — is unchanged. Imports are copied from license.py (not imported from
it) to avoid a circular import.
"""
from collections.abc import Iterable

from apps.core.models import ProductDescriptionModel
from apps.license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseDocumentModel,
    LicenseTransferModel,
    LicensePurchase,
    LicenseBalance,
    LicenseFlags,
    LicenseNotes,
    LicenseOwnership,
)


# Fields that moved from LicenseDetailsModel into OneToOne sub-tables. Reads
# still work via @property shims on the parent, but writes have to be routed
# to the correct sub-row — `setattr(parent, "balance_cif", v)` would AttributeError
# because the property has no setter.
_SUB_TABLE_FIELDS = {
    "balance":   ("balance_cif", "ledger_date"),
    "flags":     ("is_active", "is_audit", "is_mnm", "is_not_registered", "is_null",
                  "is_au", "is_incomplete", "is_expired", "is_individual"),
    "ownership": ("current_owner", "file_transfer_status", "last_ownership_fetch"),
    "notes":     ("user_comment", "condition_sheet", "user_restrictions",
                  "balance_report_notes"),
}


def _pop_sub_table_writes(validated_data):
    """Split validated_data into (parent_data, {related_name: {field: value}}).

    Parent_data is what's safe to setattr / pass to .objects.create on
    LicenseDetailsModel. The returned mapping is keyed by the OneToOne
    related_name on the parent (balance / flags / ownership / notes).
    """
    sub_writes = {rel: {} for rel in _SUB_TABLE_FIELDS}
    for rel, fields in _SUB_TABLE_FIELDS.items():
        for f in fields:
            if f in validated_data:
                sub_writes[rel][f] = validated_data.pop(f)
    return validated_data, sub_writes


def _apply_sub_table_writes(license_instance, sub_writes):
    """Persist the popped moved-field values to the right sub-table rows.

    Sub-rows are guaranteed to exist by the post_save signal on
    LicenseDetailsModel, so `.filter(license_id=...).update(...)` always
    matches exactly one row.
    """
    model_map = {
        "balance": LicenseBalance,
        "flags": LicenseFlags,
        "ownership": LicenseOwnership,
        "notes": LicenseNotes,
    }
    for rel, values in sub_writes.items():
        if values:
            model_map[rel].objects.filter(license_id=license_instance.pk).update(**values)


class LicenseWriteMixin:
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

        # Route moved fields (balance_cif, is_*, current_owner, condition_sheet, …)
        # away from the parent so .create()/setattr won't hit read-only @properties.
        validated_data, sub_writes = _pop_sub_table_writes(validated_data)

        # Wrap entire license creation in atomic transaction
        # If any error occurs, the entire license creation will be rolled back
        with transaction.atomic(), suspend_license_flag_recalc():
            instance = LicenseDetailsModel.objects.create(**validated_data)
            # Sub-rows are created by the post_save signal on the parent;
            # apply moved-field values to them now.
            _apply_sub_table_writes(instance, sub_writes)

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

        # Route moved fields to their sub-tables before touching the parent —
        # setattr on a read-only @property would raise AttributeError.
        validated_data, sub_writes = _pop_sub_table_writes(validated_data)

        # Use atomic transaction with row-level locking to prevent race conditions.
        # Suspend per-item balance recalcs — we flush them once at the end.
        with transaction.atomic(), suspend_license_flag_recalc():
            # Lock the license record for update to prevent concurrent modifications
            locked_instance = LicenseDetailsModel.objects.select_for_update().get(pk=instance.pk)

            # Update the main license fields
            for k, v in validated_data.items():
                setattr(locked_instance, k, v)
            locked_instance.save()

            # Persist moved fields into their sub-rows.
            _apply_sub_table_writes(locked_instance, sub_writes)

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
                            error_msg += "\nThese items are currently being used and cannot be removed from the license. "
                            error_msg += "To delete them, first remove their usage from trades or bills of entry, "
                            error_msg += "or include them in your save to keep them."

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
