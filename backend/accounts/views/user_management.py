# accounts/views/user_management.py
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..serializers import UserManagementSerializer
from ..permissions import UserManagementPermission

User = get_user_model()

ROLE_CODES = [
    'USER_MANAGER',
    'LICENSE_MANAGER',
    'LICENSE_VIEWER',
    'ALLOTMENT_MANAGER',
    'ALLOTMENT_VIEWER',
    'BOE_MANAGER',
    'BOE_VIEWER',
    'TRADE_MANAGER',
    'TRADE_VIEWER',
    'INCENTIVE_LICENSE_MANAGER',
    'INCENTIVE_LICENSE_VIEWER',
    'REPORT_VIEWER',
    'TL_GENERATE',
    'LEDGER_MANAGER',
    'ACCOUNT_ACCESS',
]


class UserManagementViewSet(viewsets.ModelViewSet):
    """ViewSet for managing users — accessible to superusers and USER_MANAGER role."""
    queryset = User.objects.prefetch_related('groups').order_by('-date_joined')
    serializer_class = UserManagementSerializer
    permission_classes = [UserManagementPermission]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # Search by username or email
        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(username__icontains=search) | Q(email__icontains=search))

        # Filter by role (group name)
        role = params.get('role', '').strip()
        if role:
            qs = qs.filter(groups__name=role)

        # Filter by active status
        is_active = params.get('is_active', '').strip()
        if is_active.lower() in ('true', '1'):
            qs = qs.filter(is_active=True)
        elif is_active.lower() in ('false', '0'):
            qs = qs.filter(is_active=False)

        return qs.distinct()

    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        """Reset a user's password."""
        user = self.get_object()
        password = request.data.get('password')
        if not password:
            return Response({'error': 'Password is required'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(password)
        user.save()
        return Response({'message': 'Password reset successfully'})

    @action(detail=False, methods=['get'], url_path='available-roles')
    def available_roles(self, request):
        """Return the list of predefined role codes."""
        return Response(ROLE_CODES)
