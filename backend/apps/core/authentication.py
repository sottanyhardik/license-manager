"""
Custom authentication classes for the License Manager application.
"""
import logging

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed

logger = logging.getLogger(__name__)


QUERY_PARAM_TOKEN_PATH_KEYWORDS = (
    'download',
    'pdf',
    'excel',
    'export',
    'generate-bill',
    'balance-pdf',
    'balance-excel',
    'generate-transfer',
    'generate-pdf',
    'generate-purchase',
    'balance-report',
)


class JWTAuthenticationFromQueryParam(JWTAuthentication):
    """
    JWT Authentication that supports both:
    1. Authorization header (standard)
    2. access_token query parameter (for PDF URLs)

    Query-string tokens are restricted to GET/HEAD download/export style URLs to
    avoid accepting bearer credentials on normal API endpoints.
    """

    def authenticate(self, request):
        # First try the standard Authorization header
        header_auth = super().authenticate(request)
        if header_auth is not None:
            return header_auth

        # If no header auth, try query parameter
        # Handle both request.query_params (DRF) and request.GET (Django)
        access_token = None
        if hasattr(request, 'query_params'):
            access_token = request.query_params.get('access_token')
        elif hasattr(request, 'GET'):
            access_token = request.GET.get('access_token')

        if access_token:
            path = getattr(request, 'path', '').lower()
            method = getattr(request, 'method', '').upper()
            if method not in {'GET', 'HEAD'} or not any(
                keyword in path for keyword in QUERY_PARAM_TOKEN_PATH_KEYWORDS
            ):
                return None

            try:
                validated_token = self.get_validated_token(access_token)
                return self.get_user(validated_token), validated_token
            except (InvalidToken, AuthenticationFailed) as e:
                logger.warning("JWT authentication failed: %s", e)

        return None
