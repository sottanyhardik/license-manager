"""
Item Pivot Report - JSON report assembly (generate_report).
"""

import logging
from typing import (
    Dict,
    Any,
)



logger = logging.getLogger(__name__)



class ItemPivotGenerateMixin:
    """Mixin holding methods moved verbatim from ItemPivotReportView."""

    def generate_report(self, days: int = 30, sion_norm: str = None,
                        company_ids: str = None, exclude_company_ids: str = None,
                        min_balance: int = 200, license_status: str = 'active',
                        expiry_date_from: str = None, expiry_date_to: str = None,
                        purchase_status: str = None) -> Dict[str, Any]:
        """
        Generate item-wise pivot report.

        Args:
            days: Number of days to look back for active licenses
            sion_norm: Filter by specific SION norm class (optional)
            company_ids: Comma-separated company IDs to include (optional)
            exclude_company_ids: Comma-separated company IDs to exclude (optional)
            min_balance: Minimum balance CIF to include (default 200)
            license_status: Filter by status - 'active', 'expired', 'expiring_soon', 'all' (default 'active')

        Returns:
            Dictionary with report data
        """
        from apps.license.services.item_pivot_selection import select_pivot_licenses
        valid_licenses = select_pivot_licenses(
            days=days, sion_norm=sion_norm, company_ids=company_ids,
            exclude_company_ids=exclude_company_ids, min_balance=min_balance,
            license_status=license_status, expiry_date_from=expiry_date_from,
            expiry_date_to=expiry_date_to, purchase_status=purchase_status,
        )

        # The canonical report projection (persisted effective plans plus the
        # item-linked BOE/allotment population). The former legacy cell
        # builder that followed this return was unreachable and is removed.
        from apps.license.services.item_pivot_service import ItemPivotService
        return ItemPivotService.build(valid_licenses)
