from decimal import Decimal
from types import SimpleNamespace

import pytest

pytest.importorskip("django_tables2")

from apps.license.table_columns import (
    BalanceCIFColumn,
    ColumnFactory,
    CustomCalculationColumn,
    TotalBalanceCIFColumn,
)


class _Record:
    opening_balance = Decimal("25.50")

    def __init__(self, balance):
        self._balance = balance

    def get_balance_cif(self):
        return self._balance


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("12.34"), "12.34"),
        ("8.4", "8.40"),
        (None, "0.00"),
        ("", "0.00"),
        ("not-a-number", "0.00"),
    ],
)
def test_total_column_factory_coerces_values_and_formats_decimals(value, expected):
    column = BalanceCIFColumn()

    assert column.render(_Record(value)) == expected


def test_total_column_totals_are_instance_local():
    first = BalanceCIFColumn()
    second = BalanceCIFColumn()

    assert first.render(_Record(Decimal("10.00"))) == "10.00"
    assert second.render(_Record(Decimal("2.00"))) == "2.00"

    assert first.render_footer(None, None) == "10"
    assert second.render_footer(None, None) == "2"


def test_attribute_column_factory_reads_attributes():
    column = TotalBalanceCIFColumn()

    assert column.render(_Record(Decimal("0.00"))) == "25.50"
    assert column.render_footer(None, None) == "26"


def test_dynamic_attribute_column_handles_missing_attribute():
    MissingColumn = ColumnFactory.create_attribute_column("missing", decimals=2)
    column = MissingColumn()

    assert column.render(SimpleNamespace()) == "0.00"
    assert column.render_footer(None, None) == "0"


def test_custom_calculation_column_uses_decimal_arithmetic():
    column = CustomCalculationColumn()

    assert column.render(_Record(Decimal("10.00"))) == "11.00"
    assert column.render_footer(None, None) == "11"
