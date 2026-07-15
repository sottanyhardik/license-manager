"""Notification views for license balance exceptions."""
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from shared.pagination import StandardPagination
from shared.serializers import EnvelopeMixin

from apps.accounts.permissions import LicensePermission
from apps.notifications.models import LicenseBalanceNotification
from apps.notifications.serializers import LicenseBalanceNotificationSerializer


class LicenseBalanceNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read + lifecycle actions for negative-balance notifications.

    GET    /api/v1/notifications/balance/              -> list active
    GET    /api/v1/notifications/balance/{id}/         -> detail
    POST   /api/v1/notifications/balance/{id}/acknowledge/ -> acknowledge
    POST   /api/v1/notifications/balance/{id}/resolve/    -> resolve
    """

    permission_classes = [LicensePermission]
    serializer_class = LicenseBalanceNotificationSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = LicenseBalanceNotification.objects.select_related(
            "license", "acknowledged_by", "resolved_by"
        )
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        else:
            qs = qs.filter(status=LicenseBalanceNotification.STATUS_ACTIVE)
        return qs

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        """Mark notification as acknowledged."""
        notif = self.get_object()
        if notif.status != LicenseBalanceNotification.STATUS_ACTIVE:
            return Response(
                EnvelopeMixin.wrap(message="Only ACTIVE notifications can be acknowledged."),
                status=status.HTTP_400_BAD_REQUEST,
            )
        notif.status = LicenseBalanceNotification.STATUS_ACKNOWLEDGED
        notif.acknowledged_by = request.user
        notif.acknowledged_at = timezone.now()
        notif.acknowledgement_remarks = request.data.get("remarks", "")
        notif.save(update_fields=[
            "status", "acknowledged_by", "acknowledged_at",
            "acknowledgement_remarks", "updated_at",
        ])
        return Response(EnvelopeMixin.wrap(
            data=LicenseBalanceNotificationSerializer(notif).data,
            message="Notification acknowledged.",
        ))

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        """Mark notification as resolved."""
        notif = self.get_object()
        if notif.status == LicenseBalanceNotification.STATUS_RESOLVED:
            return Response(
                EnvelopeMixin.wrap(message="Notification is already resolved."),
                status=status.HTTP_400_BAD_REQUEST,
            )
        notif.status = LicenseBalanceNotification.STATUS_RESOLVED
        notif.resolved_by = request.user
        notif.resolved_at = timezone.now()
        notif.resolution_remarks = request.data.get("remarks", "")
        notif.save(update_fields=["status", "resolved_by", "resolved_at", "resolution_remarks", "updated_at"])
        return Response(EnvelopeMixin.wrap(
            data=LicenseBalanceNotificationSerializer(notif).data,
            message="Notification resolved.",
        ))
