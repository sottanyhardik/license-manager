"""Canonical product name classification for SION percentage allocation.

Maps raw product names from BOE, Allotments, and Planning to canonical input codes.
Uses case-insensitive exact alias matching via data-driven SionInputAliasConfig.

For backward compatibility, also supports legacy enum-based classification.
"""
from enum import Enum
from typing import Optional

from apps.core.models import SionNormClassModel, ItemNameModel
from .sion_rule_resolver import SionRuleResolver


class CanonicalInput(str, Enum):
    """Legacy enum for canonical input codes recognized by SION percentage rules.

    Deprecated in favor of data-driven SionInputAliasConfig, but kept for backward
    compatibility with existing code that references these enums.
    """
    PKO = "PKO"
    OLIVE_OIL = "OLIVE_OIL"
    CHEESE = "CHEESE"
    UNMAPPED = "UNMAPPED"


class SionProductClassifier:
    """Classifies raw product names into canonical SION inputs.

    Uses data-driven alias configuration where possible, with fallback to
    legacy hardcoded aliases for backward compatibility.
    """

    # Legacy hardcoded aliases for backward compatibility
    CANONICAL_ALIASES = {
        "PKO": CanonicalInput.PKO,
        "PALM KERNEL OIL": CanonicalInput.PKO,
        "OLIVE OIL": CanonicalInput.OLIVE_OIL,
        "CHEESE": CanonicalInput.CHEESE,
    }

    @staticmethod
    def normalize_product_name(raw_name: str | None) -> str:
        """Normalize a product name for classification.

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
    ) -> CanonicalInput:
        """Resolve a product name to its canonical input code.

        Uses hierarchical lookup:
        1. Data-driven SionInputAliasConfig (if sion/output_item provided)
        2. Legacy hardcoded aliases
        3. Returns UNMAPPED if not found

        Args:
            raw_name: Raw product name
            sion: Optional SION norm for scoped lookup
            output_item: Optional output item for further scoping

        Returns:
            CanonicalInput enum (PKO, OLIVE_OIL, CHEESE, or UNMAPPED)
        """
        if not raw_name:
            return CanonicalInput.UNMAPPED

        # Try data-driven resolution first
        if sion or output_item:
            mapping = SionRuleResolver.resolve_canonical_input(
                raw_name, sion, output_item
            )
            if mapping.is_mapped:
                # Convert canonical code string to enum
                code = mapping.canonical_code
                try:
                    return CanonicalInput[code]
                except KeyError:
                    # Code doesn't match legacy enum, return UNMAPPED
                    return CanonicalInput.UNMAPPED

        # Fall back to legacy hardcoded lookup
        normalized = SionProductClassifier.normalize_product_name(raw_name)
        canonical = SionProductClassifier.CANONICAL_ALIASES.get(normalized)

        if canonical:
            return canonical

        return CanonicalInput.UNMAPPED

    @staticmethod
    def is_mapped(
        raw_name: str | None,
        sion: Optional[SionNormClassModel] = None,
        output_item: Optional[ItemNameModel] = None,
    ) -> bool:
        """Check if a product name can be classified."""
        result = SionProductClassifier.resolve_canonical_input(
            raw_name, sion, output_item
        )
        return result != CanonicalInput.UNMAPPED
