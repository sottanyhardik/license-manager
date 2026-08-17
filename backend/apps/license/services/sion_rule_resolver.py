"""Generic SION rule resolution engine.

Resolves rules by output_item + SION combination instead of hardcoded norm codes.
Works for any SION norm with any number of inputs and any rule type.
"""
from decimal import Decimal
from typing import Dict, List, Optional, NamedTuple

from apps.core.models import SionNormClassModel, ItemNameModel
from apps.core.constants import DEC_0
from apps.license.models import SionPlanningRule, SionInputAliasConfig


class CanonicalInputMapping(NamedTuple):
    """Result of resolving a product name to a canonical input."""
    canonical_code: str
    normalized_alias: str
    is_mapped: bool


class RuleInfo(NamedTuple):
    """Information about a single rule."""
    rule: SionPlanningRule
    rule_type: str
    rule_group_id: Optional[str]
    canonical_input: str
    percentage: Optional[Decimal]
    quantity_cap: Optional[Decimal]


class SionRuleResolver:
    """Resolves SION rules generically for any norm and output item combination."""

    @staticmethod
    def normalize_product_name(raw_name: str | None) -> str:
        """Normalize a product name for alias lookup.

        Performs:
        - trim leading/trailing whitespace
        - collapse internal whitespace
        - uppercase

        Args:
            raw_name: Raw product name from BOE/Allotment/Planning

        Returns:
            Normalized name suitable for alias lookup
        """
        if not raw_name:
            return ""
        # Strip and normalize whitespace
        normalized = " ".join(raw_name.strip().split()).upper()
        return normalized

    @staticmethod
    def resolve_canonical_input(
        raw_name: str | None,
        sion: Optional[SionNormClassModel] = None,
        output_item: Optional[ItemNameModel] = None,
    ) -> CanonicalInputMapping:
        """Resolve a product name to its canonical input code.

        Uses hierarchical lookup:
        1. Output item + SION specific alias
        2. SION-specific alias
        3. Global alias
        4. Unmapped

        Args:
            raw_name: Raw product name
            sion: Optional SION norm to scope the lookup
            output_item: Optional output item to further scope the lookup

        Returns:
            CanonicalInputMapping with code, normalized name, and mapped flag
        """
        if not raw_name:
            return CanonicalInputMapping(
                canonical_code="UNMAPPED",
                normalized_alias="",
                is_mapped=False,
            )

        normalized = SionRuleResolver.normalize_product_name(raw_name)

        # Try hierarchical lookup: output_item+sion -> sion -> global
        queries = []
        if output_item and sion:
            queries.append(
                SionInputAliasConfig.objects.filter(
                    sion=sion,
                    output_item=output_item,
                    alias_normalized=normalized,
                    is_active=True,
                )
            )
        if sion:
            queries.append(
                SionInputAliasConfig.objects.filter(
                    sion=sion,
                    output_item=None,
                    alias_normalized=normalized,
                    is_active=True,
                )
            )
        # Global aliases
        queries.append(
            SionInputAliasConfig.objects.filter(
                sion=None,
                output_item=None,
                alias_normalized=normalized,
                is_active=True,
            )
        )

        for query in queries:
            alias = query.first()
            if alias:
                return CanonicalInputMapping(
                    canonical_code=alias.canonical_input_code,
                    normalized_alias=normalized,
                    is_mapped=True,
                )

        # Not found
        return CanonicalInputMapping(
            canonical_code="UNMAPPED",
            normalized_alias=normalized,
            is_mapped=False,
        )

    @staticmethod
    def get_rules_for_output_item(
        output_item: ItemNameModel,
        sion: SionNormClassModel,
    ) -> List[RuleInfo]:
        """Get all active rules for a specific output item within a SION.

        Returns rules scoped to (output_item, sion) combination, ordered by type and priority.

        Args:
            output_item: The output item being planned to
            sion: The SION norm

        Returns:
            List of RuleInfo objects, sorted by rule_type and priority
        """
        rules = SionPlanningRule.objects.filter(
            sion=sion,
            output_item=output_item,
            is_active=True,
        ).order_by("rule_type", "priority")

        result = []
        for rule in rules:
            info = RuleInfo(
                rule=rule,
                rule_type=rule.rule_type or "PERCENTAGE_CAP",
                rule_group_id=rule.rule_group_id,
                canonical_input=rule.name,  # The rule name typically is the input code/name
                percentage=rule.percentage_constraint,
                quantity_cap=None,  # Can be extended for QUANTITY_CAP rules
            )
            result.append(info)

        return result

    @staticmethod
    def get_percentage_rules_for_output_item(
        output_item: ItemNameModel,
        sion: SionNormClassModel,
    ) -> Dict[str, Decimal]:
        """Get percentage-cap rules for a specific output item.

        Returns a mapping of canonical_input -> percentage_constraint for
        all PERCENTAGE_CAP rules.

        Args:
            output_item: The output item being planned to
            sion: The SION norm

        Returns:
            Dict mapping canonical input code to its percentage (e.g., {'PKO': Decimal('50.00'), ...})
        """
        rules = SionPlanningRule.objects.filter(
            sion=sion,
            output_item=output_item,
            rule_type="PERCENTAGE_CAP",
            is_active=True,
        )

        result = {}
        for rule in rules:
            if rule.percentage_constraint:
                result[rule.name] = rule.percentage_constraint

        return result

    @staticmethod
    def get_split_rules_for_output_item(
        output_item: ItemNameModel,
        sion: SionNormClassModel,
        rule_group_id: Optional[str] = None,
    ) -> Dict[str, Decimal]:
        """Get split-by-percentage rules for a specific output item.

        Returns all SPLIT_PERCENTAGE rules grouped by rule_group_id,
        ensuring percentages sum to 100%.

        Args:
            output_item: The output item being planned to
            sion: The SION norm
            rule_group_id: Optional filter to a specific rule group

        Returns:
            Dict mapping canonical input code to its split percentage
        """
        filters = {
            "sion": sion,
            "output_item": output_item,
            "rule_type": "SPLIT_PERCENTAGE",
            "is_active": True,
        }
        if rule_group_id:
            filters["rule_group_id"] = rule_group_id

        rules = SionPlanningRule.objects.filter(**filters)

        result = {}
        for rule in rules:
            if rule.percentage_constraint:
                result[rule.name] = rule.percentage_constraint

        # Validate total sums to 100
        total = sum(result.values())
        if total != Decimal("100"):
            # Return empty if invalid - Split-by-% requires 100% total
            return {}

        return result

    @staticmethod
    def has_split_percentage_rule(
        output_item: ItemNameModel,
        sion: SionNormClassModel,
    ) -> bool:
        """Check if a valid SPLIT_PERCENTAGE rule exists for this output item.

        A valid split rule must have percentages that sum to exactly 100%.

        Args:
            output_item: The output item
            sion: The SION norm

        Returns:
            True if a valid split rule exists, False otherwise
        """
        split_rules = SionRuleResolver.get_split_rules_for_output_item(
            output_item, sion
        )
        return bool(split_rules)

    @staticmethod
    def has_percentage_cap_rules(
        output_item: ItemNameModel,
        sion: SionNormClassModel,
    ) -> bool:
        """Check if any PERCENTAGE_CAP rules exist for this output item.

        Args:
            output_item: The output item
            sion: The SION norm

        Returns:
            True if any cap rules exist, False otherwise
        """
        count = SionPlanningRule.objects.filter(
            sion=sion,
            output_item=output_item,
            rule_type="PERCENTAGE_CAP",
            is_active=True,
        ).count()
        return count > 0

    @staticmethod
    def validate_split_rule_configuration(
        rule_dict: Dict[str, Decimal],
    ) -> tuple[bool, Optional[str]]:
        """Validate that a split rule configuration is valid.

        Args:
            rule_dict: Dict mapping canonical input to percentage

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not rule_dict:
            return False, "Split rule has no configured inputs"

        total = sum(rule_dict.values())
        if total != Decimal("100"):
            return False, f"Split percentages must sum to 100, got {total}"

        for code, pct in rule_dict.items():
            if pct <= DEC_0:
                return False, f"Input {code} has invalid percentage {pct}"

        return True, None
