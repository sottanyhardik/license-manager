"""
License Overview — Invoice Ledger tab (`GET .../overview-invoice-ledger/`).

One query (`select_related`/`prefetch_related`), split into Purchase / Sale
lists in Python — never two separate queries. Status is derived directly
from the existing `LicenseTrade.paid_or_received`/`due_amount` properties
(never reimplemented here).

GST is not tracked as a discrete figure in this schema (`from_gst`/`to_gst`
are GSTIN registration strings, not tax amounts) — `_gst_amount()` always
returns `None` so the frontend renders "Not tracked"; kept as a one-line
helper so that decision is a one-line change later if it's ever revisited.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict

from apps.trade.models import LicenseTrade

_PURCHASE_DIRECTIONS = (LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_COMMISSION_PURCHASE)
_SALE_DIRECTIONS = (LicenseTrade.DIR_SALE, LicenseTrade.DIR_COMMISSION_SALE)


def _gst_amount(trade) -> None:
    """GST amount is not tracked as a discrete figure in this schema — see
    module docstring. Always `None`."""
    return None


def _status_label(trade) -> str:
    due = trade.due_amount
    paid = trade.paid_or_received
    if due <= 0:
        return "Paid"
    if paid > 0:
        return "Partial"
    return "Unpaid"


def _row(trade, *, is_purchase: bool) -> Dict[str, Any]:
    if is_purchase:
        company = trade.from_company
    else:
        company = trade.to_company
    return {
        "invoice_number": trade.invoice_number,
        "invoice_date": trade.invoice_date,
        "company_name": company.name if company else None,
        "amount": trade.subtotal_amount,
        "gst": _gst_amount(trade),
        "total": trade.total_amount,
        "status": _status_label(trade),
    }


def missing_purchase_invoice_warning(purchase_trades, sale_trades) -> Dict[str, Any]:
    """
    `{"show_warning": bool, "message": str}` — always returns both keys
    explicitly (never omits `show_warning`, never shows the warning when
    purchases exist or when there are no trades at all).
    """
    show_warning = (not purchase_trades) and bool(sale_trades)
    return {
        "show_warning": show_warning,
        "message": "Purchase invoice has not been created for this licence.",
    }


def build_invoice_ledger(license_obj) -> Dict[str, Any]:
    trades = list(
        LicenseTrade.objects.filter(lines__sr_number__license=license_obj)
        .distinct()
        .select_related("from_company", "to_company")
        .prefetch_related("lines", "payments")
    )

    purchase_trades = [t for t in trades if t.direction in _PURCHASE_DIRECTIONS]
    sale_trades = [t for t in trades if t.direction in _SALE_DIRECTIONS]

    purchase_trades.sort(key=lambda t: t.invoice_date or date.min)
    sale_trades.sort(key=lambda t: t.invoice_date or date.min)

    purchase_rows = [_row(t, is_purchase=True) for t in purchase_trades]
    sale_rows = [_row(t, is_purchase=False) for t in sale_trades]

    return {
        "purchase": purchase_rows,
        "sale": sale_rows,
        "warning": missing_purchase_invoice_warning(purchase_trades, sale_trades),
    }
