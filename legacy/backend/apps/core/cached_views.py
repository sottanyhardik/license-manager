"""
Cached View Mixins and Classes
================================

Provides reusable mixins for adding caching to DRF viewsets and views.

Usage:
    from apps.core.cached_views import CachedListModelMixin

    class MyViewSet(CachedListModelMixin, viewsets.ModelViewSet):
        cache_timeout = 300  # 5 minutes
        queryset = MyModel.objects.all()
"""

import logging
from typing import Optional

from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import viewsets
from rest_framework.response import Response

from apps.core.cache_utils import generate_view_cache_key, CACHE_TIMEOUT_MEDIUM

logger = logging.getLogger(__name__)


class CachedListModelMixin:
    """
    Mixin to add caching to list() method of DRF viewsets.

    Automatically caches paginated list responses.

    Usage:
        class LicenseViewSet(CachedListModelMixin, viewsets.ModelViewSet):
            cache_timeout = 300  # Optional, default 5 minutes
            queryset = License.objects.all()
    """
    cache_timeout = CACHE_TIMEOUT_MEDIUM  # Default 5 minutes

    def list(self, request, *args, **kwargs):
        """Override list to add caching."""
        # Generate cache key
        view_name = self.__class__.__name__
        cache_key = generate_view_cache_key(request, view_name)

        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Cache HIT for {view_name}.list()")
            return Response(cached_data)

        # Cache miss - execute query
        logger.debug(f"Cache MISS for {view_name}.list()")
        response = super().list(request, *args, **kwargs)

        # Cache successful responses
        if 200 <= response.status_code < 300:
            cache.set(cache_key, response.data, self.cache_timeout)
            logger.debug(f"Cached {view_name}.list() for {self.cache_timeout}s")

        return response


class CachedRetrieveModelMixin:
    """
    Mixin to add caching to retrieve() method of DRF viewsets.

    Caches individual object detail responses.

    Usage:
        class LicenseViewSet(CachedRetrieveModelMixin, viewsets.ModelViewSet):
            cache_timeout = 600  # 10 minutes for detail views
            queryset = License.objects.all()
    """
    cache_timeout = CACHE_TIMEOUT_MEDIUM * 2  # Default 10 minutes

    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to add caching."""
        # Generate cache key including object ID
        view_name = self.__class__.__name__
        obj_id = kwargs.get('pk') or kwargs.get(self.lookup_field)
        cache_key = f"{view_name}:retrieve:{obj_id}"

        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Cache HIT for {view_name}.retrieve({obj_id})")
            return Response(cached_data)

        # Cache miss
        logger.debug(f"Cache MISS for {view_name}.retrieve({obj_id})")
        response = super().retrieve(request, *args, **kwargs)

        # Cache successful responses
        if 200 <= response.status_code < 300:
            cache.set(cache_key, response.data, self.cache_timeout)
            logger.debug(f"Cached {view_name}.retrieve({obj_id}) for {self.cache_timeout}s")

        return response


class CachedModelViewSet(CachedListModelMixin, CachedRetrieveModelMixin, viewsets.ModelViewSet):
    """
    Fully cached ModelViewSet with list and retrieve caching.

    Usage:
        class LicenseViewSet(CachedModelViewSet):
            cache_timeout = 300
            queryset = License.objects.all()
            serializer_class = LicenseSerializer
    """
    pass


class CachedReadOnlyModelViewSet(CachedListModelMixin, CachedRetrieveModelMixin, viewsets.ReadOnlyModelViewSet):
    """
    Cached read-only viewset (list + retrieve only).

    Best for master data endpoints (companies, items, HS codes).

    Usage:
        class CompanyViewSet(CachedReadOnlyModelViewSet):
            cache_timeout = 3600  # 1 hour for master data
            queryset = Company.objects.all()
    """
    pass


# ============================================================================
# Cache-aware Pagination
# ============================================================================

from rest_framework.pagination import PageNumberPagination


class CachedPageNumberPagination(PageNumberPagination):
    """
    Pagination class that includes page number in cache key.

    Standard PageNumberPagination but cache-friendly.
    """
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 200

    def get_cache_key(self, view_name: str, page: int) -> str:
        """Generate cache key for this page."""
        return f"{view_name}:page:{page}"
