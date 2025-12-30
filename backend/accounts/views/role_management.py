# accounts/views/role_management.py
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from ..models import Role
from ..serializers import RoleSerializer
from ..permissions import UserManagementPermission


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing roles
    Only USER_MANAGER can view roles
    Roles are predefined and cannot be created/updated/deleted via API
    """
    queryset = Role.objects.filter(is_active=True).order_by('name')
    serializer_class = RoleSerializer
    permission_classes = [UserManagementPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['code', 'is_active']
    search_fields = ['name', 'code', 'description']

    @action(detail=False, methods=['get'])
    def all_codes(self, request):
        """Get all role codes for reference"""
        codes = [{'code': code, 'name': name} for code, name in Role.ROLE_CODES]
        return Response(codes)
