"""
Shared Milk Products (HSN 0404) / Egg Albumin-WPC (HSN 3502) planning engine,
reused by both the E1 and E5 waterfalls (``e1_plan.py`` / ``e5_plan.py``).

Callers own two decisions this module does NOT make:

  * WHICH import items are milk (classification into the 0404 / 3502
    buckets happens in each norm's own classifier).
  * WHEN milk planning runs relative to the rest of that norm's waterfall
    (e.g. E5's Special Validation can move milk planning before or after
    the edible-oils rule; E1 always runs it in a fixed position).

This module only decides HOW a milk quantity is split into SWP / DWP / WPC
once the caller has handed it the 0404 quantity, the 3502 quantity, and the
balance remaining to draw against — configured per norm via :class:`MilkConfig`.

Three cases:

  * 0404 only  → DWP first, then SWP — both read the FULL 0404 quantity
    (not partitioned), each an independent dynamic-pricing allocation
    against the shrinking balance (:func:`allocate_step`).
  * 3502 only  → the full quantity to WPC at ``config.wpc_price``.
  * Both present, with ``config.average_split`` enabled → the combined
    quantity is split across SWP / DWP / WPC by average-price band (same
    exact-residual algorithm as ``auto_plan_shared.optimal_milk_split``,
    ported to Decimal so the reporting waterfalls stay Decimal-exact).
    When ``average_split`` is disabled (E1), "both present" simply runs
    the 0404 branch followed by the 3502 branch — E1 has no average-price
    concept at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR

from apps.license.services.planning_allocation import allocate_step, d


@dataclass(frozen=True)
class MilkConfig:
    dwp_price: Decimal
    swp_price: Decimal
    wpc_price: Decimal          # single-source (0404-only or 3502-only) WPC ceiling
    mixed_wpc_price: Decimal    # WPC ceiling used only inside the avg-price band split
    average_split: bool         # True → "both present" uses avg-price banding (E5)


MILK_CONFIG_E1 = MilkConfig(
    dwp_price=Decimal('5'),
    swp_price=Decimal('1.5'),
    wpc_price=Decimal('25'),
    mixed_wpc_price=Decimal('25'),  # unused — E1 never takes the banded path
    average_split=False,
)

MILK_CONFIG_E5 = MilkConfig(
    dwp_price=Decimal('5'),
    swp_price=Decimal('1.5'),
    wpc_price=Decimal('25'),
    mixed_wpc_price=Decimal('20'),
    average_split=True,
)


def _zero_result(config: MilkConfig) -> dict[str, Decimal]:
    return {'DWP': Decimal('0'), 'SWP': Decimal('0'), 'WPC': Decimal('0')}


def _band_split(
    total_qty: Decimal,
    remaining: Decimal,
    config: MilkConfig,
) -> tuple[dict[str, Decimal], dict[str, Decimal], Decimal]:
    """Average-price banded split — exact-residual port of
    ``auto_plan_shared.optimal_milk_split``, in Decimal CIF terms.

    Maximises quantity utilised while leaving the balance at exactly $0,
    except in the top band (avg ≥ mixed_wpc_price) where WPC absorbs the
    full quantity and any balance surplus flows back to the caller.
    """
    planned = _zero_result(config)
    rate = {'DWP': config.dwp_price, 'SWP': config.swp_price, 'WPC': config.mixed_wpc_price}
    if total_qty <= 0 or remaining <= 0:
        return planned, rate, remaining

    swp_p, dwp_p, wpc_p = config.swp_price, config.dwp_price, config.mixed_wpc_price
    avg = remaining / total_qty

    if avg < swp_p:
        # Only SWP is affordable; fractional qty absorbs the exact balance.
        planned['SWP'] = remaining
        return planned, rate, Decimal('0')

    if avg < dwp_p:
        # SWP (integer, maximised) + DWP (fractional residual → balance = 0).
        q_swp = ((dwp_p * total_qty - remaining) / (dwp_p - swp_p)).to_integral_value(rounding=ROUND_FLOOR)
        cif_swp = q_swp * swp_p
        planned['SWP'] = cif_swp
        planned['DWP'] = remaining - cif_swp
        return planned, rate, Decimal('0')

    if avg < wpc_p:
        # DWP (integer, maximised) + WPC (fractional residual → balance = 0).
        q_dwp = ((wpc_p * total_qty - remaining) / (wpc_p - dwp_p)).to_integral_value(rounding=ROUND_FLOOR)
        cif_dwp = q_dwp * dwp_p
        planned['DWP'] = cif_dwp
        planned['WPC'] = remaining - cif_dwp
        return planned, rate, Decimal('0')

    # avg >= wpc_p: full qty at WPC; any balance surplus flows back to the caller.
    cif_wpc = total_qty * wpc_p
    planned['WPC'] = cif_wpc
    return planned, rate, remaining - cif_wpc


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
        config: :data:`MILK_CONFIG_E1` or :data:`MILK_CONFIG_E5`.

    Returns:
        (planned_cif, rate, remaining_balance) — `planned_cif` / `rate` are
        keyed 'DWP' / 'SWP' / 'WPC' (all three keys always present, zero
        when unused).
    """
    qty_0404 = d(qty_0404)
    qty_3502 = d(qty_3502)
    remaining = d(remaining_balance)

    has_0404 = qty_0404 > 0
    has_3502 = qty_3502 > 0

    if has_0404 and has_3502 and config.average_split:
        return _band_split(qty_0404 + qty_3502, remaining, config)

    planned = _zero_result(config)
    rate = {'DWP': config.dwp_price, 'SWP': config.swp_price, 'WPC': config.wpc_price}

    if has_0404:
        dwp_used, dwp_rate = allocate_step(qty_0404, config.dwp_price, remaining)
        planned['DWP'] = dwp_used
        rate['DWP'] = dwp_rate
        remaining -= dwp_used

        swp_used, swp_rate = allocate_step(qty_0404, config.swp_price, remaining)
        planned['SWP'] = swp_used
        rate['SWP'] = swp_rate
        remaining -= swp_used

    if has_3502:
        wpc_used, wpc_rate = allocate_step(qty_3502, config.wpc_price, remaining)
        planned['WPC'] += wpc_used
        rate['WPC'] = wpc_rate
        remaining -= wpc_used

    return planned, rate, remaining
