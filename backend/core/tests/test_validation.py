"""
Unit tests for core.utils.validation module
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from core.utils.validation import (
    validate_positive_decimal,
    validate_non_negative_decimal,
    validate_date_range,
    validate_required_fields,
    validate_choice,
    validate_unique_items,
    is_valid_email,
    is_valid_phone,
    sanitize_string,
    validate_file_extension,
)


class TestValidatePositiveDecimal:
    """Tests for validate_positive_decimal function"""

    def test_positive_decimal(self):
        """Should accept positive decimal"""
        result = validate_positive_decimal(Decimal("10.50"), "amount")
        assert result == Decimal("10.50")

    def test_positive_integer(self):
        """Should accept positive integer"""
        result = validate_positive_decimal(5, "quantity")
        assert result == Decimal("5")

    def test_positive_float(self):
        """Should accept positive float"""
        result = validate_positive_decimal(3.14, "value")
        assert result == Decimal("3.14")

    def test_zero_not_allowed_by_default(self):
        """Should reject zero by default"""
        with pytest.raises(ValidationError) as exc_info:
            validate_positive_decimal(0, "amount")
        assert "must be positive" in str(exc_info.value)

    def test_zero_allowed_when_specified(self):
        """Should accept zero when allow_zero=True"""
        result = validate_positive_decimal(0, "amount", allow_zero=True)
        assert result == Decimal("0")

    def test_negative_value(self):
        """Should reject negative value"""
        with pytest.raises(ValidationError) as exc_info:
            validate_positive_decimal(-5, "amount")
        assert "must be positive" in str(exc_info.value)

    def test_none_value(self):
        """Should reject None"""
        with pytest.raises(ValidationError) as exc_info:
            validate_positive_decimal(None, "amount")
        assert "required" in str(exc_info.value).lower()

    def test_invalid_string(self):
        """Should reject non-numeric string"""
        with pytest.raises(ValidationError) as exc_info:
            validate_positive_decimal("not-a-number", "amount")
        assert "must be a valid number" in str(exc_info.value)

    def test_custom_field_name_in_error(self):
        """Should include field name in error message"""
        with pytest.raises(ValidationError) as exc_info:
            validate_positive_decimal(-1, "total_price")
        assert "total_price" in str(exc_info.value)


class TestValidateNonNegativeDecimal:
    """Tests for validate_non_negative_decimal function"""

    def test_positive_value(self):
        """Should accept positive value"""
        result = validate_non_negative_decimal(Decimal("10.50"), "balance")
        assert result == Decimal("10.50")

    def test_zero_value(self):
        """Should accept zero"""
        result = validate_non_negative_decimal(0, "balance")
        assert result == Decimal("0")

    def test_negative_value(self):
        """Should reject negative value"""
        with pytest.raises(ValidationError) as exc_info:
            validate_non_negative_decimal(-5, "balance")
        assert "cannot be negative" in str(exc_info.value)

    def test_very_small_positive(self):
        """Should accept very small positive values"""
        result = validate_non_negative_decimal(Decimal("0.0001"), "amount")
        assert result == Decimal("0.0001")


class TestValidateDateRange:
    """Tests for validate_date_range function"""

    def test_valid_date_range(self):
        """Should accept valid date range"""
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        result_start, result_end = validate_date_range(start, end)
        assert result_start == start
        assert result_end == end

    def test_same_start_and_end(self):
        """Should accept same start and end date"""
        same_date = date(2024, 1, 1)
        result_start, result_end = validate_date_range(same_date, same_date)
        assert result_start == same_date
        assert result_end == same_date

    def test_end_before_start(self):
        """Should reject end date before start date"""
        start = date(2024, 12, 31)
        end = date(2024, 1, 1)
        with pytest.raises(ValidationError) as exc_info:
            validate_date_range(start, end)
        assert "cannot be before" in str(exc_info.value)

    def test_none_start_date(self):
        """Should reject None start date"""
        with pytest.raises(ValidationError) as exc_info:
            validate_date_range(None, date(2024, 12, 31))
        assert "required" in str(exc_info.value).lower()

    def test_none_end_date(self):
        """Should reject None end date"""
        with pytest.raises(ValidationError) as exc_info:
            validate_date_range(date(2024, 1, 1), None)
        assert "required" in str(exc_info.value).lower()

    def test_custom_field_prefix(self):
        """Should use custom field prefix in error messages"""
        start = date(2024, 12, 31)
        end = date(2024, 1, 1)
        with pytest.raises(ValidationError) as exc_info:
            validate_date_range(start, end, field_prefix="license_")
        assert "license_" in str(exc_info.value)

    def test_string_date_conversion(self):
        """Should parse string dates"""
        result_start, result_end = validate_date_range("2024-01-01", "2024-12-31")
        assert result_start == date(2024, 1, 1)
        assert result_end == date(2024, 12, 31)


class TestValidateRequiredFields:
    """Tests for validate_required_fields function"""

    def test_all_fields_present(self):
        """Should pass when all required fields present"""
        data = {"name": "Test", "email": "test@example.com", "age": 25}
        required = ["name", "email", "age"]
        # Should not raise exception
        validate_required_fields(data, required)

    def test_missing_single_field(self):
        """Should raise error for missing field"""
        data = {"name": "Test", "age": 25}
        required = ["name", "email", "age"]
        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(data, required)
        assert "email" in str(exc_info.value)

    def test_missing_multiple_fields(self):
        """Should list all missing fields"""
        data = {"name": "Test"}
        required = ["name", "email", "age", "phone"]
        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(data, required)
        error_msg = str(exc_info.value)
        assert "email" in error_msg
        assert "age" in error_msg
        assert "phone" in error_msg

    def test_empty_string_value(self):
        """Should treat empty string as missing"""
        data = {"name": "", "email": "test@example.com"}
        required = ["name", "email"]
        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(data, required)
        assert "name" in str(exc_info.value)

    def test_none_value(self):
        """Should treat None as missing"""
        data = {"name": None, "email": "test@example.com"}
        required = ["name", "email"]
        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(data, required)
        assert "name" in str(exc_info.value)

    def test_whitespace_only_value(self):
        """Should treat whitespace-only as missing"""
        data = {"name": "   ", "email": "test@example.com"}
        required = ["name", "email"]
        with pytest.raises(ValidationError) as exc_info:
            validate_required_fields(data, required)
        assert "name" in str(exc_info.value)

    def test_zero_is_valid(self):
        """Should accept zero as valid value"""
        data = {"quantity": 0, "price": 100}
        required = ["quantity", "price"]
        # Should not raise exception
        validate_required_fields(data, required)

    def test_false_is_valid(self):
        """Should accept False as valid value"""
        data = {"is_active": False, "name": "Test"}
        required = ["is_active", "name"]
        # Should not raise exception
        validate_required_fields(data, required)


class TestValidateChoice:
    """Tests for validate_choice function"""

    def test_valid_choice(self):
        """Should accept valid choice"""
        choices = ["active", "inactive", "pending"]
        result = validate_choice("active", choices, "status")
        assert result == "active"

    def test_invalid_choice(self):
        """Should reject invalid choice"""
        choices = ["active", "inactive", "pending"]
        with pytest.raises(ValidationError) as exc_info:
            validate_choice("deleted", choices, "status")
        assert "must be one of" in str(exc_info.value)

    def test_case_sensitive_by_default(self):
        """Should be case-sensitive by default"""
        choices = ["Active", "Inactive"]
        with pytest.raises(ValidationError):
            validate_choice("active", choices, "status")

    def test_case_insensitive_when_specified(self):
        """Should ignore case when case_sensitive=False"""
        choices = ["Active", "Inactive"]
        result = validate_choice("active", choices, "status", case_sensitive=False)
        assert result.lower() == "active"

    def test_numeric_choices(self):
        """Should handle numeric choices"""
        choices = [1, 2, 3]
        result = validate_choice(2, choices, "level")
        assert result == 2

    def test_none_value(self):
        """Should reject None value"""
        choices = ["active", "inactive"]
        with pytest.raises(ValidationError) as exc_info:
            validate_choice(None, choices, "status")
        assert "required" in str(exc_info.value).lower()


class TestValidateUniqueItems:
    """Tests for validate_unique_items function"""

    def test_unique_list(self):
        """Should pass for unique items"""
        items = [1, 2, 3, 4, 5]
        # Should not raise exception
        validate_unique_items(items, "id")

    def test_duplicate_items(self):
        """Should reject duplicate items"""
        items = [1, 2, 3, 2, 4]
        with pytest.raises(ValidationError) as exc_info:
            validate_unique_items(items, "id")
        assert "duplicate" in str(exc_info.value).lower()

    def test_string_items(self):
        """Should work with string items"""
        items = ["apple", "banana", "cherry"]
        # Should not raise exception
        validate_unique_items(items, "fruit")

    def test_duplicate_strings(self):
        """Should detect duplicate strings"""
        items = ["apple", "banana", "apple"]
        with pytest.raises(ValidationError):
            validate_unique_items(items, "fruit")

    def test_empty_list(self):
        """Should pass for empty list"""
        items = []
        # Should not raise exception
        validate_unique_items(items, "items")

    def test_single_item(self):
        """Should pass for single item"""
        items = [42]
        # Should not raise exception
        validate_unique_items(items, "number")

    def test_case_sensitive_strings(self):
        """Should treat different cases as different items"""
        items = ["Apple", "apple", "APPLE"]
        # Should not raise exception (different cases)
        validate_unique_items(items, "fruit")


class TestIsValidEmail:
    """Tests for is_valid_email function"""

    def test_valid_email(self):
        """Should accept valid email"""
        assert is_valid_email("user@example.com") is True

    def test_valid_email_with_subdomain(self):
        """Should accept email with subdomain"""
        assert is_valid_email("user@mail.example.com") is True

    def test_valid_email_with_plus(self):
        """Should accept email with plus sign"""
        assert is_valid_email("user+tag@example.com") is True

    def test_valid_email_with_dots(self):
        """Should accept email with dots in username"""
        assert is_valid_email("first.last@example.com") is True

    def test_invalid_email_no_at(self):
        """Should reject email without @"""
        assert is_valid_email("userexample.com") is False

    def test_invalid_email_no_domain(self):
        """Should reject email without domain"""
        assert is_valid_email("user@") is False

    def test_invalid_email_no_username(self):
        """Should reject email without username"""
        assert is_valid_email("@example.com") is False

    def test_invalid_email_spaces(self):
        """Should reject email with spaces"""
        assert is_valid_email("user @example.com") is False

    def test_empty_string(self):
        """Should reject empty string"""
        assert is_valid_email("") is False

    def test_none_value(self):
        """Should reject None"""
        assert is_valid_email(None) is False


class TestIsValidPhone:
    """Tests for is_valid_phone function"""

    def test_valid_10_digit_phone(self):
        """Should accept 10-digit phone"""
        assert is_valid_phone("9876543210") is True

    def test_valid_phone_with_country_code(self):
        """Should accept phone with +91"""
        assert is_valid_phone("+919876543210") is True

    def test_valid_phone_with_spaces(self):
        """Should accept phone with spaces"""
        assert is_valid_phone("987 654 3210") is True

    def test_valid_phone_with_dashes(self):
        """Should accept phone with dashes"""
        assert is_valid_phone("987-654-3210") is True

    def test_valid_phone_with_parentheses(self):
        """Should accept phone with parentheses"""
        assert is_valid_phone("(987) 654-3210") is True

    def test_invalid_too_short(self):
        """Should reject too short phone"""
        assert is_valid_phone("12345") is False

    def test_invalid_too_long(self):
        """Should reject too long phone"""
        assert is_valid_phone("123456789012345678") is False

    def test_invalid_letters(self):
        """Should reject phone with letters"""
        assert is_valid_phone("98765abc10") is False

    def test_empty_string(self):
        """Should reject empty string"""
        assert is_valid_phone("") is False

    def test_none_value(self):
        """Should reject None"""
        assert is_valid_phone(None) is False


class TestSanitizeString:
    """Tests for sanitize_string function"""

    def test_normal_string(self):
        """Should return normal string unchanged"""
        result = sanitize_string("Hello World")
        assert result == "Hello World"

    def test_strip_whitespace(self):
        """Should strip leading/trailing whitespace"""
        result = sanitize_string("  Hello World  ")
        assert result == "Hello World"

    def test_remove_special_chars(self):
        """Should remove special characters when specified"""
        result = sanitize_string("Hello@#World!", remove_special=True)
        assert result == "HelloWorld"

    def test_preserve_alphanumeric_and_space(self):
        """Should preserve alphanumeric and spaces"""
        result = sanitize_string("Test 123", remove_special=True)
        assert result == "Test 123"

    def test_lowercase_conversion(self):
        """Should convert to lowercase when specified"""
        result = sanitize_string("Hello World", lowercase=True)
        assert result == "hello world"

    def test_uppercase_conversion(self):
        """Should convert to uppercase when specified"""
        result = sanitize_string("Hello World", uppercase=True)
        assert result == "HELLO WORLD"

    def test_max_length_truncation(self):
        """Should truncate to max length"""
        result = sanitize_string("Hello World", max_length=5)
        assert result == "Hello"

    def test_empty_string(self):
        """Should handle empty string"""
        result = sanitize_string("")
        assert result == ""

    def test_none_value(self):
        """Should return empty string for None"""
        result = sanitize_string(None)
        assert result == ""

    def test_combined_options(self):
        """Should apply multiple sanitization options"""
        result = sanitize_string(
            "  Hello@World!  ",
            remove_special=True,
            lowercase=True,
            max_length=10
        )
        assert result == "helloworld"


class TestValidateFileExtension:
    """Tests for validate_file_extension function"""

    def test_valid_extension(self):
        """Should accept valid extension"""
        allowed = [".pdf", ".jpg", ".png"]
        # Should not raise exception
        validate_file_extension("document.pdf", allowed)

    def test_valid_extension_case_insensitive(self):
        """Should accept extension with different case"""
        allowed = [".pdf", ".jpg", ".png"]
        # Should not raise exception
        validate_file_extension("document.PDF", allowed)

    def test_invalid_extension(self):
        """Should reject invalid extension"""
        allowed = [".pdf", ".jpg", ".png"]
        with pytest.raises(ValidationError) as exc_info:
            validate_file_extension("document.txt", allowed)
        assert "allowed extensions" in str(exc_info.value).lower()

    def test_no_extension(self):
        """Should reject filename without extension"""
        allowed = [".pdf", ".jpg"]
        with pytest.raises(ValidationError):
            validate_file_extension("document", allowed)

    def test_multiple_dots_in_filename(self):
        """Should handle filename with multiple dots"""
        allowed = [".pdf", ".tar.gz"]
        # Should not raise exception
        validate_file_extension("archive.tar.gz", allowed)

    def test_extension_without_dot_in_allowed(self):
        """Should handle allowed extensions without dot"""
        allowed = ["pdf", "jpg", "png"]
        # Should not raise exception
        validate_file_extension("document.pdf", allowed)

    def test_path_with_directories(self):
        """Should handle full file path"""
        allowed = [".pdf"]
        # Should not raise exception
        validate_file_extension("/path/to/document.pdf", allowed)


class TestEdgeCases:
    """Edge case tests for validation functions"""

    def test_very_large_decimal(self):
        """Should handle very large decimal values"""
        large_value = Decimal("999999999999.99")
        result = validate_positive_decimal(large_value, "amount")
        assert result == large_value

    def test_very_small_decimal(self):
        """Should handle very small decimal values"""
        small_value = Decimal("0.00000001")
        result = validate_positive_decimal(small_value, "amount")
        assert result == small_value

    def test_date_range_spanning_years(self):
        """Should handle date ranges spanning multiple years"""
        start = date(2020, 1, 1)
        end = date(2024, 12, 31)
        result_start, result_end = validate_date_range(start, end)
        assert result_start == start
        assert result_end == end

    def test_unicode_in_string_sanitization(self):
        """Should handle unicode characters"""
        result = sanitize_string("Hello 世界")
        assert "Hello" in result

    def test_validation_with_empty_choices(self):
        """Should handle empty choices list"""
        with pytest.raises(ValidationError):
            validate_choice("any", [], "field")

    def test_required_fields_with_dict_values(self):
        """Should handle complex data types as values"""
        data = {"name": "Test", "metadata": {"key": "value"}}
        required = ["name", "metadata"]
        # Should not raise exception
        validate_required_fields(data, required)
