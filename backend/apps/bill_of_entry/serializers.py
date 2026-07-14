# bill_of_entry/serializers.py
from django.db import transaction as db_transaction
from rest_framework import serializers

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails


class RowDetailsSerializer(serializers.ModelSerializer):
    """Serializer for BOE row details (nested items)"""
    # Make id writable so it can be passed during updates
    id = serializers.IntegerField(required=False)
    license_number = serializers.CharField(
        source="sr_number.license.license_number", read_only=True
    )
    item_description = serializers.CharField(
        source="sr_number.description", read_only=True
    )
    hs_code = serializers.CharField(
        source="sr_number.hs_code.hs_code", read_only=True
    )
    item_serial_number = serializers.IntegerField(
        source="sr_number.serial_number", read_only=True
    )
    condition_type = serializers.CharField(
        source="sr_number.condition_type", read_only=True
    )
    purchase_status = serializers.SerializerMethodField()

    def get_purchase_status(self, obj):
        """Get purchase status code safely"""
        if (
            obj.sr_number
            and obj.sr_number.license
            and obj.sr_number.license.purchase_status
        ):
            return obj.sr_number.license.purchase_status.code
        return None

    class Meta:
        model = RowDetails
        fields = [
            "id",
            "sr_number",
            "cif_inr",
            "cif_fc",
            "qty",
            "is_frozen",
            "is_dispute",
            "license_number",
            "item_description",
            "hs_code",
            "item_serial_number",
            "condition_type",
            "purchase_status",
        ]
        read_only_fields = ["is_frozen", "is_dispute"]


class BillOfEntrySerializer(serializers.ModelSerializer):
    """Serializer for Bill of Entry with nested items"""
    item_details = RowDetailsSerializer(many=True, read_only=False, required=False)

    # Read-only computed fields
    total_inr = serializers.DecimalField(
        source="get_total_inr",
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )
    total_fc = serializers.DecimalField(
        source="get_total_fc",
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )
    total_quantity = serializers.DecimalField(
        source="get_total_quantity",
        max_digits=15,
        decimal_places=3,
        read_only=True,
    )
    licenses = serializers.CharField(source="get_licenses", read_only=True)
    unit_price = serializers.DecimalField(
        source="get_unit_price",
        max_digits=15,
        decimal_places=3,
        read_only=True,
    )

    # Display fields for foreign keys
    port_name = serializers.CharField(source="port.name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = BillOfEntryModel
        fields = [
            "id",
            "company",
            "company_name",
            "bill_of_entry_number",
            "bill_of_entry_date",
            "port",
            "port_name",
            "allotment",
            "exchange_rate",
            "product_name",
            "invoice_no",
            "invoice_date",
            "is_fetch",
            "boe_pdf_copy",
            "failed",
            "appraisement",
            "ooc_date",
            "cha",
            "comments",
            "item_details",
            "total_inr",
            "total_fc",
            "total_quantity",
            "licenses",
            "unit_price",
            "created_on",
            "modified_on",
            "created_by",
            "modified_by",
        ]
        read_only_fields = ["created_on", "modified_on", "created_by", "modified_by"]

    def to_internal_value(self, data):
        """Parse JSON strings or flattened FormData from multipart/form-data"""
        import json
        import re

        data = data.copy() if hasattr(data, "copy") else dict(data)

        if "item_details" in data and isinstance(data["item_details"], str):
            try:
                data["item_details"] = json.loads(data["item_details"])
            except (json.JSONDecodeError, TypeError):
                pass

        if hasattr(data, "getlist"):
            nested_items = {}
            for key in list(data.keys()):
                match = re.match(r"item_details\[(\d+)\]\.(.+)", key)
                if match:
                    index = int(match.group(1))
                    field_name = match.group(2)
                    if index not in nested_items:
                        nested_items[index] = {}
                    nested_items[index][field_name] = data[key]

            if nested_items:
                data["item_details"] = [
                    nested_items[i] for i in sorted(nested_items.keys())
                ]

        return super().to_internal_value(data)

    def create(self, validated_data):
        """Create BOE with nested item details"""
        item_details_data = validated_data.pop("item_details", [])
        allotment_data = validated_data.pop("allotment", [])

        boe_number = validated_data.pop("bill_of_entry_number")
        boe_date = validated_data.pop("bill_of_entry_date", None)
        port = validated_data.pop("port", None)
        defaults = validated_data.copy()
        if port is not None:
            defaults["port"] = port
        boe, _ = BillOfEntryModel.objects.update_or_create(
            bill_of_entry_number=boe_number,
            bill_of_entry_date=boe_date,
            defaults=defaults,
        )

        if allotment_data:
            boe.allotment.set(allotment_data)
            for allotment in allotment_data:
                allotment.is_boe = True
                allotment.save()

        for item_data in item_details_data:
            RowDetails.objects.create(bill_of_entry=boe, **item_data)

        return boe

    def update(self, instance, validated_data):
        """Update BOE with nested item details"""
        item_details_data = validated_data.pop("item_details", None)
        allotment_data = validated_data.pop("allotment", None)

        with db_transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

        if allotment_data is not None and len(allotment_data) > 0:
            old_allotment_ids = set(instance.allotment.values_list("id", flat=True))
            instance.allotment.set(allotment_data)
            new_allotment_ids = {a.id for a in allotment_data}

            for allotment in allotment_data:
                if allotment.id not in old_allotment_ids:
                    allotment.is_boe = True
                    allotment.save()

            removed_allotment_ids = old_allotment_ids - new_allotment_ids
            if removed_allotment_ids:
                from apps.allotment.models import AllotmentModel

                for allotment_id in removed_allotment_ids:
                    try:
                        allotment = AllotmentModel.objects.get(id=allotment_id)
                        if not allotment.bill_of_entry.exclude(id=instance.id).exists():
                            allotment.is_boe = False
                            allotment.save()
                    except AllotmentModel.DoesNotExist:
                        pass

        if item_details_data is not None:
            updated_item_ids = []

            for item_data in item_details_data:
                sr_number = item_data.get("sr_number")
                if isinstance(sr_number, dict):
                    sr_number_id = sr_number.get("id")
                elif hasattr(sr_number, "id"):
                    sr_number_id = sr_number.id
                else:
                    sr_number_id = sr_number

                if not sr_number_id:
                    continue

                transaction_type = item_data.get("transaction_type", "D")
                item_id = item_data.get("id")

                item_data_clean = {
                    k: v
                    for k, v in item_data.items()
                    if k not in ["id", "sr_number", "license_number", "item_description", "hs_code"]
                }

                if item_id:
                    try:
                        item_instance = RowDetails.objects.get(
                            id=item_id, bill_of_entry=instance
                        )
                        if item_instance.is_frozen:
                            updated_item_ids.append(item_id)
                            continue
                        for key, value in item_data_clean.items():
                            setattr(item_instance, key, value)
                        item_instance.sr_number_id = sr_number_id
                        item_instance.save()
                        updated_item_ids.append(item_id)
                    except RowDetails.DoesNotExist:
                        item_data_clean["sr_number_id"] = sr_number_id
                        item_instance, _ = RowDetails.objects.update_or_create(
                            bill_of_entry=instance,
                            sr_number_id=sr_number_id,
                            transaction_type=transaction_type,
                            defaults=item_data_clean,
                        )
                        updated_item_ids.append(item_instance.id)
                else:
                    existing = RowDetails.objects.filter(
                        bill_of_entry=instance,
                        sr_number_id=sr_number_id,
                        transaction_type=transaction_type,
                    ).first()
                    if existing and existing.is_frozen:
                        updated_item_ids.append(existing.id)
                        continue
                    item_data_clean["sr_number_id"] = sr_number_id
                    item_instance, _ = RowDetails.objects.update_or_create(
                        bill_of_entry=instance,
                        sr_number_id=sr_number_id,
                        transaction_type=transaction_type,
                        defaults=item_data_clean,
                    )
                    updated_item_ids.append(item_instance.id)

            # Pre-seed updated_item_ids with ALL frozen row ids so they are never swept
            frozen_ids = list(
                RowDetails.objects.filter(bill_of_entry=instance, is_frozen=True)
                .values_list("id", flat=True)
            )
            updated_item_ids.extend(frozen_ids)
            RowDetails.objects.filter(bill_of_entry=instance, is_frozen=False).exclude(
                id__in=updated_item_ids
            ).delete()

            # Clear cached properties to force recalculation
            for cached_attr in ("item_details_cached", "get_licenses"):
                if hasattr(instance, cached_attr):
                    try:
                        delattr(instance, cached_attr)
                    except AttributeError:
                        pass

        return instance

    def to_representation(self, instance):
        """Add computed fields and auto-calculate exchange_rate when stored value is 0."""
        data = super().to_representation(instance)

        # Auto-calculate exchange_rate from row totals when stored value is 0 or null
        exc = data.get("exchange_rate")
        if not exc or float(exc) == 0:
            total_fc = float(data.get("total_fc") or 0)
            total_inr = float(data.get("total_inr") or 0)
            if total_fc > 0:
                data["exchange_rate"] = round(total_inr / total_fc, 4)

        # Add allotment information if available
        allotments = instance.allotment.all()
        if allotments:
            data["allotments"] = [
                {
                    "id": allot.id,
                    "item_name": allot.item_name,
                    "invoice": allot.invoice,
                    "required_quantity": str(allot.required_quantity),
                    "estimated_arrival_date": allot.estimated_arrival_date,
                    "company": allot.company.name if allot.company else None,
                }
                for allot in allotments
            ]

        return data
