"""
Reusable table column classes for Django Tables2.

This module provides a factory pattern for creating table columns with
totaling functionality, eliminating ~100 lines of duplicate code from tables.py.
"""
import django_tables2 as dt2
from django.contrib.humanize.templatetags.humanize import intcomma


class ColumnTotal(dt2.Column):
    """Base column class with footer totaling support."""

    column_total = 0

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
                if callable(getattr(record, method_name, None)):
                    value = getattr(record, method_name)()
                else:
                    value = getattr(record, method_name, 0)

                self.column_total += value
                return intcomma(round(value, decimals))

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
                value = getattr(record, attribute_name, 0)
                self.column_total += value
                return intcomma(round(value, decimals))

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
        value = (record.get_balance_cif * 1.1) if hasattr(record, 'get_balance_cif') else 0
        self.column_total += value
        return intcomma(round(value, 2))
