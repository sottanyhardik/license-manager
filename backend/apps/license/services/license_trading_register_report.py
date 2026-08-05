"""
License Trading Register & Profit Report — service layer.

Consolidates every purchase/sale invoice line recorded against a DFIA
license's traded items (`apps.trade.models.LicenseTrade`/`LicenseTradeLine`)
into one reconciling hierarchy:

    Dashboard -> Norm -> License -> Transaction Register -> License Summary
    -> License Item Summary -> Norm Summary -> Norm Item Summary
    -> Grand Summary -> Grand Item Summary

Scope decisions (approved plan, `prancy-munching-cake.md`):

1. **v1 covers DFIA-type `LicenseTrade` rows only** (`license_type="DFIA"`).
   Incentive-scheme trades have no SION norm / import-item structure and
   don't fit this hierarchy. A non-"DFIA" `license_type` param returns an
   empty report rather than an error, to stay resilient to arbitrary
   querystrings.
2. **`COMMISSION_PURCHASE`/`COMMISSION_SALE` trades are excluded** from the
   register and every total — they are agent-commission invoices, not
   genuine license value movement. Only `direction in (PURCHASE, SALE)`.
3. **The date filter scopes the whole register** (both purchase and sale
   sides) — unlike the sibling `purchase_profit_report.py`, which
   deliberately left `LicensePurchase` unscoped.
4. **Customer/Supplier filters are role-specific**: Supplier =
   `trade.from_company` narrows PURCHASE rows only; Customer =
   `trade.to_company` narrows SALE rows only. Rows on the *other* direction
   pass through untouched, so the opposite side of the register (needed for
   the profit calc) survives.
5. **Item/Norm/Customer/Supplier filters narrow the Transaction Register
   itself**, and every summary level rolls up from that same filtered row
   set — this is what makes "every total reconciles exactly" achievable by
   construction rather than by independent re-aggregation.
6. A `LicenseTradeLine` whose `sr_number` has multiple `items` (M2M) is
   labeled with the joined item names as ONE row (e.g. "WPC, SWP"),
   matching `ledger_pdf.py::build_dfia_ledger_detail`'s convention —
   preserves exact partition identity between the Transaction Register and
   the Item Summary.
7. The norm a license is bucketed under comes from the SION norm class of
   the *traded items* themselves (`ItemNameModel.sion_norm_class`), the same
   source `build_dfia_ledger_detail` uses for its `sion_norms` column — NOT
   from the license's own export-item norm_class (which is what the sibling
   Purchase & Profit report uses). A license whose traded items carry more
   than one distinct norm is bucketed under the joined, sorted set of those
   norms (e.g. "E1, E5"); a license with no norm-classified items lands in
   the "No Norm" catch-all bucket rather than being dropped.

Rounding: `_q2`/`_q3`/`_pct` mirror `purchase_profit_report.py` exactly
(`ROUND_HALF_UP`, Decimal end-to-end, `float()` only at final
serialization). `LicenseTradeLine.amount_inr` already carries exactly 2
decimal places at the DB level, so summing it and re-quantizing to 2 places
is idempotent — no rounding error is introduced when rolling item summaries
up into license/norm/grand totals, which is what guarantees the
reconciliation chain the spec requires.

`margin_pct` at every level is profit as a percentage of the **sale** value
(the conventional gross-margin definition), not of purchase cost — distinct
from the sibling report's `profit_pct`, which is profit over cost (markup).
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Q

from apps.core.constants import DEC_0, DEC_000
from apps.license.models import LicenseDetailsModel
from apps.trade.models import LicenseTrade, LicenseTradeLine

NO_NORM = "No Norm"

TWO_PLACES = Decimal("0.01")
THREE_PLACES = Decimal("0.001")
HUNDRED = Decimal("100")


def _q2(value) -> Decimal:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _q3(value) -> Decimal:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(THREE_PLACES, rounding=ROUND_HALF_UP)


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if not denominator:
        return DEC_0
    return _q2((numerator / denominator) * HUNDRED)


def _empty_report() -> Dict[str, Any]:
    return {
        "dashboard": {
            "total_licenses": 0,
            "open_licenses": 0,
            "closed_licenses": 0,
            "total_purchase": 0.0,
            "total_sale": 0.0,
            "total_profit": 0.0,
            "overall_margin_pct": 0.0,
        },
        "norms": [],
        "grand_summary": {
            "licenses_count": 0,
            "purchase": 0.0,
            "sale": 0.0,
            "profit": 0.0,
            "margin_pct": 0.0,
        },
        "grand_item_summary": [],
    }


def _status(purchase: Decimal, sale: Decimal) -> str:
    """'Closed' once the license's sale value has caught up with (or passed)
    its purchase value; 'Open' while purchase still exceeds sale. The
    boundary purchase == sale is Closed."""
    return "Closed" if sale >= purchase else "Open"


# ---------------------------------------------------------------------------
# License / trade-line selection
# ---------------------------------------------------------------------------

def _base_license_ids(
    license_number: Optional[str],
    exporter_id: Optional[int],
    customer_id: Optional[int],
    supplier_id: Optional[int],
) -> Optional[List[int]]:
    """
    Pre-filter candidate license ids before the bulk trade-line fetch.

    Returns ``None`` when no filter narrows the set at all — the caller then
    skips the `license_id__in` clause entirely (every DFIA license with a
    matching trade line in the date window is in scope). Returns a
    (possibly empty) list otherwise.
    """
    if not (license_number or exporter_id or customer_id or supplier_id):
        return None

    qs = LicenseDetailsModel.objects.all()
    if exporter_id:
        qs = qs.filter(exporter_id=exporter_id)
    if license_number:
        qs = qs.filter(license_number__icontains=license_number)
    if supplier_id:
        qs = qs.filter(
            import_license__trade_lines__trade__direction=LicenseTrade.DIR_PURCHASE,
            import_license__trade_lines__trade__from_company_id=supplier_id,
        )
    if customer_id:
        qs = qs.filter(
            import_license__trade_lines__trade__direction=LicenseTrade.DIR_SALE,
            import_license__trade_lines__trade__to_company_id=customer_id,
        )
    # The reverse-M2O joins above can multiply-match; distinct() collapses
    # back to one id per license.
    return list(qs.distinct().values_list("id", flat=True))


def _base_trade_line_queryset(from_date, to_date, license_ids: Optional[List[int]], customer_id, supplier_id):
    qs = (
        LicenseTradeLine.objects
        .filter(
            trade__license_type=LicenseTrade.LICENSE_TYPE_DFIA,
            trade__direction__in=[LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_SALE],
            trade__invoice_date__range=(from_date, to_date),
        )
        .select_related(
            "trade", "trade__from_company", "trade__to_company",
            "sr_number", "sr_number__license", "sr_number__license__exporter",
        )
        .prefetch_related("sr_number__items__sion_norm_class")
        .order_by("trade__invoice_date", "trade_id")
    )
    if license_ids is not None:
        qs = qs.filter(sr_number__license_id__in=license_ids)

    # Role-specific narrowing (scope decision 4): each filter constrains
    # only the direction it actually governs. Rows on the other direction
    # pass through untouched so the opposite side of the register (needed
    # for the profit calc) survives.
    if supplier_id:
        qs = qs.filter(
            ~Q(trade__direction=LicenseTrade.DIR_PURCHASE)
            | Q(trade__direction=LicenseTrade.DIR_PURCHASE, trade__from_company_id=supplier_id)
        )
    if customer_id:
        qs = qs.filter(
            ~Q(trade__direction=LicenseTrade.DIR_SALE)
            | Q(trade__direction=LicenseTrade.DIR_SALE, trade__to_company_id=customer_id)
        )
    return qs


# ---------------------------------------------------------------------------
# Per-line helpers (no DB round-trips — operate on already-prefetched data)
# ---------------------------------------------------------------------------

def _line_items(line) -> List[Any]:
    return list(line.sr_number.items.all())


def _line_item_label(line) -> str:
    items = _line_items(line)
    if not items:
        return line.sr_number.description or "-"
    names = [it.name for it in items]
    return ", ".join(names) if names else "-"


def _line_item_ids(line) -> set:
    return {it.id for it in _line_items(line)}


def _line_norms(line) -> List[str]:
    """Distinct SION norm codes carried by this line's traded item(s),
    in first-seen order."""
    norms: List[str] = []
    for it in _line_items(line):
        if it.sion_norm_class_id and it.sion_norm_class.norm_class not in norms:
            norms.append(it.sion_norm_class.norm_class)
    return norms


def _license_norm_label(rows: List[dict]) -> str:
    norms: set = set()
    for row in rows:
        norms.update(row["norms"])
    return ", ".join(sorted(norms)) if norms else NO_NORM


# ---------------------------------------------------------------------------
# Transaction register / item-summary builders
# ---------------------------------------------------------------------------

def _build_transaction_register(txn_rows: List[dict]) -> Tuple[List[dict], Decimal, Decimal]:
    """
    Chronological register for one license: sorted (invoice_date,
    direction != PURCHASE) so purchases tie-break before sales on the same
    date — the same convention as `ledger_pdf.build_dfia_ledger_detail`.
    Single forward pass accumulating running purchase/sale/profit.
    """
    ordered = sorted(txn_rows, key=lambda r: (r["date"], r["direction"] != LicenseTrade.DIR_PURCHASE))

    register: List[dict] = []
    running_purchase = DEC_0
    running_sale = DEC_0
    for row in ordered:
        running_purchase += row["purchase"]
        running_sale += row["sale"]
        running_profit = _q2(running_sale - running_purchase)
        register.append({
            "date": row["date"].isoformat() if row["date"] else None,
            "direction": row["direction"],
            "invoice_number": row["invoice_number"],
            "from_company": row["from_company"],
            "to_company": row["to_company"],
            "item": row["item"],
            "purchase": float(_q2(row["purchase"])),
            "sale": float(_q2(row["sale"])),
            "running_profit": float(running_profit),
        })
    return register, _q2(running_purchase), _q2(running_sale)


def _build_license_item_summary(txn_rows: List[dict]) -> List[dict]:
    """Groups the SAME txn_rows already used for the register (not a second
    query) into a defaultdict keyed by item label."""
    buckets: Dict[str, Dict[str, Decimal]] = defaultdict(
        lambda: {"purchase_qty": DEC_000, "sale_qty": DEC_000, "purchase_value": DEC_0, "sale_value": DEC_0}
    )
    for row in txn_rows:
        b = buckets[row["item"]]
        if row["direction"] == LicenseTrade.DIR_PURCHASE:
            b["purchase_qty"] += row["qty"]
            b["purchase_value"] += row["purchase"]
        else:
            b["sale_qty"] += row["qty"]
            b["sale_value"] += row["sale"]

    result = []
    for item in sorted(buckets.keys()):
        b = buckets[item]
        purchase_value = _q2(b["purchase_value"])
        sale_value = _q2(b["sale_value"])
        profit = _q2(sale_value - purchase_value)
        result.append({
            "item": item,
            "purchase_qty": float(_q3(b["purchase_qty"])),
            "sale_qty": float(_q3(b["sale_qty"])),
            "purchase_value": float(purchase_value),
            "sale_value": float(sale_value),
            "profit": float(profit),
            "margin_pct": float(_pct(profit, sale_value)),
        })
    return result


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def build_license_trading_register_report(
    from_date,
    to_date,
    norm: str = "All",
    license_type: str = "DFIA",
    license_number: Optional[str] = None,
    exporter_id: Optional[int] = None,
    item_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
) -> Dict[str, Any]:
    if license_type != LicenseTrade.LICENSE_TYPE_DFIA:
        # Scope decision 1: accept the param but stay resilient to
        # arbitrary querystrings rather than erroring.
        return _empty_report()

    license_ids = _base_license_ids(license_number, exporter_id, customer_id, supplier_id)
    if license_ids is not None and not license_ids:
        return _empty_report()

    lines_qs = _base_trade_line_queryset(from_date, to_date, license_ids, customer_id, supplier_id)

    apply_norm_filter = norm not in (None, "", "All")

    # --- Single bulk pass: filter (item/norm) + group by license ----------
    grouped: Dict[int, List[dict]] = defaultdict(list)
    license_meta: Dict[int, Tuple[str, str]] = {}

    for line in lines_qs:
        item_ids = _line_item_ids(line)
        if item_id and item_id not in item_ids:
            continue

        norms = _line_norms(line)
        if apply_norm_filter and norm not in norms:
            continue

        lic = line.sr_number.license
        lic_id = lic.id
        if lic_id not in license_meta:
            exporter_name = (lic.exporter.name if lic.exporter_id else "") or ""
            license_meta[lic_id] = (lic.license_number, exporter_name)

        direction = line.trade.direction
        amount = line.amount_inr if line.amount_inr is not None else DEC_0
        qty = line.qty_kg if line.qty_kg is not None else DEC_000

        grouped[lic_id].append({
            "date": line.trade.invoice_date,
            "direction": direction,
            "invoice_number": line.trade.invoice_number or "",
            "from_company": line.trade.from_company.name if line.trade.from_company_id else "",
            "to_company": line.trade.to_company.name if line.trade.to_company_id else "",
            "item": _line_item_label(line),
            "norms": norms,
            "purchase": amount if direction == LicenseTrade.DIR_PURCHASE else DEC_0,
            "sale": amount if direction == LicenseTrade.DIR_SALE else DEC_0,
            "qty": qty,
        })

    if not grouped:
        return _empty_report()

    # --- Per-license blocks, bucketed by norm ------------------------------
    licenses_by_norm: Dict[str, List[dict]] = defaultdict(list)
    license_decimals: Dict[int, Dict[str, Decimal]] = {}

    for lic_id, rows in grouped.items():
        license_number_val, exporter_name = license_meta[lic_id]
        register, purchase, sale = _build_transaction_register(rows)
        item_summary = _build_license_item_summary(rows)
        profit = _q2(sale - purchase)
        margin_pct = _pct(profit, sale)
        status = _status(purchase, sale)

        license_decimals[lic_id] = {"purchase": purchase, "sale": sale, "profit": profit}

        block = {
            "license_id": lic_id,
            "license_number": license_number_val,
            "exporter": exporter_name,
            "transactions": register,
            "summary": {
                "purchase": float(purchase),
                "sale": float(sale),
                "profit": float(profit),
                "margin_pct": float(margin_pct),
                "status": status,
            },
            "item_summary": item_summary,
        }
        licenses_by_norm[_license_norm_label(rows)].append(block)

    # --- Per-norm summaries + grand summary --------------------------------
    norms_output: List[dict] = []
    grand_purchase = DEC_0
    grand_sale = DEC_0
    grand_profit = DEC_0
    grand_licenses_count = 0
    grand_open = 0
    grand_closed = 0
    # Keyed by (norm_label, item) so every row stays a refinement of its
    # norm's item bucket — summing it reconciles to both the norm level and
    # (across all norms) the grand level, by construction.
    grand_item_totals: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
        lambda: {"licenses": set(), "purchase_qty": DEC_000, "sale_qty": DEC_000,
                 "purchase_value": DEC_0, "sale_value": DEC_0}
    )

    for norm_label in sorted(licenses_by_norm.keys()):
        blocks = sorted(licenses_by_norm[norm_label], key=lambda b: b["license_number"])

        norm_purchase = sum((license_decimals[b["license_id"]]["purchase"] for b in blocks), DEC_0)
        norm_sale = sum((license_decimals[b["license_id"]]["sale"] for b in blocks), DEC_0)
        norm_profit = sum((license_decimals[b["license_id"]]["profit"] for b in blocks), DEC_0)
        norm_margin = _pct(norm_profit, norm_sale)

        norm_item_totals: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"licenses": set(), "purchase_qty": DEC_000, "sale_qty": DEC_000,
                     "purchase_value": DEC_0, "sale_value": DEC_0}
        )
        for block in blocks:
            for it in block["item_summary"]:
                # amount_inr/qty_kg already round-tripped through _q2/_q3
                # once at the license-item-summary level (exact — those
                # fields carry at most 2/3 decimal places at the DB level),
                # so re-parsing the float here loses no precision.
                p_qty = Decimal(str(it["purchase_qty"]))
                s_qty = Decimal(str(it["sale_qty"]))
                p_val = Decimal(str(it["purchase_value"]))
                s_val = Decimal(str(it["sale_value"]))

                nb = norm_item_totals[it["item"]]
                nb["licenses"].add(block["license_id"])
                nb["purchase_qty"] += p_qty
                nb["sale_qty"] += s_qty
                nb["purchase_value"] += p_val
                nb["sale_value"] += s_val

                gb = grand_item_totals[(norm_label, it["item"])]
                gb["licenses"].add(block["license_id"])
                gb["purchase_qty"] += p_qty
                gb["sale_qty"] += s_qty
                gb["purchase_value"] += p_val
                gb["sale_value"] += s_val

        norm_item_summary = []
        for item_name in sorted(norm_item_totals.keys()):
            b = norm_item_totals[item_name]
            purchase_value = _q2(b["purchase_value"])
            sale_value = _q2(b["sale_value"])
            profit_i = _q2(sale_value - purchase_value)
            norm_item_summary.append({
                "item": item_name,
                "licenses_count": len(b["licenses"]),
                "purchase_qty": float(_q3(b["purchase_qty"])),
                "sale_qty": float(_q3(b["sale_qty"])),
                "purchase_value": float(purchase_value),
                "sale_value": float(sale_value),
                "profit": float(profit_i),
                "margin_pct": float(_pct(profit_i, sale_value)),
            })

        for b in blocks:
            if b["summary"]["status"] == "Open":
                grand_open += 1
            else:
                grand_closed += 1

        norms_output.append({
            "norm": norm_label,
            "licenses": blocks,
            "summary": {
                "licenses_count": len(blocks),
                "purchase": float(norm_purchase),
                "sale": float(norm_sale),
                "profit": float(norm_profit),
                "margin_pct": float(norm_margin),
            },
            "item_summary": norm_item_summary,
        })

        grand_purchase += norm_purchase
        grand_sale += norm_sale
        grand_profit += norm_profit
        grand_licenses_count += len(blocks)

    grand_margin = _pct(grand_profit, grand_sale)

    grand_item_summary = []
    for (norm_label, item_name) in sorted(grand_item_totals.keys()):
        b = grand_item_totals[(norm_label, item_name)]
        purchase_value = _q2(b["purchase_value"])
        sale_value = _q2(b["sale_value"])
        profit_i = _q2(sale_value - purchase_value)
        grand_item_summary.append({
            "norm": norm_label,
            "item": item_name,
            "licenses_count": len(b["licenses"]),
            "purchase_qty": float(_q3(b["purchase_qty"])),
            "sale_qty": float(_q3(b["sale_qty"])),
            "purchase_value": float(purchase_value),
            "sale_value": float(sale_value),
            "profit": float(profit_i),
            "margin_pct": float(_pct(profit_i, sale_value)),
        })

    dashboard = {
        "total_licenses": grand_licenses_count,
        "open_licenses": grand_open,
        "closed_licenses": grand_closed,
        "total_purchase": float(grand_purchase),
        "total_sale": float(grand_sale),
        "total_profit": float(grand_profit),
        "overall_margin_pct": float(grand_margin),
    }

    return {
        "dashboard": dashboard,
        "norms": norms_output,
        "grand_summary": {
            "licenses_count": grand_licenses_count,
            "purchase": float(grand_purchase),
            "sale": float(grand_sale),
            "profit": float(grand_profit),
            "margin_pct": float(grand_margin),
        },
        "grand_item_summary": grand_item_summary,
    }
