# license/serializers/license.py
"""
Serializers for the License module.

Naming convention:
  - *ListSerializer   — minimal fields for list/search responses (fast)
  - *DetailSerializer — full nested read-only representation
  - *CreateSerializer — writable fields for create/update operations

All serializers use ModelSerializer; nested sub-objects (balance, flags,
notes, ownership) are declared read_only=True so they cannot be mutated
through the parent license endpoint.
"""
from rest_framework import serializers

from apps.license.models import (
    IncentiveLicense,
    LicenseBalance,
    LicenseDetailsModel,
    LicenseDocumentModel,
    LicenseFlags,
    LicenseImportItemsModel,
    LicenseNotes,
    LicenseOwnership,
)

# ---------------------------------------------------------------------------
# Nested read-only sub-serializers
# ---------------------------------------------------------------------------


class LicenseBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LicenseBalance
        fields = ["balance_cif", "ledger_date"]
        read_only_fields = ["balance_cif", "ledger_date"]


class LicenseFlagsSerializer(serializers.ModelSerializer):
    class Meta:
        model = LicenseFlags
        fields = [
            "is_active",
            "is_audit",
            "is_mnm",
            "is_not_registered",
            "is_null",
            "is_au",
            "is_incomplete",
            "is_expired",
            "is_individual",
        ]
        read_only_fields = fields


class LicenseNotesSerializer(serializers.ModelSerializer):
    class Meta:
        model = LicenseNotes
        fields = [
            "user_comment",
            "condition_sheet",
            "user_restrictions",
            "balance_report_notes",
        ]
        read_only_fields = fields


class LicenseOwnershipSerializer(serializers.ModelSerializer):
    current_owner_name = serializers.CharField(
        source="current_owner.name", read_only=True, default=None
    )

    class Meta:
        model = LicenseOwnership
        fields = ["current_owner", "current_owner_name", "file_transfer_status", "last_ownership_fetch"]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# License serializers
# ---------------------------------------------------------------------------


class LicenseListSerializer(serializers.ModelSerializer):
    """
    Minimal projection used in list / search responses.

    exporter_name and balance_cif are denormalized from related rows to avoid
    extra per-row queries — the queryset must select_related('exporter', 'balance').
    """

    exporter_name = serializers.CharField(source="exporter.name", read_only=True, default=None)
    balance_cif = serializers.DecimalField(
        source="balance.balance_cif",
        max_digits=15,
        decimal_places=2,
        read_only=True,
        default=None,
    )
    scheme_code_display = serializers.CharField(
        source="scheme_code.code", read_only=True, default=None
    )
    is_expired = serializers.BooleanField(
        source="flags.is_expired", read_only=True, default=None
    )
    is_active = serializers.BooleanField(
        source="flags.is_active", read_only=True, default=None
    )

    class Meta:
        model = LicenseDetailsModel
        fields = [
            "id",
            "license_number",
            "license_date",
            "license_expiry_date",
            "exporter_name",
            "scheme_code_display",
            "balance_cif",
            "is_expired",
            "is_active",
        ]


class LicenseDetailSerializer(serializers.ModelSerializer):
    """
    Full representation of a license including all satellite rows.

    Used for retrieve() only — all nested fields are read_only.
    """

    balance = LicenseBalanceSerializer(read_only=True)
    flags = LicenseFlagsSerializer(read_only=True)
    notes = LicenseNotesSerializer(read_only=True)
    ownership = LicenseOwnershipSerializer(read_only=True)

    exporter_name = serializers.CharField(source="exporter.name", read_only=True, default=None)
    scheme_code_display = serializers.CharField(
        source="scheme_code.code", read_only=True, default=None
    )
    notification_number_display = serializers.CharField(
        source="notification_number.number", read_only=True, default=None
    )
    port_display = serializers.CharField(source="port.name", read_only=True, default=None)
    purchase_status_display = serializers.CharField(
        source="purchase_status.name", read_only=True, default=None
    )

    class Meta:
        model = LicenseDetailsModel
        fields = [
            "id",
            "license_number",
            "license_date",
            "license_expiry_date",
            "file_number",
            "registration_number",
            "registration_date",
            "ge_file_number",
            "archived_exporter_name",
            "exporter",
            "exporter_name",
            "port",
            "port_display",
            "scheme_code",
            "scheme_code_display",
            "notification_number",
            "notification_number_display",
            "purchase_status",
            "purchase_status_display",
            "created_on",
            "modified_on",
            "balance",
            "flags",
            "notes",
            "ownership",
        ]
        read_only_fields = fields


class LicenseCreateSerializer(serializers.ModelSerializer):
    """
    Writable serializer used by create and update endpoints.

    FK fields accept PK integers (write_only).  Validation is DRF-standard;
    the actual object creation delegates to license_service.create_license().
    """

    class Meta:
        model = LicenseDetailsModel
        fields = [
            "license_number",
            "license_date",
            "license_expiry_date",
            "file_number",
            "registration_number",
            "registration_date",
            "ge_file_number",
            "archived_exporter_name",
            "exporter",
            "port",
            "scheme_code",
            "notification_number",
            "purchase_status",
        ]

    def validate_license_number(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("License number may not be blank.")
        # On update, exclude self from uniqueness check
        instance = self.instance
        qs = LicenseDetailsModel.objects.filter(license_number=value)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f"A license with number '{value}' already exists."
            )
        return value


# ---------------------------------------------------------------------------
# Import item serializer
# ---------------------------------------------------------------------------


class ImportItemSerializer(serializers.ModelSerializer):
    """
    Full CRUD serializer for LicenseImportItemsModel.

    hs_code accepts a PK on write; hs_code_display is a read-only label.
    """

    hs_code_display = serializers.CharField(
        source="hs_code.code", read_only=True, default=None
    )

    class Meta:
        model = LicenseImportItemsModel
        fields = [
            "id",
            "license",
            "serial_number",
            "description",
            "quantity",
            "old_quantity",
            "unit",
            "cif_fc",
            "cif_inr",
            "available_quantity",
            "available_value",
            "debited_quantity",
            "debited_value",
            "allotted_quantity",
            "allotted_value",
            "is_restricted",
            "condition_type",
            "comment",
            "hs_code",
            "hs_code_display",
        ]
        read_only_fields = [
            "id",
            "license",
            "hs_code_display",
            # Derived balance fields — updated by balance_service
            "available_quantity",
            "available_value",
            "debited_quantity",
            "debited_value",
            "allotted_quantity",
            "allotted_value",
        ]


# ---------------------------------------------------------------------------
# Document serializer
# ---------------------------------------------------------------------------


class LicenseDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LicenseDocumentModel
        fields = ["id", "license", "type", "file"]
        read_only_fields = ["id"]


# ---------------------------------------------------------------------------
# Incentive license serializer
# ---------------------------------------------------------------------------


class IncentiveLicenseSerializer(serializers.ModelSerializer):
    exporter_name = serializers.CharField(source="exporter.name", read_only=True, default=None)
    port_display = serializers.CharField(source="port_code.name", read_only=True, default=None)

    class Meta:
        model = IncentiveLicense
        fields = [
            "id",
            "exporter",
            "exporter_name",
            "port_code",
            "port_display",
            "license_type",
            "license_number",
            "license_date",
            "license_expiry_date",
            "license_value",
            "sold_value",
            "balance_value",
            "sold_status",
            "is_active",
            "notes",
            "created_on",
            "modified_on",
        ]
        read_only_fields = ["id", "exporter_name", "port_display", "balance_value", "created_on", "modified_on"]
