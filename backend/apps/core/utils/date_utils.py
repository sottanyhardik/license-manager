"""
Date utility functions for date parsing, formatting, and validation.

This module provides utilities for:
- Safe date parsing from various formats
- Date formatting
- Date range validation and comparison
- Expiry checking
"""

from datetime import date, datetime, timedelta
from typing import Optional, Union, Tuple

from django.utils import timezone


def parse_date_safe(
        value: Union[str, date, datetime, None],
        default: Optional[date] = None
) -> Optional[date]:
    """
    Safely parse a date from various input formats.
    
    Args:
        value: Date value (string, date, datetime, or None)
        default: Default value if parsing fails
        
    Returns:
        Parsed date or default
        
    Examples:
        >>> parse_date_safe("2024-01-15")
        datetime.date(2024, 1, 15)
        >>> parse_date_safe("invalid")
        None
    """
    if value is None:
        return default

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        # Try common date formats - dd-mm-yyyy first (primary format)
        formats = [
            '%d-%m-%Y',
            '%d/%m/%Y',
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%d.%m.%Y',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except (ValueError, TypeError):
                continue

    return default


def parse_datetime_safe(
        value: Union[str, date, datetime, None],
        default: Optional[datetime] = None
) -> Optional[datetime]:
    if value is None:
        return default
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed
            except (ValueError, TypeError):
                continue
    return default


def format_date(
        value: Union[date, datetime, None],
        format_str: str = '%d-%m-%Y'
) -> str:
    """
    Format a date as a string.

    Args:
        value: Date to format
        format_str: Output format string (default: '%d-%m-%Y' for dd-mm-yyyy)

    Returns:
        Formatted date string or empty string if value is None

    Examples:
        >>> format_date(date(2024, 1, 15))
        '15-01-2024'
        >>> format_date(date(2024, 1, 15), '%d/%m/%Y')
        '15/01/2024'
    """
    if value is None:
        return ''

    if isinstance(value, datetime):
        value = value.date()

    return value.strftime(format_str)


def format_date_display(value: Union[date, datetime, None], format_str: str = "%d/%m/%Y") -> str:
    if not isinstance(value, (date, datetime)):
        return ""
    return format_date(value, format_str)


def format_date_iso(value: Union[date, datetime, None]) -> Optional[str]:
    if not isinstance(value, (date, datetime)):
        return None
    if isinstance(value, datetime):
        value = value.date()
    return value.isoformat()


def is_date_expired(
        expiry_date: Union[date, datetime, None],
        reference_date: Optional[date] = None
) -> bool:
    """
    Check if a date has expired.
    
    Args:
        expiry_date: Date to check
        reference_date: Date to compare against (default: today)
        
    Returns:
        True if expired, False otherwise
        
    Examples:
        >>> is_date_expired(date(2020, 1, 1))
        True
        >>> is_date_expired(date(2030, 1, 1))
        False
    """
    if expiry_date is None:
        return False

    if isinstance(expiry_date, datetime):
        expiry_date = expiry_date.date()

    if reference_date is None:
        reference_date = timezone.now().date()

    return expiry_date < reference_date


def is_date_in_range(
        check_date: Union[date, datetime, None],
        start_date: Union[date, datetime, None] = None,
        end_date: Union[date, datetime, None] = None
) -> bool:
    check_date = parse_date_safe(check_date)
    start_date = parse_date_safe(start_date)
    end_date = parse_date_safe(end_date)
    if check_date is None:
        return False
    if start_date is not None and check_date < start_date:
        return False
    if end_date is not None and check_date > end_date:
        return False
    return True


def is_date_within_days(
        check_date: Union[date, datetime, None],
        days: int,
        reference_date: Optional[date] = None
) -> bool:
    """
    Check if a date is within a specified number of days from reference date.
    
    Args:
        check_date: Date to check
        days: Number of days (negative for past, positive for future)
        reference_date: Date to compare against (default: today)
        
    Returns:
        True if within specified days, False otherwise
        
    Examples:
        >>> # Check if date is within last 90 days
        >>> is_date_within_days(date.today() - timedelta(days=30), -90)
        True
    """
    if check_date is None:
        return False

    if isinstance(check_date, datetime):
        check_date = check_date.date()

    if reference_date is None:
        reference_date = timezone.now().date()

    threshold_date = reference_date - timedelta(days=abs(days))

    if days < 0:
        # Check if date is after threshold (within last N days)
        return check_date >= threshold_date
    else:
        # Check if date is before threshold (within next N days)
        return check_date <= threshold_date


def date_range_overlaps(
        start1: Union[date, datetime, None],
        end1: Union[date, datetime, None],
        start2: Union[date, datetime, None],
        end2: Union[date, datetime, None]
) -> bool:
    """
    Check if two date ranges overlap.
    
    Args:
        start1: Start date of first range
        end1: End date of first range
        start2: Start date of second range
        end2: End date of second range
        
    Returns:
        True if ranges overlap, False otherwise
        
    Examples:
        >>> date_range_overlaps(
        ...     date(2024, 1, 1), date(2024, 3, 31),
        ...     date(2024, 2, 1), date(2024, 4, 30)
        ... )
        True
    """
    if None in (start1, end1, start2, end2):
        return False

    # Convert datetime to date if needed
    if isinstance(start1, datetime):
        start1 = start1.date()
    if isinstance(end1, datetime):
        end1 = end1.date()
    if isinstance(start2, datetime):
        start2 = start2.date()
    if isinstance(end2, datetime):
        end2 = end2.date()

    # Check for overlap: ranges overlap if start of one is before end of other
    return start1 <= end2 and start2 <= end1


def days_until(
        target_date: Union[date, datetime, None],
        reference_date: Optional[date] = None
) -> Optional[int]:
    """
    Calculate number of days until target date.
    
    Args:
        target_date: Target date
        reference_date: Date to calculate from (default: today)
        
    Returns:
        Number of days (negative if in past), or None if target_date is None
        
    Examples:
        >>> days_until(date.today() + timedelta(days=10))
        10
    """
    if target_date is None:
        return None

    if isinstance(target_date, datetime):
        target_date = target_date.date()

    if reference_date is None:
        reference_date = timezone.now().date()

    delta = target_date - reference_date
    return delta.days


def days_between(start_date: Union[date, datetime], end_date: Union[date, datetime], absolute: bool = False) -> int:
    start = parse_date_safe(start_date)
    end = parse_date_safe(end_date)
    if start is None or end is None:
        return 0
    days = (end - start).days
    return abs(days) if absolute else days


def is_weekend(value: Union[date, datetime]) -> bool:
    parsed = parse_date_safe(value)
    return bool(parsed and parsed.weekday() >= 5)


def add_business_days(start_date: date, days: int) -> date:
    if days == 0:
        return start_date
    current = start_date
    step = 1 if days > 0 else -1
    remaining = abs(days)
    while remaining:
        current += timedelta(days=step)
        if not is_weekend(current):
            remaining -= 1
    return current


def get_financial_year(value: Union[date, datetime]) -> str:
    parsed = parse_date_safe(value)
    if parsed is None:
        return ""
    start_year = parsed.year if parsed.month >= 4 else parsed.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def get_quarter(value: Union[date, datetime]) -> int:
    parsed = parse_date_safe(value)
    if parsed is None:
        return 0
    if 4 <= parsed.month <= 6:
        return 1
    if 7 <= parsed.month <= 9:
        return 2
    if 10 <= parsed.month <= 12:
        return 3
    return 4


def add_months(start_date: date, months: int) -> date:
    """
    Add months to a date.
    
    Args:
        start_date: Starting date
        months: Number of months to add (can be negative)
        
    Returns:
        New date
        
    Examples:
        >>> add_months(date(2024, 1, 15), 3)
        datetime.date(2024, 4, 15)
    """
    # Calculate new month and year
    month = start_date.month - 1 + months
    year = start_date.year + month // 12
    month = month % 12 + 1

    # Handle day overflow (e.g., Jan 31 + 1 month = Feb 28/29)
    day = min(start_date.day,
              [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31,
               30, 31][month - 1])

    return date(year, month, day)


def get_date_range_from_filter(
        filter_type: str,
        custom_start: Optional[date] = None,
        custom_end: Optional[date] = None
) -> Tuple[Optional[date], Optional[date]]:
    """
    Get date range based on filter type.
    
    Args:
        filter_type: Type of filter ('today', 'this_week', 'this_month', 'this_year', 'custom')
        custom_start: Custom start date (for 'custom' type)
        custom_end: Custom end date (for 'custom' type)
        
    Returns:
        Tuple of (start_date, end_date)
        
    Examples:
        >>> get_date_range_from_filter('today')
        (datetime.date(2024, 1, 15), datetime.date(2024, 1, 15))
    """
    today = timezone.now().date()

    if filter_type == 'today':
        return today, today

    elif filter_type == 'this_week':
        # Monday to Sunday
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end

    elif filter_type == 'this_month':
        start = date(today.year, today.month, 1)
        # Last day of month
        if today.month == 12:
            end = date(today.year, 12, 31)
        else:
            end = date(today.year, today.month + 1, 1) - timedelta(days=1)
        return start, end

    elif filter_type == 'this_year':
        start = date(today.year, 1, 1)
        end = date(today.year, 12, 31)
        return start, end

    elif filter_type == 'custom':
        return custom_start, custom_end

    return None, None


def format_date_range(
        start_date: Union[date, datetime, None],
        end_date: Union[date, datetime, None],
        format_str: str = '%d-%m-%Y',
        separator: str = ' to '
) -> str:
    """
    Format a date range as a string.

    Args:
        start_date: Start date
        end_date: End date
        format_str: Format string for dates (default: '%d-%m-%Y' for dd-mm-yyyy)
        separator: Separator between dates

    Returns:
        Formatted date range string

    Examples:
        >>> format_date_range(date(2024, 1, 1), date(2024, 12, 31))
        '01-01-2024 to 31-12-2024'
    """
    start_str = format_date(start_date, format_str)
    end_str = format_date(end_date, format_str)

    if start_str and end_str:
        return f"{start_str}{separator}{end_str}"
    elif start_str:
        return f"From {start_str}"
    elif end_str:
        return f"Until {end_str}"

    return ''
