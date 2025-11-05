from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from django.db import models


class StandardPagination(PageNumberPagination):
    """Reusable pagination class."""
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


class MasterViewSet(viewsets.ModelViewSet):
    """
    Generic reusable CRUD ViewSet for all Master data models.
    Provides:
      - Full CRUD
      - Authenticated permissions
      - Search, filter, ordering
      - created_by / modified_by tracking
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    pagination_class = StandardPagination
    ordering_fields = "__all__"
    search_fields = ["id"]

    def perform_create(self, serializer):
        """Attach current user to created_by if authenticated."""
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user)

    def perform_update(self, serializer):
        """Attach current user to modified_by if authenticated."""
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(modified_by=user)

    # --- Factory Method ---
    @classmethod
    def create(cls, model, serializer, search_fields=None):
        """
        Dynamically generates a CRUD ViewSet for any master model.
        Automatically excludes Image/File and relational fields from filterset_fields.
        Example:
            PortViewSet = MasterViewSet.create(PortModel, PortSerializer, ["code", "name"])
        """
        safe_filter_fields = [
            f.name
            for f in model._meta.get_fields()
            if not isinstance(f, (models.FileField, models.ImageField))
            and not f.is_relation
        ]

        search_fields_local = search_fields or ["id"]

        attrs = {
            "queryset": model.objects.all(),
            "serializer_class": serializer,
            "search_fields": list(search_fields_local),
            "filterset_fields": safe_filter_fields,
            "ordering_fields": safe_filter_fields,
            "model_name": model.__name__,
        }

        return type(f"{model.__name__}ViewSet", (cls,), attrs)
