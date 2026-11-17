"""Financial statements and registers — all computed from posted voucher lines (the GL)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from apps.accounting.domain.money import ZERO
from apps.accounting.models import (
    PAYABLE_KINDS, PL_NATURES, RECEIVABLE_KINDS, Account, AccountKind, DocStatus, EntityBooks, Invoice, Loan,
    Nature, ReportHead, SuspenseItem, VoucherLine,
)

from .ledger import account_balance, balances_by_account, posted_lines

H = ReportHead

#: P&L layout: (key, label, heads, sign) — sign +1 for income (credit-positive), -1 for cost lines.
PL_LAYOUT = [
    ("gross_sales", "Gross sales", [H.SALES], 1),
    ("sales_returns", "Sales returns", [H.SALES_RETURNS], 1),
    ("purchases", "Purchase cost", [H.PURCHASES, H.PURCHASE_RETURNS], -1),
    ("stock_change", "Change in stock", [H.STOCK_CHANGE], -1),
    ("freight", "Freight", [H.FREIGHT], -1),
    ("insurance", "Insurance", [H.INSURANCE], -1),
    ("customs", "Customs and clearing", [H.CUSTOMS], -1),
    ("commission_expense", "Commission paid", [H.COMMISSION_EXPENSE], -1),
    ("bank_charges", "Bank charges", [H.BANK_CHARGES], -1),
    ("operating_expenses", "Operating expenses", [H.OPERATING_EXPENSES], -1),
    ("interest_expense", "Interest expense", [H.INTEREST_EXPENSE], -1),
    ("forex", "Foreign exchange gain/(loss)", [H.FOREX], 1),
    ("commission_income", "Commission received", [H.COMMISSION_INCOME], 1),
    ("interest_income", "Interest income", [H.INTEREST_INCOME], 1),
    ("other_income", "Other income", [H.OTHER_INCOME], 1),
]
DIRECT_COSTS = ("purchases", "stock_change", "freight", "insurance", "customs")


def _accounts(entity: EntityBooks) -> dict[int, Account]:
    return {a.pk: a for a in Account.objects.filter(entity=entity).select_related("group")}


def profit_and_loss(entity: EntityBooks, start: date, end: date) -> dict:
    accts = _accounts(entity)
    moves = balances_by_account(entity, start=start, end=end)
    by_head: dict[str, Decimal] = defaultdict(lambda: ZERO)
    detail: dict[str, list] = defaultdict(list)
    for acct_id, (d, c) in moves.items():
        acct = accts[acct_id]
        if acct.group.nature not in PL_NATURES:
            continue
        credit_positive = c - d
        by_head[acct.group.report_head] += credit_positive
        detail[acct.group.report_head].append({"account_id": acct_id, "code": acct.code, "name": acct.name,
                                               "amount": credit_positive})
    lines = {}
    for key, label, heads, sign in PL_LAYOUT:
        amount = sum((by_head[hd] for hd in heads), ZERO)
        lines[key] = {"label": label, "amount": amount if sign > 0 else -amount,
                      "accounts": [a for hd in heads for a in detail[hd]]}
    net_sales = lines["gross_sales"]["amount"] + lines["sales_returns"]["amount"]
    cogs = sum((lines[k]["amount"] for k in DIRECT_COSTS), ZERO)
    gross_profit = net_sales - cogs
    indirect_cost = sum((lines[k]["amount"] for k in ("commission_expense", "bank_charges", "operating_expenses",
                                                     "interest_expense")), ZERO)
    other = sum((lines[k]["amount"] for k in ("forex", "commission_income", "interest_income", "other_income")), ZERO)
    net_profit = gross_profit - indirect_cost + other
    ledger_net = sum((c - d for a_id, (d, c) in moves.items() if accts[a_id].group.nature in PL_NATURES), ZERO)
    return {"entity_id": entity.pk, "start": start, "end": end, "lines": lines, "net_sales": net_sales,
            "cogs": cogs, "gross_profit": gross_profit, "net_profit": net_profit,
            "agrees_with_ledger": net_profit == ledger_net}


def monthly_profit_and_loss(entity: EntityBooks, start: date, end: date) -> list[dict]:
    out, cursor = [], start.replace(day=1)
    while cursor <= end:
        nxt = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        window_end = min(end, nxt - timedelta(days=1))
        pl = profit_and_loss(entity, max(start, cursor), window_end)
        out.append({"month": cursor.strftime("%Y-%m"), "net_sales": pl["net_sales"], "gross_profit": pl["gross_profit"],
                    "net_profit": pl["net_profit"]})
        cursor = nxt
    return out


BS_ASSET_HEADS = [H.FIXED_ASSETS, H.INVENTORY, H.RECEIVABLES, H.LOANS_GIVEN, H.TAX_ASSETS, H.CASH_BANK,
                  H.OTHER_ASSETS, H.SUSPENSE]
BS_LIAB_HEADS = [H.CAPITAL, H.RESERVES, H.LOANS_TAKEN, H.PAYABLES, H.TAX_LIABILITIES, H.OTHER_LIABILITIES]


def balance_sheet(entity: EntityBooks, as_of: date) -> dict:
    """Party ledgers are classified by sign (debit balance = receivable, credit = payable)."""
    accts = _accounts(entity)
    bal = balances_by_account(entity, end=as_of)
    heads: dict[str, Decimal] = defaultdict(lambda: ZERO)
    profit = ZERO
    for acct_id, (d, c) in bal.items():
        acct = accts[acct_id]
        net = d - c
        if acct.group.nature in PL_NATURES:
            profit += -net
            continue
        head = acct.group.report_head
        if acct.kind == AccountKind.PARTY:
            head = H.RECEIVABLES if net > 0 else H.PAYABLES
        elif acct.kind in (AccountKind.BANK, AccountKind.CASH) and net < 0:
            head = "BANK_OVERDRAFT"  # a credit bank balance is a liability, not a negative asset
        heads[head] += net
    assets = {hd.value: heads[hd] for hd in BS_ASSET_HEADS if heads[hd]}
    liabilities = {hd.value: -heads[hd] for hd in BS_LIAB_HEADS if heads[hd]}
    if heads["BANK_OVERDRAFT"]:
        liabilities["BANK_OVERDRAFT"] = -heads["BANK_OVERDRAFT"]
    liabilities["PROFIT_AND_LOSS"] = profit
    total_assets = sum(assets.values(), ZERO)
    total_liab = sum(liabilities.values(), ZERO)
    labels = dict(ReportHead.choices) | {"PROFIT_AND_LOSS": "Profit & Loss account (cumulative)",
                                         "BANK_OVERDRAFT": "Bank overdraft"}
    return {"entity_id": entity.pk, "as_of": as_of,
            "assets": [{"head": k, "label": labels[k], "amount": v} for k, v in assets.items()],
            "liabilities": [{"head": k, "label": labels[k], "amount": v} for k, v in liabilities.items()],
            "total_assets": total_assets, "total_liabilities": total_liab,
            "balanced": total_assets == total_liab}


def cash_flow(entity: EntityBooks, start: date, end: date) -> dict:
    """Direct method: each bank/cash movement is classified by the voucher's other accounts (pro rata)."""
    cash_ids = set(Account.objects.filter(entity=entity, kind__in=[AccountKind.BANK, AccountKind.CASH])
                   .values_list("pk", flat=True))
    accts = _accounts(entity)
    sections = {"operating": ZERO, "investing": ZERO, "financing": ZERO}
    detail: dict[str, dict] = {k: defaultdict(lambda: ZERO) for k in sections}
    lines = (posted_lines(entity).filter(voucher__date__gte=start, voucher__date__lte=end)
             .select_related("account__group").order_by("voucher_id"))
    by_voucher: dict[int, list[VoucherLine]] = defaultdict(list)
    for ln in lines:
        by_voucher[ln.voucher_id].append(ln)
    opening_in_period = ZERO
    opening_vouchers = set(posted_lines(entity).filter(voucher__voucher_type="OPENING", voucher__date__gte=start,
                                                       voucher__date__lte=end).values_list("voucher_id", flat=True))
    for vid, vlines in by_voucher.items():
        cash_move = sum((ln.debit - ln.credit for ln in vlines if ln.account_id in cash_ids), ZERO)
        if not cash_move:
            continue  # contra between bank accounts, or no cash effect
        if vid in opening_vouchers:  # an opening balance is where cash starts, not a cash flow
            opening_in_period += cash_move
            continue
        # Exact direct method: each counter-line explains -(its own net) of the cash movement, so the
        # sections always sum to the cash moved (e.g. TDS withheld on interest nets against interest).
        for ln in vlines:
            if ln.account_id in cash_ids:
                continue
            share = ln.credit - ln.debit
            head = accts[ln.account_id].group.report_head
            section = ("financing" if head in (H.LOANS_TAKEN, H.CAPITAL) else
                       "investing" if head in (H.FIXED_ASSETS, H.LOANS_GIVEN) else "operating")
            sections[section] += share
            detail[section][accts[ln.account_id].group.name] += share
    opening = sum((account_balance(accts[i], end=start - timedelta(days=1)) for i in cash_ids), ZERO) + opening_in_period
    closing = sum((account_balance(accts[i], end=end) for i in cash_ids), ZERO)
    net = sum(sections.values(), ZERO)
    return {"entity_id": entity.pk, "start": start, "end": end, "opening_cash": opening, "closing_cash": closing,
            "sections": sections, "detail": {k: dict(v) for k, v in detail.items()}, "net_change": net,
            "agrees_with_ledger": opening + net == closing}


AGEING_BUCKETS = ((0, 30), (31, 60), (61, 90), (91, 180), (181, None))


def ageing(entity: EntityBooks, *, receivable: bool, as_of: date) -> dict:
    from apps.accounting.services.invoices import outstanding_map
    kinds = RECEIVABLE_KINDS if receivable else PAYABLE_KINDS
    bills = list(Invoice.objects.filter(entity=entity, kind__in=kinds, status=DocStatus.POSTED, date__lte=as_of)
                 .select_related("party"))
    open_amounts = outstanding_map(bills, as_of)
    parties: dict[int, dict] = {}
    totals = {f"{lo}-{hi or '+'}": ZERO for lo, hi in AGEING_BUCKETS} | {"not_due": ZERO, "total": ZERO}
    for bill in bills:
        due = open_amounts[bill.pk]
        if due <= 0:
            continue
        ref = bill.due_date or bill.date
        days = (as_of - ref).days
        key = "not_due" if days < 0 else next(f"{lo}-{hi or '+'}" for lo, hi in AGEING_BUCKETS
                                               if days >= lo and (hi is None or days <= hi))
        row = parties.setdefault(bill.party_id, {"party_id": bill.party_id, "party": bill.party.name,
                                                 **{k: ZERO for k in totals}, "bills": []})
        row[key] += due
        row["total"] += due
        totals[key] += due
        totals["total"] += due
        row["bills"].append({"invoice_id": bill.pk, "number": bill.number, "date": bill.date,
                             "due_date": bill.due_date, "outstanding": due, "days_overdue": max(days, 0)})
    return {"as_of": as_of, "receivable": receivable, "parties": sorted(parties.values(), key=lambda r: -r["total"]),
            "totals": totals}


def register(entity: EntityBooks, kinds, start: date, end: date) -> dict:
    from apps.accounting.services.invoices import outstanding_map, status_for
    rows = []
    totals = defaultdict(lambda: ZERO)
    invoices = list(Invoice.objects.filter(entity=entity, kind__in=kinds, date__gte=start, date__lte=end)
                    .exclude(status=DocStatus.CANCELLED).select_related("party", "voucher", "tds_section")
                    .order_by("date", "id"))
    open_amounts = outstanding_map(invoices)
    for inv in invoices:
        row = {"invoice_id": inv.pk, "number": inv.number, "date": inv.date, "kind": inv.kind,
               "party_id": inv.party_id, "party": inv.party.name, "party_gstin": inv.party.gst_number,
               "taxable": inv.taxable_amount, "cgst": inv.cgst, "sgst": inv.sgst, "igst": inv.igst,
               "gross": inv.gross_amount, "tds_section": inv.tds_section.code if inv.tds_section else "",
               "tds": inv.tds_amount, "net": inv.net_amount, "status": status_for(inv, open_amounts[inv.pk]),
               "outstanding": open_amounts[inv.pk], "voucher_id": inv.voucher_id,
               "voucher_number": inv.voucher.number if inv.voucher else None, "trade_id": inv.trade_id}
        rows.append(row)
        if inv.status == DocStatus.POSTED:
            for k in ("taxable", "cgst", "sgst", "igst", "gross", "tds", "net", "outstanding"):
                totals[k] += row[k]
    return {"rows": rows, "totals": dict(totals)}


def tds_register(entity: EntityBooks, start: date, end: date) -> dict:
    data = register(entity, [k for k in PAYABLE_KINDS] + [k for k in RECEIVABLE_KINDS], start, end)
    rows = [r for r in data["rows"] if r["tds"]]
    by_section = defaultdict(lambda: ZERO)
    for r in rows:
        by_section[r["tds_section"] or "customer-deducted"] += r["tds"]
    return {"rows": rows, "by_section": dict(by_section),
            "tds_payable": -account_balance(_role(entity, "TDS_PAYABLE"), end=end),
            "tds_receivable": account_balance(_role(entity, "TDS_RECEIVABLE"), end=end)}


def gst_register(entity: EntityBooks, start: date, end: date) -> dict:
    out = register(entity, list(RECEIVABLE_KINDS) + ["CREDIT_NOTE"], start, end)
    inp = register(entity, list(PAYABLE_KINDS) + ["DEBIT_NOTE"], start, end)
    def tax(role):
        return account_balance(_role(entity, role), start=start, end=end)
    output_tax = -(tax("OUTPUT_CGST") + tax("OUTPUT_SGST") + tax("OUTPUT_IGST"))
    input_tax = tax("INPUT_CGST") + tax("INPUT_SGST") + tax("INPUT_IGST")
    return {"outward": out, "inward": inp, "output_tax": output_tax, "input_tax": input_tax,
            "net_payable": output_tax - input_tax}


def _role(entity, role) -> Account:
    from apps.accounting.services.chart import system_account
    return system_account(entity, role)


def trade_profitability(entity: EntityBooks, start: date, end: date) -> dict:
    """Per trade: income and costs from GL lines tagged with the trade (sales, purchases, allocated expenses)."""
    accts = _accounts(entity)
    rows: dict[int, dict] = {}
    lines = (posted_lines(entity).filter(voucher__date__gte=start, voucher__date__lte=end, trade__isnull=False)
             .values("trade_id", "account_id").annotate(d=Sum("debit"), c=Sum("credit")))
    for r in lines:
        acct = accts[r["account_id"]]
        if acct.group.nature not in PL_NATURES:
            continue
        row = rows.setdefault(r["trade_id"], {"trade_id": r["trade_id"], "revenue": ZERO, "direct_cost": ZERO,
                                              "expenses": ZERO, "by_head": defaultdict(lambda: ZERO)})
        net_credit = (r["c"] or ZERO) - (r["d"] or ZERO)
        head = acct.group.report_head
        row["by_head"][head] += net_credit
        if acct.group.nature == Nature.INCOME:
            row["revenue"] += net_credit
        elif head in (H.PURCHASES, H.PURCHASE_RETURNS, H.STOCK_CHANGE):
            row["direct_cost"] -= net_credit
        else:
            row["expenses"] -= net_credit
    out = []
    for row in rows.values():
        row["profit"] = row["revenue"] - row["direct_cost"] - row["expenses"]
        row["by_head"] = dict(row["by_head"])
        out.append(row)
    _attach_trade_refs(out)
    return {"rows": sorted(out, key=lambda r: r["trade_id"]),
            "totals": {k: sum((r[k] for r in out), ZERO) for k in ("revenue", "direct_cost", "expenses", "profit")}}


def _attach_trade_refs(rows: list[dict]) -> None:
    from apps.accounting.selectors.trade_source import trade_queryset
    trades = {t.pk: t for t in trade_queryset().filter(pk__in=[r["trade_id"] for r in rows])}
    for r in rows:
        t = trades.get(r["trade_id"])
        r["invoice_number"] = t.invoice_number if t else ""
        r["direction"] = t.direction if t else ""
        r["licences"] = sorted({ln.sr_number.license.license_number for ln in t.lines.all()
                                if ln.sr_number and ln.sr_number.license}) if t else []


def suspense_register(entity: EntityBooks, *, as_of: date | None = None) -> list[dict]:
    as_of = as_of or date.today()
    return [{"id": s.pk, "amount": s.amount, "is_receipt": s.is_receipt, "reason": s.reason, "status": s.status,
             "owner": s.owner.username if s.owner else None, "date": s.voucher.date,
             "age_days": (as_of - s.voucher.date).days, "follow_up_on": s.follow_up_on,
             "statement_line_id": s.statement_line_id, "resolution_note": s.resolution_note,
             "resolution_voucher_id": s.resolution_voucher_id}
            for s in SuspenseItem.objects.filter(entity=entity).select_related("voucher", "owner")]


def loan_register(entity: EntityBooks, as_of: date) -> list[dict]:
    rows = []
    for loan in Loan.objects.filter(entity=entity).select_related("party", "principal_account", "interest_account"):
        principal = account_balance(loan.principal_account, end=as_of)
        interest = account_balance(loan.interest_account, end=as_of)
        sign = 1 if loan.direction == Loan.GIVEN else -1
        rows.append({"loan_id": loan.pk, "party": loan.party.name, "direction": loan.direction,
                     "sanctioned": loan.principal, "rate": loan.interest_rate, "status": loan.status,
                     "principal_outstanding": sign * principal, "interest_outstanding": sign * interest,
                     "total_outstanding": sign * (principal + interest)})
    return rows


IC_FLOWS = (  # (credit-side role, debit-side role, P&L lines they sit in)
    ("INTERCOMPANY_SALES", "INTERCOMPANY_PURCHASES", "gross_sales", "purchases"),
    ("INTERCOMPANY_COMMISSION_INCOME", "INTERCOMPANY_COMMISSION_EXPENSE", "commission_income", "commission_expense"),
)


def _ic_flow(entity: EntityBooks, role: str, others: set[int], start: date, end: date) -> Decimal:
    """Debit-positive movement on ``role`` in vouchers whose counterparty is another entity of the group."""
    from apps.accounting.models import Voucher
    if not others:
        return ZERO
    vids = Voucher.objects.filter(entity=entity, lines__account__intercompany_entity_id__in=others).values("pk")
    agg = (posted_lines(entity).filter(account__system_role=role, voucher_id__in=vids,
                                       voucher__date__gte=start, voucher__date__lte=end)
           .aggregate(d=Sum("debit"), c=Sum("credit")))
    return (agg["d"] or ZERO) - (agg["c"] or ZERO)


def consolidated(entities: list[EntityBooks], start: date, end: date, *, stock_reserve: Decimal = ZERO) -> dict:
    """Sum of separate books with intercompany elimination, computed only for dealings *within* the
    selected group. Read-only: elimination entries are never posted into any entity's books.

    Unrealised intercompany profit in closing stock cannot be derived from periodic-method books; the
    accountant supplies it as ``stock_reserve`` (reduces group gross profit and inventory) and the
    report warns whenever group stock and intercompany purchases coexist.
    """
    ids = {e.pk for e in entities}
    pl_totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    per_entity = []
    for e in entities:
        pl = profit_and_loss(e, start, end)
        per_entity.append({"entity_id": e.pk, "name": e.name, "net_sales": pl["net_sales"],
                           "gross_profit": pl["gross_profit"], "net_profit": pl["net_profit"]})
        for key, line in pl["lines"].items():
            pl_totals[key] += line["amount"]
    flows = {}
    for credit_role, debit_role, credit_line, debit_line in IC_FLOWS:
        income = sum((-_ic_flow(e, credit_role, ids - {e.pk}, start, end) for e in entities), ZERO)
        cost = sum((_ic_flow(e, debit_role, ids - {e.pk}, start, end) for e in entities), ZERO)
        eliminated = min(income, cost)
        pl_totals[credit_line] -= eliminated
        pl_totals[debit_line] -= eliminated
        flows[credit_role] = {"income": income, "cost": cost, "eliminated": eliminated, "difference": income - cost}
    pl_totals["stock_change"] += stock_reserve  # unrealised profit reverses out of closing stock
    ic_balances = []
    for e in entities:
        for acct in Account.objects.filter(entity=e, kind=AccountKind.PARTY, intercompany_entity_id__in=ids - {e.pk}):
            ic_balances.append({"entity_id": e.pk, "counterparty_entity_id": acct.intercompany_entity_id,
                                "account_id": acct.pk, "balance": account_balance(acct, end=end)})
    net_sales = pl_totals["gross_sales"] + pl_totals["sales_returns"]
    cogs = sum((pl_totals[k] for k in DIRECT_COSTS), ZERO)
    indirect = sum((pl_totals[k] for k in ("commission_expense", "bank_charges", "operating_expenses",
                                          "interest_expense")), ZERO)
    other = sum((pl_totals[k] for k in ("forex", "commission_income", "interest_income", "other_income")), ZERO)
    bs = [balance_sheet(e, end) for e in entities]
    ic_receivable = sum((b["balance"] for b in ic_balances if b["balance"] > 0), ZERO)
    ic_payable = -sum((b["balance"] for b in ic_balances if b["balance"] < 0), ZERO)
    group_stock = sum((a["amount"] for b in bs for a in b["assets"] if a["head"] == "INVENTORY"), ZERO)
    sales = flows["INTERCOMPANY_SALES"]
    warnings = []
    if group_stock and sales["cost"] and not stock_reserve:
        warnings.append("Group closing stock exists and entities bought from each other: unrealised intercompany "
                        "profit in that stock is not eliminated automatically — enter a stock reserve.")
    if any(f["difference"] for f in flows.values()):
        warnings.append("Intercompany income and cost do not agree; investigate before relying on the eliminations.")
    if ic_receivable != ic_payable:
        warnings.append("Intercompany receivables and payables do not agree.")
    total_assets = sum((b["total_assets"] for b in bs), ZERO) - ic_receivable - stock_reserve
    total_liab = sum((b["total_liabilities"] for b in bs), ZERO) - ic_payable - stock_reserve
    return {
        "entities": per_entity, "start": start, "end": end,
        "eliminations": {"intercompany_sales": sales["income"], "intercompany_purchases": sales["cost"],
                         "eliminated": sales["eliminated"], "unmatched_difference": sales["difference"],
                         "commission": flows["INTERCOMPANY_COMMISSION_INCOME"],
                         "intercompany_balances": ic_balances, "intercompany_receivable": ic_receivable,
                         "intercompany_payable": ic_payable,
                         "intercompany_balance_difference": ic_receivable - ic_payable,
                         "stock_reserve": stock_reserve, "group_closing_stock": group_stock},
        "profit_and_loss": {"lines": dict(pl_totals), "net_sales": net_sales, "gross_profit": net_sales - cogs,
                            "net_profit": net_sales - cogs - indirect + other},
        "balance_sheet": {"total_assets": total_assets, "total_liabilities": total_liab,
                          "balanced": total_assets == total_liab},
        "warnings": warnings,
    }


def dashboard(entity: EntityBooks, start: date, end: date) -> dict:
    from apps.accounting.models import LineStatus, StatementLine, Voucher
    pl = profit_and_loss(entity, start, end)
    bank_cash = Account.objects.filter(entity=entity, kind__in=[AccountKind.BANK, AccountKind.CASH])
    bank_bal = sum((account_balance(a, end=end) for a in bank_cash if a.kind == AccountKind.BANK), ZERO)
    cash_bal = sum((account_balance(a, end=end) for a in bank_cash if a.kind == AccountKind.CASH), ZERO)
    recv = ageing(entity, receivable=True, as_of=end)["totals"]
    pay = ageing(entity, receivable=False, as_of=end)["totals"]
    overdue = lambda t: t["total"] - t["not_due"]  # noqa: E731  (anything past its due date)
    return {
        "entity_id": entity.pk, "start": start, "end": end,
        "sales": pl["net_sales"], "purchases": pl["lines"]["purchases"]["amount"],
        "gross_profit": pl["gross_profit"], "net_profit": pl["net_profit"],
        "bank_balance": bank_bal, "cash_balance": cash_bal,
        "receivables": recv["total"], "payables": pay["total"],
        "overdue_receivables": overdue(recv), "overdue_payables": overdue(pay),
        "draft_vouchers": Voucher.objects.filter(entity=entity, status="DRAFT").count(),
        "unposted_invoices": Invoice.objects.filter(entity=entity, status__in=["DRAFT", "CONFIRMED"]).count(),
        "unmatched_bank_lines": StatementLine.objects.filter(bank_account__entity=entity,
                                                             status__in=[LineStatus.UNMATCHED, LineStatus.PARTIAL]).count(),
        "open_suspense": SuspenseItem.objects.filter(entity=entity, status=SuspenseItem.OPEN).count(),
        "gst_net_payable": gst_register(entity, start, end)["net_payable"],
        "tds_payable": -account_balance(_role(entity, "TDS_PAYABLE"), end=end),
        "loan_outstanding": sum((r["total_outstanding"] for r in loan_register(entity, end)), ZERO),
    }
