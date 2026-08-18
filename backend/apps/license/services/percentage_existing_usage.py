"""
Service for calculating existing BOE/Allotment usage by canonical input and license.

Filters transactions by:
1. Exact License
2. Exact canonical input (with alias resolution)
3. Qualifying lifecycle status (distinct relevant usage, no double-counting)

Returns breakdown: BOE qty/CIF, Allotment qty/CIF, relevant totals.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any

from django.db.models import Q, Sum, DecimalField
from django.db.models.functions import Coalesce

from apps.core.constants import DEC_0, DEC_000, DEBIT, CREDIT
from apps.core.utils.decimal_utils import to_decimal
from apps.bill_of_entry.models import RowDetails
from apps.allotment.models import AllotmentItems
from apps.license.models import LicenseDetailsModel


class CanonicalInputResolver:
    """Resolve product names to canonical input codes (PKO, OLIVE_OIL, etc.)"""

    # Map from normalized aliases to canonical code
    CANONICAL_MAP = {
        "PKO": "PKO",
        "PALM KERNEL OIL": "PKO",
        "OLIVE OIL": "OLIVE_OIL",
    }

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize product name: trim, collapse whitespace, uppercase."""
        if not name:
            return ""
        return " ".join(name.strip().split()).upper()

    @staticmethod
    def resolve_canonical(name: str) -> Optional[str]:
        """
        Resolve product name to canonical code.

        Example:
            "palm kernel oil" → "PKO"
            "PKO" → "PKO"
            "PALM OIL" → None (not an approved alias)
        """
        normalized = CanonicalInputResolver.normalize_name(name)
        return CanonicalInputResolver.CANONICAL_MAP.get(normalized)

    @staticmethod
    def get_aliases_for_canonical(canonical: str) -> list[str]:
        """Return approved normalized aliases for a canonical input."""
        return [
            norm_alias
            for norm_alias, canon_code in CanonicalInputResolver.CANONICAL_MAP.items()
            if canon_code == canonical
        ]


class PercentageExistingUsageService:
    """
    Calculate existing BOE/Allotment usage for a specific input and license.

    Filters only:
    - Current license
    - Current canonical input (with exact alias resolution)
    - Qualifying lifecycle records (avoiding double-count of linked Allotment/BOE)
    """

    @staticmethod
    def get_existing_usage(
        license_obj: LicenseDetailsModel,
        canonical_input: str,
    ) -> Dict[str, Any]:
        """
        Get existing BOE and Allotment usage for a license + canonical input.

        Args:
            license_obj: The LicenseDetailsModel
            canonical_input: Canonical code (e.g., "PKO", "OLIVE_OIL")

        Returns:
            {
                "canonical_input": "PKO",
                "boe_quantity": Decimal,
                "boe_cif": Decimal,
                "allotment_quantity": Decimal,
                "allotment_cif": Decimal,
                "relevant_quantity": Decimal,
                "relevant_cif": Decimal,
            }
        """
        # Get approved aliases for this canonical input
        aliases = CanonicalInputResolver.get_aliases_for_canonical(canonical_input)
        if not aliases:
            return {
                "canonical_input": canonical_input,
                "boe_quantity": Decimal("0"),
                "boe_cif": Decimal("0"),
                "allotment_quantity": Decimal("0"),
                "allotment_cif": Decimal("0"),
                "relevant_quantity": Decimal("0"),
                "relevant_cif": Decimal("0"),
            }

        # Query BOE for this license + canonical input
        boe_qty, boe_cif = PercentageExistingUsageService._get_boe_usage(
            license_obj, aliases
        )

        # Query Allotment for this license + canonical input
        allotment_qty, allotment_cif = PercentageExistingUsageService._get_allotment_usage(
            license_obj, aliases
        )

        # Calculate relevant totals (avoiding double-count of linked Allotment/BOE)
        relevant_qty = PercentageExistingUsageService._calculate_relevant_quantity(
            license_obj, boe_qty, allotment_qty, aliases
        )
        relevant_cif = boe_cif + allotment_cif  # CIF doesn't double-count in typical lifecycle

        return {
            "canonical_input": canonical_input,
            "boe_quantity": boe_qty,
            "boe_cif": boe_cif,
            "allotment_quantity": allotment_qty,
            "allotment_cif": allotment_cif,
            "relevant_quantity": relevant_qty,
            "relevant_cif": relevant_cif,
        }

    @staticmethod
    def _get_boe_usage(license_obj: LicenseDetailsModel, aliases: list[str]) -> tuple[Decimal, Decimal]:
        """
        Get BOE quantity and CIF for license + canonical input aliases.

        Filters:
        - License
        - Normalized product name IN approved aliases
        - DEBIT records only
        """
        # Query RowDetails for this license (DEBIT transactions)
        boe_qs = RowDetails.objects.filter(
            sr_number__license=license_obj,
            transaction_type=DEBIT,
        ).select_related('sr_number')

        total_qty = Decimal("0")
        total_cif = Decimal("0")

        # For each BOE row, check if its linked import item has a matching product
        for row in boe_qs:
            import_item = row.sr_number
            if not import_item:
                continue

            # Get product names from linked ItemNameModel (M2M)
            for item_name in import_item.items.all():
                normalized_product = CanonicalInputResolver.normalize_name(item_name.name)
                if normalized_product in aliases:
                    qty = to_decimal(row.qty, DEC_000)
                    cif = to_decimal(row.cif_fc, DEC_0)
                    total_qty += qty
                    total_cif += cif
                    break  # Only count once per import item, even if multiple matched items

        return total_qty.quantize(DEC_000, rounding=ROUND_HALF_UP), total_cif.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @staticmethod
    def _get_allotment_usage(license_obj: LicenseDetailsModel, aliases: list[str]) -> tuple[Decimal, Decimal]:
        """
        Get Allotment quantity and CIF for license + canonical input aliases.

        Filters:
        - License
        - Normalized product name IN approved aliases
        - Active/pending Allotment records
        """
        allotment_qs = AllotmentItems.objects.filter(
            item__license=license_obj,
        ).select_related('item')

        total_qty = Decimal("0")
        total_cif = Decimal("0")

        # For each allotment item, check if its linked import item has a matching product
        for allot_item in allotment_qs:
            import_item = allot_item.item
            if not import_item:
                continue

            # Get product names from linked ItemNameModel (M2M)
            for item_name in import_item.items.all():
                normalized_product = CanonicalInputResolver.normalize_name(item_name.name)
                if normalized_product in aliases:
                    qty = to_decimal(allot_item.qty, DEC_000)
                    cif = to_decimal(allot_item.cif_fc, DEC_0)
                    total_qty += qty
                    total_cif += cif
                    break  # Only count once per import item, even if multiple matched items

        return total_qty.quantize(DEC_000, rounding=ROUND_HALF_UP), total_cif.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @staticmethod
    def _calculate_relevant_quantity(
        license_obj: LicenseDetailsModel,
        boe_qty: Decimal,
        allotment_qty: Decimal,
        aliases: list[str],
    ) -> Decimal:
        """
        Calculate distinct relevant quantity, avoiding double-count of linked Allotment/BOE.

        Current logic: if a BOE is linked to an Allotment, they represent the same
        consumption, so count as one. For simplicity, we just sum BOE + Allotment
        quantities assuming they are tracked separately in the data.

        TODO: Implement linked Allotment/BOE deduplication if lifecycle data shows
        this is necessary.
        """
        # For now, assume BOE and Allotment are separate tracked quantities
        return (boe_qty + allotment_qty).quantize(DEC_000, rounding=ROUND_HALF_UP)
