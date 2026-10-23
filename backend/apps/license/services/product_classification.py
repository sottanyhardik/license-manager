"""Product classification for E5 norm item pivot reporting.

Each product category is defined by HSN code prefixes and description text
matching conditions. The classifier evaluates an import item's HSN code and
description against the conditions in priority order, returning the first
matching product category.

The conditions match the SION planning rule expressions used in the rule
editor, but are simplified for fast evaluation in the item pivot report
context where we only need the product name, not the full expression tree.
"""
from __future__ import annotations

import re
from typing import Optional


# Product classification conditions for E5 norm.
# Order matters: higher-priority products are checked first.
# Each tuple: (product_name, hsn_prefixes, description_keywords, exclude_hsn_prefixes, exclude_description_keywords)
# - hsn_prefixes: list of HSN code prefixes to match (OR logic)
# - description_keywords: list of keywords that must appear in description (AND with HSN)
# - exclude_hsn_prefixes: list of HSN prefixes that exclude the match
# - exclude_description_keywords: list of keywords that exclude the match
E5_PRODUCT_CONDITIONS = [
    # RBD PALMOLEIN OIL: (HSN 1511 OR desc 1511) AND NOT (HSN 1513 OR desc 1513)
    {
        "name": "RBD PALMOLEIN OIL",
        "hsn_prefixes": ["1511"],
        "desc_contains_any": ["1511"],
        "exclude_hsn_prefixes": ["1513"],
        "exclude_desc_contains": ["1513"],
    },
    # PKO: HSN 1513 OR desc 1513
    {
        "name": "PKO",
        "hsn_prefixes": ["1513"],
        "desc_contains_any": ["1513"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
    },
    # CHEESE: (HSN 0406 OR desc 0406) AND NOT (HSN 0404 OR desc 0404)
    {
        "name": "CHEESE",
        "hsn_prefixes": ["0406"],
        "desc_contains_any": ["0406"],
        "exclude_hsn_prefixes": ["0404"],
        "exclude_desc_contains": ["0404"],
    },
    # DWP or SWP: HSN 0404 OR desc 0404
    {
        "name": "DWP/SWP",
        "hsn_prefixes": ["0404"],
        "desc_contains_any": ["0404"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
    },
    # WPC: (HSN 3502 OR desc 3502) AND NOT (0404 or 0406)
    {
        "name": "WPC",
        "hsn_prefixes": ["3502"],
        "desc_contains_any": ["3502"],
        "exclude_hsn_prefixes": ["0404", "0406"],
        "exclude_desc_contains": ["0404", "0406"],
    },
    # DIETARY FIBRE: HSN 0802 OR desc 0802 (no description keyword required)
    {
        "name": "DIETARY FIBRE",
        "hsn_prefixes": ["0802"],
        "desc_contains_any": ["0802"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
    },
    # YEAST: (HSN 2102/2106 OR desc 2102/2106) AND desc contains LEAVENING
    {
        "name": "YEAST",
        "hsn_prefixes": ["2102", "2106"],
        "desc_contains_any": ["2102", "2106"],
        "desc_contains_all": ["LEAVENING"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
    },
    # WHEAT FLOUR: (HSN 1101 OR desc 1101) AND desc contains FLOUR
    {
        "name": "WHEAT FLOUR",
        "hsn_prefixes": ["1101"],
        "desc_contains_any": ["1101"],
        "desc_contains_all": ["FLOUR"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
    },
    # PAPER: (HSN 48 OR desc 48) AND desc contains PAPER
    {
        "name": "PAPER",
        "hsn_prefixes": ["48"],
        "desc_contains_any": ["48"],
        "desc_contains_all": ["PAPER"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
    },
    # ALUMINIUM FOIL: (HSN 7607 OR desc 7607) AND desc contains PACKING
    {
        "name": "ALUMINIUM FOIL",
        "hsn_prefixes": ["7607"],
        "desc_contains_any": ["7607"],
        "desc_contains_all": ["PACKING"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
    },
    # PP: HSN 390 OR desc 390
    {
        "name": "PP",
        "hsn_prefixes": ["390"],
        "desc_contains_any": ["390"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
    },
    # SUGAR: desc contains SUGAR
    {
        "name": "SUGAR",
        "hsn_prefixes": [],
        "desc_contains_any": ["SUGAR"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
    },
]


def _normalize_hsn(hs_code: str) -> str:
    """Normalize HSN code for comparison: strip non-alphanumeric, lowercase."""
    if not hs_code:
        return ""
    return re.sub(r"[^a-z0-9]", "", hs_code.strip().lower())


def _normalize_text(text: str) -> str:
    """Normalize description text for comparison: lowercase, collapse whitespace."""
    if not text:
        return ""
    return " ".join(text.strip().lower().split())


def classify_product(hs_code: str, description: str) -> Optional[str]:
    """Classify an import item into a product category based on HSN and description.

    Returns the product category name (e.g., "PKO", "DIETARY FIBRE") or None
    if no condition matches.

    The conditions are evaluated in order; the first match wins.
    """
    hsn_norm = _normalize_hsn(hs_code)
    desc_norm = _normalize_text(description)

    for condition in E5_PRODUCT_CONDITIONS:
        # Check exclusion conditions first
        if condition.get("exclude_hsn_prefixes"):
            if any(hsn_norm.startswith(prefix) for prefix in condition["exclude_hsn_prefixes"]):
                continue
        if condition.get("exclude_desc_contains"):
            if any(keyword.lower() in desc_norm for keyword in condition["exclude_desc_contains"]):
                continue

        # Check HSN prefix match (OR logic within the list)
        hsn_match = False
        if condition.get("hsn_prefixes"):
            hsn_match = any(hsn_norm.startswith(prefix) for prefix in condition["hsn_prefixes"])

        # Check description contains any (OR logic within the list)
        desc_any_match = False
        if condition.get("desc_contains_any"):
            desc_any_match = any(keyword.lower() in desc_norm for keyword in condition["desc_contains_any"])

        # Check description contains all (AND logic — all must be present)
        desc_all_match = True
        if condition.get("desc_contains_all"):
            desc_all_match = all(keyword.lower() in desc_norm for keyword in condition["desc_contains_all"])

        # Match logic: (HSN match OR desc any match) AND desc all match
        # For conditions with no hsn_prefixes and no desc_contains_any,
        # we only check desc_contains_all (e.g., SUGAR)
        if not condition.get("hsn_prefixes") and not condition.get("desc_contains_any"):
            # Only desc_contains_all matters (e.g., SUGAR)
            if condition.get("desc_contains_all"):
                if desc_all_match:
                    return condition["name"]
            continue
        else:
            # (HSN OR desc any) AND desc all
            if (hsn_match or desc_any_match) and desc_all_match:
                return condition["name"]

    return None


def get_e5_product_categories() -> list:
    """Return the list of E5 product category names in priority order."""
    return [cond["name"] for cond in E5_PRODUCT_CONDITIONS]
