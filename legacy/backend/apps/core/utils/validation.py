"""
Validation utility functions for common validation tasks.

This module provides utilities for:
- Field value validation
- Data integrity checks
- Business rule validation
"""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Dict, Optional, Union

from django.core.exceptions import ValidationError

from .date_utils import parse_date_safe
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
    if value is None:
        raise ValidationError(f"{field_name} is required")

    sentinel = object()
    dec_value = to_decimal(value, sentinel)
    if dec_value is sentinel:
        raise ValidationError(f"{field_name} must be a valid number")

    if allow_zero:
        if dec_value < Decimal('0'):
            raise ValidationError(f"{field_name} cannot be negative")
    else:
        if dec_value <= Decimal('0'):
            raise ValidationError(f"{field_name} must be positive")

    return dec_value


def validate_non_negative_decimal(
        value: Union[Decimal, int, float, str, None],
        field_name: str = "value",
) -> Decimal:
    return validate_positive_decimal(value, field_name, allow_zero=True)


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
    start_date = parse_date_safe(start_date)
    end_date = parse_date_safe(end_date)

    if start_date is None:
        raise ValidationError(f"{field_prefix}start_date is required")
    if end_date is None:
        raise ValidationError(f"{field_prefix}end_date is required")

    if start_date > end_date:
        raise ValidationError(
            f"{field_prefix}end_date cannot be before {field_prefix}start_date"
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
        field_name: str = "value",
        case_sensitive: bool = True,
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
    if value is None:
        raise ValidationError(f"{field_name} is required")

    valid_values = [choice[0] if isinstance(choice, (tuple, list)) else choice for choice in choices]

    if not case_sensitive and isinstance(value, str):
        lowered = [str(choice).lower() for choice in valid_values]
        if value.lower() not in lowered:
            raise ValidationError(
                f"{field_name} must be one of: {', '.join(str(v) for v in valid_values)}"
            )
        return value

    if value not in valid_values:
        raise ValidationError(
            f"{field_name} must be one of: {', '.join(str(v) for v in valid_values)}"
        )

    return value


def validate_unique_items(items: List[Any], field_name: str = "items") -> None:
    seen = set()
    for item in items:
        if item in seen:
            raise ValidationError(f"Duplicate {field_name}: {item}")
        seen.add(item)


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

    normalized_allowed = [
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in allowed_extensions
    ]
    lower_name = filename.lower()

    if not any(lower_name.endswith(ext) for ext in normalized_allowed):
        raise ValidationError(
            f"File extension is not allowed. Allowed extensions: {', '.join(allowed_extensions)}"
        )

    return filename


def is_valid_email(value: Optional[str]) -> bool:
    if not value or not isinstance(value, str):
        return False
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return re.match(pattern, value) is not None


def is_valid_phone(value: Optional[str]) -> bool:
    if not value or not isinstance(value, str):
        return False
    digits = re.sub(r"\D", "", value)
    return 10 <= len(digits) <= 15 and not re.search(r"[A-Za-z]", value)


def sanitize_string(
        value: Optional[str],
        remove_special: bool = False,
        lowercase: bool = False,
        uppercase: bool = False,
        max_length: Optional[int] = None,
) -> str:
    if value is None:
        return ""
    result = str(value).strip()
    if remove_special:
        result = re.sub(r"[^A-Za-z0-9 ]+", "", result)
    if lowercase:
        result = result.lower()
    if uppercase:
        result = result.upper()
    if max_length is not None:
        result = result[:max_length]
    return result


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


def validate_license_number(value: str) -> str:
    """
    Sanitize and validate license number.

    Removes extra whitespace, converts to uppercase, and validates format.

    Args:
        value: License number string

    Returns:
        Sanitized license number

    Raises:
        ValidationError: If license number format is invalid

    Examples:
        >>> validate_license_number('  abc123  ')
        'ABC123'
        >>> validate_license_number('')
        ValidationError: License number cannot be empty
    """
    if not value:
        raise ValidationError("License number cannot be empty")

    # Remove extra whitespace and convert to uppercase
    sanitized = value.strip().upper()

    if not sanitized:
        raise ValidationError("License number cannot be empty")

    # Check minimum length (adjust as needed for your business rules)
    if len(sanitized) < 3:
        raise ValidationError("License number must be at least 3 characters")

    return sanitized


def validate_nested_items(
    items: List[Dict[str, Any]],
    validators: List[callable],
    field_name: str = 'items'
) -> None:
    """
    Generic validation for nested items with custom validators.

    Args:
        items: List of item dictionaries to validate
        validators: List of validator functions that take (item, index) as arguments
        field_name: Name of the field (for error messages)

    Raises:
        ValidationError: If any validation fails

    Examples:
        >>> def check_amount(item, idx):
        ...     if item.get('amount', 0) < 0:
        ...         raise ValidationError(f"Amount cannot be negative")
        >>> items = [{'amount': 100}, {'amount': -50}]
        >>> validate_nested_items(items, [check_amount], 'lines')
        ValidationError: lines[1]: Amount cannot be negative
    """
    if not isinstance(items, list):
        raise ValidationError(f"{field_name} must be a list")

    errors = {}

    for idx, item in enumerate(items):
        for validator in validators:
            try:
                validator(item, idx)
            except ValidationError as e:
                error_key = f"{field_name}[{idx}]"
                if error_key not in errors:
                    errors[error_key] = []
                errors[error_key].append(str(e))
            except Exception as e:
                error_key = f"{field_name}[{idx}]"
                if error_key not in errors:
                    errors[error_key] = []
                errors[error_key].append("Validation error occurred")

    if errors:
        # Format errors as a readable message
        error_messages = []
        for key, msgs in errors.items():
            error_messages.append(f"{key}: {'; '.join(msgs)}")
        raise ValidationError('; '.join(error_messages))


def normalize_empty_fields(
    data: Dict[str, Any],
    field_configs: Dict[str, Union[type, Any]]
) -> Dict[str, Any]:
    """
    Normalize empty string fields to None or default values.

    Converts empty strings to None for nullable fields, or to default values
    (like 0 for Decimal fields) based on field configuration.

    Args:
        data: Dictionary of data to normalize
        field_configs: Dict mapping field names to their types or default values
                      - None: convert empty string to None
                      - Decimal: convert empty string to Decimal('0')
                      - int: convert empty string to 0
                      - Any other value: use as default

    Returns:
        Dictionary with normalized fields

    Examples:
        >>> data = {'name': '', 'amount': '', 'qty': ''}
        >>> configs = {'name': None, 'amount': Decimal, 'qty': 0}
        >>> normalize_empty_fields(data, configs)
        {'name': None, 'amount': Decimal('0'), 'qty': 0}
    """
    normalized = data.copy()

    for field, config in field_configs.items():
        if field in normalized and normalized[field] == '':
            if config is None:
                normalized[field] = None
            elif config is Decimal:
                normalized[field] = Decimal('0')
            elif config is int:
                normalized[field] = 0
            elif config is float:
                normalized[field] = 0.0
            else:
                # Use config value as default
                normalized[field] = config

    return normalized


def validate_iec_number(value: str) -> str:
    """
    Validate and sanitize IEC (Importer-Exporter Code) number.

    IEC is a 10-digit code issued by DGFT (Directorate General of Foreign Trade).

    Args:
        value: IEC number string

    Returns:
        Sanitized IEC number

    Raises:
        ValidationError: If IEC format is invalid

    Examples:
        >>> validate_iec_number('1234567890')
        '1234567890'
        >>> validate_iec_number('ABC123')
        ValidationError: IEC must be exactly 10 digits
    """
    if not value:
        raise ValidationError("IEC number cannot be empty")

    # Remove whitespace
    sanitized = value.strip()

    # Check if exactly 10 characters
    if len(sanitized) != 10:
        raise ValidationError("IEC must be exactly 10 characters")

    # Check if all characters are alphanumeric (typically all digits, but some may have letters)
    if not sanitized.isalnum():
        raise ValidationError("IEC must contain only alphanumeric characters")

    return sanitized.upper()


def validate_gst_number(value: str) -> str:
    """
    Validate and sanitize GST (Goods and Services Tax) number.

    GST number format: 2 digits (state code) + 10 characters (PAN) +
    1 digit (entity number) + 1 letter (Z) + 1 check digit
    Total: 15 characters

    Args:
        value: GST number string

    Returns:
        Sanitized GST number

    Raises:
        ValidationError: If GST format is invalid

    Examples:
        >>> validate_gst_number('27AAPFU0939F1ZV')
        '27AAPFU0939F1ZV'
        >>> validate_gst_number('ABC123')
        ValidationError: GST number must be 15 characters
    """
    if not value:
        raise ValidationError("GST number cannot be empty")

    # Remove whitespace and convert to uppercase
    sanitized = value.strip().upper()

    # Check length
    if len(sanitized) != 15:
        raise ValidationError("GST number must be 15 characters")

    # Basic format validation
    if not sanitized[:2].isdigit():
        raise ValidationError("GST number must start with 2-digit state code")

    if not sanitized[2:12].isalnum():
        raise ValidationError("Invalid GST number format (PAN section)")

    if not sanitized[12].isdigit():
        raise ValidationError("Invalid GST number format (entity number)")

    if sanitized[13] != 'Z':
        raise ValidationError("Invalid GST number format (must have 'Z' at position 14)")

    if not sanitized[14].isalnum():
        raise ValidationError("Invalid GST number format (check digit)")

    return sanitized


def validate_pan_number(value: str) -> str:
    """
    Validate and sanitize PAN (Permanent Account Number).

    PAN format: 5 letters + 4 digits + 1 letter
    Total: 10 characters

    Args:
        value: PAN number string

    Returns:
        Sanitized PAN number

    Raises:
        ValidationError: If PAN format is invalid

    Examples:
        >>> validate_pan_number('AAPFU0939F')
        'AAPFU0939F'
        >>> validate_pan_number('ABC123')
        ValidationError: PAN must be 10 characters
    """
    if not value:
        raise ValidationError("PAN number cannot be empty")

    # Remove whitespace and convert to uppercase
    sanitized = value.strip().upper()

    # Check length
    if len(sanitized) != 10:
        raise ValidationError("PAN must be 10 characters")

    # Validate format: 5 letters + 4 digits + 1 letter
    if not sanitized[:5].isalpha():
        raise ValidationError("PAN must start with 5 letters")

    if not sanitized[5:9].isdigit():
        raise ValidationError("PAN must have 4 digits after first 5 letters")

    if not sanitized[9].isalpha():
        raise ValidationError("PAN must end with a letter")

    return sanitized
