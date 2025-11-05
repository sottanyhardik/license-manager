# core/views/options.py
from rest_framework import generics, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend

from core.models import CompanyModel, ItemNameModel, HSCodeModel, PortModel, SionNormClassModel
from core.serializers import (
    CompanySimpleSerializer,
    ItemNameSimpleSerializer,
    HSCodeSimpleSerializer,
    PortSimpleSerializer,
    NormClassSimpleSerializer,
)


class CompanyOptionsView(generics.ListAPIView):
    queryset = CompanyModel.objects.all().order_by("name")
    serializer_class = CompanySimpleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ["name"]


class ItemOptionsView(generics.ListAPIView):
    queryset = ItemNameModel.objects.all().order_by("name")
    serializer_class = ItemNameSimpleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]


class HSCodeOptionsView(generics.ListAPIView):
    queryset = HSCodeModel.objects.all().order_by("hs_code")
    serializer_class = HSCodeSimpleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["hs_code", "product_description"]


class PortOptionsView(generics.ListAPIView):
    queryset = PortModel.objects.all().order_by("code")
    serializer_class = PortSimpleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["code", "name"]


class NormClassOptionsView(generics.ListAPIView):
    queryset = SionNormClassModel.objects.all().order_by("norm_class")
    serializer_class = NormClassSimpleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["norm_class", "description"]
