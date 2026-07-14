from rest_framework import serializers


class DashboardStatsSerializer(serializers.Serializer):
    total_licenses = serializers.IntegerField()
    active_licenses = serializers.IntegerField()
    expired_licenses = serializers.IntegerField()
    null_licenses = serializers.IntegerField()
    expiring_soon = serializers.IntegerField()
    total_balance_cif = serializers.CharField()
    recent_boes = serializers.IntegerField()
    recent_allotments = serializers.IntegerField()
    low_balance_licenses = serializers.IntegerField()


class ExpiringLicenseSerializer(serializers.Serializer):
    license_number = serializers.CharField()
    license_expiry_date = serializers.DateField()
    balance_cif = serializers.CharField()
    days_to_expiry = serializers.IntegerField()
