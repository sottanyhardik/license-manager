"""Generic output item resolution for SION planning rules.

Auto-creates missing ItemNameModel records when:
1. A planning rule matches a source item
2. No output_item is configured on the rule
3. No canonical ItemNameModel exists for the output name

This enables generic rule-based planning without requiring manual
item master setup before execution.

Design:
- Resolves at execution time, not at preview time
- Uses get_or_create for concurrency safety
- Normalizes names to prevent duplicates
- Links resolved item to the rule for future runs
- Works for standard and split allocations
"""
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.models import ItemNameModel
from apps.license.models import SionPlanningRule


class OutputItemNotFoundError(ValueError):
    """Output item cannot be resolved or created."""
    pass


class OutputItemResolver:
    """Resolve or auto-create ItemNameModel for planning rules."""

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize item name for matching and creation.

        Removes leading/trailing whitespace, collapses internal whitespace,
        and uses the application's canonical name form.
        """
        if not name:
            raise OutputItemNotFoundError("Item name cannot be empty")
        return " ".join(str(name).split()).strip()

    @staticmethod
    def get_canonical_output_name(rule: SionPlanningRule) -> str:
        """Determine the canonical output name for a rule.

        Authority order:
        1. rule.execution_output (if set and non-empty)
        2. rule.name (fallback)
        """
        if rule.execution_output and rule.execution_output.strip():
            return OutputItemResolver.normalize_name(rule.execution_output)
        return OutputItemResolver.normalize_name(rule.name)

    @staticmethod
    def resolve_or_create(rule: SionPlanningRule) -> ItemNameModel:
        """Resolve or auto-create ItemNameModel for a planning rule.

        Args:
            rule: Active SionPlanningRule that matched a source item

        Returns:
            Associated ItemNameModel (either existing or newly created)

        Raises:
            OutputItemNotFoundError: If item cannot be resolved or created
        """
        # If already linked, return immediately
        if rule.import_item_id:
            return rule.import_item

        canonical_name = OutputItemResolver.get_canonical_output_name(rule)

        # Try to find existing ItemNameModel with exact match
        existing = ItemNameModel.objects.filter(
            name=canonical_name,
            sion_norm_class=rule.sion,
        ).first()

        if existing:
            # Found exact match - link and return
            with transaction.atomic():
                rule.import_item = existing
                rule.save(update_fields=["import_item"])
            return existing

        # Not found - create new item with atomic get_or_create
        # Using the unique constraint on 'name' as our safety mechanism
        with transaction.atomic():
            try:
                item, created = ItemNameModel.objects.get_or_create(
                    name=canonical_name,
                    defaults={
                        "sion_norm_class": rule.sion,
                        "is_active": True,
                        "restriction_percentage": 0,
                    },
                )
                # Link the rule to the item
                rule.import_item = item
                rule.save(update_fields=["import_item"])
                return item
            except Exception as e:
                raise OutputItemNotFoundError(
                    f"Failed to resolve/create ItemNameModel for rule {rule.pk} "
                    f"({rule.name}): {e}"
                ) from e

    @staticmethod
    def resolve_for_split_output(
        rule: SionPlanningRule, output_name: str
    ) -> ItemNameModel:
        """Resolve or auto-create ItemNameModel for split allocation outputs.

        Used when a split action creates multiple allocation categories
        from a single rule match.

        Args:
            rule: The matching SionPlanningRule
            output_name: Explicit output name from split config (e.g., "DWP", "SWP")

        Returns:
            Associated ItemNameModel
        """
        canonical_name = OutputItemResolver.normalize_name(output_name)

        # Try to find existing item
        existing = ItemNameModel.objects.filter(
            name=canonical_name,
            sion_norm_class=rule.sion,
        ).first()

        if existing:
            return existing

        # Create new item for split output
        with transaction.atomic():
            try:
                item, created = ItemNameModel.objects.get_or_create(
                    name=canonical_name,
                    defaults={
                        "sion_norm_class": rule.sion,
                        "is_active": True,
                        "restriction_percentage": 0,
                    },
                )
                return item
            except Exception as e:
                raise OutputItemNotFoundError(
                    f"Failed to create split output ItemNameModel "
                    f"for rule {rule.pk}, output '{output_name}': {e}"
                ) from e
