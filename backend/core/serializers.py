from rest_framework import serializers

from .helpers import _sync_nested
from .models import (
    CompanyModel, PortModel, HSCodeModel,
    HeadSIONNormsModel, SionNormClassModel,
    SIONExportModel, SIONImportModel,
    ProductDescriptionModel, UnitPriceModel, ItemNameModel, ItemHeadModel
)


# ---- Base Audit Serializer ----
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


# ---- SION Export / Import ----
class SIONExportSerializer(serializers.ModelSerializer):
    id = serializers.CharField(required=False, allow_null=True)

    class Meta:
        model = SIONExportModel
        fields = ("id", "description", "quantity", "unit")


class SIONImportSerializer(serializers.ModelSerializer):
    hsn_code_label = serializers.SerializerMethodField()
    id = serializers.CharField(required=False, allow_null=True)

    class Meta:
        model = SIONImportModel
        fields = ("id", "serial_number", "description", "quantity", "unit", "hsn_code", "hsn_code_label")

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
        # Decide deletion semantics:
        # If the client included the nested key in the request body (even if empty list),
        # we will treat that as an explicit intent. Otherwise, don't touch that nested relation.
        # Use treat_empty_list_as_delete=True if you want an empty list to mean "delete all".
        provided_export = "export_norm" in (self.initial_data or {})
        provided_import = "import_norm" in (self.initial_data or {})

        if provided_export:
            # If you want an empty array [] to delete all existing export_norm rows,
            # pass treat_empty_list_as_delete=True. Default below is False for safety.
            _sync_nested(instance, SIONExportModel, export_data, fk_field="norm_class",
                         treat_empty_list_as_delete=False)

        if provided_import:
            _sync_nested(instance, SIONImportModel, import_data, fk_field="norm_class",
                         treat_empty_list_as_delete=False)

        return instance


# ---- HS Code Duty ----
class HSCodeDutySerializer(AuditSerializerMixin):
    class Meta(AuditSerializerMixin.Meta):
        model = HSCodeModel
        fields = "__all__"


# ---- Product Description ----
class ProductDescriptionSerializer(AuditSerializerMixin):
    hs_code_label = serializers.CharField(source="hs_code.hs_code", read_only=True)

    class Meta(AuditSerializerMixin.Meta):
        model = ProductDescriptionModel
        fields = "__all__"


# ---- Unit Price ----
class UnitPriceSerializer(AuditSerializerMixin):
    class Meta(AuditSerializerMixin.Meta):
        model = UnitPriceModel
        fields = "__all__"


# ---- Item Head ----
class ItemHeadSerializer(AuditSerializerMixin):
    class Meta(AuditSerializerMixin.Meta):
        model = ItemHeadModel
        fields = "__all__"


# ---- Item Name ----
class ItemNameSerializer(AuditSerializerMixin):
    head_name = serializers.CharField(read_only=True, required=False)

    class Meta(AuditSerializerMixin.Meta):
        model = ItemNameModel
        fields = "__all__"
