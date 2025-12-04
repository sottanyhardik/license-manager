# accounts/views/user_management.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model

from ..serializers import UserManagementSerializer

User = get_user_model()


class IsAdmin(IsAuthenticated):
    """Permission class to check if user is admin"""
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == 'admin'


class UserManagementViewSet(viewsets.ModelViewSet):
    """ViewSet for managing users (admin only)"""
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserManagementSerializer
    permission_classes = [IsAdmin]

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
