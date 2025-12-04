"""
Unit tests for core.utils.decimal_utils module.
"""

from decimal import Decimal
from operator import add, mul, truediv

import pytest

from core.constants import DEC_0
from core.utils.decimal_utils import (
    to_decimal,
    safe_decimal_operation,
    round_decimal_down,
    round_decimal,
    decimal_division,
    sum_decimals,
    format_decimal,
    DecimalEncoder,
)


class TestToDecimal:
    """Tests for to_decimal function."""

    def test_decimal_input_returns_same_decimal(self):
        """Test that Decimal input is returned unchanged."""
        value = Decimal('123.45')
        result = to_decimal(value)
        assert result == Decimal('123.45')
        assert result is value

    def test_integer_input_converts_to_decimal(self):
        """Test that integer converts to Decimal."""
        result = to_decimal(100)
        assert result == Decimal('100')
        assert isinstance(result, Decimal)

    def test_float_input_converts_to_decimal(self):
        """Test that float converts to Decimal via string."""
        result = to_decimal(123.45)
        assert result == Decimal('123.45')

    def test_string_input_converts_to_decimal(self):
        """Test that string converts to Decimal."""
        result = to_decimal('123.45')
        assert result == Decimal('123.45')

    def test_none_input_returns_default(self):
        """Test that None returns default value."""
        result = to_decimal(None)
        assert result == DEC_0

        result = to_decimal(None, default=Decimal('10'))
        assert result == Decimal('10')

    def test_invalid_string_returns_default(self):
        """Test that invalid string returns default."""
        result = to_decimal('invalid')
        assert result == DEC_0

        result = to_decimal('not_a_number', default=Decimal('99'))
        assert result == Decimal('99')

    def test_empty_string_returns_default(self):
        """Test that empty string returns default."""
        result = to_decimal('')
        assert result == DEC_0


class TestSafeDecimalOperation:
    """Tests for safe_decimal_operation function."""

    def test_addition_with_valid_values(self):
        """Test safe addition with valid values."""
        result = safe_decimal_operation(add, '10.5', '20.3')
        assert result == Decimal('30.8')

    def test_multiplication_with_integers(self):
        """Test safe multiplication with integers."""
        result = safe_decimal_operation(mul, 5, 3)
        assert result == Decimal('15')

    def test_division_with_valid_values(self):
        """Test safe division with valid values."""
        result = safe_decimal_operation(truediv, 100, 4)
        assert result == Decimal('25')

    def test_division_by_zero_returns_default(self):
        """Test that division by zero returns default."""
        result = safe_decimal_operation(truediv, 100, 0, default=Decimal('-1'))
        assert result == Decimal('-1')

    def test_invalid_values_return_default(self):
        """Test that invalid values return default."""
        result = safe_decimal_operation(add, 'invalid', 10, default=Decimal('0'))
        assert result == Decimal('0')


class TestRoundDecimalDown:
    """Tests for round_decimal_down function."""

    def test_round_down_to_two_decimals(self):
        """Test rounding down to 2 decimal places."""
        result = round_decimal_down(Decimal('10.567'), 2)
        assert result == Decimal('10.56')

    def test_round_down_to_zero_decimals(self):
        """Test rounding down to integer."""
        result = round_decimal_down(123.99, 0)
        assert result == Decimal('123')

    def test_round_down_to_three_decimals(self):
        """Test rounding down to 3 decimal places."""
        result = round_decimal_down(Decimal('5.6789'), 3)
        assert result == Decimal('5.678')

    def test_round_down_negative_number(self):
        """Test rounding down negative numbers."""
        result = round_decimal_down(Decimal('-10.567'), 2)
        # floor of -10.567 with 2 decimals is -10.57
        assert result == Decimal('-10.57')


class TestRoundDecimal:
    """Tests for round_decimal function."""

    def test_round_half_up_default(self):
        """Test rounding with ROUND_HALF_UP (default)."""
        result = round_decimal(Decimal('10.565'), 2)
        assert result == Decimal('10.57')

    def test_round_down_explicit(self):
        """Test rounding with ROUND_DOWN."""
        from decimal import ROUND_DOWN
        result = round_decimal(Decimal('10.565'), 2, ROUND_DOWN)
        assert result == Decimal('10.56')

    def test_round_to_zero_decimals(self):
        """Test rounding to integer."""
        result = round_decimal(Decimal('123.5'), 0)
        assert result == Decimal('124')


class TestDecimalDivision:
    """Tests for decimal_division function."""

    def test_simple_division(self):
        """Test simple division."""
        result = decimal_division(100, 3, decimals=2)
        assert result == Decimal('33.33')

    def test_division_by_zero_returns_default(self):
        """Test division by zero returns default."""
        result = decimal_division(10, 0)
        assert result == DEC_0

        result = decimal_division(10, 0, default=Decimal('-1'))
        assert result == Decimal('-1')

    def test_division_with_decimal_precision(self):
        """Test division with specific precision."""
        result = decimal_division(100, 3, decimals=4)
        assert result == Decimal('33.3333')

    def test_division_with_strings(self):
        """Test division with string inputs."""
        result = decimal_division('100', '4', decimals=2)
        assert result == Decimal('25.00')


class TestSumDecimals:
    """Tests for sum_decimals function."""

    def test_sum_multiple_values(self):
        """Test summing multiple values."""
        result = sum_decimals(10, '20.5', Decimal('5.25'))
        assert result == Decimal('35.75')

    def test_sum_with_none_values(self):
        """Test summing with None values (treated as 0)."""
        result = sum_decimals(None, 10, None, 5)
        assert result == Decimal('15')

    def test_sum_empty_returns_zero(self):
        """Test summing no values returns zero."""
        result = sum_decimals()
        assert result == DEC_0

    def test_sum_single_value(self):
        """Test summing single value."""
        result = sum_decimals(Decimal('42.5'))
        assert result == Decimal('42.5')


class TestDecimalEncoder:
    """Tests for DecimalEncoder class."""

    def test_encode_decimal_to_string(self):
        """Test encoding Decimal to JSON string."""
        import json
        data = {'amount': Decimal('123.45')}
        result = json.dumps(data, cls=DecimalEncoder)
        assert result == '{"amount": "123.45"}'

    def test_encode_mixed_types(self):
        """Test encoding mixed types including Decimal."""
        import json
        data = {
            'decimal': Decimal('100.50'),
            'integer': 42,
            'string': 'test',
            'float': 3.14
        }
        result = json.dumps(data, cls=DecimalEncoder)
        parsed = json.loads(result)
        assert parsed['decimal'] == '100.50'
        assert parsed['integer'] == 42
        assert parsed['string'] == 'test'


class TestFormatDecimal:
    """Tests for format_decimal function."""

    def test_format_with_thousands_separator(self):
        """Test formatting with thousand separators."""
        result = format_decimal(1234567.89)
        assert result == '1,234,567.89'

    def test_format_to_zero_decimals(self):
        """Test formatting to integer with separator."""
        result = format_decimal(1000, 0)
        assert result == '1,000'

    def test_format_small_number(self):
        """Test formatting small number."""
        result = format_decimal(123.45, 2)
        assert result == '123.45'

    def test_format_with_custom_decimals(self):
        """Test formatting with custom decimal places."""
        result = format_decimal(1234.5678, 3)
        assert result == '1,234.568'

    def test_format_zero(self):
        """Test formatting zero."""
        result = format_decimal(0, 2)
        assert result == '0.00'


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_to_decimal_with_very_large_number(self):
        """Test handling very large numbers."""
        large = '999999999999999999.99'
        result = to_decimal(large)
        assert result == Decimal(large)

    def test_to_decimal_with_scientific_notation(self):
        """Test handling scientific notation."""
        result = to_decimal('1.23e5')
        assert result == Decimal('123000')

    def test_round_decimal_down_with_zero(self):
        """Test rounding down zero."""
        result = round_decimal_down(0, 2)
        assert result == Decimal('0')

    def test_decimal_division_with_none_numerator(self):
        """Test division with None numerator."""
        result = decimal_division(None, 5)
        assert result == DEC_0

    def test_format_decimal_with_invalid_input(self):
        """Test formatting with invalid input."""
        result = format_decimal('invalid', 2)
        assert result == '0.00'


# Run tests with pytest
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
