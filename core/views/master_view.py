# common/views.py
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Type

from django.db import models
from django.db.models import F
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, filters
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.request import Request
from rest_framework.response import Response


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
        - Search, Filter, Ordering, Pagination
        - list_display / form_fields driven from backend config
        - Annotated FK display support (e.g., head_norm__name)
        - Exposes 'nested_field_defs' and 'field_meta' in list() and OPTIONS metadata
    """

    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [permissions.AllowAny]
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    ordering_fields = "__all__"

    # Defaults (overwritten by factory)
    search_fields: list[str] = ["id"]
    filterset_fields: list[str] = []
    list_display: list[str] = []
    form_fields: list[str] = []
    nested_field_defs: Dict[str, Any] = {}
    field_meta: Dict[str, Any] = {}
    model_name: Optional[str] = None
    serializer_class = None
    queryset = None

    def perform_create(self, serializer):
        """Attach created_by when possible."""
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            serializer.save(created_by=user)
        else:
            serializer.save()

    def perform_update(self, serializer):
        """Attach modified_by when possible."""
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            serializer.save(modified_by=user)
        else:
            serializer.save()

    # --- Factory Method ---
    @classmethod
    def create(cls, model: Type[models.Model], serializer, config: Optional[dict] | list = None):
        """
        Factory to dynamically generate CRUD ViewSet classes.

        Args:
            model: Django model class
            serializer: DRF serializer class
            config: dict or list controlling fields and behavior
                - search: list of searchable fields
                - filter: list of filterable fields
                - list_display: visible table columns (can include __ lookups)
                - form_fields: editable fields in form
                - ordering: list of sortable fields
                - nested_field_defs: dict describing nested export/import fields (optional)
                - field_meta: dict describing special UI metadata for fields (optional)
        """
        # Normalize config
        if isinstance(config, list):
            config = {"search": config}
        elif not isinstance(config, dict):
            config = {}

        # Determine safe fields for filters (exclude file/image fields)
        safe_fields = [
            f.name
            for f in model._meta.get_fields()
            if not isinstance(f, (models.FileField, models.ImageField))
        ]

        # Attributes for the generated class
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
            "field_meta": config.get("field_meta", {}),
        }

        # --- Dynamically create the subclass ---
        class _ViewSet(cls):  # type: ignore[misc]
            # set attributes on the subclass
            queryset = attrs["queryset"]
            serializer_class = attrs["serializer_class"]
            search_fields = attrs["search_fields"]
            filterset_fields = attrs["filterset_fields"]
            list_display = attrs["list_display"]
            form_fields = attrs["form_fields"]
            ordering_fields = attrs["ordering_fields"]
            nested_field_defs = attrs["nested_field_defs"]
            field_meta = attrs["field_meta"]
            model_name = attrs["model_name"]

            def get_queryset(self):
                """Annotate queryset with FK display lookups listed in list_display (e.g., fk__name)."""
                qs = super().get_queryset()
                annotations: Dict[str, F] = {}
                for field in getattr(self, "list_display", []):
                    if "__" in field:
                        alias = field.replace("__", "_")
                        # Safe annotate: F() accepts dotted lookups
                        annotations[alias] = F(field)
                if annotations:
                    qs = qs.annotate(**annotations)
                return qs

            def list(self, request: Request, *args, **kwargs) -> Response:
                """
                Return list of objects with frontend metadata and pagination details:
                  - total_pages
                  - current_page
                  - page_size
                  - has_next
                  - has_previous
                Keeps original 'count', 'next', 'previous' keys when paginated.
                """
                # Use parent's list implementation (handles filtering, pagination, serialization)
                response = super().list(request, *args, **kwargs)

                # Extract results and pagination info
                if isinstance(response.data, dict) and "results" in response.data:
                    results = response.data.get("results", [])
                    count = response.data.get("count", None)
                    next_link = response.data.get("next", None)
                    previous_link = response.data.get("previous", None)
                else:
                    results = response.data
                    count = None
                    next_link = None
                    previous_link = None

                # Default pagination metadata
                total_pages = 1
                current_page = 1
                page_size = None
                has_next = False
                has_previous = False

                paginator = getattr(self, "paginator", None)
                if count is not None:
                    # Determine page_size
                    try:
                        if paginator is not None:
                            page_size = paginator.get_page_size(request)
                    except Exception:
                        page_size = None

                    if not page_size:
                        page_size = getattr(self.pagination_class, "page_size", 1) or 1

                    # Compute pages
                    try:
                        total_pages = int(math.ceil(float(count) / float(page_size))) if page_size and int(
                            page_size) > 0 else 1
                    except Exception:
                        total_pages = 1

                    # current page from query params (PageNumberPagination param is 'page')
                    try:
                        current_page = int(request.query_params.get("page", 1))
                        if current_page < 1:
                            current_page = 1
                        if current_page > total_pages:
                            current_page = total_pages
                    except Exception:
                        current_page = 1

                    # has_next/has_previous derived from next/previous links if present
                    has_next = bool(next_link)
                    has_previous = bool(previous_link)

                # Build final payload
                data: Dict[str, Any] = {
                    "results": results,
                    "list_display": getattr(self, "list_display", []),
                    "form_fields": getattr(self, "form_fields", []),
                    "search_fields": getattr(self, "search_fields", []),
                    "filter_fields": getattr(self, "filterset_fields", []),
                    "ordering_fields": getattr(self, "ordering_fields", []),
                    "nested_field_defs": getattr(self, "nested_field_defs", {}),
                    "field_meta": getattr(self, "field_meta", {}),

                    # Pagination metadata
                    "total_pages": total_pages,
                    "current_page": current_page,
                    "page_size": page_size,
                    "has_next": has_next,
                    "has_previous": has_previous,
                }

                # Preserve count/next/previous if present in original paginated response
                if isinstance(response.data, dict):
                    for key in ("count", "next", "previous"):
                        if key in response.data:
                            data[key] = response.data[key]

                # Replace response data
                response.data = data
                return response

            def options(self, request: Request, *args, **kwargs) -> Response:
                """
                Extend OPTIONS response with extra metadata including nested_field_defs and field_meta
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
                            "field_meta": getattr(self, "field_meta", {}),
                        }
                        response.data.update(extra)
                except Exception:
                    # Never raise from OPTIONS metadata enrichment
                    pass
                return response

        # Give the generated class a helpful name
        _ViewSet.__name__ = f"{model.__name__}ViewSet"

        # Attach attrs to generated class for easy inspection (alternatively already set above)
        for k, v in attrs.items():
            setattr(_ViewSet, k, v)

        return _ViewSet
