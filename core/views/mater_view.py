# views/master.py
from rest_framework import viewsets, permissions, filters
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from rest_framework.response import Response
from rest_framework.request import Request


class StandardPagination(PageNumberPagination):
    """Reusable pagination for all master data endpoints."""
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


class MasterViewSet(viewsets.ModelViewSet):
    """
    🔹 Generic Reusable Master CRUD ViewSet.

    Provides:
        - Full CRUD
        - Authenticated access
        - Search, Filter, Ordering
        - Pagination
        - Auto metadata for frontend (list/form fields)
    """

    permission_classes = [permissions.AllowAny]
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    ordering_fields = "__all__"

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

        Accepts:
            - config (dict): define search, filter, list_display, form_fields
            - OR config (list): shorthand for `search_fields`
        """

        # ✅ Allow list shorthand for backward compatibility
        if isinstance(config, list):
            config = {"search": config}
        elif not isinstance(config, dict):
            config = {}

        safe_fields = [
            f.name
            for f in model._meta.get_fields()
            if not isinstance(f, (models.FileField, models.ImageField))
        ]

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

        return type(f"{model.__name__}ViewSet", (cls,), attrs)

    # --- Frontend Metadata ---
    def metadata(self):
        """
        Additional metadata helper (not strictly required for OPTIONS,
        but useful if other parts of the system call view.metadata()).
        """
        base = super().metadata() if hasattr(super(), "metadata") else {}
        base.update({
            "list_display": getattr(self, "list_display", []),
            "form_fields": getattr(self, "form_fields", []),
            "search_fields": getattr(self, "search_fields", []),
            "filter_fields": getattr(self, "filterset_fields", []),
            "ordering_fields": getattr(self, "ordering_fields", []),
            "model_name": getattr(self, "model_name", None),
        })
        return base

    def options(self, request: Request, *args, **kwargs) -> Response:
        """
        Override OPTIONS so the response returned to the client includes the
        frontend-friendly meta keys (list_display, form_fields, etc.)

        We call super().options(...) to retain DRF's default behaviour and
        then merge our custom metadata into response.data when possible.
        """
        response = super().options(request, *args, **kwargs)

        # Defensive: only update if response.data is a dict-like structure
        try:
            if isinstance(response.data, dict):
                extra_meta = {
                    "list_display": getattr(self, "list_display", []),
                    "form_fields": getattr(self, "form_fields", []),
                    "search_fields": getattr(self, "search_fields", []),
                    "filter_fields": getattr(self, "filterset_fields", []),
                    "ordering_fields": getattr(self, "ordering_fields", []),
                    "model_name": getattr(self, "model_name", None),
                }
                # Only write keys that are not already present (or overwrite intentionally)
                response.data.update(extra_meta)
        except Exception:
            # Never fail OPTIONS: keep original response on error
            pass

        return response
