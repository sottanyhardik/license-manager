"""
Redis Caching Utilities for License Manager
==============================================

Provides decorators and utilities for implementing multi-tier caching strategy:
- View-level caching (entire API responses)
- Query-level caching (expensive aggregations)
- Object-level caching (frequently accessed objects)

Usage:
    from apps.core.cache_utils import cache_view, cache_query, invalidate_cache

    @cache_view(timeout=300)
    def my_view(request):
        return Response(data)

    @cache_query(key_prefix='license_balance', timeout=900)
    def get_license_balance(license_id):
        return expensive_calculation(license_id)
"""

import functools
import hashlib
import logging
from collections.abc import Callable

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.utils.encoding import force_bytes
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _cache_key_hash(value: str) -> str:
    """Return a short hash for cache keys; this is not used for security."""
    return hashlib.md5(force_bytes(value), usedforsecurity=False).hexdigest()[:16]

# ============================================================================
# Cache Key Generators
# ============================================================================


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a unique cache key from prefix and arguments.

    Args:
        prefix: Cache key prefix (e.g., 'license_list', 'dashboard')
        *args: Positional arguments to include in key
        **kwargs: Keyword arguments to include in key

    Returns:
        String cache key like: 'license_list:abc123def456'

    Example:
        >>> generate_cache_key('license_list', company_id=123, is_active=True)
        'license_list:4f3a2b1c...'
    """
    # Combine all args and kwargs into a string
    key_parts = [str(arg) for arg in args]
    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
    key_string = "|".join(key_parts)

    # Hash for consistent length
    key_hash = _cache_key_hash(key_string)

    return f"{prefix}:{key_hash}"


def generate_view_cache_key(request: HttpRequest, view_name: str) -> str:
    """
    Generate cache key for view-level caching including request params.

    Args:
        request: Django/DRF request object
        view_name: Name of the view (e.g., 'item_report')

    Returns:
        Cache key incorporating query params and user

    Example:
        GET /api/licenses/?is_active=true&page=1
        -> 'view:licenses:user123:active_true_page_1'
    """
    # Include user ID for user-specific caching
    user_id = getattr(request.user, 'id', 'anon')

    # Get query parameters
    query_params = request.GET.dict() if hasattr(request, 'GET') else {}

    # Sort for consistent keys
    params_str = "&".join([f"{k}={v}" for k, v in sorted(query_params.items())])

    # Hash params if too long
    if len(params_str) > 100:
        params_hash = _cache_key_hash(params_str)
        return f"view:{view_name}:user{user_id}:{params_hash}"

    return f"view:{view_name}:user{user_id}:{params_str}"


# ============================================================================
# Decorators
# ============================================================================


def cache_view(timeout: int = 300, key_prefix: str | None = None):
    """
    Decorator for view-level caching of entire API responses.

    Caches the complete response for GET requests. Skips caching for POST/PUT/DELETE.

    Args:
        timeout: Cache TTL in seconds (default: 5 minutes)
        key_prefix: Optional custom prefix (auto-generated from view name if None)

    Usage:
        @cache_view(timeout=300)
        @api_view(['GET'])
        def license_list(request):
            return Response({'licenses': [...]})

    Cache Invalidation:
        invalidate_cache('view:license_list:*')
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Only cache GET requests
            if request.method != 'GET':
                return view_func(request, *args, **kwargs)

            # Generate cache key
            prefix = key_prefix or f"view:{view_func.__name__}"
            cache_key = generate_view_cache_key(request, prefix)

            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                logger.debug("Cache HIT: %s", cache_key)
                # Ensure we return proper Response object
                if isinstance(cached_response, dict):
                    return Response(cached_response)
                return cached_response

            # Cache miss - execute view
            logger.debug("Cache MISS: %s", cache_key)
            response = view_func(request, *args, **kwargs)

            # Only cache successful responses
            if isinstance(response, Response) and 200 <= response.status_code < 300:
                # Cache the data, not the Response object
                cache.set(cache_key, response.data, timeout)
                logger.debug("Cached response for %s (TTL: %ss)", cache_key, timeout)
            elif isinstance(response, JsonResponse) and 200 <= response.status_code < 300:
                cache.set(cache_key, response.content, timeout)

            return response

        return wrapper
    return decorator


def cache_query(key_prefix: str, timeout: int = 900):
    """
    Decorator for query-level caching of expensive database operations.

    Best for functions that perform complex aggregations, joins, or calculations.

    Args:
        key_prefix: Cache key prefix (e.g., 'license_balance')
        timeout: Cache TTL in seconds (default: 15 minutes)

    Usage:
        @cache_query(key_prefix='license_balance', timeout=900)
        def calculate_license_balance(license_id):
            # Expensive aggregation
            return License.objects.filter(id=license_id).aggregate(...)

    Cache Invalidation:
        invalidate_cache(f'license_balance:{license_id}')
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function args
            cache_key = generate_cache_key(key_prefix, *args, **kwargs)

            # Try cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug("Query cache HIT: %s", cache_key)
                return cached_result

            # Cache miss - execute function
            logger.debug("Query cache MISS: %s", cache_key)
            result = func(*args, **kwargs)

            # Cache result
            cache.set(cache_key, result, timeout)
            logger.debug("Cached query result for %s (TTL: %ss)", cache_key, timeout)

            return result

        return wrapper
    return decorator


def cache_method(timeout: int = 300):
    """
    Decorator for caching instance method results.

    Includes instance ID in cache key for proper isolation.

    Usage:
        class License(models.Model):
            @cache_method(timeout=600)
            def calculate_balance(self):
                # Expensive calculation
                return sum(...)

    Cache Invalidation:
        license.calculate_balance.invalidate_cache(license)
    """
    def decorator(method: Callable) -> Callable:
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            # Generate cache key including instance ID
            instance_id = getattr(self, 'id', None) or getattr(self, 'pk', 'unknown')
            cache_key = generate_cache_key(
                f"{self.__class__.__name__}:{method.__name__}",
                instance_id,
                *args,
                **kwargs
            )

            # Try cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug("Method cache HIT: %s", cache_key)
                return cached_result

            # Execute method
            logger.debug("Method cache MISS: %s", cache_key)
            result = method(self, *args, **kwargs)

            # Cache result
            cache.set(cache_key, result, timeout)

            return result

        # Add invalidation helper
        def invalidate_cache(self, *args, **kwargs):
            instance_id = getattr(self, 'id', None) or getattr(self, 'pk', 'unknown')
            cache_key = generate_cache_key(
                f"{self.__class__.__name__}:{method.__name__}",
                instance_id,
                *args,
                **kwargs
            )
            cache.delete(cache_key)

        wrapper.invalidate_cache = invalidate_cache
        return wrapper

    return decorator


# ============================================================================
# Cache Invalidation
# ============================================================================


def invalidate_cache(pattern: str) -> int:
    """
    Invalidate cache keys matching a pattern.

    Args:
        pattern: Cache key pattern (supports wildcards with django-redis)

    Returns:
        Number of keys deleted

    Usage:
        # Invalidate all license list caches
        invalidate_cache('view:license_list:*')

        # Invalidate specific license balance
        invalidate_cache(f'license_balance:{license_id}')

        # Invalidate all dashboard caches
        invalidate_cache('view:dashboard:*')
    """
    try:
        # django-redis supports delete_pattern
        deleted_count = cache.delete_pattern(pattern)
        logger.info("Invalidated %s cache keys matching: %s", deleted_count, pattern)
        return deleted_count
    except AttributeError:
        # Fallback if delete_pattern not available
        logger.warning("delete_pattern not available, deleting single key")
        cache.delete(pattern)
        return 1


def invalidate_model_caches(model_name: str, instance_id: int | None = None):
    """
    Invalidate all caches related to a model.

    Args:
        model_name: Name of the model (e.g., 'LicenseDetailsModel')
        instance_id: Optional specific instance ID

    Usage:
        # Invalidate all license caches
        invalidate_model_caches('LicenseDetailsModel')

        # Invalidate specific license
        invalidate_model_caches('LicenseDetailsModel', instance_id=123)
    """
    patterns = [
        f"view:*{model_name.lower()}*",
        f"{model_name}:*",
    ]

    if instance_id:
        patterns.append(f"*:{instance_id}:*")

    total_deleted = 0
    for pattern in patterns:
        total_deleted += invalidate_cache(pattern)

    logger.info("Invalidated %s cache keys for %s", total_deleted, model_name)
    return total_deleted


# ============================================================================
# Cache Statistics
# ============================================================================


def get_cache_stats() -> dict:
    """
    Get Redis cache statistics.

    Returns:
        Dictionary with cache metrics

    Usage:
        stats = get_cache_stats()
        print(f"Hit rate: {stats['hit_rate']:.2%}")
    """
    try:
        # Get Redis info via django-redis
        client = cache.client.get_client()
        info = client.info('stats')

        hits = int(info.get('keyspace_hits', 0))
        misses = int(info.get('keyspace_misses', 0))
        total = hits + misses

        return {
            'hits': hits,
            'misses': misses,
            'hit_rate': hits / total if total > 0 else 0,
            'keys': client.dbsize(),
            'memory_used': info.get('used_memory_human', 'N/A'),
            'connected_clients': info.get('connected_clients', 0),
        }
    except Exception as exc:
        logger.exception("Failed to get cache stats")
        return {'error': str(exc)}


def warm_cache(func: Callable, cache_key: str, timeout: int, *args, **kwargs):
    """
    Pre-warm cache with computed value.

    Useful for background tasks that pre-compute expensive data.

    Usage:
        # In Celery task
        @shared_task
        def warm_dashboard_cache():
            data = compute_dashboard_data()
            warm_cache(lambda: data, 'view:dashboard:all', 300)
    """
    result = func(*args, **kwargs)
    cache.set(cache_key, result, timeout)
    logger.info("Warmed cache for %s", cache_key)
    return result


# ============================================================================
# Context Managers
# ============================================================================


class cache_disabled:
    """
    Context manager to temporarily disable caching.

    Useful for testing or admin operations.

    Usage:
        with cache_disabled():
            # This won't use cache
            data = get_expensive_data()
    """
    def __enter__(self):
        self.old_backend = settings.CACHES['default']['BACKEND']
        settings.CACHES['default']['BACKEND'] = 'django.core.cache.backends.dummy.DummyCache'
        cache._cache = cache._lib.get_cache(settings.CACHES['default'])
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        settings.CACHES['default']['BACKEND'] = self.old_backend
        cache._cache = cache._lib.get_cache(settings.CACHES['default'])


# ============================================================================
# Constants
# ============================================================================

# Recommended cache timeouts (in seconds)
CACHE_TIMEOUT_SHORT = 60          # 1 minute - for rapidly changing data
CACHE_TIMEOUT_MEDIUM = 300        # 5 minutes - for moderately changing data
CACHE_TIMEOUT_LONG = 900          # 15 minutes - for slowly changing data
CACHE_TIMEOUT_VERY_LONG = 3600    # 1 hour - for rarely changing data
CACHE_TIMEOUT_MASTER_DATA = 86400  # 24 hours - for master/reference data
