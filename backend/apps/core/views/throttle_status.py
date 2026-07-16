"""
Throttle Status Monitoring API

Provides endpoints to monitor and manage API rate limiting status.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.core.cache import cache

from apps.core.throttling import (
    get_throttle_status,
    get_all_throttle_status,
    reset_throttle,
    AnonRateThrottle,
    UserRateThrottle,
    StaffRateThrottle,
    BurstRateThrottle,
    SustainedRateThrottle,
    UploadRateThrottle,
    ExportRateThrottle,
    LoginRateThrottle,
    StrictRateThrottle,
)


class ThrottleStatusView(APIView):
    """
    Get current throttle status for the authenticated user.

    GET /api/throttle-status/

    Returns:
        {
            "anon": {
                "allowed": true,
                "rate": "100/hour",
                "remaining": 95,
                "available_in": 0,
                "limit": 100,
                "duration": 3600
            },
            "user": {
                "allowed": true,
                "rate": "1000/hour",
                "remaining": 987,
                "available_in": 0,
                "limit": 1000,
                "duration": 3600
            },
            ...
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get throttle status for all scopes"""
        status = get_all_throttle_status(request)
        return Response(status)


class ThrottleScopeStatusView(APIView):
    """
    Get throttle status for a specific scope.

    GET /api/throttle-status/{scope}/

    Returns:
        {
            "allowed": true,
            "rate": "100/hour",
            "remaining": 95,
            "available_in": 0,
            "limit": 100,
            "duration": 3600
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, scope):
        """Get throttle status for specific scope"""
        throttle_map = {
            'anon': AnonRateThrottle,
            'user': UserRateThrottle,
            'staff': StaffRateThrottle,
            'burst': BurstRateThrottle,
            'sustained': SustainedRateThrottle,
            'upload': UploadRateThrottle,
            'export': ExportRateThrottle,
            'login': LoginRateThrottle,
            'strict': StrictRateThrottle,
        }

        throttle_class = throttle_map.get(scope)
        if not throttle_class:
            return Response(
                {'error': f'Unknown throttle scope: {scope}'},
                status=400
            )

        status = get_throttle_status(request, throttle_class)
        return Response(status)


class ThrottleResetView(APIView):
    """
    Reset throttle for a user or IP (admin only).

    POST /api/throttle-reset/

    Body:
        {
            "user_id": 123,  // optional
            "ip_address": "192.168.1.1",  // optional
            "scope": "user"  // required
        }

    Returns:
        {
            "message": "Throttle reset successfully",
            "user_id": 123,
            "scope": "user"
        }
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        """Reset throttle for user or IP"""
        user_id = request.data.get('user_id')
        ip_address = request.data.get('ip_address')
        scope = request.data.get('scope', 'user')

        if not user_id and not ip_address:
            return Response(
                {'error': 'user_id or ip_address required'},
                status=400
            )

        reset_throttle(user_id=user_id, ip_address=ip_address, scope=scope)

        return Response({
            'message': 'Throttle reset successfully',
            'user_id': user_id,
            'ip_address': ip_address,
            'scope': scope
        })


class ThrottleStatsView(APIView):
    """
    Get aggregated throttle statistics (admin only).

    GET /api/throttle-stats/

    Returns:
        {
            "total_requests": 12345,
            "throttled_requests": 45,
            "throttle_rate": 0.36,
            "by_scope": {
                "user": {"total": 10000, "throttled": 20},
                "burst": {"total": 5000, "throttled": 15},
                ...
            },
            "top_users": [
                {"user_id": 1, "username": "john", "request_count": 500},
                ...
            ]
        }
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        """Get throttle statistics"""
        # Get all cache keys for throttle
        all_keys = cache.keys('throttle_*') if hasattr(cache, 'keys') else []

        stats = {
            'total_cache_keys': len(all_keys),
            'scopes': {
                'anon': len([k for k in all_keys if 'throttle_anon_' in str(k)]),
                'user': len([k for k in all_keys if 'throttle_user_' in str(k)]),
                'staff': len([k for k in all_keys if 'throttle_staff_' in str(k)]),
                'burst': len([k for k in all_keys if 'throttle_burst_' in str(k)]),
                'sustained': len([k for k in all_keys if 'throttle_sustained_' in str(k)]),
                'upload': len([k for k in all_keys if 'throttle_upload_' in str(k)]),
                'export': len([k for k in all_keys if 'throttle_export_' in str(k)]),
                'login': len([k for k in all_keys if 'throttle_login_' in str(k)]),
                'strict': len([k for k in all_keys if 'throttle_strict_' in str(k)]),
            },
            'note': 'Detailed request tracking requires additional logging middleware'
        }

        return Response(stats)


class ThrottleHealthView(APIView):
    """
    Check throttle system health.

    GET /api/throttle-health/

    Returns:
        {
            "status": "healthy",
            "cache_backend": "redis",
            "cache_available": true,
            "configured_scopes": ["anon", "user", "staff", ...],
            "rates": {
                "anon": "100/hour",
                "user": "1000/hour",
                ...
            }
        }
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        """Check throttle system health"""
        from django.conf import settings

        # Check cache availability
        cache_available = True
        cache_backend = 'unknown'
        try:
            cache.set('throttle_health_check', 'ok', 10)
            test = cache.get('throttle_health_check')
            cache_available = (test == 'ok')
            cache.delete('throttle_health_check')

            # Get cache backend info
            if hasattr(cache, 'client'):
                cache_backend = 'redis'
            elif hasattr(cache, '_cache'):
                cache_backend = 'memcached'
            else:
                cache_backend = 'locmem'
        except Exception:
            cache_available = False

        # Get configured throttle rates
        throttle_rates = getattr(settings, 'REST_FRAMEWORK', {}).get('DEFAULT_THROTTLE_RATES', {})

        health_status = {
            'status': 'healthy' if cache_available else 'degraded',
            'cache_backend': cache_backend,
            'cache_available': cache_available,
            'configured_scopes': list(throttle_rates.keys()),
            'rates': throttle_rates,
            'default_throttle_classes': [
                cls.rsplit('.', 1)[-1]
                for cls in getattr(settings, 'REST_FRAMEWORK', {}).get('DEFAULT_THROTTLE_CLASSES', [])
            ]
        }

        return Response(health_status)
