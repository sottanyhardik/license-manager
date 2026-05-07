"""
Rate Limiting & Throttling for License Manager API

This module provides custom throttle classes for controlling API request rates.
Throttling helps prevent API abuse, ensures fair resource allocation, and protects
against DDoS attacks.

Throttle Classes:
- AnonRateThrottle: For anonymous/unauthenticated users
- UserRateThrottle: For authenticated users (general)
- StaffRateThrottle: For staff/admin users (higher limits)
- BurstRateThrottle: For short-term burst protection
- SustainedRateThrottle: For long-term sustained usage
- UploadRateThrottle: For file upload endpoints
- ExportRateThrottle: For report export endpoints
- LoginRateThrottle: For authentication endpoints
- StripeRateThrottle: For strict rate limiting on sensitive operations

Usage:
    # In ViewSet or APIView
    from core.throttling import UserRateThrottle, BurstRateThrottle

    class MyViewSet(viewsets.ModelViewSet):
        throttle_classes = [UserRateThrottle, BurstRateThrottle]
"""

import logging
from rest_framework.throttling import (
    AnonRateThrottle as DRFAnonRateThrottle,
    UserRateThrottle as DRFUserRateThrottle,
    SimpleRateThrottle,
)
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AnonRateThrottle(DRFAnonRateThrottle):
    """
    Throttle for anonymous users.
    Rate: 100 requests per hour (configurable in settings)

    Scope: 'anon'
    """
    scope = 'anon'

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            logger.warning(
                f"Anonymous rate limit exceeded from IP: {self.get_ident(request)}"
            )
        return allowed


class UserRateThrottle(DRFUserRateThrottle):
    """
    Throttle for authenticated users (general usage).
    Rate: 1000 requests per hour (configurable in settings)

    Scope: 'user'
    """
    scope = 'user'

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            user = request.user
            logger.warning(
                f"User rate limit exceeded for user: {user.username if user.is_authenticated else 'Anonymous'}"
            )
        return allowed


class StaffRateThrottle(SimpleRateThrottle):
    """
    Throttle for staff/admin users (higher limits).
    Rate: 5000 requests per hour (configurable in settings)

    Scope: 'staff'
    """
    scope = 'staff'

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None  # Don't throttle unauthenticated users with this class

        if not request.user.is_staff:
            return None  # Only throttle staff users

        return self.cache_format % {
            'scope': self.scope,
            'ident': request.user.pk
        }

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            logger.warning(
                f"Staff rate limit exceeded for user: {request.user.username}"
            )
        return allowed


class BurstRateThrottle(SimpleRateThrottle):
    """
    Short-term burst protection.
    Rate: 60 requests per minute (configurable in settings)

    Prevents rapid-fire requests within a short time window.
    Scope: 'burst'
    """
    scope = 'burst'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            user = request.user
            logger.warning(
                f"Burst rate limit exceeded for: {user.username if user.is_authenticated else self.get_ident(request)}"
            )
        return allowed


class SustainedRateThrottle(SimpleRateThrottle):
    """
    Long-term sustained usage throttle.
    Rate: 10000 requests per day (configurable in settings)

    Prevents excessive usage over extended periods.
    Scope: 'sustained'
    """
    scope = 'sustained'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            user = request.user
            logger.warning(
                f"Sustained rate limit exceeded for: {user.username if user.is_authenticated else self.get_ident(request)}"
            )
        return allowed


class UploadRateThrottle(SimpleRateThrottle):
    """
    Throttle for file upload endpoints.
    Rate: 20 requests per hour (configurable in settings)

    Stricter limits for resource-intensive operations.
    Scope: 'upload'
    """
    scope = 'upload'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            user = request.user
            logger.warning(
                f"Upload rate limit exceeded for: {user.username if user.is_authenticated else self.get_ident(request)}"
            )
        return allowed


class ExportRateThrottle(SimpleRateThrottle):
    """
    Throttle for report export endpoints (Excel, PDF, etc.).
    Rate: 30 requests per hour (configurable in settings)

    Prevents abuse of resource-intensive export operations.
    Scope: 'export'
    """
    scope = 'export'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            user = request.user
            logger.warning(
                f"Export rate limit exceeded for: {user.username if user.is_authenticated else self.get_ident(request)}"
            )
        return allowed


class LoginRateThrottle(SimpleRateThrottle):
    """
    Throttle for authentication endpoints (login, token generation).
    Rate: 5 requests per minute (configurable in settings)

    Protects against brute-force attacks on authentication.
    Scope: 'login'
    """
    scope = 'login'

    def get_cache_key(self, request, view):
        # Use IP address for login throttling (before authentication)
        ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            logger.warning(
                f"Login rate limit exceeded from IP: {self.get_ident(request)}"
            )
        return allowed


class StrictRateThrottle(SimpleRateThrottle):
    """
    Strict throttle for sensitive operations (delete, bulk operations).
    Rate: 10 requests per hour (configurable in settings)

    Very strict limits for dangerous or sensitive operations.
    Scope: 'strict'
    """
    scope = 'strict'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            user = request.user
            logger.warning(
                f"Strict rate limit exceeded for: {user.username if user.is_authenticated else self.get_ident(request)}"
            )
        return allowed


class PerViewRateThrottle(SimpleRateThrottle):
    """
    Custom throttle that allows per-view rate limiting.

    Usage:
        class MyView(APIView):
            throttle_classes = [PerViewRateThrottle]
            throttle_scope = 'my_custom_scope'

        # In settings.py:
        REST_FRAMEWORK = {
            'DEFAULT_THROTTLE_RATES': {
                'my_custom_scope': '100/hour',
            }
        }
    """

    def get_cache_key(self, request, view):
        # Get scope from view if defined
        if hasattr(view, 'throttle_scope'):
            self.scope = view.throttle_scope

        if not self.scope:
            return None

        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


# Throttle utilities

def get_throttle_status(request, throttle_class):
    """
    Get current throttle status for a request.

    Args:
        request: Django request object
        throttle_class: Throttle class to check

    Returns:
        dict: {
            'allowed': bool,
            'rate': str,
            'remaining': int,
            'available_in': int (seconds)
        }
    """
    throttle = throttle_class()

    # Get rate
    rate = throttle.get_rate()

    # Check if request would be allowed
    if request.user.is_authenticated:
        ident = request.user.pk
    else:
        ident = throttle.get_ident(request)

    cache_key = throttle.cache_format % {
        'scope': throttle.scope,
        'ident': ident
    }

    # Get current history from cache
    history = cache.get(cache_key, [])
    now = throttle.timer()

    # Calculate how many requests are in the current window
    num_requests, duration = throttle.parse_rate(rate)

    # Remove old requests outside the window
    while history and history[-1] <= now - duration:
        history.pop()

    remaining = num_requests - len(history)

    # Calculate when next request will be available
    available_in = 0
    if remaining <= 0 and history:
        available_in = int(duration - (now - history[-1]))

    return {
        'allowed': remaining > 0,
        'rate': rate,
        'remaining': max(0, remaining),
        'available_in': max(0, available_in),
        'limit': num_requests,
        'duration': duration
    }


def reset_throttle(user_id=None, ip_address=None, scope='user'):
    """
    Reset throttle for a specific user or IP.

    Args:
        user_id: User ID to reset (optional)
        ip_address: IP address to reset (optional)
        scope: Throttle scope to reset
    """
    if user_id:
        cache_key = f'throttle_{scope}_{user_id}'
        cache.delete(cache_key)
        logger.info(f"Reset throttle for user {user_id}, scope: {scope}")

    if ip_address:
        cache_key = f'throttle_{scope}_{ip_address}'
        cache.delete(cache_key)
        logger.info(f"Reset throttle for IP {ip_address}, scope: {scope}")


def get_all_throttle_status(request):
    """
    Get throttle status for all common throttle classes.

    Args:
        request: Django request object

    Returns:
        dict: Throttle status for each scope
    """
    throttles = {
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

    status = {}
    for scope, throttle_class in throttles.items():
        try:
            status[scope] = get_throttle_status(request, throttle_class)
        except Exception as e:
            logger.error(f"Error getting throttle status for {scope}: {e}")
            status[scope] = {'error': str(e)}

    return status
