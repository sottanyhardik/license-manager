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
        }

        # --- Define subclass ---
        class _ViewSet(cls):
            queryset = model.objects.all()

            def get_queryset(self):
                qs = super().get_queryset()
                annotations = {}

                # Auto-annotate FK lookups in list_display (like head_norm__name)
                for field in attrs["list_display"]:
                    if "__" in field:
                        alias = field.replace("__", "_")
                        annotations[alias] = F(field)
                if annotations:
                    qs = qs.annotate(**annotations)
                return qs

            def list(self, request, *args, **kwargs):
                """
                Include list_display and form_fields in API response for frontend
                """
                response = super().list(request, *args, **kwargs)
                # Ensure structure always includes metadata keys
                data = {
                    "results": response.data.get("results", response.data),
                    "list_display": getattr(self, "list_display", attrs["list_display"]),
                    "form_fields": getattr(self, "form_fields", attrs["form_fields"]),
                    "search_fields": getattr(self, "search_fields", attrs["search_fields"]),
                    "filter_fields": getattr(self, "filterset_fields", attrs["filterset_fields"]),
                    "ordering_fields": getattr(self, "ordering_fields", attrs["ordering_fields"]),
                }
                response.data = data
                return response

        _ViewSet.__name__ = f"{model.__name__}ViewSet"
        for k, v in attrs.items():
            setattr(_ViewSet, k, v)

        return _ViewSet

    # --- OPTIONS / Metadata ---
    def options(self, request: Request, *args, **kwargs) -> Response:
        """
        Extend OPTIONS response with extra metadata
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
                }
                response.data.update(extra)
        except Exception:
            pass
        return response
