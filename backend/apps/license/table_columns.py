"""
Reusable table column classes for Django Tables2.

This module provides a factory pattern for creating table columns with
totaling functionality, eliminating ~100 lines of duplicate code from tables.py.
"""
from decimal import Decimal, InvalidOperation

import django_tables2 as dt2
from django.contrib.humanize.templatetags.humanize import intcomma


def _as_decimal(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")
    if not decimal_value.is_finite():
        return Decimal("0")
    return decimal_value


class ColumnTotal(dt2.Column):
    """Base column class with footer totaling support."""

    def __init__(self, *args, **kwargs):
        self.column_total = Decimal("0")
        super().__init__(*args, **kwargs)

    def render_total_value(self, value, places: int = 0):
        decimal_value = _as_decimal(value)
        self.column_total += decimal_value
        return intcomma(round(decimal_value, places))

    def render_footer(self, bound_column, table):
        """Render footer with formatted total."""
        return intcomma(round(self.column_total, 0))


class ColumnFactory:
    """
    Factory for creating table columns with consistent totaling behavior.

    Example:
        # Instead of defining 10+ similar classes:
        BalanceCIFColumn = ColumnFactory.create_total_column('get_balance_cif', decimals=2)
        SugarColumn = ColumnFactory.create_total_column('get_sugar', decimals=0)
    """

    @staticmethod
    def create_total_column(method_name: str, decimals: int = 0):
        """
        Create a column class that calls a method on the record and totals results.

        Args:
            method_name: Name of the method to call on each record
            decimals: Number of decimal places to round to

        Returns:
            A new column class with totaling functionality
        """
        class DynamicTotalColumn(ColumnTotal):
            def render(self, record):
                # Call the method on the record
                value = getattr(record, method_name, Decimal("0"))
                if callable(value):
                    value = value()
                return self.render_total_value(value, decimals)

        # Set a meaningful class name for debugging
        DynamicTotalColumn.__name__ = f'{method_name.title().replace("_", "")}Column'
        return DynamicTotalColumn

    @staticmethod
    def create_attribute_column(attribute_name: str, decimals: int = 0):
        """
        Create a column class that accesses an attribute directly and totals results.

        Args:
            attribute_name: Name of the attribute to access on each record
            decimals: Number of decimal places to round to

        Returns:
            A new column class with totaling functionality
        """
        class DynamicAttributeColumn(ColumnTotal):
            def render(self, record):
                value = getattr(record, attribute_name, Decimal("0"))
                return self.render_total_value(value, decimals)

        # Set a meaningful class name for debugging
        DynamicAttributeColumn.__name__ = f'{attribute_name.title().replace("_", "")}Column'
        return DynamicAttributeColumn


# ============================================================================
# Pre-defined common columns for backward compatibility
# ============================================================================

# Balance columns
BalanceCIFColumn = ColumnFactory.create_total_column('get_balance_cif', decimals=2)
TotalBalanceCIFColumn = ColumnFactory.create_attribute_column('opening_balance', decimals=2)
PERCIFColumn = ColumnFactory.create_total_column('get_per_cif', decimals=0)

# Item quantity columns
WheatQuantityColumn = ColumnFactory.create_total_column('get_wheat', decimals=0)
SugarQuantityColumn = ColumnFactory.create_total_column('get_sugar', decimals=0)
BOPPQuantityColumn = ColumnFactory.create_total_column('get_bopp', decimals=0)
FruitsQuantityColumn = ColumnFactory.create_total_column('get_fruit', decimals=0)
PaperQuantityColumn = ColumnFactory.create_total_column('get_paper', decimals=0)
MNMQuantityColumn = ColumnFactory.create_total_column('get_m_n_m', decimals=0)
PPQuantityColumn = ColumnFactory.create_total_column('get_pp', decimals=0)
PaperBoardQuantityColumn = ColumnFactory.create_total_column('get_paper_board', decimals=0)
RBDQuantityColumn = ColumnFactory.create_total_column('get_rbd', decimals=0)
DietaryFibreQuantityColumn = ColumnFactory.create_total_column('get_dietary_fibre', decimals=0)
PomaceQuantityColumn = ColumnFactory.create_total_column('get_pomace', decimals=0)
VegetableOilQuantityColumn = ColumnFactory.create_total_column('get_veg_oil', decimals=0)


# ============================================================================
# Usage example for extending with custom logic:
# ============================================================================

class CustomCalculationColumn(ColumnTotal):
    """
    Example of a custom column with complex calculation logic.

    Use this pattern when you need custom logic beyond simple method calls.
    """

    def render(self, record):
        # Custom calculation
        value = getattr(record, 'get_balance_cif', Decimal("0"))
        if callable(value):
            value = value()
        return self.render_total_value(_as_decimal(value) * Decimal("1.1"), 2)


__all__ = [
    "BalanceCIFColumn",
    "BOPPQuantityColumn",
    "ColumnFactory",
    "ColumnTotal",
    "CustomCalculationColumn",
    "DietaryFibreQuantityColumn",
    "FruitsQuantityColumn",
    "MNMQuantityColumn",
    "PERCIFColumn",
    "PPQuantityColumn",
    "PaperBoardQuantityColumn",
    "PaperQuantityColumn",
    "PomaceQuantityColumn",
    "RBDQuantityColumn",
    "SugarQuantityColumn",
    "TotalBalanceCIFColumn",
    "VegetableOilQuantityColumn",
    "WheatQuantityColumn",
]
