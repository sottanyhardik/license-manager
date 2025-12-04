"""
License filtering service for allocation.

This module handles filtering of available licenses for allocation to allotments.
"""

from typing import Optional

from django.db.models import Q, QuerySet

from core.utils.decimal_utils import to_decimal


class LicenseFilterService:
    """
    Service for filtering license items available for allocation.
    """

    @staticmethod
    def get_available_items_queryset() -> QuerySet:
        """
        Get base queryset for available license items.
        
        Returns:
            QuerySet with base filters and related data
        """
        from license.models import LicenseImportItemsModel

        return LicenseImportItemsModel.objects.filter(
            available_quantity__gt=0
        ).select_related(
            'license',
            'license__exporter',
            'hs_code'
        ).prefetch_related(
            'items',
            'items__head'
        ).order_by(
            'license__license_expiry_date',
            'serial_number'
        )

    @staticmethod
    def apply_search_filter(queryset: QuerySet, search: str) -> QuerySet:
        """
        Apply general search filter.
        
        Searches in license number, description, and exporter name.
        
        Args:
            queryset: QuerySet to filter
            search: Search term
            
        Returns:
            Filtered QuerySet
        """
        if not search:
            return queryset

        return queryset.filter(
            Q(license__license_number__icontains=search) |
            Q(description__icontains=search) |
            Q(license__exporter__name__icontains=search)
        )

    @staticmethod
    def apply_license_number_filter(queryset: QuerySet, license_number: str) -> QuerySet:
        """
        Filter by license number.
        
        Args:
            queryset: QuerySet to filter
            license_number: License number to search for
            
        Returns:
            Filtered QuerySet
        """
        if not license_number:
            return queryset

        return queryset.filter(license__license_number__icontains=license_number)

    @staticmethod
    def apply_description_filter(queryset: QuerySet, description: str) -> QuerySet:
        """
        Filter by description (searches in multiple fields).
        
        Searches in:
        - Import item description
        - Item names
        - HS code
        - HS code product description
        
        Args:
            queryset: QuerySet to filter
            description: Description to search for
            
        Returns:
            Filtered QuerySet (with distinct to avoid duplicates)
        """
        if not description:
            return queryset

        return queryset.filter(
            Q(description__icontains=description) |
            Q(items__name__icontains=description) |
            Q(hs_code__hs_code__icontains=description) |
            Q(hs_code__product_description__icontains=description)
        ).distinct()

    @staticmethod
    def apply_exporter_filter(queryset: QuerySet, exporter_id: Optional[int]) -> QuerySet:
        """
        Filter by exporter ID.
        
        Args:
            queryset: QuerySet to filter
            exporter_id: Exporter ID
            
        Returns:
            Filtered QuerySet
        """
        if not exporter_id:
            return queryset

        return queryset.filter(license__exporter_id=exporter_id)

    @staticmethod
    def apply_quantity_filters(
            queryset: QuerySet,
            min_quantity: Optional[str] = None,
            max_quantity: Optional[str] = None
    ) -> QuerySet:
        """
        Filter by available quantity range.
        
        Args:
            queryset: QuerySet to filter
            min_quantity: Minimum available quantity
            max_quantity: Maximum available quantity
            
        Returns:
            Filtered QuerySet
        """
        if min_quantity:
            try:
                min_qty = to_decimal(min_quantity)
                queryset = queryset.filter(available_quantity__gte=min_qty)
            except (ValueError, TypeError):
                pass

        if max_quantity:
            try:
                max_qty = to_decimal(max_quantity)
                queryset = queryset.filter(available_quantity__lte=max_qty)
            except (ValueError, TypeError):
                pass

        return queryset

    @staticmethod
    def apply_value_filters(
            queryset: QuerySet,
            min_value: Optional[str] = None,
            max_value: Optional[str] = None
    ) -> QuerySet:
        """
        Filter by available value (balance CIF) range.
        
        Args:
            queryset: QuerySet to filter
            min_value: Minimum available value
            max_value: Maximum available value
            
        Returns:
            Filtered QuerySet
        """
        if min_value:
            try:
                min_val = to_decimal(min_value)
                queryset = queryset.filter(balance_cif_fc__gte=min_val)
            except (ValueError, TypeError):
                pass

        if max_value:
            try:
                max_val = to_decimal(max_value)
                queryset = queryset.filter(balance_cif_fc__lte=max_val)
            except (ValueError, TypeError):
                pass

        return queryset

    @staticmethod
    def apply_notification_filter(queryset: QuerySet, notification_number: str) -> QuerySet:
        """
        Filter by license notification number.
        
        Args:
            queryset: QuerySet to filter
            notification_number: Notification number
            
        Returns:
            Filtered QuerySet
        """
        if not notification_number:
            return queryset

        return queryset.filter(license__notification_number=notification_number)

    @staticmethod
    def apply_norm_class_filter(queryset: QuerySet, norm_class: str) -> QuerySet:
        """
        Filter by license norm class (from export items).
        
        Args:
            queryset: QuerySet to filter
            norm_class: Norm class
            
        Returns:
            Filtered QuerySet
        """
        if not norm_class:
            return queryset

        return queryset.filter(license__export_license__norm_class=norm_class).distinct()

    @staticmethod
    def apply_hs_code_filter(queryset: QuerySet, hs_code: str) -> QuerySet:
        """
        Filter by HS code.
        
        Args:
            queryset: QuerySet to filter
            hs_code: HS code to search for
            
        Returns:
            Filtered QuerySet
        """
        if not hs_code:
            return queryset

        return queryset.filter(hs_code__hs_code__icontains=hs_code)

    @staticmethod
    def apply_expiry_filter(queryset: QuerySet, is_expired: Optional[str]) -> QuerySet:
        """
        Filter by license expiry status.
        
        Args:
            queryset: QuerySet to filter
            is_expired: "true" to show only expired, "false" to exclude expired
            
        Returns:
            Filtered QuerySet
        """
        if not is_expired:
            return queryset

        if is_expired.lower() == 'true':
            queryset = queryset.filter(license__is_expired=True)
        elif is_expired.lower() == 'false':
            queryset = queryset.filter(license__is_expired=False)

        return queryset

    @classmethod
    def filter_available_items(
            cls,
            search: str = '',
            license_number: str = '',
            exporter: str = '',
            description: str = '',
            min_quantity: str = '',
            max_quantity: str = '',
            min_value: str = '',
            max_value: str = '',
            notification_number: str = '',
            norm_class: str = '',
            hs_code: str = '',
            is_expired: str = ''
    ) -> QuerySet:
        """
        Apply all filters to get available license items.
        
        Args:
            search: General search term
            license_number: License number filter
            exporter: Exporter ID filter
            description: Description filter
            min_quantity: Minimum quantity filter
            max_quantity: Maximum quantity filter
            min_value: Minimum value filter
            max_value: Maximum value filter
            notification_number: Notification number filter
            norm_class: Norm class filter
            hs_code: HS code filter
            is_expired: Expiry filter
            
        Returns:
            Filtered QuerySet
        """
        # Start with base queryset
        queryset = cls.get_available_items_queryset()

        # Apply filters in order
        queryset = cls.apply_search_filter(queryset, search)
        queryset = cls.apply_license_number_filter(queryset, license_number)
        queryset = cls.apply_description_filter(queryset, description)
        queryset = cls.apply_exporter_filter(queryset, exporter)
        queryset = cls.apply_quantity_filters(queryset, min_quantity, max_quantity)
        queryset = cls.apply_value_filters(queryset, min_value, max_value)
        queryset = cls.apply_notification_filter(queryset, notification_number)
        queryset = cls.apply_norm_class_filter(queryset, norm_class)
        queryset = cls.apply_hs_code_filter(queryset, hs_code)
        queryset = cls.apply_expiry_filter(queryset, is_expired)

        return queryset
