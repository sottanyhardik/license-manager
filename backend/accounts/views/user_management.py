# accounts/views/user_management.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model

from ..serializers import UserManagementSerializer, UserRoleAssignmentSerializer
from ..permissions import UserManagementPermission

User = get_user_model()


class UserManagementViewSet(viewsets.ModelViewSet):
    """ViewSet for managing users (USER_MANAGER role or superuser)"""
    queryset = User.objects.prefetch_related('roles').all().order_by('-date_joined')
    serializer_class = UserManagementSerializer
    permission_classes = [UserManagementPermission]

    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        """Reset user password"""
        user = self.get_object()
        password = request.data.get('password')
        if not password:
            return Response({'error': 'Password is required'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(password)
        user.save()
        return Response({'message': 'Password reset successfully'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='assign-roles')
    def assign_roles(self, request, pk=None):
        """Assign roles to a user"""
        user = self.get_object()
        serializer = UserRoleAssignmentSerializer(data={'user_id': user.id, 'role_ids': request.data.get('role_ids', [])})

        if serializer.is_valid():
            user.roles.set(serializer.validated_data['role_ids'])
            return Response({
                'message': 'Roles assigned successfully',
                'roles': user.get_role_codes()
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='remove-roles')
    def remove_roles(self, request, pk=None):
        """Remove roles from a user"""
        user = self.get_object()
        role_ids = request.data.get('role_ids', [])

        if not role_ids:
            return Response({'error': 'role_ids is required'}, status=status.HTTP_400_BAD_REQUEST)

        user.roles.remove(*role_ids)
        return Response({
            'message': 'Roles removed successfully',
            'roles': user.get_role_codes()
        }, status=status.HTTP_200_OK)
