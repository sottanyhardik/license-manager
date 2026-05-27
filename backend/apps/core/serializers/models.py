from rest_framework import serializers

from apps.core.helpers import _sync_nested
from apps.core.models import (
    CompanyModel, PortModel, HSCodeModel,
    HeadSIONNormsModel, SionNormClassModel,
    SIONExportModel, SIONImportModel,
    ProductDescriptionModel, UnitPriceModel, ItemNameModel, ItemHeadModel, ItemGroupModel,
    TransferLetterModel, SionNormNote, SionNormCondition, ExchangeRateModel, PurchaseStatus,
    SchemeCode, NotificationNumber,
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


# ---- SION Norm Notes and Conditions ----
class SionNormNoteSerializer(serializers.ModelSerializer):
    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = SionNormNote
        fields = ("id", "note_text", "display_order")


class SionNormConditionSerializer(serializers.ModelSerializer):
    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = SionNormCondition
        fields = ("id", "condition_text", "display_order")


# ---- SION Norm Class (Nested) ----
class SionNormClassNestedSerializer(AuditSerializerMixin):
    export_norm = SIONExportSerializer(many=True)
    import_norm = SIONImportSerializer(many=True)
    notes = SionNormNoteSerializer(many=True, required=False)
    conditions = SionNormConditionSerializer(many=True, required=False)
    head_norm_name = serializers.CharField(source="head_norm.name", read_only=True)
    label = serializers.SerializerMethodField()

    class Meta(AuditSerializerMixin.Meta):
        model = SionNormClassModel
        fields = "__all__"

    def get_label(self, obj):
        """Return formatted label for async select display"""
        if obj.description:
            return f"{obj.norm_class} - {obj.description}"
        return obj.norm_class

    def to_internal_value(self, data):
        """Parse JSON strings or flattened FormData from multipart/form-data"""
        import json
        import re

        # Create a mutable copy of the data
        data = data.copy() if hasattr(data, 'copy') else dict(data)

        # Handle JSON string format for nested fields
        for field in ['export_norm', 'import_norm', 'notes', 'conditions']:
            if field in data and isinstance(data[field], str):
                try:
                    data[field] = json.loads(data[field])
                except (json.JSONDecodeError, TypeError):
                    pass

        # Handle flattened FormData format
        if hasattr(data, 'getlist'):
            nested_fields = {
                'export_norm': {},
                'import_norm': {},
                'notes': {},
                'conditions': {}
            }
            for key in list(data.keys()):
                for field_name in nested_fields.keys():
                    match = re.match(rf'{field_name}\[(\d+)\]\.(.+)', key)
                    if match:
                        index = int(match.group(1))
                        sub_field = match.group(2)
                        if index not in nested_fields[field_name]:
                            nested_fields[field_name][index] = {}
                        nested_fields[field_name][index][sub_field] = data[key]

            for field_name, items in nested_fields.items():
                if items:
                    data[field_name] = [items[i] for i in sorted(items.keys())]

        return super().to_internal_value(data)

    def create(self, validated_data):
        export_data = validated_data.pop("export_norm", [])
        import_data = validated_data.pop("import_norm", [])
        notes_data = validated_data.pop("notes", [])
        conditions_data = validated_data.pop("conditions", [])
        instance = SionNormClassModel.objects.create(**validated_data)

        for e in export_data:
            SIONExportModel.objects.create(norm_class=instance, **e)
        for i in import_data:
            SIONImportModel.objects.create(norm_class=instance, **i)
        for n in notes_data:
            SionNormNote.objects.create(sion_norm=instance, **n)
        for c in conditions_data:
            SionNormCondition.objects.create(sion_norm=instance, **c)

        return instance

    def update(self, instance, validated_data):
        export_data = validated_data.pop("export_norm", [])
        import_data = validated_data.pop("import_norm", [])
        notes_data = validated_data.pop("notes", [])
        conditions_data = validated_data.pop("conditions", [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Decide deletion semantics:
        # If the client included the nested key in the request body (even if empty list),
        # we will treat that as an explicit intent. Otherwise, don't touch that nested relation.
        # Use treat_empty_list_as_delete=True if you want an empty list to mean "delete all".
        provided_export = "export_norm" in (self.initial_data or {})
        provided_import = "import_norm" in (self.initial_data or {})
        provided_notes = "notes" in (self.initial_data or {})
        provided_conditions = "conditions" in (self.initial_data or {})

        if provided_export:
            _sync_nested(instance, SIONExportModel, export_data, fk_field="norm_class",
                         treat_empty_list_as_delete=False)

        if provided_import:
            _sync_nested(instance, SIONImportModel, import_data, fk_field="norm_class",
                         treat_empty_list_as_delete=False)

        if provided_notes:
            _sync_nested(instance, SionNormNote, notes_data, fk_field="sion_norm",
                         treat_empty_list_as_delete=False)

        if provided_conditions:
            _sync_nested(instance, SionNormCondition, conditions_data, fk_field="sion_norm",
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


# ---- Group ----
class GroupSerializer(AuditSerializerMixin):
    class Meta(AuditSerializerMixin.Meta):
        model = ItemGroupModel
        fields = "__all__"


# ---- Item Head (Deprecated) ----
class ItemHeadSerializer(AuditSerializerMixin):
    """Deprecated: Use GroupSerializer instead"""
    restriction_norm_display = serializers.CharField(source='restriction_norm.norm_class', read_only=True,
                                                     required=False)

    class Meta(AuditSerializerMixin.Meta):
        model = ItemHeadModel
        fields = "__all__"

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Replace restriction_norm ID with the norm_class value for display
        if instance.restriction_norm:
            rep['restriction_norm'] = instance.restriction_norm.norm_class
        return rep


# ---- Item Name ----
class ItemNameSerializer(AuditSerializerMixin):
    group_name = serializers.CharField(source='group.name', read_only=True, required=False)
    sion_norm_class_label = serializers.SerializerMethodField()

    class Meta(AuditSerializerMixin.Meta):
        model = ItemNameModel
        fields = "__all__"

    def get_sion_norm_class_label(self, obj):
        """Return formatted label for SION norm class"""
        if obj.sion_norm_class:
            if obj.sion_norm_class.description:
                return f"{obj.sion_norm_class.norm_class} - {obj.sion_norm_class.description}"
            return obj.sion_norm_class.norm_class
        return None


# ---- Transfer Letter ----
class TransferLetterSerializer(AuditSerializerMixin):
    class Meta(AuditSerializerMixin.Meta):
        model = TransferLetterModel
        fields = "__all__"


# ---- Exchange Rate ----
class ExchangeRateSerializer(AuditSerializerMixin):
    is_active = serializers.SerializerMethodField()

    class Meta(AuditSerializerMixin.Meta):
        model = ExchangeRateModel
        fields = "__all__"

    def get_is_active(self, obj):
        """Check if this is the active (latest) exchange rate"""
        from apps.core.models import ExchangeRateModel
        active_rate = ExchangeRateModel.get_active_rate()
        return obj.id == active_rate.id if active_rate else False


# ---- Purchase Status ----
class PurchaseStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseStatus
        fields = ['id', 'code', 'label', 'is_active', 'display_order']
        read_only_fields = ['id']


# ---- Scheme Code ----
class SchemeCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeCode
        fields = ['id', 'code', 'label']
        read_only_fields = ['id']


# ---- Notification Number ----
class NotificationNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationNumber
        fields = ['id', 'code', 'label']
        read_only_fields = ['id']
