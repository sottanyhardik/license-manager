from decimal import Decimal
from types import SimpleNamespace

import pytest

pytest.importorskip("django_tables2")

from apps.license.tables import (
    BalanceCIFColumn,
    ColumnWithThousandsSeparator,
    DecimalColumnWithTotal,
    SugarQuantityColumn,
    TruncatedBigTextColumn,
    TruncatedTextColumn,
)


def test_balance_cif_column_totals_are_instance_scoped():
    first = BalanceCIFColumn()
    second = BalanceCIFColumn()
    record = SimpleNamespace(get_balance_cif=Decimal("12.50"))

    assert first.render(record) == "12.50"
    assert first.render_footer(None, None) == "12"
    assert second.render_footer(None, None) == "0"


def test_column_total_normalizes_invalid_and_non_finite_values():
    balance_column = BalanceCIFColumn()
    sugar_column = SugarQuantityColumn()

    assert balance_column.render(SimpleNamespace(get_balance_cif="NaN")) == "0.00"
    assert balance_column.render(SimpleNamespace(get_balance_cif="Infinity")) == "0.00"
    assert sugar_column.render(SimpleNamespace(get_sugar=lambda: None)) == "0"
    assert sugar_column.render(SimpleNamespace(get_sugar=lambda: "10.4")) == "10"
    assert sugar_column.render_footer(None, None) == "10"


def test_decimal_column_with_total_handles_none_and_invalid_values():
    column = DecimalColumnWithTotal(accessor="amount")

    assert column.render(SimpleNamespace(amount=None)) == "0.00"
    assert column.render(SimpleNamespace(amount="not-a-number")) == "0.00"
    assert column.render(SimpleNamespace(amount=Decimal("NaN"))) == "0.00"
    assert column.render(SimpleNamespace(amount="12.345")) == "12.35"
    assert column.render_footer() == "12.35"


def test_truncated_text_columns_handle_none_and_long_values():
    assert TruncatedTextColumn().render(None) == ""
    assert TruncatedTextColumn().render("ABCDEFGHIJK") == "ABCDEFGHIJ..."
    assert TruncatedBigTextColumn().render(None) == ""
    assert TruncatedBigTextColumn().render("A" * 33) == f"{'A' * 30}..."


def test_column_with_thousands_separator_totals_values():
    column = ColumnWithThousandsSeparator()

    assert column.render(None) == "0.00"
    assert column.render("1234.567") == "1,234.57"
    assert column.render_footer(None, None) == "1,235"
