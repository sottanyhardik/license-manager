"""Ledger queries. Every balance in the system is computed here from posted voucher lines."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum

from apps.accounting.domain.money import ZERO
from apps.accounting.models import (
    LEDGER_STATUSES, PL_NATURES, Account, AccountKind, EntityBooks, Invoice, VoucherLine,
)


def posted_lines(entity: EntityBooks | None = None):
    qs = VoucherLine.objects.filter(voucher__status__in=LEDGER_STATUSES)
    return qs.filter(voucher__entity=entity) if entity is not None else qs


def _date_filter(start: date | None, end: date | None) -> Q:
    q = Q()
    if start:
        q &= Q(voucher__date__gte=start)
    if end:
        q &= Q(voucher__date__lte=end)
    return q


def account_balance(account: Account, *, start: date | None = None, end: date | None = None) -> Decimal:
    """Debit-positive balance of one account over the window (all history when start is None)."""
    agg = posted_lines().filter(_date_filter(start, end), account=account).aggregate(d=Sum("debit"), c=Sum("credit"))
    return (agg["d"] or ZERO) - (agg["c"] or ZERO)


def balances_by_account(entity: EntityBooks, *, start: date | None = None, end: date | None = None) -> dict[int, tuple]:
    """{account_id: (debit, credit)} for posted lines in the window."""
    rows = (posted_lines(entity).filter(_date_filter(start, end)).values("account_id")
            .annotate(d=Sum("debit"), c=Sum("credit")))
    return {r["account_id"]: (r["d"] or ZERO, r["c"] or ZERO) for r in rows}


def trial_balance(entity: EntityBooks, *, start: date, end: date, fy_start: date) -> dict:
    """Opening (P&L accounts open from fy_start; BS accounts carry all history), period movement, closing."""
    accounts = list(Account.objects.filter(entity=entity).select_related("group").order_by("code"))
    before_fy = balances_by_account(entity, end=_day_before(fy_start))
    fy_to_start = balances_by_account(entity, start=fy_start, end=_day_before(start)) if start > fy_start else {}
    movement = balances_by_account(entity, start=start, end=end)
    rows, totals = [], {"opening_debit": ZERO, "opening_credit": ZERO, "debit": ZERO, "credit": ZERO,
                        "closing_debit": ZERO, "closing_credit": ZERO}
    for acct in accounts:
        carried = ZERO if acct.group.nature in PL_NATURES else _net(before_fy.get(acct.pk))
        opening = carried + _net(fy_to_start.get(acct.pk))
        debit, credit = movement.get(acct.pk, (ZERO, ZERO))
        closing = opening + debit - credit
        if not (opening or debit or credit):
            continue
        row = {
            "account_id": acct.pk, "code": acct.code, "name": acct.name, "group": acct.group.name,
            "nature": acct.group.nature, "kind": acct.kind,
            "opening_debit": max(opening, ZERO), "opening_credit": max(-opening, ZERO),
            "debit": debit, "credit": credit,
            "closing_debit": max(closing, ZERO), "closing_credit": max(-closing, ZERO),
        }
        for k in totals:
            totals[k] += row[k]
        rows.append(row)
    # Profit of prior FYs sits in P&L accounts' history; show it as one carried-forward line so the TB balances.
    retained = sum((_net(before_fy.get(a.pk)) for a in accounts if a.group.nature in PL_NATURES), ZERO)
    if retained:
        row = {"account_id": None, "code": "", "name": "Profit & Loss (prior years, carried forward)",
               "group": "Reserves and Surplus", "nature": "EQUITY", "kind": "GENERAL",
               "opening_debit": max(retained, ZERO), "opening_credit": max(-retained, ZERO),
               "debit": ZERO, "credit": ZERO,
               "closing_debit": max(retained, ZERO), "closing_credit": max(-retained, ZERO)}
        for k in totals:
            totals[k] += row[k]
        rows.append(row)
    return {"rows": rows, "totals": totals,
            "balanced": totals["closing_debit"] == totals["closing_credit"] and totals["debit"] == totals["credit"]}


def _net(pair) -> Decimal:
    return (pair[0] - pair[1]) if pair else ZERO


def _day_before(d: date) -> date:
    from datetime import timedelta
    return d - timedelta(days=1)


def general_ledger(account: Account, *, start: date, end: date) -> dict:
    opening = account_balance(account, end=_day_before(start)) if account.group.nature not in PL_NATURES else \
        _pl_opening(account, start)
    lines = (posted_lines().filter(_date_filter(start, end), account=account)
             .select_related("voucher").order_by("voucher__date", "voucher__id", "line_no"))
    running, rows = opening, []
    for ln in lines:
        running += ln.debit - ln.credit
        v = ln.voucher
        rows.append({
            "voucher_id": v.pk, "voucher_number": v.number, "voucher_type": v.voucher_type, "date": v.date,
            "narration": ln.narration or v.narration, "debit": ln.debit, "credit": ln.credit, "balance": running,
            "source_type": v.source_type, "source_id": v.source_id, "trade_id": ln.trade_id, "status": v.status,
        })
    return {"account_id": account.pk, "code": account.code, "name": account.name, "opening": opening,
            "closing": running, "rows": rows}


def _pl_opening(account: Account, start: date) -> Decimal:
    from apps.accounting.services.books import fy_bounds
    _label, fy_start, _end = fy_bounds(start)
    return account_balance(account, start=fy_start, end=_day_before(start)) if start > fy_start else ZERO


def party_ledger(entity: EntityBooks, party_id: int, *, start: date, end: date) -> dict:
    account = Account.objects.filter(entity=entity, kind=AccountKind.PARTY, party_id=party_id).select_related("group").first()
    if account is None:
        return {"account_id": None, "opening": ZERO, "closing": ZERO, "rows": [], "open_bills": []}
    data = general_ledger(account, start=start, end=end)
    from apps.accounting.services.invoices import outstanding_map, status_for
    bills = list(Invoice.objects.filter(entity=entity, party_id=party_id, status="POSTED").order_by("date", "id"))
    due = outstanding_map(bills, end)
    data["open_bills"] = [
        {"invoice_id": b.pk, "number": b.number, "kind": b.kind, "date": b.date, "due_date": b.due_date,
         "amount": b.net_amount, "outstanding": due[b.pk], "status": status_for(b, due[b.pk]), "trade_id": b.trade_id}
        for b in bills if due[b.pk] > 0
    ]
    return data
