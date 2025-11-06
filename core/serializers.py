from rest_framework import serializers
from .models import (
    CompanyModel, PortModel, HSCodeModel,
    HeadSIONNormsModel, SionNormClassModel,
    SIONExportModel, SIONImportModel,
    HSCodeDutyModel, ProductDescriptionModel, UnitPriceModel
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
    class Meta:
        model = SIONExportModel
        fields = ("id", "description", "quantity", "unit")
        extra_kwargs = {"id": {"read_only": True}}


class SIONImportSerializer(serializers.ModelSerializer):
    hsn_code_label = serializers.SerializerMethodField()

    class Meta:
        model = SIONImportModel
        fields = ("id", "description", "quantity", "unit", "hsn_code", "hsn_code_label")
        extra_kwargs = {"id": {"read_only": True}}

    def get_hsn_code_label(self, obj):
        if obj.hsn_code:
            return f"{obj.hsn_code.hs_code} - {obj.hsn_code.product_description}"
        return None


# ---- SION Norm Class (Nested) ----
# Purpose: Patch to replace the SionNormClassNestedSerializer in your serializers.py
# Instructions: Copy the SionNormClassNestedSerializer class below and replace the
# existing class definition in your project's serializers.py.
class SionNormClassNestedSerializer(serializers.ModelSerializer):
    """
    Updated serializer for SionNormClassModel.

    Key behaviour change: on update(), nested fields (export_norm / import_norm)
    are only modified when the frontend actually includes them in the payload.
    This prevents accidental deletion of nested rows when the frontend omits
    those fields during partial updates.

    Usage:
    - Replace the existing SionNormClassNestedSerializer in your serializers.py
      with this class.
    - Keep the rest of your serializers.py unchanged.

    Notes on semantics:
    - create(): unchanged — will create nested children if provided.
    - update(): detects absence vs explicit empty array by using None as default
      for the nested fields (pop(..., None)). If payload contains [] then the
      nested set will be cleared; if payload omits the key, existing children
      are preserved.
    """

    export_norm = serializers.PrimaryKeyRelatedField(
        many=True, read_only=False, required=False
    )
    import_norm = serializers.PrimaryKeyRelatedField(
        many=True, read_only=False, required=False
    )

    class Meta:
        model = SionNormClassModel
        fields = "__all__"

    def create(self, validated_data):
        # preserve existing behaviour: pop nested payloads as empty list
        export_data = validated_data.pop("export_norm", [])
        import_data = validated_data.pop("import_norm", [])

        instance = SionNormClassModel.objects.create(**validated_data)

        for e in export_data:
            # assumes e is dict with export fields
            SIONExportModel.objects.create(norm_class=instance, **e)

        for i in import_data:
            SIONImportModel.objects.create(norm_class=instance, **i)

        return instance

    def update(self, instance, validated_data):
        """Update parent fields and only touch nested sets when provided.

        - If `export_norm` or `import_norm` is absent in the incoming data,
          do not modify existing related rows.
        - If the incoming value is an empty list `[]`, clear the related rows.
        """
        # Detect whether nested payloads are present
        export_data = validated_data.pop("export_norm", None)
        import_data = validated_data.pop("import_norm", None)

        # Update non-related fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Only modify export children if the payload was provided (including [])
        if export_data is not None:
            instance.export_norm.all().delete()
            for e in export_data:
                SIONExportModel.objects.create(norm_class=instance, **e)

        # Only modify import children if the payload was provided (including [])
        if import_data is not None:
            instance.import_norm.all().delete()
            for i in import_data:
                SIONImportModel.objects.create(norm_class=instance, **i)

        return instance

# End of patch file



# ---- HS Code Duty ----
class HSCodeDutySerializer(AuditSerializerMixin):
    class Meta(AuditSerializerMixin.Meta):
        model = HSCodeDutyModel
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
