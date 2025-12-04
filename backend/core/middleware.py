"""
Custom middleware for License Manager
"""
from django.utils.deprecation import MiddlewareMixin


class DisableCSRFForAPIMiddleware(MiddlewareMixin):
    """
    Disable CSRF validation for API endpoints that use JWT authentication.

    This middleware exempts /api/ endpoints from CSRF validation since they use
    JWT tokens in the Authorization header instead of session-based authentication.
    """

    def process_request(self, request):
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)
        return None
