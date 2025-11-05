# license/views/license.py
from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response

from license.serializers import (
    LicenseSerializer,
    LicenseImportItemSerializer,
    LicenseExportItemSerializer,
)
from license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseExportItemModel

from api_utils.form_schema import model_to_form_schema


class LicenseViewSet(viewsets.ModelViewSet):
    queryset = LicenseDetailsModel.objects.all().order_by("-license_date")
    serializer_class = LicenseSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["license_number", "exporter__id", "scheme_code"]
    search_fields = ["license_number", "exporter__name"]
    ordering_fields = ["license_date", "license_expiry_date", "id"]

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def schema(self, request):
        schema = model_to_form_schema(
            LicenseDetailsModel,
            exclude=["created_on", "modified_on", "created_by", "modified_by"],
        )
        return Response(schema)


class LicenseImportItemViewSet(viewsets.ModelViewSet):
    queryset = LicenseImportItemsModel.objects.all().order_by("license", "serial_number")
    serializer_class = LicenseImportItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["license__id", "hs_code__hs_code"]
    search_fields = ["description", "items__name"]

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def schema(self, request):
        schema = model_to_form_schema(
            LicenseImportItemsModel,
            exclude=["created_on", "modified_on", "created_by", "modified_by"],
        )
        return Response(schema)


class LicenseExportItemViewSet(viewsets.ModelViewSet):
    queryset = LicenseExportItemModel.objects.all().order_by("license")
    serializer_class = LicenseExportItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["license__id", "item__id"]
    search_fields = ["description"]

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def schema(self, request):
        schema = model_to_form_schema(
            LicenseExportItemModel,
            exclude=["created_on", "modified_on", "created_by", "modified_by"],
        )
        return Response(schema)
