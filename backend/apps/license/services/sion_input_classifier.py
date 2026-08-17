"""SION input classification from product names.

Normalizes BOE/Allotment product names and matches them against
configured aliases to derive the canonical SION input code.
"""
from decimal import Decimal
from django.db.models import Q
from apps.license.models.sion_input_alias import SionCanonicalInput, SionInputAlias


class SionInputClassifier:
    """Resolve product names to canonical SION inputs for percentage rules."""

    @staticmethod
    def normalize_product_name(value: str) -> str:
        """Normalize product name for case-insensitive matching.

        Removes leading/trailing whitespace, converts to uppercase,
        and collapses multiple spaces into single spaces.

        Args:
            value: Raw product name (e.g., "  Palm   Kernel Oil ")

        Returns:
            Normalized form (e.g., "PALM KERNEL OIL")

        Raises:
            ValueError: If value is empty or only whitespace
        """
        if not value or not isinstance(value, str):
            raise ValueError("Product name must be a non-empty string")
        normalized = " ".join(value.strip().upper().split())
        if not normalized:
            raise ValueError("Product name cannot be empty or whitespace-only")
        return normalized

    @staticmethod
    def resolve_canonical_input(product_name: str) -> SionCanonicalInput | None:
        """Resolve product name to canonical SION input.

        Normalizes the product name and searches for exact alias match
        among active canonical inputs.

        Args:
            product_name: Raw product name from BOE/Allotment

        Returns:
            SionCanonicalInput if found, None if no exact match (UNMAPPED)

        Example:
            >>> classifier.resolve_canonical_input("PALM KERNEL OIL")
            SionCanonicalInput(code="PKO", display_name="Palm Kernel Oil")

            >>> classifier.resolve_canonical_input("unknown product")
            None
        """
        try:
            normalized = SionInputClassifier.normalize_product_name(product_name)
        except ValueError:
            return None

        alias = SionInputAlias.objects.select_related("canonical_input").filter(
            normalized_alias=normalized,
            canonical_input__is_active=True
        ).first()

        return alias.canonical_input if alias else None

    @staticmethod
    def get_all_active_inputs() -> list[SionCanonicalInput]:
        """Retrieve all active canonical inputs."""
        return list(
            SionCanonicalInput.objects.filter(is_active=True).order_by("code")
        )

    @staticmethod
    def get_aliases_for_input(input_code: str) -> list[str]:
        """Retrieve all aliases for a canonical input."""
        return list(
            SionInputAlias.objects.filter(
                canonical_input__code=input_code
            ).values_list("alias", flat=True).order_by("alias")
        )

    @staticmethod
    def seed_initial_aliases() -> dict:
        """Seed initial E126/E132 canonical inputs and aliases.

        Called during migration to populate initial configuration.
        Safe to call repeatedly (uses get_or_create internally).

        Returns:
            Dict with counts of created canonical inputs and aliases
        """
        created_count = {"inputs": 0, "aliases": 0}

        # E126/E132 canonical inputs
        inputs_config = {
            "PKO": "Palm Kernel Oil",
            "OLIVE_OIL": "Olive Oil",
            "CHEESE": "Cheese Cream Butter and Fats",
            "NUT": "Nuts and Seeds",
            "YEAST": "Yeast and Baking Products",
            "RBD": "RBD Palmolein Oil",
            "SWP": "Sweet Whey Powder",
            "DWP": "Demineralized Whey Powder",
            "WPC": "Whey Protein Concentrate",
            "ALUMINIUM_FOIL": "Aluminium Foil",
        }

        for code, display_name in inputs_config.items():
            input_obj, created = SionCanonicalInput.objects.get_or_create(
                code=code,
                defaults={"display_name": display_name, "is_active": True}
            )
            if created:
                created_count["inputs"] += 1

        # Aliases per input
        aliases_config = {
            "PKO": [
                "PKO", "pko", "Palm Kernel Oil", "PALM KERNEL OIL",
                "palm kernel oil", "Pure Palm Kernel Oil"
            ],
            "OLIVE_OIL": [
                "OLIVE OIL", "Olive Oil", "olive oil", "Extra Virgin Olive Oil",
                "OLIVE OIL - E126"
            ],
            "CHEESE": [
                "CHEESE", "Cheese", "CHEESE CREAM BUTTER AND FATS",
                "Cheese Cream Butter and Fats"
            ],
            "NUT": [
                "NUT", "NUTS", "Nuts", "NUT & NUTS - E132",
                "Nuts and Seeds", "Cashew", "Almonds"
            ],
            "YEAST": [
                "YEAST", "Yeast", "Bakers Yeast", "Yeast - E132"
            ],
            "RBD": [
                "RBD", "RBD OIL", "RBD PALMOLEIN OIL",
                "RBD Palm Oil", "RBD - E132"
            ],
            "SWP": [
                "SWP", "Sweet Whey Powder", "SWP - E132"
            ],
            "DWP": [
                "DWP", "Demineralized Whey Powder", "DWP - E132"
            ],
            "WPC": [
                "WPC", "Whey Protein Concentrate", "WPC - E132"
            ],
            "ALUMINIUM_FOIL": [
                "ALUMINIUM FOIL", "Aluminium Foil", "Aluminium Foil - E132"
            ],
        }

        for code, aliases_list in aliases_config.items():
            try:
                canonical = SionCanonicalInput.objects.get(code=code)
            except SionCanonicalInput.DoesNotExist:
                continue

            for alias in aliases_list:
                normalized = SionInputClassifier.normalize_product_name(alias)
                _, created = SionInputAlias.objects.get_or_create(
                    normalized_alias=normalized,
                    defaults={
                        "canonical_input": canonical,
                        "alias": alias,
                    }
                )
                if created:
                    created_count["aliases"] += 1

        return created_count
