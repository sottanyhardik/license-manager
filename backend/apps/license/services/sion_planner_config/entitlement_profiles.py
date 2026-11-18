"""Entitlement-planning profiles (data only).

Supplements the DB planning rules (``SionPlanningRule`` + its
``SionPlanningPercentageRow`` split rows, which remain the single source of
split percentages and maximum unit prices) with what those tables cannot
express:

* product group labels and the stable registry keys they belong to;
* the product → entitlement mapping (e.g. Sunflower Oil draws on the Olive Oil
  entitlement) used to attribute BOE debits and allotments;
* the waterfall sequence of entitlements inside a group;
* the CIF valuation method of each entitlement after debits:
  ``RATE``     — balance CIF = balance quantity × opening rate;
  ``RESIDUAL`` — the entitlement absorbs whatever licence CIF remains after
                 every other entitlement (at most one per profile, last).

The engine (``apps.license.services.entitlement_planning``) contains no
product names; a norm without a profile here is still planned generically
(entitlement label = canonical item name, valuation ``RATE``).

Keys of ``entitlements`` and ``entitlement_items`` are canonical
``ItemNameModel.name`` values (upper-case), the same identity the percentage
rows link to.
"""
from __future__ import annotations

ENTITLEMENT_PROFILES: dict[str, dict] = {
    "E126": {
        "groups": [
            {
                "key": "FOOD_FLAVOUR",
                "label": "Food Flavour",
                "entitlement_items": ["FOOD FLAVOUR"],
            },
            {
                "key": "VEGETABLE_OIL",
                "label": "Vegetable Oil",
                "entitlement_items": ["PALM KERNEL OIL", "OLIVE OIL"],
                # Registry identity of this split (sion_legacy_configurations.E126).
                "source_rule": "E126:RULE:002:PKO_OLIVE_SPLIT",
                "split_action": "E126:ACTION:002:SPLIT",
                # Product → entitlement mapping.  ``aliases`` are matched as
                # upper-case substrings of BOE product names / allotment item
                # names; a text that matches products of two entitlements is
                # ambiguous and is never guessed.
                "products": [
                    {"name": "Sunflower Oil", "entitlement": "OLIVE OIL", "aliases": ["SUNFLOWER"]},
                    {"name": "Olive Oil", "entitlement": "OLIVE OIL", "aliases": ["OLIVE"]},
                    {"name": "PKO", "entitlement": "PALM KERNEL OIL", "aliases": ["PALM KERNEL", "PKO"]},
                ],
            },
        ],
        "entitlements": {
            "FOOD FLAVOUR": {"label": "Food Flavour", "valuation": "RATE", "sequence": 1},
            # Owner decision (preserved): REBALANCE / VALUE_GAIN_SHIFT never moves
            # quantity between PKO and Olive Oil after the 50:50 split — only
            # CIF released by a cheaper actual rate flows to the residual.
            "PALM KERNEL OIL": {"label": "PKO", "split_target": "PKO", "valuation": "RATE", "sequence": 1},
            "OLIVE OIL": {
                "label": "Olive Oil + Sunflower Oil",
                "split_target": "OLIVE",
                "valuation": "RESIDUAL",
                "sequence": 2,
            },
        },
    },
}


def entitlement_profile(norm: str) -> dict:
    """Profile for ``norm`` (case-insensitive) or an empty generic profile."""
    return ENTITLEMENT_PROFILES.get(str(norm or "").strip().upper(), {"groups": [], "entitlements": {}})
