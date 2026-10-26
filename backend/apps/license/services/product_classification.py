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

from apps.license.services.a3627_classifier import AMBIGUOUS, CONFIRMED, NORM as NORM_A3627, classify_a3627
from apps.license.services.c969_product_classifier import C969_CATEGORY_ORDER, C969_NORM, classify_c969_category
from apps.license.services.product_norm_guard import guard_product_for_norm


# Product classification conditions for E5 norm.
# Order matters: higher-priority products are checked first.
# The `sort_order` field controls display order in the item pivot report.
# Classification priority is the position in this list (first match wins). It is not the
# display order; see NORM_DISPLAY_SEQUENCES below. sort_order is only the fallback display order.
# Each dict: (product_name, hsn_prefixes, desc_contains_any, desc_contains_all,
# exclude_hsn_prefixes, exclude_desc_contains, sort_order)
# - hsn_prefixes: list of HSN code prefixes to match (OR logic)
# - desc_contains_any: list of keywords, any one matches (OR logic)
# - desc_word_any: list of whole-word keywords (e.g. "PP"), any one matches (OR logic)
# - desc_required_any: list of keywords, one must match, ANDed with the HSN/desc match
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
    # RBD PAL (canonical label for RBD palmolein oil): (HSN 1511 OR desc 1511) AND NOT (HSN 1513/1509/1510 OR desc 1513/1509/1510)
    {
        "name": "RBD PAL",
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
    # APPLE DIES: HSN 0813 OR desc contains 0813 (checked before FOOD FLAVOUR so pure 0813 items match here)
    # Excludes items with "FOOD ADDITIVES" in description so they fall through to FOOD FLAVOUR
    {
        "name": "APPLE DIES",
        "hsn_prefixes": ["0813"],
        "desc_contains_any": ["0813"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": ["FOOD ADDITIVES"],
        "sort_order": 99,
    },
    # OTHER CONFECTIONERY: (Norm = E1) AND (HSN 0802 OR desc 0802) AND (desc contains CONFECTIONERY OR INGREDIENTS OR NUT)
    # E1 norm only — checked before FOOD FLAVOUR so E1 confectionery items match here
    {
        "name": "OTHER CONFECTIONERY",
        "hsn_prefixes": ["0802"],
        "desc_contains_any": ["0802"],
        "desc_required_any": ["CONFECTIONERY", "INGREDIENTS", "NUT"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "norm": "E1",
        "sort_order": 99,
    },
    # FRUIT COCKTAIL: HSN 2008 AND desc contains FRUIT — fruit preparations like cocktails, pulps, purees
    # Exclude NUT so HSN 2008 + NUT items fall through to FOOD FLAVOUR
    {
        "name": "FRUIT COCKTAIL",
        "hsn_prefixes": ["2008"],
        "desc_contains_any": [],
        "desc_contains_all": ["FRUIT"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": ["NUT"],
        "sort_order": 99,
    },
    # JUICE: HSN 2009 only — these HSN codes are specifically for fruit juice preparations
    # Works for all norms — checked before FOOD FLAVOUR so HSN 2009 items match JUICE first
    # Matches items like "Juice HS 20098990" based on HSN alone
    {
        "name": "JUICE",
        "hsn_prefixes": ["2009"],
        "desc_contains_any": [],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 99,
    },
    # FOOD FLAVOUR: (HSN 0802/0804/0805/0813/2008 OR desc contains any of those OR desc contains FOOD ADDITIVES) AND NOT desc contains DIETARY AND NOT desc contains CONFECTIONERY AND NOT desc contains NUT
    # Covers: Fruit (0804/0805/0813), Nut Products (0802), Yeast Extract, Cinnamon, Cumin, Garlic, Vinegar
    # HSN 2008 items with NUT in description match here (FRUIT COCKTAIL excludes NUT)
    {
        "name": "FOOD FLAVOUR",
        "hsn_prefixes": ["0802", "0804", "0805", "0813", "2008"],
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
    # PP (Polypropylene): HSN 3902/3920/3923/4415 OR desc contains 3902/3920/3923 OR desc has the word PP
    # (exclude 7607 so aluminium foil doesn't match PP). The word PP must be whole-word so "supply" is not PP,
    # and HSN chapter 48 (paper/board, e.g. "PP-Laminated Board" 48115900) is never PP.
    # HSN 4415 is packing material (wooden sheets / pallets) and is classed as PP.
    {
        "name": "PP",
        "hsn_prefixes": ["3902", "3920", "3923", "4415"],
        "desc_contains_any": ["3902", "3920", "3923"],
        "desc_word_any": ["PP"],
        "exclude_hsn_prefixes": ["3912", "7607", "48"],
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
    # LIQUID GLUCOSE: desc contains both LIQUID and GLUCOSE (spelling variations handled)
    {
        "name": "LIQUID GLUCOSE",
        "hsn_prefixes": [],
        "desc_contains_any": [],
        "desc_contains_all": ["LIQUID", "GLUCOSE"],
        "exclude_hsn_prefixes": [],
        "exclude_desc_contains": [],
        "sort_order": 99,
    },
    # LECITHIN: desc contains LECITHIN or THICKENERS (spelling variations like "Leicithin" handled)
    {
        "name": "LECITHIN",
        "hsn_prefixes": [],
        "desc_contains_any": ["LECITHIN", "LEICITHIN", "THICKENERS"],
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


def _keyword_in(keyword: str, desc_norm: str) -> bool:
    """Whether a keyword appears in a normalized description.

    A purely numeric keyword is an HSN prefix, so it matches only where a
    number starts: "1513" matches "15132110", but "1510" is not a prefix of
    "44151000" (wooden packing material) and must not match it.  Text keywords
    keep plain substring matching.
    """
    if keyword.isdigit():
        return re.search(rf"(?<!\d){keyword}", desc_norm) is not None
    return keyword.lower() in desc_norm


def _word_in(word: str, desc_norm: str) -> bool:
    """Whether a keyword appears in a normalized description as a whole word.

    Used for short tokens such as "PP" that would otherwise match inside
    "supply" or "approx".
    """
    return re.search(rf"(?<![a-z0-9]){re.escape(word.lower())}(?![a-z0-9])", desc_norm) is not None


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

    if norm_upper == NORM_A3627:
        # The A3627 registry owns every A3627 product. Ambiguous lines stay unclassified for
        # review; only lines the registry does not cover fall through to the generic rules.
        result = classify_a3627(None, hs_code, description)
        if result.status == CONFIRMED:
            return guard_product_for_norm(norm, result.category, context="classify_product")
        if result.status == AMBIGUOUS:
            return None

    if norm_upper == C969_NORM:
        # The C969 rules own every C969 line: the product name first, then the generic C969 products,
        # then a named bucket. HSN and the generic E5 conditions never apply to C969.
        return classify_c969_category(description)

    for condition in E5_PRODUCT_CONDITIONS:
        # Check exclusion conditions first
        if condition.get("exclude_hsn_prefixes"):
            if any(hsn_norm.startswith(prefix) for prefix in condition["exclude_hsn_prefixes"]):
                continue
        if condition.get("exclude_desc_contains"):
            if any(_keyword_in(keyword, desc_norm) for keyword in condition["exclude_desc_contains"]):
                continue

        # Check HSN prefix match (OR logic within the list)
        hsn_match = False
        if condition.get("hsn_prefixes"):
            hsn_match = any(hsn_norm.startswith(prefix) for prefix in condition["hsn_prefixes"])

        # Check description contains any (OR logic within the list)
        desc_any_match = False
        if condition.get("desc_contains_any"):
            desc_any_match = any(_keyword_in(keyword, desc_norm) for keyword in condition["desc_contains_any"])
        if condition.get("desc_word_any"):
            desc_any_match = desc_any_match or any(_word_in(word, desc_norm) for word in condition["desc_word_any"])

        # Check description contains all (AND logic — all must be present)
        desc_all_match = True
        if condition.get("desc_contains_all"):
            desc_all_match = all(_keyword_in(keyword, desc_norm) for keyword in condition["desc_contains_all"])

        # Check description contains at least one required keyword (AND logic with the rest)
        desc_required_match = True
        if condition.get("desc_required_any"):
            desc_required_match = any(_keyword_in(keyword, desc_norm) for keyword in condition["desc_required_any"])

        # Check norm filter if specified
        if condition.get("norm"):
            if norm_upper != condition["norm"].upper():
                continue

        # Match logic: (HSN match OR desc any match) AND desc all match AND desc required match
        # For conditions with no hsn_prefixes and no desc_contains_any,
        # we only check desc_contains_all (e.g., SUGAR)
        if not condition.get("hsn_prefixes") and not condition.get("desc_contains_any"):
            # Only desc_contains_all matters (e.g., SUGAR)
            if condition.get("desc_contains_all"):
                if desc_all_match:
                    return guard_product_for_norm(norm, condition["name"], context="classify_product")
            continue
        else:
            # (HSN OR desc any) AND desc all AND desc required
            if (hsn_match or desc_any_match) and desc_all_match and desc_required_match:
                return guard_product_for_norm(norm, condition["name"], context="classify_product")

    return None


def get_classification_priority(category_name: str) -> Optional[int]:
    """Position of a category in the rule list. Lower is checked first; None if not a rule."""
    for index, cond in enumerate(E5_PRODUCT_CONDITIONS):
        if cond["name"] == category_name:
            return index
    return None


def get_e5_product_categories() -> list:
    """Return the list of E5 product category names in priority order."""
    return [cond["name"] for cond in E5_PRODUCT_CONDITIONS]


# Global fallback order for categories that have no norm sequence (display only).
# Classification priority is the position in E5_PRODUCT_CONDITIONS and never reads this.
_PRODUCT_SORT_ORDER = {cond["name"]: cond.get("sort_order", 99) for cond in E5_PRODUCT_CONDITIONS}


def get_product_category_sort_order(category_name: Optional[str]) -> int:
    """Fallback display order of a category: its sort_order, 99 if unknown, 999 for UNCLASSIFIED."""
    if not category_name:
        return 999
    return _PRODUCT_SORT_ORDER.get(category_name, 99)


# Per-norm display sequences. Each configured norm is one contiguous block of columns, in the
# block order given by this dict's insertion order. Inside a block the listed categories come
# first, in exactly this order; other categories of that norm follow by get_product_category_sort_order.
# Display only: classification (E5_PRODUCT_CONDITIONS) never reads this table.
NORM_DISPLAY_SEQUENCES = {
    "A3627": (
        "RUTILE",
        "ALUMINIUM OXIDE",
        "SODA ASH",
        "TITANIUM DIOXIDE",
        "PP",
        "BB-BOARD",
        "PP LAMINATED BOARD",
        "KRAFT LINER",
        "WOODEN SHEETS / PALLETS",
    ),
    "E1": (
        "OTHER CONFECTIONERY",
        "DWP/SWP",
        "WPC",
        "RBD PAL",
        "ESSENTIAL OIL",
        "APPLE DIES",
        "CITRIC ACID",
        "PP",
        "PAPER",
        "CMC",
    ),
    "E126": (
        "FOOD FLAVOUR",
        "OLIVE OIL",
        "PKO",
        "ALUMINIUM FOIL",
    ),
    "E132": (
        "FOOD FLAVOUR",
        "YEAST",
        "PKO",
        "CHEESE",
        "APPLE DIES",
        "CEREALS",
        "CMC",
        "ALUMINIUM FOIL",
        "PP",
    ),
    "C969": C969_CATEGORY_ORDER,
}


def pivot_category_sort_key(category_name: Optional[str], norm: str = "") -> tuple:
    """Column sort key for an item pivot category under a SION norm: (block, position).

    A configured norm's categories sort inside that norm's block, first by its sequence, then by
    the global fallback order. Blocks never interleave. Norms without a sequence come after every
    configured block, one block per SION, each in the global fallback order.
    """
    norm_upper = norm.strip().upper() if norm else ""
    blocks = list(NORM_DISPLAY_SEQUENCES)
    if norm_upper not in NORM_DISPLAY_SEQUENCES:
        # Unconfigured norms form one tail, one block per SION (never interleaved).
        return (len(blocks), norm_upper, get_product_category_sort_order(category_name))
    sequence = NORM_DISPLAY_SEQUENCES[norm_upper]
    block = blocks.index(norm_upper)
    if category_name in sequence:
        return (block, sequence.index(category_name))
    return (block, len(sequence) + get_product_category_sort_order(category_name))