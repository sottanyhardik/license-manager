# license/views/license_items.py
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
from rest_framework import viewsets, filters

from license.models import LicenseImportItemsModel


class LicenseItemSimpleSerializer(serializers.ModelSerializer):
    """Simple serializer for license items dropdown"""
    license_number = serializers.CharField(source='license.license_number', read_only=True)
    hs_code = serializers.CharField(source='hs_code.hs_code', read_only=True)
    label = serializers.SerializerMethodField()

    class Meta:
        model = LicenseImportItemsModel
        fields = ['id', 'serial_number', 'description', 'license_number', 'hs_code', 'label']

    def get_label(self, obj):
        """Format label for dropdown"""
        return f"{obj.license.license_number} - S.No.{obj.serial_number}"


class LicenseItemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for license items.
    Used for dropdowns and selection in BOE forms.
    """
    queryset = LicenseImportItemsModel.objects.select_related('license', 'hs_code').all()
    serializer_class = LicenseItemSimpleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'license__license_number', 'hs_code__hs_code']
    filterset_fields = ['license', 'hs_code']
    ordering_fields = ['serial_number', 'license__license_number']
    ordering = ['license__license_number', 'serial_number']
