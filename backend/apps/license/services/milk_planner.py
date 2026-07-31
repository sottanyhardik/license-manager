"""
Shared Milk Products (HSN 0404) / Egg Albumin-WPC (HSN 3502) planning engine
for E1's reporting waterfall (``e1_plan.py``).

E5 has its own per-item milk rules in ``e5_plan.py`` (no averaging between
0404 and 3502 — each item is classified and priced independently); this
module is now E1-only.

Callers own two decisions this module does NOT make:

  * WHICH import items are milk (classification into the 0404 / 3502
    buckets happens in each norm's own classifier).
  * WHEN milk planning runs relative to the rest of that norm's waterfall.

This module only decides HOW a milk quantity is split into SWP / DWP / WPC
once the caller has handed it the 0404 quantity, the 3502 quantity, and the
balance remaining to draw against — configured via :class:`MilkConfig`.

Two cases:

  * 0404 only  → DWP first, then SWP — both read the FULL 0404 quantity
    (not partitioned), each an independent dynamic-pricing allocation
    against the shrinking balance (:func:`allocate_step`).
  * 3502 only  → the full quantity to WPC at ``config.wpc_price``.
  * Both present → simply the 0404 branch followed by the 3502 branch — E1
    has no average-price concept.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.license.services.planning_allocation import allocate_step, d


@dataclass(frozen=True)
class MilkConfig:
    dwp_price: Decimal
    swp_price: Decimal
    wpc_price: Decimal


MILK_CONFIG_E1 = MilkConfig(
    dwp_price=Decimal('5'),
    swp_price=Decimal('1.5'),
    wpc_price=Decimal('25'),
)


def _zero_result(config: MilkConfig) -> dict[str, Decimal]:
    return {'DWP': Decimal('0'), 'SWP': Decimal('0'), 'WPC': Decimal('0')}


def plan_milk(
    qty_0404,
    qty_3502,
    remaining_balance,
    config: MilkConfig,
) -> tuple[dict[str, Decimal], dict[str, Decimal], Decimal]:
    """Run the shared milk sub-waterfall.

    Args:
        qty_0404: utilization quantity classified as Milk Products (HSN 0404).
        qty_3502: utilization quantity classified as Egg Albumin / WPC (HSN 3502).
        remaining_balance: balance available for milk planning to draw down.
        config: :data:`MILK_CONFIG_E1`.

    Returns:
        (planned_cif, rate, remaining_balance) — `planned_cif` / `rate` are
        keyed 'DWP' / 'SWP' / 'WPC' (all three keys always present, zero
        when unused).
    """
    qty_0404 = d(qty_0404)
    qty_3502 = d(qty_3502)
    remaining = d(remaining_balance)

    planned = _zero_result(config)
    rate = {'DWP': config.dwp_price, 'SWP': config.swp_price, 'WPC': config.wpc_price}

    if qty_0404 > 0:
        dwp_used, dwp_rate = allocate_step(qty_0404, config.dwp_price, remaining)
        planned['DWP'] = dwp_used
        rate['DWP'] = dwp_rate
        remaining -= dwp_used

        swp_used, swp_rate = allocate_step(qty_0404, config.swp_price, remaining)
        planned['SWP'] = swp_used
        rate['SWP'] = swp_rate
        remaining -= swp_used

    if qty_3502 > 0:
        wpc_used, wpc_rate = allocate_step(qty_3502, config.wpc_price, remaining)
        planned['WPC'] += wpc_used
        rate['WPC'] = wpc_rate
        remaining -= wpc_used

    return planned, rate, remaining
