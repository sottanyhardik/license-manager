"""SION percentage rule capacity calculation and enforcement.

Calculates and tracks usage of percentage-constrained output items
during planning and allotment.
"""
from decimal import Decimal
from django.db.models import Sum, Q
from apps.core.constants import DEC_0
from apps.license.models import LicenseDetailsModel, AllotmentItems
from apps.bill_of_entry.models import RowDetails
from apps.license.services.sion_input_classifier import SionInputClassifier


class SionPercentageRule:
    """Calculate percentage rule capacity for planning."""

    @staticmethod
    def calculate_total_eligible_cif(license_obj: LicenseDetailsModel) -> Decimal:
        """Calculate TOTAL SION eligible quantity in CIF (financial value).

        This is the authoritative base for percentage calculations.
        Not the current balance, but the original total credit.

        For export/import licenses, this is the SUM of export CIF.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Decimal CIF value (or 0 if no exports)
        """
        if not license_obj:
            return DEC_0

        # For export licenses, sum all export CIF values
        export_items = license_obj.export_items.all()
        if not export_items.exists():
            return DEC_0

        total = export_items.aggregate(
            total_cif=Sum('cif')
        )['total_cif'] or DEC_0

        return Decimal(str(total))

    @staticmethod
    def get_percentage_cap_for_input(license_obj: LicenseDetailsModel, canonical_input_code: str, percentage: Decimal) -> Decimal:
        """Calculate absolute CIF cap for a canonical input.

        Cap = total_eligible_cif × (percentage / 100)

        Args:
            license_obj: LicenseDetailsModel
            canonical_input_code: Code like "PKO", "OLIVE_OIL", "CHEESE"
            percentage: Decimal percentage (e.g., Decimal("50.00") for 50%)

        Returns:
            Decimal CIF cap for the input
        """
        if not percentage or percentage < DEC_0:
            return DEC_0

        total_cif = SionPercentageRule.calculate_total_eligible_cif(license_obj)
        if total_cif <= DEC_0:
            return DEC_0

        cap = (total_cif * percentage) / Decimal("100")
        return cap.quantize(Decimal("0.01"))

    @staticmethod
    def get_allotted_for_input(license_obj: LicenseDetailsModel, canonical_input_code: str) -> Decimal:
        """Get total allotted quantity (CIF) for a canonical input.

        Aggregates AllotmentItems where the source item maps to canonical_input_code.

        Args:
            license_obj: LicenseDetailsModel
            canonical_input_code: Code like "PKO", "OLIVE_OIL"

        Returns:
            Decimal total allotted CIF
        """
        # Get all allotment items for this license (not yet BOE-d)
        allotment_items = AllotmentItems.objects.filter(
            allotment__license=license_obj,
            allotment__bill_of_entry__isnull=True,  # Not yet debited via BOE
        ).select_related('item')

        total_cif = DEC_0
        for item in allotment_items:
            # Classify the item's source by product name
            item_name = item.item.name if item.item else item.allotment.item_name or ""
            classified = SionInputClassifier.resolve_canonical_input(item_name)
            if classified and classified.code == canonical_input_code:
                # Convert quantity to CIF using unit price
                unit_price = Decimal(str(item.item.unit_price or DEC_0)) if item.item else DEC_0
                item_cif = Decimal(str(item.qty or DEC_0)) * unit_price
                total_cif += item_cif

        return total_cif.quantize(Decimal("0.01"))

    @staticmethod
    def get_debited_for_input(license_obj: LicenseDetailsModel, canonical_input_code: str) -> Decimal:
        """Get total debited quantity (CIF) for a canonical input.

        Aggregates BOE RowDetails where the source item maps to canonical_input_code.

        Args:
            license_obj: LicenseDetailsModel
            canonical_input_code: Code like "PKO", "OLIVE_OIL"

        Returns:
            Decimal total debited CIF
        """
        # Get BOE rows for items in this license
        from apps.bill_of_entry.models import RowDetails

        debit_rows = RowDetails.objects.filter(
            bill_of_entry__rowdetails__sr_number__license=license_obj,
            transaction_type='D',
        ).select_related('bill_of_entry', 'sr_number')

        total_cif = DEC_0
        for row in debit_rows:
            # Classify by BOE product_name
            boe_product_name = row.bill_of_entry.product_name or ""
            classified = SionInputClassifier.resolve_canonical_input(boe_product_name)
            if classified and classified.code == canonical_input_code:
                # CIF already stored in RowDetails
                item_cif = Decimal(str(row.cif_inr or DEC_0))
                total_cif += item_cif

        return total_cif.quantize(Decimal("0.01"))

    @staticmethod
    def get_remaining_capacity_for_input(license_obj: LicenseDetailsModel, canonical_input_code: str, percentage: Decimal) -> Decimal:
        """Calculate remaining CIF capacity for a canonical input under percentage constraint.

        Remaining = cap - (allotted + debited)

        Args:
            license_obj: LicenseDetailsModel
            canonical_input_code: Code like "PKO", "OLIVE_OIL"
            percentage: Decimal percentage (e.g., 50.00)

        Returns:
            Decimal remaining capacity (non-negative)
        """
        cap = SionPercentageRule.get_percentage_cap_for_input(license_obj, canonical_input_code, percentage)
        allotted = SionPercentageRule.get_allotted_for_input(license_obj, canonical_input_code)
        debited = SionPercentageRule.get_debited_for_input(license_obj, canonical_input_code)

        used = allotted + debited
        remaining = max(DEC_0, cap - used)

        return remaining.quantize(Decimal("0.01"))

    @staticmethod
    def check_percentage_capacity(
        license_obj: LicenseDetailsModel,
        canonical_input_code: str,
        percentage: Decimal,
        requested_qty: Decimal,
        requested_unit_price: Decimal
    ) -> tuple[bool, str]:
        """Check if a new allocation would violate percentage constraint.

        Args:
            license_obj: LicenseDetailsModel
            canonical_input_code: Code like "PKO"
            percentage: Constraint percentage (e.g., 50.00)
            requested_qty: Quantity trying to allocate
            requested_unit_price: Unit price for the quantity

        Returns:
            (allowed: bool, message: str) where message is empty if allowed
        """
        if not percentage or percentage < DEC_0:
            return True, ""  # No constraint

        remaining = SionPercentageRule.get_remaining_capacity_for_input(
            license_obj, canonical_input_code, percentage
        )
        requested_cif = (Decimal(str(requested_qty)) * Decimal(str(requested_unit_price))).quantize(Decimal("0.01"))

        if requested_cif > remaining:
            cap = SionPercentageRule.get_percentage_cap_for_input(license_obj, canonical_input_code, percentage)
            return False, (
                f"{canonical_input_code} percentage cap exceeded. "
                f"Cap: {cap} CIF, Remaining: {remaining} CIF, Requested: {requested_cif} CIF"
            )

        return True, ""
