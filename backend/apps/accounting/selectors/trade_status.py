"""Trade-to-invoice-to-voucher tracking. Every status is derived from actual accounting records."""
from __future__ import annotations

from apps.accounting.models import DocStatus, EntityBooks, Invoice, Payment

from .trade_source import trades_for_company, view_of

NOT_ACCOUNTED, PENDING, ACCOUNTED = "NOT_ACCOUNTED", "PENDING", "ACCOUNTED"
PARTIAL, EXCEPTION, REVERSED = "PARTIALLY_ACCOUNTED", "EXCEPTION", "REVERSED"


def trade_accounting_rows(entity: EntityBooks, *, start=None, end=None, status: str | None = None) -> list[dict]:
    from apps.accounting.services.invoices import outstanding_map, status_for
    qs = trades_for_company(entity.pk).order_by("-invoice_date", "-id")
    if start:
        qs = qs.filter(invoice_date__gte=start)
    if end:
        qs = qs.filter(invoice_date__lte=end)
    trades = list(qs)
    invoices = {i.trade_id: i for i in Invoice.objects.filter(trade_id__in=[t.pk for t in trades])
                .select_related("voucher", "party")}
    open_amounts = outstanding_map(invoices.values())
    accounted = set(Payment.objects.filter(trade_payment__trade_id__in=[t.pk for t in trades])
                    .values_list("trade_payment_id", flat=True))
    rows = []
    for t in trades:
        view = view_of(t)
        inv = invoices.get(t.pk)
        payments = list(t.payments.all())
        unaccounted_payments = [p.pk for p in payments if p.pk not in accounted]
        if inv is None or inv.status == DocStatus.CANCELLED:
            st = NOT_ACCOUNTED
        elif inv.status == DocStatus.REVERSED:
            st = REVERSED
        elif inv.source_version != view.version:
            st = EXCEPTION
        elif inv.status in (DocStatus.DRAFT, DocStatus.CONFIRMED):
            st = PENDING
        elif unaccounted_payments:
            st = PARTIAL
        else:
            st = ACCOUNTED
        if status and st != status:
            continue
        rows.append({
            "trade_id": t.pk, "direction": t.direction, "invoice_number": view.invoice_number,
            "invoice_date": view.invoice_date, "party_id": view.party_company_id,
            "party": (t.from_company if view.kind in ("PURCHASE", "COMMISSION_PAYABLE") else t.to_company).name
            if view.party_company_id else None,
            "trade_total": view.total, "accounting_status": st,
            "invoice_id": inv.pk if inv else None, "invoice_status": inv.status if inv else None,
            "voucher_id": inv.voucher_id if inv else None,
            "voucher_number": inv.voucher.number if inv and inv.voucher_id else None,
            "payment_status": status_for(inv, open_amounts[inv.pk]) if inv else None,
            "outstanding": open_amounts[inv.pk] if inv else None,
            "trade_payments": len(payments), "unaccounted_payment_ids": unaccounted_payments,
            "is_paired": view.is_paired,
        })
    return rows
