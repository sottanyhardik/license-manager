# core/views/activity_log.py
from django.db.models import Q
from rest_framework import serializers, viewsets

from apps.accounts.permissions import UserManagementPermission
from apps.core.models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = (
            'id', 'username', 'action', 'module', 'resource_id',
            'description', 'endpoint', 'method', 'ip_address',
            'status_code', 'timestamp',
        )


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for the audit log.
    Access: Superadmin (is_superuser) and Admin (USER_MANAGER role) only.
    Superadmin sees ALL logs; USER_MANAGER sees all logs to support user oversight.
    """
    serializer_class = ActivityLogSerializer
    permission_classes = [UserManagementPermission]
    pagination_class = None   # use DRF default; caller can add ?page_size=

    def get_queryset(self):
        qs = ActivityLog.objects.select_related('user').order_by('-timestamp')
        params = self.request.query_params

        username = params.get('username', '').strip()
        if username:
            qs = qs.filter(username__icontains=username)

        action = params.get('action', '').strip().upper()
        if action:
            qs = qs.filter(action=action)

        module = params.get('module', '').strip()
        if module:
            qs = qs.filter(module__icontains=module)

        date_from = params.get('date_from', '').strip()
        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)

        date_to = params.get('date_to', '').strip()
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)

        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search) |
                Q(description__icontains=search) |
                Q(module__icontains=search) |
                Q(ip_address__icontains=search)
            )

        limit = params.get('limit', '100')
        try:
            limit = max(1, min(int(limit), 1000))
        except (ValueError, TypeError):
            limit = 100

        return qs[:limit]
