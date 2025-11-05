from rest_framework import serializers
from .models import (
    CompanyModel, PortModel, HSCodeModel,
    HeadSIONNormsModel, SionNormClassModel,
    SIONExportModel, SIONImportModel
)

# ---- Base Serializer ----
class AuditSerializerMixin(serializers.ModelSerializer):
    """Mixin to make audit fields read-only automatically."""
    class Meta:
        read_only_fields = ("created_by", "modified_by", "created_on", "modified_on")


# ---- Company ----
class CompanySerializer(AuditSerializerMixin):
    class Meta(AuditSerializerMixin.Meta):
        model = CompanyModel
        fields = "__all__"


# ---- Port ----
class PortSerializer(AuditSerializerMixin):
    class Meta(AuditSerializerMixin.Meta):
        model = PortModel
        fields = "__all__"


# ---- HS Code ----
class HSCodeSerializer(AuditSerializerMixin):
    class Meta(AuditSerializerMixin.Meta):
        model = HSCodeModel
        fields = "__all__"


# ---- Head SION Norm ----
class HeadSIONNormsSerializer(AuditSerializerMixin):
    class Meta(AuditSerializerMixin.Meta):
        model = HeadSIONNormsModel
        fields = "__all__"


# ---- SION Export/Import ----
class SIONExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SIONExportModel
        fields = ("id", "description", "quantity", "unit")


class SIONImportSerializer(serializers.ModelSerializer):
    hsn_code_label = serializers.SerializerMethodField()

    class Meta:
        model = SIONImportModel
        fields = ("id", "description", "quantity", "unit", "hsn_code", "hsn_code_label")

    def get_hsn_code_label(self, obj):
        if obj.hsn_code:
            return f"{obj.hsn_code.hs_code} - {obj.hsn_code.product_description}"
        return None


# ---- SION Norm Class (Nested) ----
class SionNormClassNestedSerializer(AuditSerializerMixin):
    export_norm = SIONExportSerializer(many=True)
    import_norm = SIONImportSerializer(many=True)
    head_norm_name = serializers.CharField(source="head_norm.name", read_only=True)

    class Meta(AuditSerializerMixin.Meta):
        model = SionNormClassModel
        fields = "__all__"

    def create(self, validated_data):
        export_data = validated_data.pop("export_norm", [])
        import_data = validated_data.pop("import_norm", [])
        instance = SionNormClassModel.objects.create(**validated_data)

        for e in export_data:
            SIONExportModel.objects.create(norm_class=instance, **e)
        for i in import_data:
            SIONImportModel.objects.create(norm_class=instance, **i)

        return instance

    def update(self, instance, validated_data):
        export_data = validated_data.pop("export_norm", [])
        import_data = validated_data.pop("import_norm", [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        instance.export_norm.all().delete()
        instance.import_norm.all().delete()

        for e in export_data:
            SIONExportModel.objects.create(norm_class=instance, **e)
        for i in import_data:
            SIONImportModel.objects.create(norm_class=instance, **i)

        return instance

from .models import HSCodeDutyModel, ProductDescriptionModel, UnitPriceModel


# ---- HS Code Duty ----
class HSCodeDutySerializer(serializers.ModelSerializer):
    class Meta:
        model = HSCodeDutyModel
        fields = "__all__"
        read_only_fields = ("created_by", "modified_by", "created_on", "modified_on")


# ---- Product Description ----
class ProductDescriptionSerializer(serializers.ModelSerializer):
    hs_code_label = serializers.CharField(source="hs_code.hs_code", read_only=True)

    class Meta:
        model = ProductDescriptionModel
        fields = "__all__"
        read_only_fields = ("created_by", "modified_by", "created_on", "modified_on")


# ---- Unit Price ----
class UnitPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitPriceModel
        fields = "__all__"
        read_only_fields = ("created_by", "modified_by", "created_on", "modified_on")
