"""
Unit tests for core.utils.date_utils module
"""
import pytest
from datetime import date, datetime, timedelta
from core.utils.date_utils import (
    parse_date_safe,
    parse_datetime_safe,
    format_date_display,
    format_date_iso,
    is_date_expired,
    is_date_in_range,
    date_range_overlaps,
    days_between,
    add_business_days,
    get_financial_year,
    get_quarter,
    is_weekend,
)


class TestParseDateSafe:
    """Tests for parse_date_safe function"""

    def test_parse_date_object(self):
        """Should return the same date object"""
        input_date = date(2024, 1, 15)
        result = parse_date_safe(input_date)
        assert result == input_date

    def test_parse_datetime_object(self):
        """Should extract date from datetime"""
        input_datetime = datetime(2024, 1, 15, 10, 30, 45)
        result = parse_date_safe(input_datetime)
        assert result == date(2024, 1, 15)

    def test_parse_iso_string(self):
        """Should parse ISO format date string"""
        result = parse_date_safe("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_parse_slash_format(self):
        """Should parse dd/mm/yyyy format"""
        result = parse_date_safe("15/01/2024")
        assert result == date(2024, 1, 15)

    def test_parse_dot_format(self):
        """Should parse dd.mm.yyyy format"""
        result = parse_date_safe("15.01.2024")
        assert result == date(2024, 1, 15)

    def test_parse_none(self):
        """Should return None for None input"""
        result = parse_date_safe(None)
        assert result is None

    def test_parse_empty_string(self):
        """Should return None for empty string"""
        result = parse_date_safe("")
        assert result is None

    def test_parse_invalid_string(self):
        """Should return default value for invalid string"""
        default = date(2000, 1, 1)
        result = parse_date_safe("invalid", default=default)
        assert result == default

    def test_parse_with_custom_default(self):
        """Should use custom default for unparseable input"""
        custom_default = date(1999, 12, 31)
        result = parse_date_safe("not-a-date", default=custom_default)
        assert result == custom_default


class TestParseDatetimeSafe:
    """Tests for parse_datetime_safe function"""

    def test_parse_datetime_object(self):
        """Should return the same datetime object"""
        input_dt = datetime(2024, 1, 15, 10, 30, 45)
        result = parse_datetime_safe(input_dt)
        assert result == input_dt

    def test_parse_date_object(self):
        """Should convert date to datetime"""
        input_date = date(2024, 1, 15)
        result = parse_datetime_safe(input_date)
        assert result == datetime(2024, 1, 15, 0, 0, 0)

    def test_parse_iso_string(self):
        """Should parse ISO format datetime string"""
        result = parse_datetime_safe("2024-01-15T10:30:45")
        assert result == datetime(2024, 1, 15, 10, 30, 45)

    def test_parse_date_string(self):
        """Should parse date-only string"""
        result = parse_datetime_safe("2024-01-15")
        assert result == datetime(2024, 1, 15, 0, 0, 0)

    def test_parse_none(self):
        """Should return None for None input"""
        result = parse_datetime_safe(None)
        assert result is None

    def test_parse_invalid(self):
        """Should return default for invalid input"""
        default = datetime(2000, 1, 1, 0, 0, 0)
        result = parse_datetime_safe("invalid", default=default)
        assert result == default


class TestFormatDateDisplay:
    """Tests for format_date_display function"""

    def test_format_date_object(self):
        """Should format date object"""
        input_date = date(2024, 1, 15)
        result = format_date_display(input_date)
        assert result == "15/01/2024"

    def test_format_datetime_object(self):
        """Should format datetime object (date part only)"""
        input_dt = datetime(2024, 1, 15, 10, 30, 45)
        result = format_date_display(input_dt)
        assert result == "15/01/2024"

    def test_format_custom_format(self):
        """Should use custom format string"""
        input_date = date(2024, 1, 15)
        result = format_date_display(input_date, format_str="%Y-%m-%d")
        assert result == "2024-01-15"

    def test_format_none(self):
        """Should return empty string for None"""
        result = format_date_display(None)
        assert result == ""

    def test_format_invalid(self):
        """Should return empty string for invalid input"""
        result = format_date_display("not-a-date")
        assert result == ""


class TestFormatDateIso:
    """Tests for format_date_iso function"""

    def test_format_date_object(self):
        """Should format date in ISO format"""
        input_date = date(2024, 1, 15)
        result = format_date_iso(input_date)
        assert result == "2024-01-15"

    def test_format_datetime_object(self):
        """Should format datetime in ISO format"""
        input_dt = datetime(2024, 1, 15, 10, 30, 45)
        result = format_date_iso(input_dt)
        assert result == "2024-01-15"

    def test_format_none(self):
        """Should return None for None input"""
        result = format_date_iso(None)
        assert result is None


class TestIsDateExpired:
    """Tests for is_date_expired function"""

    def test_expired_date(self):
        """Should return True for past date"""
        past_date = date.today() - timedelta(days=10)
        assert is_date_expired(past_date) is True

    def test_future_date(self):
        """Should return False for future date"""
        future_date = date.today() + timedelta(days=10)
        assert is_date_expired(future_date) is False

    def test_today(self):
        """Should return False for today"""
        assert is_date_expired(date.today()) is False

    def test_with_reference_date(self):
        """Should compare against custom reference date"""
        expiry = date(2024, 1, 15)
        reference = date(2024, 1, 20)
        assert is_date_expired(expiry, reference) is True

    def test_none_input(self):
        """Should return False for None input"""
        assert is_date_expired(None) is False


class TestIsDateInRange:
    """Tests for is_date_in_range function"""

    def test_date_within_range(self):
        """Should return True when date is within range"""
        check_date = date(2024, 1, 15)
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        assert is_date_in_range(check_date, start, end) is True

    def test_date_on_start(self):
        """Should return True when date equals start"""
        check_date = date(2024, 1, 1)
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        assert is_date_in_range(check_date, start, end) is True

    def test_date_on_end(self):
        """Should return True when date equals end"""
        check_date = date(2024, 1, 31)
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        assert is_date_in_range(check_date, start, end) is True

    def test_date_before_range(self):
        """Should return False when date is before start"""
        check_date = date(2023, 12, 31)
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        assert is_date_in_range(check_date, start, end) is False

    def test_date_after_range(self):
        """Should return False when date is after end"""
        check_date = date(2024, 2, 1)
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        assert is_date_in_range(check_date, start, end) is False

    def test_none_start(self):
        """Should handle None start date"""
        check_date = date(2024, 1, 15)
        end = date(2024, 1, 31)
        assert is_date_in_range(check_date, None, end) is True

    def test_none_end(self):
        """Should handle None end date"""
        check_date = date(2024, 1, 15)
        start = date(2024, 1, 1)
        assert is_date_in_range(check_date, start, None) is True


class TestDateRangeOverlaps:
    """Tests for date_range_overlaps function"""

    def test_ranges_overlap_middle(self):
        """Should detect overlap when ranges intersect"""
        start1 = date(2024, 1, 1)
        end1 = date(2024, 1, 20)
        start2 = date(2024, 1, 15)
        end2 = date(2024, 1, 31)
        assert date_range_overlaps(start1, end1, start2, end2) is True

    def test_ranges_overlap_complete(self):
        """Should detect when one range contains another"""
        start1 = date(2024, 1, 1)
        end1 = date(2024, 1, 31)
        start2 = date(2024, 1, 10)
        end2 = date(2024, 1, 20)
        assert date_range_overlaps(start1, end1, start2, end2) is True

    def test_ranges_touch_at_boundary(self):
        """Should detect touch at boundary as overlap"""
        start1 = date(2024, 1, 1)
        end1 = date(2024, 1, 15)
        start2 = date(2024, 1, 15)
        end2 = date(2024, 1, 31)
        assert date_range_overlaps(start1, end1, start2, end2) is True

    def test_ranges_no_overlap(self):
        """Should return False when ranges don't overlap"""
        start1 = date(2024, 1, 1)
        end1 = date(2024, 1, 15)
        start2 = date(2024, 1, 20)
        end2 = date(2024, 1, 31)
        assert date_range_overlaps(start1, end1, start2, end2) is False

    def test_ranges_adjacent(self):
        """Should return False when ranges are adjacent"""
        start1 = date(2024, 1, 1)
        end1 = date(2024, 1, 14)
        start2 = date(2024, 1, 15)
        end2 = date(2024, 1, 31)
        assert date_range_overlaps(start1, end1, start2, end2) is False


class TestDaysBetween:
    """Tests for days_between function"""

    def test_positive_difference(self):
        """Should return positive days for future date"""
        start = date(2024, 1, 1)
        end = date(2024, 1, 11)
        assert days_between(start, end) == 10

    def test_negative_difference(self):
        """Should return negative days for past date"""
        start = date(2024, 1, 11)
        end = date(2024, 1, 1)
        assert days_between(start, end) == -10

    def test_same_date(self):
        """Should return 0 for same date"""
        same_date = date(2024, 1, 1)
        assert days_between(same_date, same_date) == 0

    def test_absolute_difference(self):
        """Should return absolute difference when requested"""
        start = date(2024, 1, 11)
        end = date(2024, 1, 1)
        assert days_between(start, end, absolute=True) == 10


class TestAddBusinessDays:
    """Tests for add_business_days function"""

    def test_add_business_days_weekdays(self):
        """Should add business days skipping weekends"""
        start = date(2024, 1, 1)  # Monday
        result = add_business_days(start, 5)
        assert result == date(2024, 1, 8)  # Monday next week (skips weekend)

    def test_add_zero_days(self):
        """Should return same date for zero days"""
        start = date(2024, 1, 1)
        result = add_business_days(start, 0)
        assert result == start

    def test_add_negative_days(self):
        """Should subtract business days"""
        start = date(2024, 1, 8)  # Monday
        result = add_business_days(start, -5)
        assert result == date(2024, 1, 1)  # Previous Monday

    def test_start_on_weekend(self):
        """Should handle starting on weekend"""
        start = date(2024, 1, 6)  # Saturday
        result = add_business_days(start, 1)
        assert result.weekday() < 5  # Should land on weekday


class TestGetFinancialYear:
    """Tests for get_financial_year function"""

    def test_first_quarter(self):
        """Should return correct FY for Q1"""
        input_date = date(2024, 5, 15)  # May
        result = get_financial_year(input_date)
        assert result == "2024-25"

    def test_last_quarter(self):
        """Should return correct FY for Q4"""
        input_date = date(2024, 2, 15)  # February
        result = get_financial_year(input_date)
        assert result == "2023-24"

    def test_april_start(self):
        """Should handle April (FY start)"""
        input_date = date(2024, 4, 1)
        result = get_financial_year(input_date)
        assert result == "2024-25"

    def test_march_end(self):
        """Should handle March (FY end)"""
        input_date = date(2024, 3, 31)
        result = get_financial_year(input_date)
        assert result == "2023-24"


class TestGetQuarter:
    """Tests for get_quarter function"""

    def test_q1_months(self):
        """Should return Q1 for Apr-Jun"""
        assert get_quarter(date(2024, 4, 15)) == 1
        assert get_quarter(date(2024, 5, 15)) == 1
        assert get_quarter(date(2024, 6, 15)) == 1

    def test_q2_months(self):
        """Should return Q2 for Jul-Sep"""
        assert get_quarter(date(2024, 7, 15)) == 2
        assert get_quarter(date(2024, 8, 15)) == 2
        assert get_quarter(date(2024, 9, 15)) == 2

    def test_q3_months(self):
        """Should return Q3 for Oct-Dec"""
        assert get_quarter(date(2024, 10, 15)) == 3
        assert get_quarter(date(2024, 11, 15)) == 3
        assert get_quarter(date(2024, 12, 15)) == 3

    def test_q4_months(self):
        """Should return Q4 for Jan-Mar"""
        assert get_quarter(date(2024, 1, 15)) == 4
        assert get_quarter(date(2024, 2, 15)) == 4
        assert get_quarter(date(2024, 3, 15)) == 4


class TestIsWeekend:
    """Tests for is_weekend function"""

    def test_saturday(self):
        """Should return True for Saturday"""
        saturday = date(2024, 1, 6)  # Saturday
        assert is_weekend(saturday) is True

    def test_sunday(self):
        """Should return True for Sunday"""
        sunday = date(2024, 1, 7)  # Sunday
        assert is_weekend(sunday) is True

    def test_weekday(self):
        """Should return False for weekday"""
        monday = date(2024, 1, 1)  # Monday
        assert is_weekend(monday) is False

    def test_friday(self):
        """Should return False for Friday"""
        friday = date(2024, 1, 5)  # Friday
        assert is_weekend(friday) is False


class TestEdgeCases:
    """Edge case tests for date_utils"""

    def test_leap_year_handling(self):
        """Should handle leap year dates"""
        leap_date = date(2024, 2, 29)
        result = parse_date_safe("2024-02-29")
        assert result == leap_date

    def test_year_boundary(self):
        """Should handle year boundaries"""
        dec_31 = date(2023, 12, 31)
        jan_1 = date(2024, 1, 1)
        assert days_between(dec_31, jan_1) == 1

    def test_century_dates(self):
        """Should handle dates across centuries"""
        old_date = date(1999, 12, 31)
        new_date = date(2000, 1, 1)
        assert days_between(old_date, new_date) == 1

    def test_very_large_day_difference(self):
        """Should handle large date differences"""
        start = date(2000, 1, 1)
        end = date(2024, 1, 1)
        days = days_between(start, end)
        assert days > 8000  # More than 24 years

    def test_datetime_with_timezone_awareness(self):
        """Should handle datetime objects (timezone-naive)"""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = parse_date_safe(dt)
        assert result == date(2024, 1, 15)
