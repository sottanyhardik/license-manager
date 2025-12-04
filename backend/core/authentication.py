"""
Custom authentication classes for the License Manager application.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed


class JWTAuthenticationFromQueryParam(JWTAuthentication):
    """
    JWT Authentication that supports both:
    1. Authorization header (standard)
    2. access_token query parameter (for PDF URLs)

    This allows PDFs to be opened with direct URLs instead of blob URLs.
    """

    def authenticate(self, request):
        # First try the standard Authorization header
        header_auth = super().authenticate(request)
        if header_auth is not None:
            return header_auth

        # If no header auth, try query parameter
        access_token = request.query_params.get('access_token')
        if access_token:
            try:
                validated_token = self.get_validated_token(access_token)
                return self.get_user(validated_token), validated_token
            except (InvalidToken, AuthenticationFailed):
                pass

        return None
