# FILE: accounts/old_views.py
from rest_framework import viewsets, permissions, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.generics import CreateAPIView
from django.contrib.auth import get_user_model
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import RegisterSerializer, UserSerializer, AvatarSerializer
from . import services

User = get_user_model()


class RegistrationView(CreateAPIView):
    """Register new users via API."""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Allow access only to object owner or admin.
    """

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_authenticated:
            return request.user.is_superuser or obj.pk == request.user.pk
        return False


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """
    Minimal user viewset:
    - list (admin-only)
    - retrieve (owner or admin)
    - partial_update (owner or admin)
    - upload_avatar (owner)
    """
    queryset = User.objects.all().order_by("pk")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action == "list":
            permission_classes = [permissions.IsAdminUser]
        elif self.action in ("retrieve", "partial_update", "upload_avatar", "remove_avatar"):
            permission_classes = [IsOwnerOrAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [p() for p in permission_classes]

    @action(detail=False, methods=["get"], url_path="me", url_name="me")
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="avatar", url_name="avatar", parser_classes=[MultiPartParser, FormParser])
    def upload_avatar(self, request, pk=None):
        user = self.get_object()
        # only owner can upload
        if request.user.pk != user.pk and not request.user.is_superuser:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        serializer = AvatarSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            avatar = request.data.get("avatar")
            services.set_avatar(user, avatar)
            return Response(self.get_serializer(user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="avatar/remove", url_name="avatar_remove")
    def remove_avatar(self, request, pk=None):
        user = self.get_object()
        if request.user.pk != user.pk and not request.user.is_superuser:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        services.remove_avatar(user)
        return Response(status=status.HTTP_204_NO_CONTENT)
