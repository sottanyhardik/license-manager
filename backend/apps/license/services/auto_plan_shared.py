"""
Shared helpers for E1 / E5 / future Auto Plan services.

Keeping the optimization logic here means a single change propagates to all
norms automatically — no duplicated code to drift out of sync.
"""
from __future__ import annotations

import math


def optimal_milk_split(
    total_qty: float,
    remaining_cif: float,
) -> tuple[float, float, float]:
    """
    Exact-residual optimization for Milk & Milk planning.

    Finds the combination of SWP / DWP / WPC that:
      1. Maximises quantity utilised  (subject to total_qty constraint)
      2. Leaves Remaining CIF = $0.00 (the "residual" product absorbs the exact
         leftover CIF with 3 dp fractional precision)
      3. Prefers cheaper base + expensive residual (maximises qty first)

    Algorithm
    ---------
    Divide the available qty/CIF space into avg-price bands and solve
    analytically — no iteration needed.

      avg = remaining_cif / total_qty

      avg < 1.50        SWP only;  qty = C / 1.50  (fractional)
      1.50 ≤ avg < 5    SWP (int, maximised) + DWP (fractional residual)
      5    ≤ avg < 20   DWP (int, maximised) + WPC (fractional residual)
      avg ≥ 20          WPC at full qty; surplus CIF flows to the caller

    Maximisation formula for a two-product band (SWP+DWP example):
        q_base     = FLOOR((p_high × Q − C) / (p_high − p_low))
        q_residual = (C − q_base × p_low) / p_high   ← exact, 3 dp

    Returns
    -------
    (q_swp, q_dwp, q_wpc) — non-negative floats, each rounded to 3 dp.
    The caller is responsible for mapping these to the norm-specific item
    names (e.g. "SWP - E1" vs "SWP - E5").
    """
    if total_qty <= 0 or remaining_cif <= 0:
        return 0.0, 0.0, 0.0

    Q = total_qty
    C = remaining_cif
    avg = C / Q

    if avg < 1.50:
        # Only SWP is affordable; fractional qty absorbs the exact CIF.
        return round(C / 1.50, 3), 0.0, 0.0

    if avg < 5.00:
        # SWP (integer, maximised) + DWP (fractional residual → CIF = 0)
        q_swp = float(math.floor((5.0 * Q - C) / 3.50))
        q_dwp = round((C - q_swp * 1.50) / 5.00, 3)
        return q_swp, q_dwp, 0.0

    if avg < 20.00:
        # DWP (integer, maximised) + WPC (fractional residual → CIF = 0)
        q_dwp = float(math.floor((20.0 * Q - C) / 15.00))
        q_wpc = round((C - q_dwp * 5.00) / 20.00, 3)
        return 0.0, q_dwp, q_wpc

    # avg ≥ 20: use all qty at WPC; surplus CIF (C − Q×20) flows to the
    # next planning rule (e.g. wheat flour mop-up in E5).
    return 0.0, 0.0, float(Q)
