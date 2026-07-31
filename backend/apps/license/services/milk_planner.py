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

  * 0404 only  → the 0404 quantity is PARTITIONED between DWP and SWP (see
    :func:`_split_milk_0404`) — the two no longer read the same
    unpartitioned quantity.
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
    dwp_min_price: Decimal
    swp_price: Decimal
    wpc_price: Decimal


MILK_CONFIG_E1 = MilkConfig(
    dwp_price=Decimal('5'),
    dwp_min_price=Decimal('4.40'),
    swp_price=Decimal('1.5'),
    wpc_price=Decimal('25'),
)


def _zero_result(config: MilkConfig) -> dict[str, Decimal]:
    return {'DWP': Decimal('0'), 'SWP': Decimal('0'), 'WPC': Decimal('0')}


def _split_milk_0404(qty: Decimal, balance: Decimal, config: MilkConfig) -> tuple[Decimal, Decimal, Decimal]:
    """Partition a Milk Products (HSN 0404) quantity between DWP and SWP.

    DWP quantity is maximised subject to its rate staying within
    ``[config.dwp_min_price, config.dwp_price]``; SWP (always priced at
    ``config.swp_price``) absorbs whatever quantity DWP can't take. Since
    raising DWP's share while holding total value at ``balance`` forces its
    rate down, "maximise DWP quantity" and "minimise remaining balance"
    converge on the same point: the largest DWP quantity whose rate hasn't
    yet dropped below ``dwp_min_price``.

    Returns ``(dwp_qty, dwp_rate, swp_qty)``. When even SWP can't cover the
    full quantity, DWP is 0 and SWP is capped at what the balance affords —
    `qty` is then only partially covered (mirrors :func:`allocate_step`'s
    balance-insufficient case elsewhere in the codebase).
    """
    if qty <= 0 or balance <= 0:
        return Decimal('0'), config.dwp_price, Decimal('0')

    avg = balance / qty

    if avg >= config.dwp_price:
        return qty, config.dwp_price, Decimal('0')

    if avg >= config.dwp_min_price:
        return qty, avg, Decimal('0')

    if avg >= config.swp_price:
        spread = config.dwp_min_price - config.swp_price
        dwp_qty = (balance - config.swp_price * qty) / spread
        dwp_qty = min(max(dwp_qty, Decimal('0')), qty)
        return dwp_qty, config.dwp_min_price, qty - dwp_qty

    return Decimal('0'), config.dwp_price, balance / config.swp_price


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
        dwp_qty, dwp_rate, swp_qty = _split_milk_0404(qty_0404, remaining, config)
        planned['DWP'] = dwp_qty * dwp_rate
        rate['DWP'] = dwp_rate
        planned['SWP'] = swp_qty * config.swp_price
        remaining -= (planned['DWP'] + planned['SWP'])

    if qty_3502 > 0:
        wpc_used, wpc_rate = allocate_step(qty_3502, config.wpc_price, remaining)
        planned['WPC'] += wpc_used
        rate['WPC'] = wpc_rate
        remaining -= wpc_used

    return planned, rate, remaining
