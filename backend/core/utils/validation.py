"""
Validation utility functions for common validation tasks.

This module provides utilities for:
- Field value validation
- Data integrity checks
- Business rule validation
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Dict, Optional, Union

from django.core.exceptions import ValidationError

from .decimal_utils import to_decimal


def validate_positive_decimal(
        value: Union[Decimal, int, float, str, None],
        field_name: str = "value",
        allow_zero: bool = False
) -> Decimal:
    """
    Validate that a value is a positive decimal.
    
    Args:
        value: Value to validate
        field_name: Name of field (for error message)
        allow_zero: Whether to allow zero value
        
    Returns:
        Validated Decimal value
        
    Raises:
        ValidationError: If value is not positive
        
    Examples:
        >>> validate_positive_decimal(10.5)
        Decimal('10.5')
        >>> validate_positive_decimal(-5, "amount")
        ValidationError: amount must be positive
    """
    dec_value = to_decimal(value)

    if allow_zero:
        if dec_value < Decimal('0'):
            raise ValidationError(f"{field_name} must be non-negative")
    else:
        if dec_value <= Decimal('0'):
            raise ValidationError(f"{field_name} must be positive")

    return dec_value


def validate_date_range(
        start_date: Union[date, datetime, None],
        end_date: Union[date, datetime, None],
        field_prefix: str = ""
) -> tuple:
    """
    Validate that start date is before or equal to end date.
    
    Args:
        start_date: Start date
        end_date: End date
        field_prefix: Prefix for field names in error messages
        
    Returns:
        Tuple of (start_date, end_date)
        
    Raises:
        ValidationError: If date range is invalid
        
    Examples:
        >>> validate_date_range(date(2024, 1, 1), date(2024, 12, 31))
        (datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))
    """
    if start_date is None or end_date is None:
        return start_date, end_date

    # Convert datetime to date if needed
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()

    if start_date > end_date:
        raise ValidationError(
            f"{field_prefix}start_date must be before or equal to {field_prefix}end_date"
        )

    return start_date, end_date


def validate_required_fields(
        data: Dict[str, Any],
        required_fields: List[str]
) -> None:
    """
    Validate that required fields are present and not empty.
    
    Args:
        data: Dictionary of data to validate
        required_fields: List of required field names
        
    Raises:
        ValidationError: If any required field is missing or empty
        
    Examples:
        >>> validate_required_fields({'name': 'John', 'age': 30}, ['name', 'age'])
        None
        >>> validate_required_fields({'name': 'John'}, ['name', 'age'])
        ValidationError: Missing required fields: age
    """
    missing_fields = []
    empty_fields = []

    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
        elif data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
            empty_fields.append(field)

    errors = []
    if missing_fields:
        errors.append(f"Missing required fields: {', '.join(missing_fields)}")
    if empty_fields:
        errors.append(f"Empty required fields: {', '.join(empty_fields)}")

    if errors:
        raise ValidationError('; '.join(errors))


def validate_choice(
        value: Any,
        choices: List[tuple],
        field_name: str = "value"
) -> Any:
    """
    Validate that value is in a list of choices.
    
    Args:
        value: Value to validate
        choices: List of (value, label) tuples (Django choices format)
        field_name: Name of field (for error message)
        
    Returns:
        Validated value
        
    Raises:
        ValidationError: If value is not in choices
        
    Examples:
        >>> choices = [('A', 'Option A'), ('B', 'Option B')]
        >>> validate_choice('A', choices)
        'A'
    """
    valid_values = [choice[0] for choice in choices]

    if value not in valid_values:
        raise ValidationError(
            f"{field_name} must be one of: {', '.join(str(v) for v in valid_values)}"
        )

    return value


def validate_decimal_range(
        value: Union[Decimal, int, float, str, None],
        min_value: Optional[Decimal] = None,
        max_value: Optional[Decimal] = None,
        field_name: str = "value"
) -> Decimal:
    """
    Validate that a decimal value is within a specified range.
    
    Args:
        value: Value to validate
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        field_name: Name of field (for error message)
        
    Returns:
        Validated Decimal value
        
    Raises:
        ValidationError: If value is out of range
        
    Examples:
        >>> validate_decimal_range(50, Decimal('0'), Decimal('100'))
        Decimal('50')
    """
    dec_value = to_decimal(value)

    if min_value is not None and dec_value < min_value:
        raise ValidationError(f"{field_name} must be at least {min_value}")

    if max_value is not None and dec_value > max_value:
        raise ValidationError(f"{field_name} must be at most {max_value}")

    return dec_value


def validate_balance_sufficient(
        available: Union[Decimal, int, float],
        required: Union[Decimal, int, float],
        field_name: str = "balance"
) -> None:
    """
    Validate that available balance is sufficient for required amount.
    
    Args:
        available: Available balance
        required: Required amount
        field_name: Name of field (for error message)
        
    Raises:
        ValidationError: If balance is insufficient
        
    Examples:
        >>> validate_balance_sufficient(100, 50)
        None
        >>> validate_balance_sufficient(30, 50)
        ValidationError: Insufficient balance
    """
    available_dec = to_decimal(available)
    required_dec = to_decimal(required)

    if available_dec < required_dec:
        raise ValidationError(
            f"Insufficient {field_name}. Available: {available_dec}, Required: {required_dec}"
        )


def validate_unique_in_list(
        items: List[Dict[str, Any]],
        field_name: str
) -> None:
    """
    Validate that a field value is unique across all items in a list.
    
    Args:
        items: List of dictionaries
        field_name: Name of field to check for uniqueness
        
    Raises:
        ValidationError: If duplicate values are found
        
    Examples:
        >>> items = [{'code': 'A'}, {'code': 'B'}, {'code': 'A'}]
        >>> validate_unique_in_list(items, 'code')
        ValidationError: Duplicate values found for code: A
    """
    values = [item.get(field_name) for item in items if field_name in item]
    seen = set()
    duplicates = set()

    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)

    if duplicates:
        raise ValidationError(
            f"Duplicate values found for {field_name}: {', '.join(str(d) for d in duplicates)}"
        )


def validate_file_extension(
        filename: str,
        allowed_extensions: List[str]
) -> str:
    """
    Validate that a filename has an allowed extension.
    
    Args:
        filename: Name of file
        allowed_extensions: List of allowed extensions (without dot)
        
    Returns:
        Validated filename
        
    Raises:
        ValidationError: If extension is not allowed
        
    Examples:
        >>> validate_file_extension('document.pdf', ['pdf', 'docx'])
        'document.pdf'
    """
    if '.' not in filename:
        raise ValidationError("File has no extension")

    extension = filename.rsplit('.', 1)[1].lower()

    if extension not in [ext.lower() for ext in allowed_extensions]:
        raise ValidationError(
            f"File extension .{extension} is not allowed. Allowed: {', '.join(allowed_extensions)}"
        )

    return filename


def validate_conditional_required(
        data: Dict[str, Any],
        field: str,
        condition_field: str,
        condition_value: Any
) -> None:
    """
    Validate that a field is required when another field has a specific value.
    
    Args:
        data: Dictionary of data
        field: Field to validate
        condition_field: Field that determines if field is required
        condition_value: Value that makes field required
        
    Raises:
        ValidationError: If conditional validation fails
        
    Examples:
        >>> data = {'type': 'custom', 'custom_value': ''}
        >>> validate_conditional_required(data, 'custom_value', 'type', 'custom')
        ValidationError: custom_value is required when type is custom
    """
    if data.get(condition_field) == condition_value:
        if field not in data or not data[field]:
            raise ValidationError(
                f"{field} is required when {condition_field} is {condition_value}"
            )
