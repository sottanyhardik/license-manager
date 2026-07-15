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
    """
    Balance snapshot for a license.

    In addition to the stored balance_cif, exposes three computed breakdown
    fields so the UI can render a full balance summary without additional
    API calls:

      total_authorised  — SUM(export items CIF FC)  [the "credit" side]
      total_debited     — SUM(BOE RowDetails CIF FC) [direct debit consumption]
      total_allotted    — SUM(pending AllotmentItems CIF FC) [reserved, not yet debited]

    These are computed on-the-fly from the live DB state (same formulas used
    by balance_service._compute_*) so they are always consistent with
    balance_cif = max(0, total_authorised - total_debited - total_allotted - trade).

    Only used on the license detail endpoint — single record, so the extra
    DB round-trips are acceptable.
    """

    total_authorised = serializers.SerializerMethodField()
    total_debited = serializers.SerializerMethodField()
    total_allotted = serializers.SerializerMethodField()

    class Meta:
        model = LicenseBalance
        fields = ["balance_cif", "ledger_date", "total_authorised", "total_debited", "total_allotted"]
        read_only_fields = ["balance_cif", "ledger_date", "total_authorised", "total_debited", "total_allotted"]

    def get_total_authorised(self, obj) -> str | None:
        from apps.license.services.balance_service import _compute_credit
        try:
            return str(_compute_credit(obj.license_id))
        except Exception:
            return None

    def get_total_debited(self, obj) -> str | None:
        from apps.license.services.balance_service import _compute_debit
        try:
            return str(_compute_debit(obj.license_id))
        except Exception:
            return None

    def get_total_allotted(self, obj) -> str | None:
        from apps.license.services.balance_service import _compute_allotment
        try:
            return str(_compute_allotment(obj.license_id))
        except Exception:
            return None


class LicenseFlagsSerializer(serializers.ModelSerializer):
    balance_status = serializers.SerializerMethodField()

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
            "balance_status",  # NEW: "healthy" | "null" | "negative"
        ]
        read_only_fields = fields

    def get_balance_status(self, obj) -> str:
        """
        Richer status replacing the boolean is_null (BD-003).
        Returns: 'negative' | 'null' | 'healthy'
        """
        try:
            balance_cif = obj.license.balance.balance_cif
            if balance_cif < 0:
                return "negative"
            if balance_cif < 500:  # _NULL_THRESHOLD
                return "null"
            return "healthy"
        except Exception:
            return "healthy"


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
            "exporter_name",      # company column in list
            "scheme_code_display",  # serves as license_type (e.g. "DFIA", "RODTEP")
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

    Planning fields (planned_quantity, planned_cif_fc) are fetched from the
    related LicenseItemPlan row (if one exists). They are read-only in this
    serializer — plans are managed via the /api/v1/licenses/{id}/item-plans/
    endpoint.
    """

    hs_code_display = serializers.CharField(
        source="hs_code.code", read_only=True, default=None
    )

    # Planning fields — derived from LicenseItemPlan (may be null if no plan exists)
    planned_quantity = serializers.SerializerMethodField()
    planned_cif_fc = serializers.SerializerMethodField()

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
            # Planning fields
            "planned_quantity",
            "planned_cif_fc",
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
            # Planning fields — managed via item-plans endpoint
            "planned_quantity",
            "planned_cif_fc",
        ]

    def get_planned_quantity(self, obj) -> str | None:
        """Return planned_quantity from the first LicenseItemPlan for this item, or None."""
        from apps.license.models import LicenseItemPlan
        plan = LicenseItemPlan.objects.filter(import_item_id=obj.pk).first()
        return str(plan.planned_quantity) if plan else None

    def get_planned_cif_fc(self, obj) -> str | None:
        """Return planned_cif_fc from the first LicenseItemPlan for this item, or None."""
        from apps.license.models import LicenseItemPlan
        plan = LicenseItemPlan.objects.filter(import_item_id=obj.pk).first()
        return str(plan.planned_cif_fc) if plan else None


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
    """
    Serializer for IncentiveLicense (RODTEP / ROSTL / MEIS).

    Value fields (sold_value, balance_value) are read-only — updated by
    the trade signal via IncentiveLicense.update_sold_status().
    sold_status is also read-only for the same reason.
    expiry_date is auto-calculated in IncentiveLicense.save() and is
    excluded from writable fields.
    """

    exporter_name = serializers.CharField(
        source="exporter.name", read_only=True, default=None
    )
    port_display = serializers.CharField(
        source="port_code.name", read_only=True, default=None
    )
    sold_value = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    balance_value = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )

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
        read_only_fields = [
            "id",
            "exporter_name",
            "port_display",
            "sold_value",
            "balance_value",
            "sold_status",
            "license_expiry_date",
            "created_on",
            "modified_on",
        ]

    def validate_license_number(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("License number may not be blank.")
        instance = self.instance
        qs = IncentiveLicense.objects.filter(license_number=value)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f"An incentive license with number '{value}' already exists."
            )
        return value
