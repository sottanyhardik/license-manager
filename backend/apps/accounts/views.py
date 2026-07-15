# accounts/views.py
"""
Auth endpoints — all under /api/v1/auth/.

All responses are wrapped in the standard envelope:
  {"success": true/false, "data": ..., "message": ...}

Views contain NO business logic — they delegate to serializers and SimpleJWT.
"""
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
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

from .permissions import UserManagementPermission
from .serializers import LoginSerializer, UserManagementSerializer, UserSerializer, UsersListSerializer

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
    GET /api/v1/auth/users/ (legacy list-only view — kept for backward compat).

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


# Role codes replicated from legacy — single source of truth for the API response.
_ROLE_CODES = [
    "USER_MANAGER",
    "LICENSE_MANAGER",
    "LICENSE_VIEWER",
    "ALLOTMENT_MANAGER",
    "ALLOTMENT_VIEWER",
    "BOE_MANAGER",
    "BOE_VIEWER",
    "TRADE_MANAGER",
    "TRADE_VIEWER",
    "INCENTIVE_LICENSE_MANAGER",
    "INCENTIVE_LICENSE_VIEWER",
    "REPORT_VIEWER",
    "TL_GENERATE",
    "LEDGER_MANAGER",
    "ACCOUNT_ACCESS",
]


class UserViewSet(viewsets.ModelViewSet):
    """
    Full CRUD + actions for user administration.

    Endpoints (all under /api/v1/auth/users/):
      GET    /                      — paginated list with search + role/is_active filters
      POST   /                      — create user with roles
      GET    /{id}/                 — retrieve
      PUT    /{id}/                 — update
      PATCH  /{id}/                 — partial update
      DELETE /{id}/                 — delete (superuser only)
      GET    /available-roles/      — list of all RBAC role codes
      POST   /{id}/reset-password/  — admin password reset (superuser only, no SMTP)

    Permissions:
      - List/detail/create/update: USER_MANAGER role or superuser
      - Delete / reset-password:   superuser only
    """

    queryset = User.objects.prefetch_related("groups").order_by("-date_joined")
    serializer_class = UserManagementSerializer
    permission_classes = [UserManagementPermission]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # Search by username, email, first_name, or last_name
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        # Filter by role (group name)
        role = params.get("role", "").strip()
        if role:
            qs = qs.filter(groups__name=role)

        # Filter by active status
        is_active = params.get("is_active", "").strip().lower()
        if is_active in ("true", "1"):
            qs = qs.filter(is_active=True)
        elif is_active in ("false", "0"):
            qs = qs.filter(is_active=False)

        return qs.distinct()

    def get_permissions(self):
        """
        Delete and reset-password require superuser.
        All other actions require USER_MANAGER or superuser.
        """
        if self.action in ("destroy", "reset_password"):
            from rest_framework.permissions import IsAuthenticated

            class SuperuserOnly(IsAuthenticated):
                def has_permission(self, request, view):
                    return (
                        super().has_permission(request, view)
                        and request.user.is_active
                        and request.user.is_superuser
                    )

            return [SuperuserOnly()]
        return [UserManagementPermission()]

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

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(
            EnvelopeMixin.wrap(data=serializer.data),
            status=status.HTTP_200_OK,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            EnvelopeMixin.wrap(
                data=self.get_serializer(instance).data,
                message="User created successfully.",
            ),
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            EnvelopeMixin.wrap(
                data=self.get_serializer(instance).data,
                message="User updated successfully.",
            ),
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(
            EnvelopeMixin.wrap(data=None, message="User deleted."),
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="available-roles")
    def available_roles(self, request):
        """Return the list of predefined RBAC role codes."""
        return Response(
            EnvelopeMixin.wrap(data=_ROLE_CODES),
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        """
        Admin-only direct password reset (OQ-4: no SMTP / email).
        Body: {"new_password": "..."}
        """
        user = self.get_object()
        new_password = request.data.get("new_password", "").strip()
        if not new_password:
            return Response(
                EnvelopeMixin.wrap(success=False, message="new_password is required."),
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response(
            EnvelopeMixin.wrap(data=None, message="Password updated successfully."),
            status=status.HTTP_200_OK,
        )
