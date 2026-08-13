"""
Canonical per-licence PROFIT definition — the single source of the
"Profit / Loss" figure for a DFIA licence.

Extracted verbatim (same filters, same fields, same Decimal discipline) from
`apps.license.services.purchase_profit_report`, which is now a consumer of this
module rather than a second implementation of the same maths.

THE DEFINITION
--------------
For one DFIA licence (`LicenseDetailsModel`):

    purchase_amount = Σ LicenseTradeLine.amount_inr   (INR)
    purchase_usd    = Σ LicenseTradeLine.cif_fc       (USD / foreign-currency CIF)
        over lines with
            sr_number__license_id      = <licence>
            trade__direction           = LicenseTrade.DIR_PURCHASE
            trade__linked_trade__isnull = True

    sale_amount     = Σ LicenseTradeLine.amount_inr   (INR)
    sale_usd        = Σ LicenseTradeLine.cif_fc       (USD)
        over lines with the same licence filter but
            trade__direction           = LicenseTrade.DIR_SALE
            trade__linked_trade__isnull = True

    profit_loss     = sale_amount − purchase_amount   (INR)

**Currency:** `profit_loss` is INR (`amount_inr`). It is NOT the same currency as
the licence ledger balance, which is CIF USD for DFIA. Never add the two.

WHY `linked_trade__isnull=True`
-------------------------------
`LicenseTrade.linked_trade` is set on BOTH legs of an auto-created paired
counterpart (see `apps.trade.serializers`'s `auto_create_paired` flow) — an
internal transfer between two of the business's own companies, not a genuine
external market purchase or sale. Both legs are excluded so an internal shuffle
never shows up as profit or as an acquisition cost.

NOT THE SAME FIGURE AS THE LICENSE LEDGER'S "PROFIT / LOSS" CARD
---------------------------------------------------------------
Two different questions, deliberately answered by two different modules:

  * THIS module — REALISED TRADING MARGIN, in **INR**: what the business made
    selling the licence versus what it paid for it. Excludes internal
    linked/mirror legs (see below). Consumer: the Purchase & Profit report.
  * The License Ledger `summary` — UNUTILISED POSITION, in the licence's own
    currency (**USD** CIF for DFIA): licence value acquired minus licence value
    consumed, summed from the rows on screen. Includes every trade for the
    licence by direction, and sums `cif_fc`, not `amount_inr`. Computed in
    `canonical_ledger_service._build_summary` as the single value it publishes
    as BOTH `current_balance` and `total_profit_loss`.

They use different populations, different columns and different currencies, so
they are NOT expected to match and must never be compared or added. Each is
defined exactly once, in the module that owns it. Do not "reconcile" them by
making one call the other — that would silently redefine one screen's meaning.

SCOPE: THE MONEY DEFINITIONS ARE DFIA ONLY
------------------------------------------
(The `first_purchase_date` definition further down covers BOTH licence families
— see `incentive_first_purchase_date_by_license`. Everything in this section is
about the profit/purchase/sale AMOUNTS.)

The licence is reached through `LicenseTradeLine.sr_number__license_id`, i.e.
`LicenseImportItemsModel.license` → `LicenseDetailsModel`. Incentive licences
(`IncentiveLicense`, RODTEP/ROSTL/MEIS) are traded through `IncentiveTradeLine`,
which has NO `cif_fc` column and no link to `LicenseImportItemsModel`, so this
definition does not apply to them at all. `LicenseDetailsModel.id` and
`IncentiveLicense.id` are separate sequences, so passing an incentive licence id
here would silently return an unrelated DFIA licence's money. Callers MUST
confirm the licence is DFIA before calling, and must report "not applicable"
rather than fabricating a figure for an incentive licence.

ROUNDING DISCIPLINE
-------------------
Everything returned here is a RAW, UNQUANTIZED `Decimal` straight off the SQL
`SUM()`. Callers building grand totals must sum these raw Decimals and quantize
ONCE at the end — never quantize per row and add the rounded values. `_q2`
lives in `purchase_profit_report` and in `canonical_ledger_service`; this module
deliberately does no rounding of its own.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List

from django.db.models import DecimalField, Min, Sum, Value
from django.db.models.functions import Coalesce

from apps.core.constants import DEC_0
from apps.trade.models import LicenseTrade, LicenseTradeLine

__all__ = [
    "PURCHASE_LINE_FILTERS",
    "SALE_LINE_FILTERS",
    "EMPTY_PROFIT",
    "purchase_lines_ordered",
    "sale_totals_by_license",
    "profit_for_licenses",
    "profit_for_license",
    "first_purchase_by_license",
    "first_purchase_date_by_license",
    "first_purchase_date_for_license",
    "incentive_first_purchase_date_by_license",
]


#: The ONE definition of "a qualifying external PURCHASE trade line".
#: Shared by this module and by `purchase_profit_report` so the two can never
#: drift apart. Combine with `sr_number__license_id__in=<ids>`.
PURCHASE_LINE_FILTERS: Dict[str, Any] = {
    "trade__direction": LicenseTrade.DIR_PURCHASE,
    "trade__linked_trade__isnull": True,
}

#: The ONE definition of "a qualifying external SALE trade line" (the disposal-
#: side counterpart of `PURCHASE_LINE_FILTERS`).
SALE_LINE_FILTERS: Dict[str, Any] = {
    "trade__direction": LicenseTrade.DIR_SALE,
    "trade__linked_trade__isnull": True,
}


def _empty_profit() -> Dict[str, Decimal]:
    """A fresh all-zero profit record (fresh dict — callers may mutate)."""
    return {
        "purchase_amount": DEC_0,
        "purchase_usd": DEC_0,
        "sale_amount": DEC_0,
        "sale_usd": DEC_0,
        "profit_loss": DEC_0,
    }


#: Read-only reference for callers that want the shape without allocating.
EMPTY_PROFIT: Dict[str, Decimal] = _empty_profit()


def _clean_ids(license_ids: Iterable[int]) -> List[int]:
    return [lid for lid in dict.fromkeys(license_ids or []) if lid]


def purchase_lines_ordered(license_ids: Iterable[int]):
    """
    The canonical qualifying-PURCHASE trade lines for `license_ids`, ordered by
    ``(license_id, trade invoice_date, trade_id)`` and returned as a
    non-aggregated ``.values()`` queryset.

    This is the query `purchase_profit_report` iterates: the ordering means the
    FIRST row seen per licence IS its earliest qualifying purchase, which is
    where that report gets "first purchase date" and "Purchase From" without a
    second query. It lives here so the *filters* are defined exactly once, next
    to the money definition they belong to.

    Returns rows with keys: ``sr_number__license_id``, ``trade_id``,
    ``trade__invoice_date``, ``trade__from_company__name``, ``amount_inr``,
    ``cif_fc``.
    """
    return (
        LicenseTradeLine.objects.filter(
            sr_number__license_id__in=list(license_ids or []),
            **PURCHASE_LINE_FILTERS,
        )
        .order_by("sr_number__license_id", "trade__invoice_date", "trade_id")
        .values(
            "sr_number__license_id",
            "trade_id",
            "trade__invoice_date",
            "trade__from_company__name",
            "amount_inr",
            "cif_fc",
        )
    )


# ---------------------------------------------------------------------------
# FIRST PURCHASE DATE — the canonical per-licence acquisition date
#
# THE DEFINITION (one sentence, one place):
#
#     first_purchase_date(licence) = MIN(trade.invoice_date)
#                                    over lines matching PURCHASE_LINE_FILTERS
#
# i.e. the earliest QUALIFYING (external, non-linked) purchase invoice date. For
# a licence purchased on 16-Dec-2025, 17-Jan-2026 and 13-Feb-2026 that is
# 16-Dec-2025 — the licence "belongs to" the date it was first acquired, and
# later top-up purchases never move it.
#
# `None` when the licence has no qualifying purchase, or when every qualifying
# purchase has a NULL invoice_date. A `None` licence is NOT in any purchase-date
# range — it has no acquisition date to compare — so date filters must EXCLUDE
# it rather than treat it as an open bound.
#
# TWO ACCESS PATHS, ONE DEFINITION
# --------------------------------
# Both read `PURCHASE_LINE_FILTERS`, so "what counts as a qualifying purchase"
# exists exactly once. They differ only in how the rows are reached, because the
# two call shapes have opposite cost profiles:
#
#   * `first_purchase_by_license(rows)` — a pure-Python fold over rows the caller
#     ALREADY has from `purchase_lines_ordered` (the Purchase & Profit report
#     needs every line anyway for its sums). Costs ZERO extra queries, and also
#     yields "Purchase From" from that same first row.
#   * `first_purchase_date_by_license(ids)` — a SQL `MIN()` aggregate for callers
#     that want ONLY the date over a potentially large id set (the ledger list
#     filter, the ledger detail DTO). Streaming every purchase line just to take
#     a minimum would be wasteful there.
#
# `test_first_purchase_date_both_paths_agree` locks the two together.
#
# NULL ORDERING NOTE: the fold relies on `purchase_lines_ordered`'s
# `ORDER BY trade__invoice_date ASC`, which on PostgreSQL sorts NULLs LAST — so
# the first row seen carries the earliest NON-NULL date, exactly what `MIN()`
# returns (SQL `MIN` ignores NULLs). The two agree including the all-NULL case,
# where both yield `None`.
# ---------------------------------------------------------------------------


def first_purchase_by_license(purchase_rows) -> Dict[int, Dict[str, Any]]:
    """
    Fold ordered purchase rows into
    ``{license_id: {'first_purchase_date': date|None, 'purchase_from': str}}``.

    Args:
        purchase_rows: rows from `purchase_lines_ordered` — MUST retain that
            function's ``(license_id, invoice_date, trade_id)`` ordering, because
            "the first row seen per licence" is what makes this the *earliest*
            qualifying purchase.

    Costs no query of its own. Licences absent from `purchase_rows` are absent
    from the result (they have no qualifying purchase).
    """
    first: Dict[int, Dict[str, Any]] = {}
    for row in purchase_rows:
        lid = row["sr_number__license_id"]
        if lid in first:
            continue
        # First row for this licence, given the ordering, IS its earliest
        # qualifying purchase — so this row also supplies "Purchase From".
        first[lid] = {
            "first_purchase_date": row["trade__invoice_date"],
            "purchase_from": row["trade__from_company__name"] or "",
        }
    return first


def first_purchase_date_by_license(license_ids: Iterable[int]) -> Dict[int, Any]:
    """
    ``{license_id: first_purchase_date}`` in ONE grouped SQL query, for any
    number of licences.

    Licences with no qualifying purchase — and licences whose every qualifying
    purchase has a NULL invoice_date — are ABSENT from the map (never mapped to
    `None`, and never zero-filled), so a caller iterating the result only ever
    sees real acquisition dates. Callers needing "has no first purchase date"
    should test membership.
    """
    ids = _clean_ids(license_ids)
    if not ids:
        return {}
    rows = (
        LicenseTradeLine.objects.filter(
            sr_number__license_id__in=ids,
            **PURCHASE_LINE_FILTERS,
        )
        .values("sr_number__license_id")
        .annotate(first_purchase_date=Min("trade__invoice_date"))
    )
    return {
        row["sr_number__license_id"]: row["first_purchase_date"]
        for row in rows
        # MIN() is NULL only when every qualifying purchase has a NULL
        # invoice_date. That licence has no usable acquisition date, so it is
        # omitted rather than published as a null.
        if row["first_purchase_date"] is not None
    }


def first_purchase_date_for_license(license_id: int) -> Any:
    """
    `first_purchase_date` for one DFIA licence, or ``None`` when it has none.

    Still ONE query. DFIA only — see the module docstring's SCOPE section.
    """
    if not license_id:
        return None
    return first_purchase_date_by_license([license_id]).get(license_id)


def incentive_first_purchase_date_by_license(license_ids: Iterable[int]) -> Dict[int, Any]:
    """
    The INCENTIVE-licence counterpart of `first_purchase_date_by_license`:
    ``{incentive_license_id: first_purchase_date}`` in ONE grouped query.

    SAME RULE, DIFFERENT RELATION. The rule is identical — earliest invoice date
    among qualifying (external, non-linked) PURCHASE trades — but an incentive
    licence is reached through `IncentiveTradeLine.incentive_license_id` instead
    of `LicenseTradeLine.sr_number__license_id`, so the two cannot share one
    queryset. The FILTER SEMANTICS are read from `PURCHASE_LINE_FILTERS` rather
    than restated, so "qualifying purchase" still means one thing system-wide.

    ⚠ `LicenseDetailsModel.id` and `IncentiveLicense.id` are INDEPENDENT
    sequences — passing DFIA ids here (or incentive ids to the DFIA function)
    silently returns another licence's dates. Callers must know which family
    they hold.

    Licences with no qualifying purchase, or whose every qualifying purchase has
    a NULL invoice_date, are ABSENT from the map (see the DFIA function).
    """
    from apps.trade.models import IncentiveTradeLine

    ids = _clean_ids(license_ids)
    if not ids:
        return {}
    rows = (
        IncentiveTradeLine.objects.filter(
            incentive_license_id__in=ids,
            **PURCHASE_LINE_FILTERS,
        )
        .values("incentive_license_id")
        .annotate(first_purchase_date=Min("trade__invoice_date"))
    )
    return {
        row["incentive_license_id"]: row["first_purchase_date"]
        for row in rows
        if row["first_purchase_date"] is not None
    }


def sale_totals_by_license(license_ids: Iterable[int]) -> Dict[int, Dict[str, Decimal]]:
    """
    ``{license_id: {'sale_amount': Decimal, 'sale_usd': Decimal}}`` in ONE bulk
    query (grouped by licence). Licences with no qualifying SALE line are simply
    absent from the map; callers default to `DEC_0`.

    Raw unquantized Decimals — see the module docstring's rounding discipline.
    """
    ids = list(license_ids or [])
    if not ids:
        return {}
    rows = (
        LicenseTradeLine.objects.filter(
            sr_number__license_id__in=ids,
            **SALE_LINE_FILTERS,
        )
        .values("sr_number__license_id")
        .annotate(
            sale_amount=Coalesce(Sum("amount_inr"), Value(DEC_0), output_field=DecimalField()),
            sale_usd=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()),
        )
    )
    return {
        row["sr_number__license_id"]: {
            "sale_amount": row["sale_amount"],
            "sale_usd": row["sale_usd"],
        }
        for row in rows
    }


def profit_for_licenses(license_ids: Iterable[int]) -> Dict[int, Dict[str, Decimal]]:
    """
    Bulk per-licence profit. ONE query for any number of licences — never a
    per-licence DB hit.

    Args:
        license_ids: `LicenseDetailsModel` (DFIA) ids. See the module docstring:
            passing an `IncentiveLicense` id is a caller bug, not something this
            function can detect.

    Returns:
        ``{license_id: {'purchase_amount', 'purchase_usd', 'sale_amount',
        'sale_usd', 'profit_loss'}}`` — every value a raw, unquantized
        `Decimal`. EVERY requested id is present, zero-filled when the licence
        has no qualifying trade lines, so callers never need `.get(..., DEC_0)`.

    Implementation note: purchases and sales are fetched in a SINGLE query
    grouped by ``(license_id, direction)`` rather than two direction-filtered
    aggregates. The row population is identical to running
    `PURCHASE_LINE_FILTERS` and `SALE_LINE_FILTERS` separately — the only
    difference is `direction` moves from the WHERE clause into the GROUP BY.
    """
    ids = _clean_ids(license_ids)
    result: Dict[int, Dict[str, Decimal]] = {lid: _empty_profit() for lid in ids}
    if not ids:
        return result

    rows = (
        LicenseTradeLine.objects.filter(
            sr_number__license_id__in=ids,
            trade__direction__in=(LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_SALE),
            trade__linked_trade__isnull=True,
        )
        .values("sr_number__license_id", "trade__direction")
        .annotate(
            amount=Coalesce(Sum("amount_inr"), Value(DEC_0), output_field=DecimalField()),
            usd=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()),
        )
    )

    for row in rows:
        entry = result.get(row["sr_number__license_id"])
        if entry is None:  # pragma: no cover — defensive; ids came from the filter
            continue
        if row["trade__direction"] == LicenseTrade.DIR_PURCHASE:
            entry["purchase_amount"] = row["amount"] or DEC_0
            entry["purchase_usd"] = row["usd"] or DEC_0
        else:
            entry["sale_amount"] = row["amount"] or DEC_0
            entry["sale_usd"] = row["usd"] or DEC_0

    for entry in result.values():
        # THE definition. Raw Decimal subtraction, quantized by the caller once.
        entry["profit_loss"] = entry["sale_amount"] - entry["purchase_amount"]

    return result


def profit_for_license(license_id: int) -> Dict[str, Decimal]:
    """Thin single-licence wrapper around `profit_for_licenses` (still 1 query).

    An unknown/falsy id yields the all-zero record rather than raising.
    """
    return profit_for_licenses([license_id]).get(license_id) or _empty_profit()
