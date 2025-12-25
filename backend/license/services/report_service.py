"""
Service layer for generating license reports.

This module consolidates duplicate DFIA report generation logic into
reusable service methods with clear, consistent interfaces.
"""
from typing import List, Dict, Optional, Any

from core.constants import GE, MI
from license.models import LicenseDetailsModel
from license.utils.query_builder import LicenseQueryBuilder


class DFIAReportService:
    """
    Service for generating DFIA (Duty Free Import Authorization) reports.

    Consolidates common patterns for biscuit, confectionery, namkeen, and tractor reports.
    """

    @staticmethod
    def get_licenses_by_norm_class(
        norm_class: str,
        date_range: Optional[Dict[str, str]] = None,
        party: Optional[List[str]] = None,
        exclude_party: Optional[List[str]] = None,
        is_expired: bool = False,
        purchase_status: str = GE,
        additional_filters: Optional[Dict[str, Any]] = None
    ) -> 'QuerySet':
        """
        Generic method to get licenses filtered by norm class and other criteria.

        Args:
            norm_class: The norm class code (e.g., 'E5', 'E1', 'E132')
            date_range: Optional date range dict with 'start' and 'end'
            party: List of party names to include (OR logic)
            exclude_party: List of party names to exclude
            is_expired: Whether to filter for expired licenses
            purchase_status: Purchase status (GE, MI, etc.)
            additional_filters: Any additional filters to apply

        Returns:
            Filtered and ordered QuerySet of LicenseDetailsModel
        """
        builder = (LicenseQueryBuilder(LicenseDetailsModel)
                   .with_norm_class(norm_class)
                   .with_purchase_status(purchase_status)
                   .with_is_au(False))

        # Apply date filters
        if is_expired:
            builder.with_expiry_filters(is_expired=True)
        else:
            builder.with_date_range(date_range)

        # Apply party filters
        if party:
            builder.with_party(party)
        if exclude_party:
            builder.exclude_party(exclude_party)

        # Apply additional filters
        if additional_filters:
            builder.with_base_filters(**additional_filters)

        # Default ordering
        builder.order_by('license_expiry_date', 'license_date')

        return builder.build()

    @staticmethod
    def split_licenses_by_balance(
        licenses: 'QuerySet',
        balance_threshold: float
    ) -> tuple[List, List]:
        """
        Split licenses into two groups based on balance threshold.

        Args:
            licenses: QuerySet of licenses
            balance_threshold: Minimum balance to be in "active" group

        Returns:
            Tuple of (active_licenses, low_balance_licenses)
        """
        active = []
        low_balance = []

        for license_obj in licenses:
            if license_obj.get_balance_cif > balance_threshold:
                active.append(license_obj)
            else:
                low_balance.append(license_obj)

        return active, low_balance

    @classmethod
    def get_biscuit_licenses(
        cls,
        date_range: Optional[Dict[str, str]] = None,
        party: Optional[List[str]] = None,
        exclude_party: Optional[List[str]] = None,
        is_expired: bool = False,
        purchase_status: str = GE
    ) -> 'QuerySet':
        """Get biscuit conversion licenses (E5 norm class)."""
        return cls.get_licenses_by_norm_class(
            norm_class='E5',
            date_range=date_range,
            party=party,
            exclude_party=exclude_party,
            is_expired=is_expired,
            purchase_status=purchase_status
        )

    @classmethod
    def get_confectionery_licenses(
        cls,
        date_range: Optional[Dict[str, str]] = None,
        party: Optional[List[str]] = None,
        exclude_party: Optional[List[str]] = None,
        is_expired: bool = False
    ) -> 'QuerySet':
        """Get confectionery conversion licenses (E1 norm class)."""
        return cls.get_licenses_by_norm_class(
            norm_class='E1',
            date_range=date_range,
            party=party,
            exclude_party=exclude_party,
            is_expired=is_expired,
            additional_filters={'export_license__old_quantity__gt': 0}  # Exclude 0 old_quantity
        )

    @classmethod
    def get_namkeen_licenses(
        cls,
        date_range: Optional[Dict[str, str]] = None,
        party: Optional[List[str]] = None,
        exclude_party: Optional[List[str]] = None,
        is_expired: bool = False
    ) -> 'QuerySet':
        """Get namkeen licenses (E132 norm class)."""
        return cls.get_licenses_by_norm_class(
            norm_class='E132',
            date_range=date_range,
            party=party,
            exclude_party=exclude_party,
            is_expired=is_expired
        )

    @classmethod
    def get_tractor_licenses(
        cls,
        date_range: Optional[Dict[str, str]] = None,
        party: Optional[List[str]] = None,
        exclude_party: Optional[List[str]] = None,
        is_expired: bool = False,
        notification_number: Optional[str] = None
    ) -> 'QuerySet':
        """Get tractor licenses (C969 norm class)."""
        additional_filters = {}
        if notification_number:
            additional_filters['notification_number'] = notification_number

        return cls.get_licenses_by_norm_class(
            norm_class='C969',
            date_range=date_range,
            party=party,
            exclude_party=exclude_party,
            is_expired=is_expired,
            additional_filters=additional_filters
        )

    @classmethod
    def generate_biscuit_report(
        cls,
        date_range: Optional[Dict[str, str]] = None,
        status: Optional[str] = None,
        party: str = GE
    ) -> List[Dict[str, Any]]:
        """
        Generate biscuit DFIA report with categorized results.

        Args:
            date_range: Optional date range
            status: 'expired' to show expired licenses
            party: 'parle', 'mi', or GE for different categorizations

        Returns:
            List of table dicts with 'label' and 'table' keys
        """
        is_expired = (status == 'expired')
        balance_limit = 20000 if is_expired else 1000
        tables = []

        if party == 'parle':
            licenses = cls.get_biscuit_licenses(
                date_range=date_range,
                party=['Parle'],
                is_expired=is_expired,
                purchase_status=GE
            )
            active, _ = cls.split_licenses_by_balance(licenses, balance_limit)
            tables.append({'label': 'Parle Biscuits', 'table': active})

        elif party == 'mi':
            licenses = cls.get_biscuit_licenses(
                date_range=date_range,
                is_expired=is_expired,
                purchase_status=MI
            )
            active, _ = cls.split_licenses_by_balance(licenses, balance_limit)
            tables.append({'label': 'Nilesh Sir DFIA', 'table': active})

        else:
            licenses = cls.get_biscuit_licenses(
                date_range=date_range,
                exclude_party=['Parle'],
                is_expired=is_expired,
                purchase_status=GE
            )
            active, _ = cls.split_licenses_by_balance(licenses, balance_limit)
            tables.append({'label': 'GE DFIA', 'table': active})

        return tables

    @classmethod
    def generate_confectionery_report(
        cls,
        date_range: Optional[Dict[str, str]] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate confectionery DFIA report.

        Args:
            date_range: Optional date range
            status: 'expired' to show expired licenses

        Returns:
            List of table dicts with active and low-balance licenses
        """
        is_expired = (status == 'expired')
        balance_limit = 20000 if is_expired else 1000

        licenses = cls.get_confectionery_licenses(
            date_range=date_range,
            party=[],
            is_expired=is_expired
        )

        active, low_balance = cls.split_licenses_by_balance(licenses, balance_limit)

        return [
            {'label': 'All DFIA', 'table': active},
            {'label': 'NULL DFIA', 'table': low_balance}
        ]


class ItemReportService:
    """Service for item-based reports and table generation."""

    @staticmethod
    def generate_report_context(
        tables: List[Dict[str, Any]],
        title: str,
        total_quantity: Optional[float] = None,
        template_name: str = 'license/report_pdf.html'
    ) -> Dict[str, Any]:
        """
        Generate standardized report context dict.

        Args:
            tables: List of table dicts
            title: Report page title
            total_quantity: Total quantity (if None, will be calculated)
            template_name: Template to use for rendering

        Returns:
            Context dict for rendering report
        """
        import datetime

        # Calculate total if not provided
        if total_quantity is None:
            total_quantity = 0
            for table in tables:
                if table.get('total'):
                    total_quantity += table['total']

        return {
            'page_title': title,
            'tables': tables,
            'total_quantity': total_quantity,
            'today': datetime.datetime.now().date(),
            'template_name': template_name
        }
