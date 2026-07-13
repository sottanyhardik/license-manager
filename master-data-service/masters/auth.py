"""Service-to-service token auth + scope permission for the MDS API."""

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission


class ServiceClient:
    """A lightweight authenticated principal (a consuming service, not a user)."""

    is_authenticated = True

    def __init__(self, token, scope):
        self.token = token
        self.scope = scope

    def __str__(self):
        return f"service:{self.scope}"


class ServiceTokenAuthentication(BaseAuthentication):
    """`Authorization: Bearer <token>` matched against settings.MDS_SERVICE_TOKENS."""

    keyword = "Bearer"

    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header:
            return None  # no credentials -> permission layer denies
        parts = header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            raise AuthenticationFailed("Invalid Authorization header. Use 'Bearer <token>'.")
        scope = settings.MDS_SERVICE_TOKENS.get(parts[1])
        if scope is None:
            raise AuthenticationFailed("Invalid service token.")
        return (ServiceClient(parts[1], scope), parts[1])


class HasServiceScope(BasePermission):
    """Any valid token may read; only 'write'-scoped tokens may mutate."""

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    def has_permission(self, request, view):
        client = request.user
        scope = getattr(client, "scope", None)
        if not scope:
            return False
        if request.method in self.SAFE_METHODS:
            return True
        return scope == "write"
