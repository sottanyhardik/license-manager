from django.db import models
from django.db.models import F
from rest_framework import viewsets, permissions, filters
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.request import Request
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser


class StandardPagination(PageNumberPagination):
    """Reusable pagination for all master data endpoints."""
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


class MasterViewSet(viewsets.ModelViewSet):
    """
    🔹 Generic Reusable Master CRUD ViewSet

    Provides:
        - Full CRUD
        - Authenticated access
        - Search, Filter, Ordering, Pagination
        - list_display / form_fields driven from backend config
        - Annotated FK display support (e.g., head_norm__name)
        - Optional nested_field_defs support for nested structures (export/import)
    """

    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [permissions.AllowAny]
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    ordering_fields = "__all__"

    # Defaults (overwritten by factory)
    search_fields = ["id"]
    filterset_fields = []
    list_display = []
    form_fields = []
    nested_field_defs = {}  # <-- default empty

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(modified_by=self.request.user)
        else:
            serializer.save()

    # --- Factory Method ---
    @classmethod
    def create(cls, model, serializer, config=None):
        """
        Factory to dynamically generate CRUD ViewSet classes.

        Accepts config dict with:
            - search: list of searchable fields
            - filter: list of filterable fields
            - list_display: visible table columns (can include __ lookups)
            - form_fields: editable fields in form
            - ordering: list of sortable fields
            - nested_field_defs: dict describing nested export/import fields (optional)
        """

        # Backward-compatible shorthand
        if isinstance(config, list):
            config = {"search": config}
        elif not isinstance(config, dict):
            config = {}

        # Determine safe fields for filters
        safe_fields = [
            f.name
            for f in model._meta.get_fields()
            if not isinstance(f, (models.FileField, models.ImageField))
        ]

        # Class factory attrs
        attrs = {
            "queryset": model.objects.all(),
            "serializer_class": serializer,
            "search_fields": config.get("search", ["id"]),
            "filterset_fields": config.get("filter", safe_fields),
            "list_display": config.get("list_display", safe_fields),
            "form_fields": config.get("form_fields", safe_fields),
            "ordering_fields": config.get("ordering", safe_fields),
            "model_name": model.__name__,
            "nested_field_defs": config.get("nested_field_defs", {}),
        }

        # --- Define subclass ---
        class _ViewSet(cls):
            queryset = model.objects.all()

            # copy attrs to class so getattr works inside methods
            search_fields = attrs["search_fields"]
            filterset_fields = attrs["filterset_fields"]
            list_display = attrs["list_display"]
            form_fields = attrs["form_fields"]
            ordering_fields = attrs["ordering_fields"]
            nested_field_defs = attrs["nested_field_defs"]
            model_name = attrs["model_name"]
            serializer_class = attrs["serializer_class"]

            def get_queryset(self):
                qs = super().get_queryset()
                annotations = {}

                # Auto-annotate FK lookups in list_display (like head_norm__name)
                for field in getattr(self, "list_display", []):
                    if "__" in field:
                        alias = field.replace("__", "_")
                        annotations[alias] = F(field)
                if annotations:
                    qs = qs.annotate(**annotations)
                return qs

            def list(self, request, *args, **kwargs):
                """
                Include list_display, form_fields, and nested_field_defs in API response for frontend
                """
                response = super().list(request, *args, **kwargs)
                # Ensure structure always includes metadata keys
                results = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
                data = {
                    "results": results,
                    "list_display": getattr(self, "list_display", attrs["list_display"]),
                    "form_fields": getattr(self, "form_fields", attrs["form_fields"]),
                    "search_fields": getattr(self, "search_fields", attrs["search_fields"]),
                    "filter_fields": getattr(self, "filterset_fields", attrs["filterset_fields"]),
                    "ordering_fields": getattr(self, "ordering_fields", attrs["ordering_fields"]),
                    "nested_field_defs": getattr(self, "nested_field_defs", attrs["nested_field_defs"]),
                }
                response.data = data
                return response

            def options(self, request: Request, *args, **kwargs) -> Response:
                """
                Extend OPTIONS response with extra metadata including nested_field_defs
                """
                response = super().options(request, *args, **kwargs)
                try:
                    if isinstance(response.data, dict):
                        extra = {
                            "list_display": getattr(self, "list_display", []),
                            "form_fields": getattr(self, "form_fields", []),
                            "search_fields": getattr(self, "search_fields", []),
                            "filter_fields": getattr(self, "filterset_fields", []),
                            "ordering_fields": getattr(self, "ordering_fields", []),
                            "model_name": getattr(self, "model_name", None),
                            "nested_field_defs": getattr(self, "nested_field_defs", {}),
                        }
                        response.data.update(extra)
                except Exception:
                    pass
                return response

        _ViewSet.__name__ = f"{model.__name__}ViewSet"
        for k, v in attrs.items():
            setattr(_ViewSet, k, v)

        return _ViewSet




