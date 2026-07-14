# accounts/views.py
"""
Auth endpoints — all under /api/v1/auth/.

All responses are wrapped in the standard envelope:
  {"success": true/false, "data": ..., "message": ...}

Views contain NO business logic — they delegate to serializers and SimpleJWT.
"""
from django.contrib.auth import get_user_model
from rest_framework import filters, status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView
from shared.pagination import StandardPagination
from shared.permissions import IsAdminUser
from shared.serializers import EnvelopeMixin

from .serializers import LoginSerializer, UserSerializer, UsersListSerializer

User = get_user_model()


class LoginRateThrottle(AnonRateThrottle):
    rate = '5/min'


class LoginView(APIView):
    """
    POST /api/v1/auth/login/

    Body:   {"username": "...", "password": "..."}
    Returns {"success": true, "data": {"access": "...", "refresh": "...", "user": {...}}}
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            return Response(
                EnvelopeMixin.wrap(
                    success=False,
                    errors=serializer.errors,
                    message="Invalid credentials.",
                ),
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)

        return Response(
            EnvelopeMixin.wrap(
                data={
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user": UserSerializer(user, context={"request": request}).data,
                }
            ),
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/

    Body:   {"refresh": "<refresh_token>"}
    Action: blacklists the refresh token (requires token_blacklist app).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        token_str = request.data.get("refresh")
        if not token_str:
            return Response(
                EnvelopeMixin.wrap(success=False, message="refresh token required."),
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(token_str).blacklist()
        except TokenError:
            return Response(
                EnvelopeMixin.wrap(success=False, message="Invalid or already-used refresh token."),
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            EnvelopeMixin.wrap(data=None, message="Logged out successfully."),
            status=status.HTTP_200_OK,
        )


class TokenRefreshView(BaseTokenRefreshView):
    """
    POST /api/v1/auth/token/refresh/

    Body:    {"refresh": "<refresh_token>"}
    Returns: {"success": true, "data": {"access": "...", "refresh": "..."}}

    Wraps the SimpleJWT base view in the standard envelope.
    ROTATE_REFRESH_TOKENS=True means the old refresh is blacklisted on rotation.
    """

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc

        return Response(
            EnvelopeMixin.wrap(data=serializer.validated_data),
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """
    GET /api/v1/auth/me/

    Returns the authenticated user's profile and roles.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = User.objects.prefetch_related("groups").get(pk=request.user.pk)
        serializer = UserSerializer(user, context={"request": request})
        return Response(
            EnvelopeMixin.wrap(data=serializer.data),
            status=status.HTTP_200_OK,
        )


class UsersView(ListAPIView):
    """
    GET /api/v1/auth/users/

    Returns a paginated list of all users (staff / superuser access only).
    Supports ?search=<username|email|first_name|last_name>.
    """

    serializer_class = UsersListSerializer
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["username", "email", "first_name", "last_name"]

    def get_permissions(self):
        return [IsAdminUser()]

    def get_queryset(self):
        return (
            User.objects.prefetch_related("groups")
            .order_by("username")
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            EnvelopeMixin.wrap(data=serializer.data),
            status=status.HTTP_200_OK,
        )
