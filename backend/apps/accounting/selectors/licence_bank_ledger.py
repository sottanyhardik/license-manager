"""
Licence bank ledger: every bank payment/receipt that touches a licence's trades.

Linkage is structural, NEVER by amount matching:
  (a) active `Settlement`s (with a payment) against an invoice that is linked to
      one of the licence's trades (`InvoiceLine.trade` or `Invoice.trade`);
  (b) `Payment`s whose `trade_payment.trade` is one of the licence's trades.
One row per `Payment` (union, de-duplicated). Cancelled / reversed payments are
excluded; draft, confirmed and posted ones are returned with their status.

`trades` (additive): every licence trade with its bank settlement — the allocations above re-keyed by trade
(a settlement → its invoice's trade; a trade-payment link → that trade; each allocation counted once). Only
POSTED payments count towards `bank_settled`; drafts/confirmed ones are listed with their status but do not
make an invoice paid. A trade with no allocation is UNPAID ("not linked") — never inferred from amounts.
`bank_direction` is the bank statement side (debit → WITHDRAWAL, credit → DEPOSIT) when the payment is matched
to a statement line, else the payment direction (PAYMENT → WITHDRAWAL, RECEIPT → DEPOSIT).
Read-only.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List

from django.db.models import Prefetch

from apps.accounting.models import (
    BankMatch, DocStatus, Invoice, InvoiceLine, Payment, PaymentDirection, Settlement,
)
from apps.trade.models import LicenseTrade, q2

_ZERO = Decimal("0.00")
EXCLUDED_STATUSES = (DocStatus.CANCELLED, DocStatus.REVERSED)
_PURCHASE_DIRECTIONS = (LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_COMMISSION_PURCHASE)


def _reconciliation(matched: Decimal, amount: Decimal) -> str:
    if matched >= amount and matched > 0:
        return "RECONCILED"
    if matched > 0:
        return "PARTIAL"
    return "UNRECONCILED"


def licence_bank_ledger(license_obj) -> Dict[str, Any]:
    trade_ids = set(
        LicenseTrade.objects.filter(lines__sr_number__license=license_obj).values_list("pk", flat=True)
    )

    # invoice_id -> trade_id for invoices linked to the licence's trades
    invoice_trade: Dict[int, int] = {}
    if trade_ids:
        for inv_id, t_id in InvoiceLine.objects.filter(trade_id__in=trade_ids).values_list("invoice_id", "trade_id"):
            invoice_trade.setdefault(inv_id, t_id)
        for inv_id, t_id in Invoice.objects.filter(trade_id__in=trade_ids).values_list("pk", "trade_id"):
            invoice_trade[inv_id] = t_id
    invoice_numbers: Dict[int, str] = (
        dict(Invoice.objects.filter(pk__in=invoice_trade).values_list("pk", "number")) if invoice_trade else {}
    )

    payment_ids = set()
    if invoice_trade:
        payment_ids |= set(
            Settlement.objects.filter(is_active=True, payment__isnull=False, invoice_id__in=invoice_trade)
            .values_list("payment_id", flat=True)
        )
    if trade_ids:
        payment_ids |= set(
            Payment.objects.filter(trade_payment__trade_id__in=trade_ids).values_list("pk", flat=True)
        )
    if not payment_ids:
        return _wrap([], _trade_rows(trade_ids, {}))

    payments = list(
        Payment.objects.filter(pk__in=payment_ids)
        .exclude(status__in=EXCLUDED_STATUSES)
        .select_related("party", "bank_account", "trade_payment__trade", "voucher")
        .prefetch_related(
            Prefetch("settlements", queryset=Settlement.objects.filter(is_active=True).select_related("invoice"),
                     to_attr="active_settlements"),
            Prefetch("voucher__bank_matches",
                     queryset=BankMatch.objects.filter(is_active=True).select_related("statement_line"),
                     to_attr="active_matches"),
        )
        .order_by("date", "id")
    )

    rows: List[Dict[str, Any]] = []
    allocations_by_trade: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for p in payments:
        licence_sets = [s for s in p.active_settlements if s.invoice_id in invoice_trade]
        settled_all = sum((s.amount for s in p.active_settlements), _ZERO)
        trade_link = p.trade_payment if p.trade_payment_id and p.trade_payment.trade_id in trade_ids else None
        linked_invoices = [
            {"invoice_id": s.invoice_id, "number": s.invoice.number, "trade_id": invoice_trade[s.invoice_id],
             "amount": q2(s.amount)}
            for s in licence_sets
        ]
        if licence_sets:
            allocated = sum((s.amount for s in licence_sets), _ZERO)
            unallocated = p.party_amount - settled_all
        elif trade_link is not None and not p.active_settlements:
            # No bill-wise settlement: the payment's structural link to the licence trade (trade_payment) is its
            # allocation — counted once, both as allocated and against the unallocated balance.
            allocated = trade_link.amount
            unallocated = p.party_amount - trade_link.amount
            trade_invoices = [inv_id for inv_id, t_id in invoice_trade.items() if t_id == trade_link.trade_id]
            linked_invoices = [
                {"invoice_id": inv_id, "number": invoice_numbers.get(inv_id, trade_link.trade.invoice_number),
                 "trade_id": trade_link.trade_id, "amount": q2(trade_link.amount)}
                for inv_id in trade_invoices
            ] or [{"invoice_id": None, "number": trade_link.trade.invoice_number, "trade_id": trade_link.trade_id,
                   "amount": q2(trade_link.amount)}]
        else:
            allocated = _ZERO
            unallocated = p.party_amount - settled_all

        matches = list(getattr(p.voucher, "active_matches", [])) if p.voucher_id else []
        matched = sum((m.amount for m in matches), _ZERO)
        seen, lines = set(), []
        for m in matches:
            sl = m.statement_line
            if sl.pk in seen:
                continue
            seen.add(sl.pk)
            lines.append({"id": sl.pk, "txn_date": sl.txn_date, "reference": sl.reference, "amount": q2(sl.amount),
                          "bank_direction": "WITHDRAWAL" if sl.debit > 0 else "DEPOSIT"})
        if lines:
            bank_direction = lines[0]["bank_direction"]
        else:
            bank_direction = "WITHDRAWAL" if p.direction == PaymentDirection.PAYMENT else "DEPOSIT"
        reconciliation = _reconciliation(matched, p.amount)
        bank_account = str(p.bank_account).strip()
        for inv in linked_invoices:
            if inv["trade_id"] is None:
                continue
            allocations_by_trade[inv["trade_id"]].append({
                "payment_id": p.pk, "date": p.date, "bank_account": bank_account, "reference": p.reference,
                "mode": p.mode, "bank_direction": bank_direction, "bank_amount": q2(p.amount),
                "allocated": inv["amount"], "payment_unallocated": q2(unallocated), "invoice_number": inv["number"],
                "reconciliation": reconciliation, "status": p.status,
                "counted": p.status == DocStatus.POSTED,
            })

        rows.append({
            "payment_id": p.pk,
            "date": p.date,
            "bank_account": bank_account,
            "reference": p.reference,
            "mode": p.mode,
            "direction": p.direction,
            "party": p.party.name if p.party_id else "",
            "amount": q2(p.amount),
            "status": p.status,
            "allocated_to_licence": q2(allocated),
            "unallocated": q2(unallocated),
            "invoices": linked_invoices,
            "reconciliation": reconciliation,
            "bank_direction": bank_direction,
            "statement_lines": lines,
        })
    return _wrap(rows, _trade_rows(trade_ids, allocations_by_trade))


def _trade_rows(trade_ids, allocations_by_trade: Dict[int, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Bank settlement per licence trade (posted allocations only count); every trade listed, linked or not."""
    out: List[Dict[str, Any]] = []
    trades = (LicenseTrade.objects.filter(pk__in=trade_ids)
              .values("pk", "direction", "invoice_number", "invoice_date", "total_amount")
              .order_by("invoice_date", "pk"))
    for t in trades:
        allocations = sorted(allocations_by_trade.get(t["pk"], []), key=lambda a: (a["date"], a["payment_id"]))
        settled = q2(sum((a["allocated"] for a in allocations if a["counted"]), _ZERO))
        total = q2(t["total_amount"] or _ZERO)
        outstanding = q2(total - settled)
        if settled > 0 and outstanding <= 0:
            status = "PAID"
        elif settled > 0:
            status = "PARTIAL"
        else:
            status = "UNPAID"
        out.append({
            "trade_id": t["pk"],
            "direction": "PURCHASE" if t["direction"] in _PURCHASE_DIRECTIONS else "SALE",
            "invoice_number": t["invoice_number"],
            "invoice_date": t["invoice_date"],
            "total": total,
            "bank_settled": settled,
            "outstanding": outstanding,
            "status": status,
            "linked": bool(allocations),
            "allocations": allocations,
        })
    return out


def _wrap(rows: List[Dict[str, Any]], trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    def total(key, direction=None):
        return q2(sum((r[key] for r in rows if direction is None or r["direction"] == direction), _ZERO))

    def by_bank_side(key, side):
        return q2(sum((r[key] for r in rows if r["bank_direction"] == side), _ZERO))

    def outstanding(direction):
        return q2(sum((t["outstanding"] for t in trades if t["direction"] == direction), _ZERO))
    return {
        "summary": {
            "transaction_count": len(rows),
            "total_payments": total("amount", PaymentDirection.PAYMENT),
            "total_receipts": total("amount", PaymentDirection.RECEIPT),
            "total_allocated": total("allocated_to_licence"),
            "total_unallocated": total("unallocated"),
            # Additive — licence-linked bank movement by statement side, and invoice outstanding by bank settlement.
            "total_withdrawals": by_bank_side("amount", "WITHDRAWAL"),
            "total_credits": by_bank_side("amount", "DEPOSIT"),
            "total_allocated_payments": total("allocated_to_licence", PaymentDirection.PAYMENT),
            "total_allocated_receipts": total("allocated_to_licence", PaymentDirection.RECEIPT),
            "total_unallocated_withdrawals": by_bank_side("unallocated", "WITHDRAWAL"),
            "total_unallocated_credits": by_bank_side("unallocated", "DEPOSIT"),
            "total_outstanding_purchase": outstanding("PURCHASE"),
            "total_outstanding_sales": outstanding("SALE"),
        },
        "rows": rows,
        "trades": trades,
    }
