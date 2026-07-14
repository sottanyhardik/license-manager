# trade/serializers.py
import logging

from django.db import transaction
from rest_framework import serializers

from .models import (
    LicenseTrade,
    LicenseTradeLine,
    IncentiveTradeLine,
    LicenseTradePayment,
)

logger = logging.getLogger(__name__)


class LicenseTradePaymentSerializer(serializers.ModelSerializer):
    """Serializer for payment settlements."""

    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = LicenseTradePayment
        fields = ("id", "date", "amount", "note")


class LicenseTradeLineSerializer(serializers.ModelSerializer):
    """Serializer for trade line items."""

    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    sr_number_label = serializers.SerializerMethodField()
    condition_type = serializers.CharField(
        source="sr_number.condition_type", read_only=True, allow_blank=True, default=""
    )
    computed_amount = serializers.SerializerMethodField()

    def to_internal_value(self, data):
        """Remove empty string fields to prevent overwriting existing values with zeros."""
        data = data.copy() if hasattr(data, "copy") else dict(data)

        # Extract sr_number ID if it's an object (from frontend HybridSelect)
        if "sr_number" in data and isinstance(data["sr_number"], dict):
            data["sr_number"] = data["sr_number"].get("id") or data["sr_number"].get("pk")

        fields_to_check = [
            "qty_kg", "rate_inr_per_kg", "cif_fc", "exc_rate",
            "cif_inr", "fob_inr", "pct", "amount_inr",
        ]
        for field in fields_to_check:
            if field in data and data[field] == "":
                del data[field]

        return super().to_internal_value(data)

    class Meta:
        model = LicenseTradeLine
        fields = (
            "id", "sr_number", "sr_number_label", "condition_type", "description",
            "hsn_code", "mode", "qty_kg", "rate_inr_per_kg", "cif_fc", "exc_rate",
            "cif_inr", "fob_inr", "pct", "amount_inr", "computed_amount",
        )

    def get_sr_number_label(self, obj):
        if obj.sr_number:
            license_number = (
                obj.sr_number.license.license_number
                if obj.sr_number.license
                else "Unknown"
            )
            return f"{license_number} - SR {obj.sr_number.serial_number}"
        return None

    def get_computed_amount(self, obj):
        return float(obj.compute_amount())


class IncentiveTradeLineSerializer(serializers.ModelSerializer):
    """Serializer for incentive trade line items."""

    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    incentive_license_label = serializers.SerializerMethodField()

    class Meta:
        model = IncentiveTradeLine
        fields = (
            "id", "incentive_license", "incentive_license_label",
            "license_value", "rate_pct", "amount_inr",
        )

    def get_incentive_license_label(self, obj):
        if obj.incentive_license:
            return f"{obj.incentive_license.license_type} - {obj.incentive_license.license_number}"
        return None


def _sync_nested(instance, model, incoming_list, fk_field, treat_empty_list_as_delete=False):
    """
    Sync a nested list of items against the DB for the given FK.

    - Items with an existing id are updated in place.
    - Items without id (or id not found) are created.
    - Existing items whose id is absent from incoming_list are deleted,
      unless treat_empty_list_as_delete is False and incoming_list is empty.
    """
    if incoming_list is None:
        return

    incoming_ids = set()
    for item in incoming_list:
        rid = item.get("id") or item.get("pk")
        if rid not in (None, ""):
            try:
                incoming_ids.add(int(rid))
            except (ValueError, TypeError):
                pass

    existing_qs = model.objects.filter(**{fk_field: instance})
    existing_map = {obj.id: obj for obj in existing_qs}

    if incoming_ids:
        model.objects.filter(**{fk_field: instance}).exclude(id__in=incoming_ids).delete()
    elif treat_empty_list_as_delete:
        model.objects.filter(**{fk_field: instance}).delete()

    for item in incoming_list:
        raw_id = item.get("id") or item.get("pk")
        try:
            item_id = int(raw_id) if raw_id not in (None, "") else None
        except (ValueError, TypeError):
            item_id = None

        if item_id and item_id in existing_map:
            obj = existing_map[item_id]
            for k, v in item.items():
                if k not in ("id", "pk") and hasattr(obj, k):
                    setattr(obj, k, v)
            obj.save()
        else:
            create_data = {k: v for k, v in item.items() if k not in ("id", "pk")}
            model.objects.create(**{fk_field: instance}, **create_data)


class LicenseTradeSerializer(serializers.ModelSerializer):
    """Nested serializer for LicenseTrade with lines and payments."""

    lines = LicenseTradeLineSerializer(many=True, required=False)
    incentive_lines = IncentiveTradeLineSerializer(many=True, required=False)
    payments = LicenseTradePaymentSerializer(many=True, required=False)

    # Display fields
    from_company_label = serializers.CharField(source="from_company.name", read_only=True)
    to_company_label = serializers.CharField(source="to_company.name", read_only=True)
    boe_label = serializers.CharField(source="boe.boe_number", read_only=True, allow_null=True)
    direction_label = serializers.CharField(source="get_direction_display", read_only=True)
    license_type_label = serializers.CharField(source="get_license_type_display", read_only=True)
    incentive_license = serializers.SerializerMethodField()

    # Computed fields
    paid_or_received = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    due_amount = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)

    # Linked trade fields
    auto_create_paired = serializers.BooleanField(write_only=True, required=False, default=False)
    linked_trade_info = serializers.SerializerMethodField(read_only=True)

    def get_linked_trade_info(self, obj):
        lt = obj.linked_trade
        if not lt:
            lt = obj.paired_trades.first()
        if not lt:
            return None
        return {
            "id": lt.id,
            "direction": lt.direction,
            "direction_label": lt.get_direction_display(),
            "invoice_number": lt.invoice_number,
            "total_amount": str(lt.total_amount),
            "paid_or_received": str(lt.paid_or_received),
            "due_amount": str(lt.due_amount),
        }

    def to_internal_value(self, data):
        """Parse JSON strings OR flattened FormData from multipart/form-data."""
        import json
        import re

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("to_internal_value called. Data keys: %s", list(data.keys()))

        raw_data = data
        if hasattr(data, "getlist"):
            data = {key: raw_data.get(key) for key in raw_data.keys()}
        else:
            data = data.copy() if hasattr(data, "copy") else dict(data)

        for field in ["lines", "incentive_lines", "payments"]:
            if field in data:
                if isinstance(data[field], str):
                    try:
                        parsed = json.loads(data[field])
                        data[field] = parsed
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.error("Failed to parse %s as JSON: %s", field, str(e))
                        raise serializers.ValidationError({
                            field: f"Invalid JSON format: {str(e)}"
                        })

        # Flattened FormData format: "lines[0].field"
        if hasattr(raw_data, "keys"):
            nested_fields = {"lines": {}, "incentive_lines": {}, "payments": {}}

            for key in list(raw_data.keys()):
                for field_name in nested_fields.keys():
                    match = re.match(rf"{field_name}\[(\d+)\][\.\[](.+?)[\]\.]?$", key)
                    if match:
                        index = int(match.group(1))
                        sub_field = match.group(2).replace("]", "").replace("[", ".")
                        if index not in nested_fields[field_name]:
                            nested_fields[field_name][index] = {}
                        nested_fields[field_name][index][sub_field] = raw_data[key]

            for field_name, items in nested_fields.items():
                if items:
                    data[field_name] = [items[i] for i in sorted(items.keys())]

        return super().to_internal_value(data)

    def validate(self, data):
        """Validate that at least one line (regular or incentive) is present."""
        lines = data.get("lines", [])
        incentive_lines = data.get("incentive_lines", [])

        if not lines and not incentive_lines:
            raise serializers.ValidationError({
                "lines": "At least one trade line or incentive line must be defined.",
                "incentive_lines": "At least one trade line or incentive line must be defined.",
            })
        return data

    def get_incentive_license(self, obj):
        """Return all license numbers (DFIA and Incentive) comma-separated."""
        license_numbers = set()
        for line in obj.lines.all():
            if line.sr_number and line.sr_number.license:
                license_numbers.add(line.sr_number.license.license_number)
        for line in obj.incentive_lines.all():
            if line.incentive_license:
                license_numbers.add(line.incentive_license.license_number)
        return ", ".join(sorted(license_numbers)) if license_numbers else None

    class Meta:
        model = LicenseTrade
        fields = "__all__"

    def to_representation(self, instance):
        """Customize output to include nested company and BOE objects."""
        data = super().to_representation(instance)

        if instance.from_company:
            data["from_company"] = {
                "id": instance.from_company.id,
                "name": instance.from_company.name,
            }

        if instance.to_company:
            data["to_company"] = {
                "id": instance.to_company.id,
                "name": instance.to_company.name,
            }

        if instance.boe:
            data["boe"] = {
                "id": instance.boe.id,
                "bill_of_entry_number": instance.boe.bill_of_entry_number,
            }

        data["linked_trade_id"] = instance.linked_trade_id
        data["linked_trade_info"] = self.get_linked_trade_info(instance)
        return data

    @transaction.atomic
    def create(self, validated_data):
        """Create trade with nested lines and payments inside a single transaction."""
        lines_data = validated_data.pop("lines", [])
        incentive_lines_data = validated_data.pop("incentive_lines", [])
        payments_data = validated_data.pop("payments", [])
        auto_create_paired = validated_data.pop("auto_create_paired", False)

        trade = LicenseTrade.objects.create(**validated_data)
        trade.snapshot_parties()

        for line_data in lines_data:
            line_data.pop("id", None)
            LicenseTradeLine.objects.create(trade=trade, **line_data)

        for line_data in incentive_lines_data:
            line_data.pop("id", None)
            IncentiveTradeLine.objects.create(trade=trade, **line_data)

        for payment_data in payments_data:
            payment_data.pop("id", None)
            LicenseTradePayment.objects.create(trade=trade, **payment_data)

        trade.recompute_totals()
        trade.refresh_from_db()

        if trade.boe and trade.invoice_number:
            trade.boe.invoice_no = trade.invoice_number
            trade.boe.save(update_fields=["invoice_no"])

        if auto_create_paired and trade.direction in (
            "PURCHASE", "SALE", "COMMISSION_PURCHASE", "COMMISSION_SALE"
        ):
            from apps.trade.models import get_next_invoice_number

            direction_map = {
                "PURCHASE": "SALE",
                "SALE": "PURCHASE",
                "COMMISSION_PURCHASE": "COMMISSION_SALE",
                "COMMISSION_SALE": "COMMISSION_PURCHASE",
            }
            paired_direction = direction_map[trade.direction]
            paired_from = trade.to_company
            paired_to = trade.from_company

            paired_invoice = get_next_invoice_number(
                direction=paired_direction,
                company_name=paired_from.name if paired_from else "",
                invoice_date=trade.invoice_date,
            )

            paired_trade = LicenseTrade.objects.create(
                direction=paired_direction,
                license_type=trade.license_type,
                incentive_license=trade.incentive_license,
                boe=trade.boe,
                from_company=paired_from,
                to_company=paired_to,
                invoice_number=paired_invoice,
                invoice_date=trade.invoice_date,
                remarks=trade.remarks,
                linked_trade=trade,
                created_by=trade.created_by,
            )
            paired_trade.snapshot_parties()

            for line in trade.lines.all():
                LicenseTradeLine.objects.create(
                    trade=paired_trade,
                    sr_number=line.sr_number,
                    description=line.description,
                    hsn_code=line.hsn_code,
                    mode=line.mode,
                    qty_kg=line.qty_kg,
                    rate_inr_per_kg=line.rate_inr_per_kg,
                    cif_fc=line.cif_fc,
                    exc_rate=line.exc_rate,
                    cif_inr=line.cif_inr,
                    fob_inr=line.fob_inr,
                    pct=line.pct,
                    amount_inr=line.amount_inr,
                )

            for line in trade.incentive_lines.all():
                IncentiveTradeLine.objects.create(
                    trade=paired_trade,
                    incentive_license=line.incentive_license,
                    license_value=line.license_value,
                    rate_pct=line.rate_pct,
                    amount_inr=line.amount_inr,
                )

            paired_trade.recompute_totals()
            paired_trade.refresh_from_db()

            LicenseTrade.objects.filter(pk=trade.pk).update(linked_trade=paired_trade)
            trade.refresh_from_db()

        return trade

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update trade with nested lines and payments inside a single transaction."""
        lines_data = validated_data.pop("lines", None)
        incentive_lines_data = validated_data.pop("incentive_lines", None)
        payments_data = validated_data.pop("payments", None)
        validated_data.pop("auto_create_paired", None)

        old_boe = instance.boe

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        instance.snapshot_parties()

        if lines_data is not None:
            _sync_nested(instance, LicenseTradeLine, lines_data, fk_field="trade")

        if incentive_lines_data is not None:
            _sync_nested(instance, IncentiveTradeLine, incentive_lines_data, fk_field="trade")

        if payments_data is not None:
            _sync_nested(instance, LicenseTradePayment, payments_data, fk_field="trade")

        instance.recompute_totals()
        instance.refresh_from_db()

        if old_boe and old_boe != instance.boe:
            if old_boe.invoice_no == instance.invoice_number:
                old_boe.invoice_no = None
                old_boe.save(update_fields=["invoice_no"])

        if instance.boe and instance.invoice_number:
            instance.boe.invoice_no = instance.invoice_number
            instance.boe.save(update_fields=["invoice_no"])

        return instance


class TradeLineSimpleSerializer(serializers.ModelSerializer):
    """Simple serializer for trade lines without nested data."""

    sr_number_label = serializers.CharField(source="sr_number.__str__", read_only=True)
    mode_label = serializers.CharField(source="get_mode_display", read_only=True)

    class Meta:
        model = LicenseTradeLine
        fields = "__all__"
