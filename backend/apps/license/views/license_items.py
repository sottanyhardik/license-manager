from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
from rest_framework import filters, mixins, viewsets

from apps.accounts.permissions import LicensePermission
from apps.license.models import LicenseImportItemsModel


class LicenseItemSimpleSerializer(serializers.ModelSerializer):
    """Read serializer for license item dropdowns."""

    license_number = serializers.CharField(source="license.license_number", read_only=True)
    hs_code = serializers.CharField(source="hs_code.hs_code", read_only=True, allow_null=True)
    label = serializers.SerializerMethodField()

    class Meta:
        model = LicenseImportItemsModel
        fields = [
            "id",
            "serial_number",
            "description",
            "license_number",
            "hs_code",
            "label",
            "condition_type",
        ]

    def get_label(self, obj):
        """Format a compact label for dropdowns."""
        license_number = getattr(getattr(obj, "license", None), "license_number", "")
        return f"{license_number} - S.No.{obj.serial_number}".strip()


class LicenseItemViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for license items.
    Used for dropdowns, selection in BOE forms, and updating individual fields like is_restricted.
    """

    queryset = LicenseImportItemsModel.objects.select_related("license", "hs_code").prefetch_related("items").all()
    serializer_class = LicenseItemSimpleSerializer
    permission_classes = [LicensePermission]
    http_method_names = ["get", "put", "patch", "head", "options"]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["description", "items__name", "license__license_number", "hs_code__hs_code"]
    filterset_fields = ["license", "hs_code"]
    ordering_fields = ["serial_number", "license__license_number"]
    ordering = ["license__license_number", "serial_number"]

    def get_serializer_class(self):
        """Use simple serializer for list/retrieve, allow full model updates for update/partial_update."""
        if self.action in {"update", "partial_update"}:
            from apps.license.serializers import LicenseImportItemSerializer

            return LicenseImportItemSerializer
        return self.serializer_class
