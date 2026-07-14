# core/serializers/masters.py
"""
ModelSerializer classes for all 23 core master models.

Design principles:
- Audit fields (created_by, modified_by, created_on, modified_on) are read-only.
- No custom create/update logic — pure CRUD with DRF defaults.
- Extra display-friendly fields added as read_only SerializerMethodField / source.
"""
from rest_framework import serializers

from apps.core.models import (
    ActivityLog,
    CeleryTaskTracker,
    CompanyModel,
    ExchangeRateModel,
    HeadSIONNormsModel,
    HSCodeModel,
    InvoiceEntity,
    ItemGroupModel,
    ItemHeadModel,
    ItemNameModel,
    MasterChange,
    NotificationNumber,
    PortModel,
    ProductDescriptionModel,
    PurchaseStatus,
    SchemeCode,
    SIONExportModel,
    SIONImportModel,
    SionNormClassModel,
    SionNormCondition,
    SionNormNote,
    TransferLetterModel,
    UnitPriceModel,
)


class AuditSerializerMixin(serializers.ModelSerializer):
    """Make audit tracking fields read-only automatically."""

    class Meta:
        read_only_fields = ("created_by", "modified_by", "created_on", "modified_on")


# ---------------------------------------------------------------------------
# Priority masters
# ---------------------------------------------------------------------------

class CompanySerializer(AuditSerializerMixin):
    """
    Full company record including banking, branding, and address fields.
    Image fields (logo, signature, stamp) are included; clients should use
    multipart/form-data for uploads.
    """

    class Meta(AuditSerializerMixin.Meta):
        model = CompanyModel
        fields = "__all__"


class PortSerializer(AuditSerializerMixin):
    """Port code + name. Used in license, BOE, and trade dropdowns."""

    class Meta(AuditSerializerMixin.Meta):
        model = PortModel
        fields = "__all__"


class HSCodeSerializer(AuditSerializerMixin):
    """Harmonised System Code with duty, unit, and policy information."""

    class Meta(AuditSerializerMixin.Meta):
        model = HSCodeModel
        fields = "__all__"


class HeadSIONNormsSerializer(serializers.ModelSerializer):
    """Top-level SION norm heading."""

    class Meta:
        model = HeadSIONNormsModel
        fields = "__all__"
        read_only_fields = ("created_on", "modified_on")


class ItemGroupSerializer(AuditSerializerMixin):
    """Item group / category master."""

    class Meta(AuditSerializerMixin.Meta):
        model = ItemGroupModel
        fields = "__all__"


class ItemNameSerializer(AuditSerializerMixin):
    """
    Item name with group and SION norm class labels for display purposes.
    """

    group_name = serializers.CharField(source="group.name", read_only=True)
    sion_norm_class_label = serializers.SerializerMethodField()

    class Meta(AuditSerializerMixin.Meta):
        model = ItemNameModel
        fields = "__all__"

    def get_sion_norm_class_label(self, obj):
        """Return formatted label: '<code> - <description>' or just code."""
        if obj.sion_norm_class:
            if obj.sion_norm_class.description:
                return f"{obj.sion_norm_class.norm_class} - {obj.sion_norm_class.description}"
            return obj.sion_norm_class.norm_class
        return None


class SionNormClassSerializer(AuditSerializerMixin):
    """
    SION norm class with head norm name for display.
    Nested export/import norms are NOT included here — use the detail
    endpoint or the nested serializer variants in the legacy app.
    """

    head_norm_name = serializers.CharField(source="head_norm.name", read_only=True)
    label = serializers.SerializerMethodField()

    class Meta(AuditSerializerMixin.Meta):
        model = SionNormClassModel
        fields = "__all__"

    def get_label(self, obj):
        """Return '<norm_class> - <description>' or just norm_class."""
        if obj.description:
            return f"{obj.norm_class} - {obj.description}"
        return obj.norm_class


class ExchangeRateSerializer(AuditSerializerMixin):
    """
    Exchange rate record. is_active indicates whether this is the latest rate.
    """

    is_active = serializers.SerializerMethodField()

    class Meta(AuditSerializerMixin.Meta):
        model = ExchangeRateModel
        fields = "__all__"

    def get_is_active(self, obj):
        """True if this row has the latest date (the active rate)."""
        # Cache the active rate on the serializer context to avoid N queries.
        if "_active_exchange_rate" not in self.context:
            self.context["_active_exchange_rate"] = ExchangeRateModel.get_active_rate()
        active = self.context["_active_exchange_rate"]
        return obj.id == active.id if active else False


# ---------------------------------------------------------------------------
# SION sub-models
# ---------------------------------------------------------------------------

class SIONExportSerializer(serializers.ModelSerializer):
    """SION export norm row (description, quantity, unit)."""

    id = serializers.CharField(required=False, allow_null=True)

    class Meta:
        model = SIONExportModel
        fields = ("id", "description", "quantity", "unit")
        read_only_fields = ("created_on", "modified_on")


class SIONImportSerializer(serializers.ModelSerializer):
    """SION import norm row including optional HS code reference."""

    id = serializers.CharField(required=False, allow_null=True)
    hsn_code_label = serializers.SerializerMethodField()

    class Meta:
        model = SIONImportModel
        fields = (
            "id",
            "serial_number",
            "description",
            "quantity",
            "unit",
            "hsn_code",
            "hsn_code_label",
            "condition",
        )
        read_only_fields = ("created_on", "modified_on")

    def get_hsn_code_label(self, obj):
        if obj.hsn_code:
            return f"{obj.hsn_code.hs_code} - {obj.hsn_code.product_description}"
        return None


class SionNormNoteSerializer(serializers.ModelSerializer):
    """Supplementary note attached to a SION norm class."""

    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = SionNormNote
        fields = ("id", "note_text", "display_order")
        read_only_fields = ("created_on", "modified_on")


class SionNormConditionSerializer(serializers.ModelSerializer):
    """Condition attached to a SION norm class."""

    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = SionNormCondition
        fields = ("id", "condition_text", "display_order")
        read_only_fields = ("created_on", "modified_on")


# ---------------------------------------------------------------------------
# Secondary masters
# ---------------------------------------------------------------------------

class InvoiceEntitySerializer(serializers.ModelSerializer):
    """Invoice-issuing entity (billing company)."""

    class Meta:
        model = InvoiceEntity
        fields = "__all__"


class SchemeCodeSerializer(serializers.ModelSerializer):
    """DGFT scheme codes."""

    class Meta:
        model = SchemeCode
        fields = ["id", "code", "label"]
        read_only_fields = ["id"]


class NotificationNumberSerializer(serializers.ModelSerializer):
    """DGFT notification numbers."""

    class Meta:
        model = NotificationNumber
        fields = ["id", "code", "label"]
        read_only_fields = ["id"]


class PurchaseStatusSerializer(serializers.ModelSerializer):
    """Purchase status codes for BOE line items."""

    class Meta:
        model = PurchaseStatus
        fields = ["id", "code", "label", "is_active", "display_order"]
        read_only_fields = ["id"]


class TransferLetterSerializer(AuditSerializerMixin):
    """Transfer letter document store."""

    class Meta(AuditSerializerMixin.Meta):
        model = TransferLetterModel
        fields = "__all__"


class UnitPriceSerializer(AuditSerializerMixin):
    """Unit price master."""

    class Meta(AuditSerializerMixin.Meta):
        model = UnitPriceModel
        fields = "__all__"


class ProductDescriptionSerializer(AuditSerializerMixin):
    """Product description linked to an HS code."""

    hs_code_label = serializers.CharField(source="hs_code.hs_code", read_only=True)

    class Meta(AuditSerializerMixin.Meta):
        model = ProductDescriptionModel
        fields = "__all__"


# ---------------------------------------------------------------------------
# Deprecated
# ---------------------------------------------------------------------------

class ItemHeadSerializer(AuditSerializerMixin):
    """
    DEPRECATED: Use ItemGroupSerializer instead.
    Retained for backward compatibility with legacy read paths.
    """

    restriction_norm_display = serializers.CharField(
        source="restriction_norm.norm_class",
        read_only=True,
        required=False,
    )

    class Meta(AuditSerializerMixin.Meta):
        model = ItemHeadModel
        fields = "__all__"

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if instance.restriction_norm:
            rep["restriction_norm"] = instance.restriction_norm.norm_class
        return rep


# ---------------------------------------------------------------------------
# System / ops models
# ---------------------------------------------------------------------------

class MasterChangeSerializer(serializers.ModelSerializer):
    """Append-only master change feed (read-only)."""

    class Meta:
        model = MasterChange
        fields = "__all__"
        read_only_fields = ("model_label", "natural_key", "op", "at")


class CeleryTaskTrackerSerializer(serializers.ModelSerializer):
    """Celery task tracking (read-only)."""

    duration = serializers.ReadOnlyField()

    class Meta:
        model = CeleryTaskTracker
        fields = "__all__"
        read_only_fields = (
            "task_id",
            "task_name",
            "status",
            "args",
            "kwargs",
            "result",
            "traceback",
            "created_at",
            "started_at",
            "completed_at",
            "current",
            "total",
            "progress_message",
        )


class ActivityLogSerializer(serializers.ModelSerializer):
    """User activity audit log (read-only)."""

    class Meta:
        model = ActivityLog
        fields = "__all__"
        read_only_fields = (
            "user",
            "username",
            "action",
            "module",
            "resource_id",
            "description",
            "endpoint",
            "method",
            "ip_address",
            "user_agent",
            "status_code",
            "extra",
            "timestamp",
        )
