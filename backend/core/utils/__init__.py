"""
Core utility modules for the license manager application.

This package contains reusable utility functions and classes:
- decimal_utils: Decimal conversion and arithmetic helpers
- date_utils: Date manipulation and formatting utilities
- validation: Common validation functions
"""

from .date_utils import (
    parse_date_safe,
    format_date,
    is_date_expired,
    date_range_overlaps,
)
from .decimal_utils import (
    to_decimal,
    safe_decimal_operation,
    round_decimal_down,
    DecimalEncoder,
)
from .validation import (
    validate_positive_decimal,
    validate_date_range,
    validate_required_fields,
)

__all__ = [
    # Decimal utilities
    'to_decimal',
    'safe_decimal_operation',
    'round_decimal_down',
    'DecimalEncoder',
    # Date utilities
    'parse_date_safe',
    'format_date',
    'is_date_expired',
    'date_range_overlaps',
    # Validation utilities
    'validate_positive_decimal',
    'validate_date_range',
    'validate_required_fields',
]
