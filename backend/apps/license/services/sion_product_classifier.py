"""Canonical product name classification for SION percentage allocation.

Maps raw product names from BOE, Allotments, and Planning to canonical input codes.
Uses case-insensitive exact alias matching.
"""
from enum import Enum


class CanonicalInput(str, Enum):
    """Canonical input codes recognized by SION percentage rules."""
    PKO = "PKO"
    OLIVE_OIL = "OLIVE_OIL"
    CHEESE = "CHEESE"
    UNMAPPED = "UNMAPPED"


class SionProductClassifier:
    """Classifies raw product names into canonical SION inputs."""

    # Canonical product aliases - normalized to uppercase, matched exactly
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
    def resolve_canonical_input(raw_name: str | None) -> CanonicalInput:
        """Resolve a product name to its canonical input code.

        Performs exact matching after normalization.
        Unknown products return UNMAPPED.

        Args:
            raw_name: Raw product name

        Returns:
            CanonicalInput enum (PKO, OLIVE_OIL, CHEESE, or UNMAPPED)
        """
        if not raw_name:
            return CanonicalInput.UNMAPPED

        normalized = SionProductClassifier.normalize_product_name(raw_name)
        canonical = SionProductClassifier.CANONICAL_ALIASES.get(normalized)

        if canonical:
            return canonical

        return CanonicalInput.UNMAPPED

    @staticmethod
    def is_mapped(raw_name: str | None) -> bool:
        """Check if a product name can be classified."""
        return SionProductClassifier.resolve_canonical_input(raw_name) != CanonicalInput.UNMAPPED
