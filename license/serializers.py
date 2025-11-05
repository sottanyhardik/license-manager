# license/serializers.py
from rest_framework import serializers
from core.models import ItemNameModel, HSCodeModel, CompanyModel
from .models import LicenseDetailsModel, LicenseImportItemsModel, LicenseExportItemModel


class LicenseExportItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = LicenseExportItemModel
        fields = "__all__"
        read_only_fields = ("id",)


class LicenseImportItemSerializer(serializers.ModelSerializer):
    items = serializers.PrimaryKeyRelatedField(
        many=True, queryset=ItemNameModel.objects.all(), required=False
    )

    class Meta:
        model = LicenseImportItemsModel
        fields = "__all__"
        read_only_fields = ("id",)


class LicenseSerializer(serializers.ModelSerializer):
    import_items = LicenseImportItemSerializer(many=True, source="import_license", required=False)
    export_items = LicenseExportItemSerializer(many=True, source="export_license", required=False)
    exporter = serializers.PrimaryKeyRelatedField(queryset=CompanyModel.objects.all(), required=False, allow_null=True)

    class Meta:
        model = LicenseDetailsModel
        fields = (
            "id",
            "license_number",
            "license_date",
            "license_expiry_date",
            "file_number",
            "exporter",
            "port",
            "scheme_code",
            "notification_number",
            "import_items",
            "export_items",
        )
        read_only_fields = ("id",)

    def create(self, validated_data):
        import_items = validated_data.pop("import_license", [])
        export_items = validated_data.pop("export_license", [])
        license_obj = super().create(validated_data)
        for it in import_items:
            LicenseImportItemsModel.objects.create(license=license_obj, **it)
        for ex in export_items:
            LicenseExportItemModel.objects.create(license=license_obj, **ex)
        return license_obj

    def update(self, instance, validated_data):
        import_items = validated_data.pop("import_license", None)
        export_items = validated_data.pop("export_license", None)
        instance = super().update(instance, validated_data)
        if import_items is not None:
            instance.import_license.all().delete()
            for it in import_items:
                LicenseImportItemsModel.objects.create(license=instance, **it)
        if export_items is not None:
            instance.export_license.all().delete()
            for ex in export_items:
                LicenseExportItemModel.objects.create(license=instance, **ex)
        return instance
