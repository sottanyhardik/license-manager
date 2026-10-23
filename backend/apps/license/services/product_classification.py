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
# The `sort_order` field controls display order in the item pivot report.
# Sequence: 1=DIETARY FIBRE, 2=PKO, 3=RBD PALMOLEIN OIL, 4=DWP/SWP, 5=WPC,
# 6=WHEAT FLOUR, 7=YEAST, then 99+ for all others (alphabetical fallback).
# Each dict: (product_name, hsn_prefixes, desc_contains_any, desc_contains_all,
# exclude_hsn_prefixes, exclude_desc_contains, sort_order)
# - hsn_prefixes: list of HSN code prefixes to match (OR logic)
# - desc_contains_any: list of keywords, any one matches (OR logic)
# - desc_contains_all: list of keywords, all must match (AND logic)
# - exclude_hsn_prefixes: list of HSN prefixes that exclude the match
# - exclude_desc_contains: list of keywords that exclude the match
# - sort_order: display order in item pivot report (lower = first)
E5_PRODUCT_CONDITIONS = [
    # DIETARY FIBRE: (HSN 0802 OR desc 0802) AND desc contains DIETARY
    {
        "name": "DIETARY FIBRE",
        "hsn_prefixes": ["0802"],
        "desc_contains_any": ["0802"],
        "desc_contains_all": ["DIETARY"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 1,
    },
    # OLIVE OIL: (HSN starts with 1509 OR HSN starts with 1510 OR Description contains 1509 OR Description contains 1510)
    # If item has 1509 and 1511 then olive oil (checked before RBD PALMOLEIN OIL)
    # If item has 1509 and 1513 then olive oil (checked before PKO)
    {
        "name": "OLIVE OIL",
        "hsn_prefixes": ["1509", "1510"],
        "desc_contains_any": ["1509", "1510"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 2,
    },
    # PKO: HSN 1513 OR desc 1513 (exclude if also olive oil 1509/1510)
    {
        "name": "PKO",
        "hsn_prefixes": ["1513"],
        "desc_contains_any": ["1513"],
        "exclude_hsn_prefixes": ["1509", "1510"],
        "exclude_desc_contains": ["1509", "1510"],
        "sort_order": 3,
    },
    # RBD PALMOLEIN OIL: (HSN 1511 OR desc 1511) AND NOT (HSN 1513/1509/1510 OR desc 1513/1509/1510)
    {
        "name": "RBD PALMOLEIN OIL",
        "hsn_prefixes": ["1511"],
        "desc_contains_any": ["1511"],
        "exclude_hsn_prefixes": ["1513", "1509", "1510"],
        "exclude_desc_contains": ["1513", "1509", "1510"],
        "sort_order": 4,
    },
    # DWP or SWP: HSN 0404 OR desc 0404
    {
        "name": "DWP/SWP",
        "hsn_prefixes": ["0404"],
        "desc_contains_any": ["0404"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 5,
    },
    # WPC: (HSN 3502 OR desc 3502) AND NOT (0404 or 0406)
    {
        "name": "WPC",
        "hsn_prefixes": ["3502"],
        "desc_contains_any": ["3502"],
        "exclude_hsn_prefixes": ["0404", "0406"],
        "exclude_desc_contains": ["0404", "0406"],
        "sort_order": 6,
    },
    # WHEAT FLOUR: (HSN 1101 OR desc 1101) AND desc contains FLOUR
    {
        "name": "WHEAT FLOUR",
        "hsn_prefixes": ["1101"],
        "desc_contains_any": ["1101"],
        "desc_contains_all": ["FLOUR"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 7,
    },
    # YEAST: (HSN 2102/2106 OR desc 2102/2106) AND desc contains YEAST
    {
        "name": "YEAST",
        "hsn_prefixes": ["2102", "2106"],
        "desc_contains_any": ["2102", "2106"],
        "desc_contains_all": ["YEAST"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 8,
    },
    # CHEESE: (HSN 0406 OR desc 0406) AND NOT (HSN 0404 OR desc 0404)
    {
        "name": "CHEESE",
        "hsn_prefixes": ["0406"],
        "desc_contains_any": ["0406"],
        "exclude_hsn_prefixes": ["0404"],
        "exclude_desc_contains": ["0404"],
        "sort_order": 99,
    },
    # APPLE DRIES: HSN 0813 OR desc contains 0813 (checked before FOOD FLAVOUR so pure 0813 items match here)
    # Excludes items with "FOOD ADDITIVES" in description so they fall through to FOOD FLAVOUR
    {
        "name": "APPLE DRIES",
        "hsn_prefixes": ["0813"],
        "desc_contains_any": ["0813"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": ["FOOD ADDITIVES"],
        "sort_order": 99,
    },
    # OTHER CONFECTIONERY INGREDIENTS: (Norm = E1) AND (HSN 0802 OR desc 0802) AND (desc contains CONFECTIONERY OR INGREDIENTS OR NUT)
    # E1 norm only — checked before FOOD FLAVOUR so E1 confectionery items match here
    {
        "name": "OTHER CONFECTIONERY INGREDIENTS",
        "hsn_prefixes": ["0802"],
        "desc_contains_any": ["0802", "CONFECTIONERY", "INGREDIENTS", "NUT"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "norm": "E1",
        "sort_order": 99,
    },
    # JUICE: HSN 2008/2009 only — these HSN codes are specifically for fruit preparations (juice, cocktail, pulp, puree)
    # Works for all norms — checked before FOOD FLAVOUR so HSN 2008/2009 items match JUICE first
    # Matches items like "Fruit Cocktail HS 20089991" or "Juice HS 20098990" based on HSN alone
    {
        "name": "JUICE",
        "hsn_prefixes": ["2008", "2009"],
        "desc_contains_any": [],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 99,
    },
    # FOOD FLAVOUR: (HSN 0802/0804/0805/0813 OR desc contains any of those OR desc contains FOOD ADDITIVES) AND NOT desc contains DIETARY AND NOT desc contains CONFECTIONERY
    # Covers: Fruit (0804/0805/0813), Nut Products (0802), Yeast Extract, Cinnamon, Cumin, Garlic, Vinegar
    # Note: HSN 2008/2009 are handled by JUICE category above; FOOD FLAVOUR catches 2008/2009 only if desc contains the numbers
    {
        "name": "FOOD FLAVOUR",
        "hsn_prefixes": ["0802", "0804", "0805", "0813"],
        "desc_contains_any": ["0802", "0804", "0805", "0813", "2008", "2009", "FOOD ADDITIVES"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": ["DIETARY", "CONFECTIONERY"],
        "sort_order": 99,
    },
    # PAPER: (HSN 48 OR desc 48) AND desc contains PAPER
    {
        "name": "PAPER",
        "hsn_prefixes": ["48"],
        "desc_contains_any": ["48"],
        "desc_contains_all": ["PAPER"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 99,
    },
    # SUGAR: desc contains SUGAR
    {
        "name": "SUGAR",
        "hsn_prefixes": [],
        "desc_contains_any": ["SUGAR"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 99,
    },
    # CEREALS: (HSN 1104/0713/0710 OR desc) OR desc contains CEREAL/CHICKPEAS/LENTILS/PEAS/SOYABEAN/CEREAL FLAKES
    {
        "name": "CEREALS",
        "hsn_prefixes": ["1104", "0713", "0710"],
        "desc_contains_any": ["1104", "0713", "0710", "CEREAL", "CHICKPEAS", "LENTILS", "PEAS", "SOYABEAN", "SOYBEAN"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 99,
    },
    # CMC: HSN 3912 OR desc contains 3912
    {
        "name": "CMC",
        "hsn_prefixes": ["3912"],
        "desc_contains_any": ["3912"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 99,
    },
    # ALUMINIUM FOIL: HSN 7607 OR desc contains 7607 (priority before PP so 7607 matches first)
    {
        "name": "ALUMINIUM FOIL",
        "hsn_prefixes": ["7607"],
        "desc_contains_any": ["7607"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 99,
    },
    # PP (Polypropylene): HSN 3902/3920/3923 OR desc contains 3902/3920/3923/PP (exclude 7607 so aluminium foil doesn't match PP)
    {
        "name": "PP",
        "hsn_prefixes": ["3902", "3920", "3923"],
        "desc_contains_any": ["3902", "3920", "3923", "PP"],
        "exclude_hsn_prefixes": ["3912", "7607"],
        "exclude_desc_contains": ["3912", "7607"],
        "sort_order": 99,
    },
    # GLASS BOTTLE: HSN 7010 OR desc contains 7010
    {
        "name": "GLASS BOTTLE",
        "hsn_prefixes": ["7010"],
        "desc_contains_any": ["7010"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 99,
    },
    # SANITATION: desc contains SANITATION
    {
        "name": "SANITATION",
        "hsn_prefixes": [],
        "desc_contains_any": ["SANITATION"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 99,
    },
    # ESSENTIAL OIL: desc contains ESSENTIAL OIL
    {
        "name": "ESSENTIAL OIL",
        "hsn_prefixes": [],
        "desc_contains_any": ["ESSENTIAL OIL"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 99,
    },
    # CITRIC ACID: HSN 2918 OR desc contains CITRIC ACID
    {
        "name": "CITRIC ACID",
        "hsn_prefixes": ["2918"],
        "desc_contains_any": ["2918", "CITRIC ACID"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 99,
    },
    # FOOD COLOURS: desc contains FOOD COLOUR
    {
        "name": "FOOD COLOURS",
        "hsn_prefixes": [],
        "desc_contains_any": ["FOOD COLOUR"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 99,
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


def classify_product(hs_code: str, description: str, norm: str = "") -> Optional[str]:
    """Classify an import item into a product category based on HSN, description, and norm.

    Returns the product category name (e.g., "PKO", "DIETARY FIBRE") or None
    if no condition matches.

    The conditions are evaluated in order; the first match wins.
    Some conditions are norm-specific (e.g., OTHER CONFECTIONERY INGREDIENTS for E1 only).
    """
    hsn_norm = _normalize_hsn(hs_code)
    desc_norm = _normalize_text(description)
    norm_upper = norm.strip().upper() if norm else ""

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

        # Check norm filter if specified
        if condition.get("norm"):
            if norm_upper != condition["norm"].upper():
                continue

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


# Build a lookup dict: category name -> sort_order
_PRODUCT_SORT_ORDER = {cond["name"]: cond.get("sort_order", 99) for cond in E5_PRODUCT_CONDITIONS}


def get_product_category_sort_order(category_name: Optional[str]) -> int:
    """Return the sort order for a product category name.

    Returns the sort_order if the category is known, otherwise 99 (sort last).
    UNCLASSIFIED items sort after all known categories (99 + alphabetical fallback).
    """
    if not category_name:
        return 999  # UNCLASSIFIED sorts last
    return _PRODUCT_SORT_ORDER.get(category_name, 99)
