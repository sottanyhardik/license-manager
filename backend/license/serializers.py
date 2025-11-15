# license/serializers.py
from datetime import date, datetime, time
from typing import Any, Dict, Iterable

from rest_framework import serializers

from core.models import ItemNameModel
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
    class Meta:
        model = LicenseExportItemModel
        fields = "__all__"


class LicenseImportItemSerializer(serializers.ModelSerializer):
    items = serializers.PrimaryKeyRelatedField(many=True, queryset=ItemNameModel.objects.all(), required=False)
    license_date = serializers.DateField(source="license.license_date", read_only=True, format="%Y-%m-%d")
    license_expiry = serializers.DateField(source="license.license_expiry_date", read_only=True, format="%Y-%m-%d")

    class Meta:
        model = LicenseImportItemsModel
        fields = "__all__"


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

    export_license = LicenseExportItemSerializer(many=True, required=False)
    import_license = LicenseImportItemSerializer(many=True, required=False)

    # license_documents = LicenseDocumentSerializer(many=True, required=False)
    # transfers = LicenseTransferSerializer(many=True, required=False)
    # purchases = LicensePurchaseSerializer(many=True, required=False)

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

        def walk(obj):
            if isinstance(obj, dict):
                return {k: walk(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [walk(v) for v in obj]
            return _safe_iso(obj)

        return walk(rep)

    # helper for M2M items in import rows
    def _create_import_item(self, license_inst, payload):
        items = payload.pop("items", [])
        obj = LicenseImportItemsModel.objects.create(license=license_inst, **payload)
        if isinstance(items, Iterable):
            obj.items.set(items)
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
            instance.export_license.all().delete()
            for e in exports:
                LicenseExportItemModel.objects.create(license=instance, **e)

        if imports is not None:
            instance.import_license.all().delete()
            for i in imports:
                self._create_import_item(instance, i)

        if docs is not None:
            instance.license_documents.all().delete()
            for d in docs:
                LicenseDocumentModel.objects.create(license=instance, **d)

        if transfers is not None:
            instance.transfers.all().delete()
            for t in transfers:
                LicenseTransferModel.objects.create(license=instance, **t)

        if purchases is not None:
            instance.purchases.all().delete()
            for p in purchases:
                LicensePurchase.objects.create(license=instance, **p)

        return instance
