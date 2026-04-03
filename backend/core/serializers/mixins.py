"""
Serializer mixins for common functionality.

This module provides reusable mixins for DRF serializers including:
- FormDataParserMixin: Handle multipart/form-data nested array parsing
- NestedObjectNormalizerMixin: Extract IDs from nested objects
- EmptyStringNormalizerMixin: Convert empty strings to None/Zero
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional

from rest_framework import serializers

logger = logging.getLogger(__name__)


class FormDataParserMixin:
    """
    Mixin to parse nested arrays from multipart/form-data.

    Handles both JSON string format and flattened FormData format for nested arrays.
    Supports patterns like:
    - lines[0].field_name (dot notation)
    - lines[0][field_name] (bracket notation)

    Usage:
        class MySerializer(FormDataParserMixin, serializers.ModelSerializer):
            lines = NestedSerializer(many=True)
            payments = PaymentSerializer(many=True)

            class Meta:
                model = MyModel
                fields = '__all__'

            # Specify which fields contain nested arrays
            nested_array_fields = ['lines', 'payments']
    """

    # Override in subclass to specify which fields are nested arrays
    nested_array_fields: List[str] = []

    def to_internal_value(self, data):
        """Parse JSON strings OR flattened FormData from multipart/form-data"""
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "%s.to_internal_value called. Data keys: %s",
                self.__class__.__name__,
                list(data.keys()) if hasattr(data, 'keys') else 'N/A'
            )

        # Create a mutable copy of the data
        # For QueryDict, convert to a plain dict to avoid string-coercion on assignment
        raw_data = data
        if hasattr(data, 'getlist'):
            data = {key: raw_data.get(key) for key in raw_data.keys()}
        else:
            data = data.copy() if hasattr(data, 'copy') else dict(data)

        # Get nested fields to parse
        nested_fields = self.nested_array_fields or []

        # Handle both JSON string format AND flattened FormData format
        for field in nested_fields:
            if field in data:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Field '%s' found. Type: %s",
                        field,
                        type(data[field]).__name__
                    )

                # Format 1: JSON string (from forms with JSON.stringify)
                if isinstance(data[field], str):
                    try:
                        parsed = json.loads(data[field])
                        data[field] = parsed
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(
                                "Parsed %s from JSON string: %d items",
                                field,
                                len(parsed) if isinstance(parsed, list) else 0
                            )
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.error("Failed to parse %s as JSON: %s", field, str(e))
                        raise serializers.ValidationError({
                            field: f"Invalid JSON format: {str(e)}"
                        })
                elif logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "%s already parsed as %s",
                        field,
                        type(data[field]).__name__
                    )
            elif logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "Field '%s' NOT in data - checking for flattened format",
                    field
                )

        # Format 2: Flattened FormData format (from MasterForm)
        # Check if data has flattened keys like "lines[0].field" or "lines[0][field]"
        if hasattr(raw_data, 'keys'):
            nested_items = {field_name: {} for field_name in nested_fields}

            for key in list(raw_data.keys()):
                for field_name in nested_fields:
                    # Match patterns like:
                    # - "lines[0].sr_number" (dot notation)
                    # - "lines[0][sr_number]" (bracket notation)
                    # - "lines[0].nested.field" (nested dot notation)
                    match = re.match(rf'{field_name}\[(\d+)\][\.\[](.+?)[\]\.]?$', key)
                    if match:
                        index = int(match.group(1))
                        sub_field = match.group(2).replace(']', '').replace('[', '.')

                        if index not in nested_items[field_name]:
                            nested_items[field_name][index] = {}

                        nested_items[field_name][index][sub_field] = raw_data[key]
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(
                                "Found flattened field: %s -> %s[%d].%s",
                                key,
                                field_name,
                                index,
                                sub_field
                            )

            # Convert flattened format to list format
            for field_name, items in nested_items.items():
                if items:
                    data[field_name] = [items[i] for i in sorted(items.keys())]
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            "Reconstructed %s from flattened format: %d items",
                            field_name,
                            len(data[field_name])
                        )

        return super().to_internal_value(data)


class NestedObjectNormalizerMixin:
    """
    Mixin to extract IDs from nested objects in serializer data.

    Handles cases where frontend sends full objects instead of just IDs.
    For example: {'sr_number': {'id': 5, 'name': 'foo'}} -> {'sr_number': 5}

    Usage:
        class MyLineSerializer(NestedObjectNormalizerMixin, serializers.ModelSerializer):
            class Meta:
                model = MyLine
                fields = '__all__'

            # Specify which fields should extract IDs from objects
            nested_object_fields = ['sr_number', 'company', 'port']
    """

    # Override in subclass to specify which fields are nested objects
    nested_object_fields: List[str] = []

    def to_internal_value(self, data):
        """Extract IDs from nested objects"""
        # Create a copy to avoid modifying the original data
        data = data.copy() if hasattr(data, 'copy') else dict(data)

        # Get fields to normalize
        object_fields = self.nested_object_fields or []

        for field_name in object_fields:
            if field_name in data and isinstance(data[field_name], dict):
                # Extract ID from object (try 'id' first, then 'pk')
                obj_id = data[field_name].get('id') or data[field_name].get('pk')
                if obj_id:
                    data[field_name] = obj_id
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            "Extracted ID %s from nested object %s",
                            obj_id,
                            field_name
                        )

        return super().to_internal_value(data)


class EmptyStringNormalizerMixin:
    """
    Mixin to normalize empty strings to None or Zero for numeric fields.

    Prevents empty strings from being coerced to 0 for numeric fields,
    which can cause unintended data overwrites during updates.

    Usage:
        class MySerializer(EmptyStringNormalizerMixin, serializers.ModelSerializer):
            class Meta:
                model = MyModel
                fields = '__all__'

            # Specify which numeric fields should have empty strings removed
            empty_to_none_fields = ['qty_kg', 'rate', 'amount']

            # Or specify which string fields should convert empty to None
            empty_string_to_none = ['description', 'remarks']
    """

    # Override in subclass - numeric fields where empty string should be removed
    empty_to_none_fields: List[str] = []

    # Override in subclass - string fields where empty string should become None
    empty_string_to_none: List[str] = []

    def to_internal_value(self, data):
        """Remove empty string fields to prevent overwriting with zeros"""
        # Create a copy to avoid modifying the original data
        data = data.copy() if hasattr(data, 'copy') else dict(data)

        # Remove empty strings from numeric fields
        for field in self.empty_to_none_fields:
            if field in data and data[field] == '':
                del data[field]
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Removed empty string for numeric field: %s",
                        field
                    )

        # Convert empty strings to None for string fields
        for field in self.empty_string_to_none:
            if field in data and data[field] == '':
                data[field] = None
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Converted empty string to None for field: %s",
                        field
                    )

        return super().to_internal_value(data)


class NestedValidationMixin:
    """
    Mixin to validate nested items with custom validators.

    Usage:
        class MySerializer(NestedValidationMixin, serializers.ModelSerializer):
            lines = LineSerializer(many=True)

            class Meta:
                model = MyModel
                fields = '__all__'

            def validate(self, data):
                data = super().validate(data)

                # Validate nested lines
                self.validate_nested_items(
                    data.get('lines', []),
                    field_name='lines',
                    min_items=1,
                    validators=[self.validate_line_amount]
                )

                return data

            def validate_line_amount(self, item, index):
                if item.get('amount', 0) < 0:
                    raise serializers.ValidationError(
                        f"Line {index + 1}: Amount cannot be negative"
                    )
    """

    def validate_nested_items(
        self,
        items: List[Dict[str, Any]],
        field_name: str = 'items',
        min_items: Optional[int] = None,
        max_items: Optional[int] = None,
        validators: Optional[List[callable]] = None
    ):
        """
        Validate nested items with custom validators.

        Args:
            items: List of item dictionaries
            field_name: Name of the nested field (for error messages)
            min_items: Minimum number of items required
            max_items: Maximum number of items allowed
            validators: List of validator functions that take (item, index) as args

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(items, list):
            raise serializers.ValidationError({
                field_name: "Must be a list"
            })

        # Validate item count
        if min_items is not None and len(items) < min_items:
            raise serializers.ValidationError({
                field_name: f"At least {min_items} item(s) required"
            })

        if max_items is not None and len(items) > max_items:
            raise serializers.ValidationError({
                field_name: f"At most {max_items} item(s) allowed"
            })

        # Run custom validators
        if validators:
            for idx, item in enumerate(items):
                for validator in validators:
                    try:
                        validator(item, idx)
                    except serializers.ValidationError as e:
                        # Re-raise with field context
                        raise serializers.ValidationError({
                            field_name: f"Item {idx + 1}: {str(e)}"
                        })
                    except Exception as e:
                        logger.error(
                            "Validator %s failed for %s[%d]: %s",
                            validator.__name__,
                            field_name,
                            idx,
                            str(e)
                        )
                        raise serializers.ValidationError({
                            field_name: f"Item {idx + 1}: Validation error"
                        })


# Combined mixin for common use case
class FormDataNestedMixin(
    FormDataParserMixin,
    NestedObjectNormalizerMixin,
    EmptyStringNormalizerMixin
):
    """
    Combined mixin for handling form data with nested arrays.

    Combines all common functionality:
    - Parse nested arrays from FormData/JSON
    - Extract IDs from nested objects
    - Normalize empty strings

    Usage:
        class MySerializer(FormDataNestedMixin, serializers.ModelSerializer):
            lines = LineSerializer(many=True)
            payments = PaymentSerializer(many=True)

            class Meta:
                model = MyModel
                fields = '__all__'

            # Configure nested parsing
            nested_array_fields = ['lines', 'payments']
            nested_object_fields = ['company', 'port']
            empty_to_none_fields = ['amount', 'qty']
    """
    pass
