from rest_framework import serializers

from apps.notifications.models import LicenseBalanceNotification


class LicenseBalanceNotificationSerializer(serializers.ModelSerializer):
    license_number = serializers.CharField(source="license.license_number", read_only=True)
    acknowledged_by_username = serializers.CharField(
        source="acknowledged_by.username", read_only=True, default=None
    )
    resolved_by_username = serializers.CharField(
        source="resolved_by.username", read_only=True, default=None
    )

    class Meta:
        model = LicenseBalanceNotification
        fields = [
            "id", "license", "license_number", "status", "balance_cif",
            "last_boe_reference", "acknowledged_by", "acknowledged_by_username",
            "acknowledged_at", "acknowledgement_remarks",
            "resolved_by", "resolved_by_username", "resolved_at", "resolution_remarks",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "license_number", "acknowledged_by_username", "resolved_by_username",
            "created_at", "updated_at",
        ]
