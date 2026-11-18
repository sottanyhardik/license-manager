"""
License Overview — Payment ledgers (`GET .../overview-payment-ledgers/`).

Read-only. Purchase / sale trades linked to a licence (same linkage as
`license_overview_invoices.build_invoice_ledger`) with their settlement taken
from `LicenseTradePayment` (the authoritative paid/received figure). The
numbers use the same definitions as `LicenseTrade.paid_or_received` /
`due_amount` but are computed from prefetched payments in Python (no per-trade
aggregate query). Summaries are derived from the rows so they reconcile.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List

from apps.trade.models import LicenseTrade, q2  # q2: same quantiser as the trade model

_PURCHASE_DIRECTIONS = (LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_COMMISSION_PURCHASE)
_SALE_DIRECTIONS = (LicenseTrade.DIR_SALE, LicenseTrade.DIR_COMMISSION_SALE)
_ZERO = Decimal("0.00")


def _status(total: Decimal, settled: Decimal) -> str:
    if total - settled <= 0:
        return "PAID"
    if settled > 0:
        return "PARTIAL"
    return "UNPAID"


def _file_url(f):
    try:
        return f.url if f else None
    except ValueError:
        return None


def _document(trade, *, is_purchase: bool):
    if is_purchase:
        url = _file_url(trade.purchase_invoice_copy)
        return {"kind": "purchase_invoice_copy", "url": url} if url else None
    for doc in trade.generated_invoice_documents.all():  # ordered newest first
        url = _file_url(doc.file)
        if url:
            return {"kind": "generated_sale_invoice", "url": url}
    return None


def _row(trade, license_obj, *, is_purchase: bool) -> Dict[str, Any]:
    company = trade.from_company if is_purchase else trade.to_company
    payments = list(trade.payments.all())
    settled = q2(sum((q2(p.amount) for p in payments), _ZERO))
    total = q2(trade.total_amount)
    licence_amount = q2(sum(
        (q2(ln.amount_inr) for ln in trade.lines.all()
         if ln.sr_number_id and ln.sr_number.license_id == license_obj.pk),
        _ZERO,
    ))
    pay_rows = []
    for p in payments:
        acc = getattr(p, "accounting_payment", None)
        pay_rows.append({
            "id": p.id,
            "date": p.date,
            "amount": q2(p.amount),
            "note": p.note,
            "bank_reference": (acc.reference or None) if acc else None,
        })
    return {
        "trade_id": trade.id,
        "invoice_number": trade.invoice_number,
        "invoice_date": trade.invoice_date,
        "company_name": company.name if company else None,
        "amount": q2(trade.subtotal_amount),
        "gst": None,  # GST not tracked as a discrete figure (see build_invoice_ledger)
        "total": total,
        "licence_amount": licence_amount,
        "settled": settled,
        "outstanding": total - settled,
        "status": _status(total, settled),
        "payments": pay_rows,
        "document": _document(trade, is_purchase=is_purchase),
    }


def _section(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "summary": {
            "invoice_count": len(rows),
            "total_amount": q2(sum((r["total"] for r in rows), _ZERO)),
            "total_settled": q2(sum((r["settled"] for r in rows), _ZERO)),
            "total_outstanding": q2(sum((r["outstanding"] for r in rows), _ZERO)),
        },
        "rows": rows,
    }


def build_trade_payment_ledgers(license_obj) -> Dict[str, Any]:
    trades = list(
        LicenseTrade.objects.filter(lines__sr_number__license=license_obj)
        .distinct()
        .select_related("from_company", "to_company")
        .prefetch_related(
            "lines__sr_number", "payments", "payments__accounting_payment",
            "generated_invoice_documents",
        )
    )
    purchase = sorted((t for t in trades if t.direction in _PURCHASE_DIRECTIONS),
                      key=lambda t: t.invoice_date or date.min)
    sale = sorted((t for t in trades if t.direction in _SALE_DIRECTIONS),
                  key=lambda t: t.invoice_date or date.min)
    return {
        "purchase": _section([_row(t, license_obj, is_purchase=True) for t in purchase]),
        "sale": _section([_row(t, license_obj, is_purchase=False) for t in sale]),
    }
