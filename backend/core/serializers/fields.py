"""
Custom serializer fields for common use cases.

This module provides custom DRF field classes including:
- SafeDateField: Handles both date and datetime inputs
- SafeDateTimeField: Tolerates receiving datetime.date
- DateFormatterMixin: Mixin for serializers with date formatting methods
"""

from datetime import date, datetime
from typing import Optional

from rest_framework import serializers


class SafeDateField(serializers.DateField):
    """
    Date field that safely handles both date and datetime inputs.

    This field is tolerant of receiving datetime.datetime objects and will
    automatically extract the date portion. Useful when frontend or other
    systems might send datetime where only date is expected.

    Usage:
        class MySerializer(serializers.ModelSerializer):
            start_date = SafeDateField()
            end_date = SafeDateField()

            class Meta:
                model = MyModel
                fields = ['start_date', 'end_date']

    Example:
        >>> field = SafeDateField()
        >>> field.to_internal_value('2024-01-15')
        datetime.date(2024, 1, 15)
        >>> field.to_internal_value(datetime(2024, 1, 15, 10, 30))
        datetime.date(2024, 1, 15)
    """

    def to_internal_value(self, value):
        """Convert input to date, handling datetime objects"""
        # If already a datetime object, extract date
        if isinstance(value, datetime):
            return value.date()

        # If already a date object, return as-is
        if isinstance(value, date):
            return value

        # Otherwise use parent's parsing logic
        return super().to_internal_value(value)

    def to_representation(self, value):
        """Convert date to string representation"""
        # If datetime, extract date first
        if isinstance(value, datetime):
            value = value.date()

        return super().to_representation(value)


class SafeDateTimeField(serializers.DateTimeField):
    """
    DateTime field that safely handles receiving date objects.

    This field is tolerant of receiving datetime.date objects and will
    automatically convert them to datetime by setting time to midnight.
    Useful when data sources might send date where datetime is expected.

    Usage:
        class MySerializer(serializers.ModelSerializer):
            created_at = SafeDateTimeField()
            updated_at = SafeDateTimeField()

            class Meta:
                model = MyModel
                fields = ['created_at', 'updated_at']

    Example:
        >>> field = SafeDateTimeField()
        >>> field.to_internal_value('2024-01-15T10:30:00')
        datetime.datetime(2024, 1, 15, 10, 30, 0)
        >>> field.to_internal_value(date(2024, 1, 15))
        datetime.datetime(2024, 1, 15, 0, 0, 0)
    """

    def to_internal_value(self, value):
        """Convert input to datetime, handling date objects"""
        # If date but not datetime, convert to datetime at midnight
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, datetime.min.time())

        # If already datetime, return as-is
        if isinstance(value, datetime):
            return value

        # Otherwise use parent's parsing logic
        return super().to_internal_value(value)

    def to_representation(self, value):
        """Convert datetime to string representation"""
        # If date but not datetime, convert first
        if isinstance(value, date) and not isinstance(value, datetime):
            value = datetime.combine(value, datetime.min.time())

        return super().to_representation(value)


class FlexibleDateField(serializers.Field):
    """
    Flexible date field that accepts multiple input formats.

    Accepts date strings in various formats, datetime objects, and date objects.
    Returns date object. Useful for APIs that need to accept dates from
    different sources with varying formats.

    Usage:
        class MySerializer(serializers.ModelSerializer):
            date_field = FlexibleDateField(
                input_formats=['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'],
                output_format='%Y-%m-%d'
            )

    Example:
        >>> field = FlexibleDateField(input_formats=['%Y-%m-%d', '%d-%m-%Y'])
        >>> field.to_internal_value('2024-01-15')
        datetime.date(2024, 1, 15)
        >>> field.to_internal_value('15-01-2024')
        datetime.date(2024, 1, 15)
    """

    def __init__(self, input_formats=None, output_format='%Y-%m-%d', **kwargs):
        """
        Initialize flexible date field.

        Args:
            input_formats: List of accepted input date format strings
            output_format: Output date format string
            **kwargs: Additional field arguments
        """
        super().__init__(**kwargs)
        self.input_formats = input_formats or ['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y']
        self.output_format = output_format

    def to_internal_value(self, value):
        """Convert various date formats to date object"""
        if value is None:
            return None

        # If already a date or datetime, extract date
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        # Try to parse string with each format
        if isinstance(value, str):
            value = value.strip()
            for fmt in self.input_formats:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.date()
                except (ValueError, TypeError):
                    continue

            # If no format worked, raise validation error
            raise serializers.ValidationError(
                f"Date format not recognized. Expected one of: {', '.join(self.input_formats)}"
            )

        raise serializers.ValidationError(
            f"Invalid date type: {type(value).__name__}"
        )

    def to_representation(self, value):
        """Convert date to string representation"""
        if value is None:
            return None

        if isinstance(value, datetime):
            value = value.date()

        if isinstance(value, date):
            return value.strftime(self.output_format)

        return str(value)


class DateFormatterMixin:
    """
    Mixin for serializers that need date formatting utilities.

    Provides helper methods for formatting dates in various formats commonly
    used in Indian business contexts.

    Usage:
        class MySerializer(DateFormatterMixin, serializers.ModelSerializer):
            class Meta:
                model = MyModel
                fields = '__all__'

            def to_representation(self, instance):
                data = super().to_representation(instance)
                # Format dates for display
                data['invoice_date_display'] = self.format_date_indian(instance.invoice_date)
                data['year_display'] = self.format_year(instance.financial_year_start)
                return data
    """

    def format_date_indian(self, date_obj: Optional[date], format_str: str = '%d-%b-%y') -> str:
        """
        Format date in Indian style (DD-Mon-YY).

        Args:
            date_obj: Date or datetime object
            format_str: Format string (default: '%d-%b-%y')

        Returns:
            Formatted date string or empty string if None

        Examples:
            >>> self.format_date_indian(date(2024, 1, 15))
            '15-Jan-24'
            >>> self.format_date_indian(datetime(2024, 1, 15, 10, 30))
            '15-Jan-24'
        """
        if date_obj is None:
            return ''

        if isinstance(date_obj, datetime):
            date_obj = date_obj.date()

        return date_obj.strftime(format_str)

    def format_date_full(self, date_obj: Optional[date]) -> str:
        """
        Format date in full style (DD-MM-YYYY).

        Args:
            date_obj: Date or datetime object

        Returns:
            Formatted date string or empty string if None

        Example:
            >>> self.format_date_full(date(2024, 1, 15))
            '15-01-2024'
        """
        return self.format_date_indian(date_obj, '%d-%m-%Y')

    def format_date_iso(self, date_obj: Optional[date]) -> str:
        """
        Format date in ISO style (YYYY-MM-DD).

        Args:
            date_obj: Date or datetime object

        Returns:
            Formatted date string or empty string if None

        Example:
            >>> self.format_date_iso(date(2024, 1, 15))
            '2024-01-15'
        """
        return self.format_date_indian(date_obj, '%Y-%m-%d')

    def format_datetime_indian(
        self,
        datetime_obj: Optional[datetime],
        format_str: str = '%d-%b-%y %H:%M'
    ) -> str:
        """
        Format datetime in Indian style.

        Args:
            datetime_obj: Datetime object
            format_str: Format string (default: '%d-%b-%y %H:%M')

        Returns:
            Formatted datetime string or empty string if None

        Example:
            >>> self.format_datetime_indian(datetime(2024, 1, 15, 10, 30))
            '15-Jan-24 10:30'
        """
        if datetime_obj is None:
            return ''

        if isinstance(datetime_obj, date) and not isinstance(datetime_obj, datetime):
            # Convert date to datetime
            datetime_obj = datetime.combine(datetime_obj, datetime.min.time())

        return datetime_obj.strftime(format_str)

    def format_year(self, date_obj: Optional[date]) -> str:
        """
        Extract and format year from date.

        Args:
            date_obj: Date or datetime object

        Returns:
            Year as string or empty string if None

        Example:
            >>> self.format_year(date(2024, 1, 15))
            '2024'
        """
        if date_obj is None:
            return ''

        if isinstance(date_obj, datetime):
            date_obj = date_obj.date()

        return str(date_obj.year)

    def format_month_year(self, date_obj: Optional[date], format_str: str = '%b-%Y') -> str:
        """
        Format date as month and year.

        Args:
            date_obj: Date or datetime object
            format_str: Format string (default: '%b-%Y')

        Returns:
            Formatted month-year string or empty string if None

        Example:
            >>> self.format_month_year(date(2024, 1, 15))
            'Jan-2024'
        """
        return self.format_date_indian(date_obj, format_str)

    def parse_date_flexible(self, date_string: str) -> Optional[date]:
        """
        Parse date string with multiple format attempts.

        Args:
            date_string: Date string in various formats

        Returns:
            Date object or None if parsing fails

        Example:
            >>> self.parse_date_flexible('15-01-2024')
            datetime.date(2024, 1, 15)
            >>> self.parse_date_flexible('2024-01-15')
            datetime.date(2024, 1, 15)
        """
        if not date_string:
            return None

        formats = [
            '%Y-%m-%d',      # ISO format
            '%d-%m-%Y',      # DD-MM-YYYY
            '%d/%m/%Y',      # DD/MM/YYYY
            '%d-%b-%y',      # DD-Mon-YY
            '%d-%b-%Y',      # DD-Mon-YYYY
            '%Y/%m/%d',      # YYYY/MM/DD
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_string.strip(), fmt)
                return dt.date()
            except (ValueError, TypeError):
                continue

        return None


class FinancialYearField(serializers.Field):
    """
    Field for handling financial year periods.

    Represents financial year as a string like "2023-24" and converts to/from
    date ranges. Useful for Indian financial year (April to March).

    Usage:
        class MySerializer(serializers.ModelSerializer):
            financial_year = FinancialYearField()

            class Meta:
                model = MyModel
                fields = ['financial_year']

    Example:
        >>> field = FinancialYearField()
        >>> field.to_internal_value('2023-24')
        {'start_date': datetime.date(2023, 4, 1), 'end_date': datetime.date(2024, 3, 31)}
    """

    def to_internal_value(self, value):
        """
        Convert financial year string to date range.

        Args:
            value: String like "2023-24"

        Returns:
            Dict with 'start_date' and 'end_date'
        """
        if not value:
            return None

        if isinstance(value, dict):
            return value

        # Parse format like "2023-24"
        try:
            parts = value.split('-')
            if len(parts) != 2:
                raise serializers.ValidationError(
                    "Financial year must be in format 'YYYY-YY'"
                )

            start_year = int(parts[0])
            end_year_short = int(parts[1])

            # Validate end year
            expected_end = start_year + 1
            if end_year_short != expected_end % 100:
                raise serializers.ValidationError(
                    f"Invalid financial year range: {value}"
                )

            # Indian financial year: April to March
            start_date = date(start_year, 4, 1)
            end_date = date(start_year + 1, 3, 31)

            return {
                'start_date': start_date,
                'end_date': end_date,
                'year_string': value
            }
        except (ValueError, IndexError) as e:
            raise serializers.ValidationError(
                f"Invalid financial year format: {value}"
            )

    def to_representation(self, value):
        """
        Convert date range to financial year string.

        Args:
            value: Dict with start_date and end_date, or date object

        Returns:
            String like "2023-24"
        """
        if value is None:
            return None

        # If already a string, return as-is
        if isinstance(value, str):
            return value

        # If dict with year_string, return that
        if isinstance(value, dict) and 'year_string' in value:
            return value['year_string']

        # If dict with start_date, derive from that
        if isinstance(value, dict) and 'start_date' in value:
            start_date = value['start_date']
            if isinstance(start_date, datetime):
                start_date = start_date.date()
            if isinstance(start_date, date):
                year = start_date.year
                return f"{year}-{(year + 1) % 100:02d}"

        # If single date, derive financial year
        if isinstance(value, (date, datetime)):
            if isinstance(value, datetime):
                value = value.date()

            # If month >= April, FY is current year to next year
            # Otherwise, FY is previous year to current year
            if value.month >= 4:
                year = value.year
            else:
                year = value.year - 1

            return f"{year}-{(year + 1) % 100:02d}"

        return str(value)
