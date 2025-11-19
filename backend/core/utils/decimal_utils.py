"""
Decimal utility functions for safe decimal operations.

This module provides utilities for:
- Safe conversion of values to Decimal
- Decimal arithmetic operations with error handling
- Rounding operations
- JSON serialization of Decimal values
"""

import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_DOWN
from typing import Union, Callable, Any

import math

from core.constants import DEC_0


def to_decimal(
        value: Union[Decimal, int, float, str, None],
        default: Decimal = DEC_0
) -> Decimal:
    """
    Safely convert value to Decimal.
    
    Args:
        value: Value to convert (Decimal, int, float, str, or None)
        default: Default value to return if conversion fails
        
    Returns:
        Decimal value or default
        
    Examples:
        >>> to_decimal(100)
        Decimal('100')
        >>> to_decimal("123.45")
        Decimal('123.45')
        >>> to_decimal(None)
        Decimal('0')
        >>> to_decimal("invalid", Decimal('10'))
        Decimal('10')
    """
    if isinstance(value, Decimal):
        return value
    if value is None:
        return default
    try:
        # Convert via string to avoid float precision issues
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def safe_decimal_operation(
        operation: Callable[[Decimal, Decimal], Decimal],
        value1: Union[Decimal, int, float, str, None],
        value2: Union[Decimal, int, float, str, None],
        default: Decimal = DEC_0
) -> Decimal:
    """
    Perform safe decimal arithmetic operation.
    
    Args:
        operation: Function that takes two Decimals and returns a Decimal
        value1: First operand
        value2: Second operand
        default: Default value if operation fails
        
    Returns:
        Result of operation or default
        
    Examples:
        >>> from operator import add, mul
        >>> safe_decimal_operation(add, "10.5", "20.3")
        Decimal('30.8')
        >>> safe_decimal_operation(mul, 5, 3)
        Decimal('15')
    """
    try:
        dec1 = to_decimal(value1, DEC_0)
        dec2 = to_decimal(value2, DEC_0)
        return operation(dec1, dec2)
    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
        return default


def round_decimal_down(value: Union[Decimal, int, float], decimals: int = 0) -> Decimal:
    """
    Round a decimal value down to specified decimal places.
    
    Args:
        value: Value to round
        decimals: Number of decimal places
        
    Returns:
        Rounded down Decimal value
        
    Examples:
        >>> round_decimal_down(Decimal('10.567'), 2)
        Decimal('10.56')
        >>> round_decimal_down(123.99, 0)
        Decimal('123')
    """
    multiplier = 10 ** decimals
    dec_value = to_decimal(value, DEC_0)

    # Convert to float for math.floor, then back to Decimal via string
    # This preserves precision better than direct Decimal arithmetic
    floored = math.floor(float(dec_value) * multiplier) / multiplier
    return Decimal(str(floored))


def round_decimal(
        value: Union[Decimal, int, float],
        decimals: int = 2,
        rounding: str = ROUND_HALF_UP
) -> Decimal:
    """
    Round a decimal value to specified decimal places with configurable rounding.
    
    Args:
        value: Value to round
        decimals: Number of decimal places
        rounding: Rounding mode (ROUND_HALF_UP, ROUND_DOWN, etc.)
        
    Returns:
        Rounded Decimal value
        
    Examples:
        >>> round_decimal(Decimal('10.565'), 2)
        Decimal('10.57')
        >>> round_decimal(Decimal('10.565'), 2, ROUND_DOWN)
        Decimal('10.56')
    """
    dec_value = to_decimal(value, DEC_0)
    quantize_value = Decimal(10) ** -decimals
    return dec_value.quantize(quantize_value, rounding=rounding)


def decimal_division(
        numerator: Union[Decimal, int, float, str, None],
        denominator: Union[Decimal, int, float, str, None],
        decimals: int = 2,
        default: Decimal = DEC_0
) -> Decimal:
    """
    Safely divide two values and return as Decimal.
    
    Args:
        numerator: Dividend
        denominator: Divisor
        decimals: Number of decimal places to round to
        default: Default value if division fails or denominator is zero
        
    Returns:
        Result of division or default
        
    Examples:
        >>> decimal_division(100, 3, 2)
        Decimal('33.33')
        >>> decimal_division(10, 0)
        Decimal('0')
    """
    try:
        num = to_decimal(numerator, DEC_0)
        den = to_decimal(denominator, DEC_0)

        if den == DEC_0:
            return default

        result = num / den
        return round_decimal(result, decimals)
    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
        return default


def sum_decimals(*values: Union[Decimal, int, float, str, None]) -> Decimal:
    """
    Safely sum multiple decimal values.
    
    Args:
        *values: Variable number of values to sum
        
    Returns:
        Sum as Decimal
        
    Examples:
        >>> sum_decimals(10, "20.5", Decimal('5.25'))
        Decimal('35.75')
        >>> sum_decimals(None, 10, None, 5)
        Decimal('15')
    """
    total = DEC_0
    for value in values:
        total += to_decimal(value, DEC_0)
    return total


class DecimalEncoder(json.JSONEncoder):
    """
    JSON encoder that handles Decimal types.
    
    Usage:
        >>> data = {'amount': Decimal('123.45')}
        >>> json.dumps(data, cls=DecimalEncoder)
        '{"amount": "123.45"}'
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def format_decimal(
        value: Union[Decimal, int, float, str, None],
        decimals: int = 2,
        thousands_sep: str = ","
) -> str:
    """
    Format a decimal value as a string with thousand separators.
    
    Args:
        value: Value to format
        decimals: Number of decimal places
        thousands_sep: Thousands separator character
        
    Returns:
        Formatted string
        
    Examples:
        >>> format_decimal(1234567.89)
        '1,234,567.89'
        >>> format_decimal(1000, 0)
        '1,000'
    """
    dec_value = to_decimal(value, DEC_0)
    rounded = round_decimal(dec_value, decimals)

    # Split into integer and decimal parts
    parts = str(rounded).split('.')
    integer_part = parts[0]
    decimal_part = parts[1] if len(parts) > 1 else '0' * decimals

    # Add thousands separator
    integer_with_sep = f"{int(integer_part):,}".replace(',', thousands_sep)

    if decimals > 0:
        return f"{integer_with_sep}.{decimal_part}"
    return integer_with_sep
