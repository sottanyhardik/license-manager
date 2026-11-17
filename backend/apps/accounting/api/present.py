"""Read representations (plain dicts). Money stays Decimal until ``jsonable`` turns it into strings."""
from __future__ import annotations

from apps.accounting.models import BankAccount, Invoice, Payment, StatementLine, Voucher


def entity_dict(e) -> dict:
    return {"id": e.pk, "company_id": e.company_id, "name": e.company.name, "gstin": e.company.gst_number,
            "pan": e.company.pan, "state_code": e.state_code, "books_start_date": e.books_start_date,
            "default_credit_days": e.default_credit_days, "require_maker_checker": e.require_maker_checker,
            "is_active": e.is_active}


def account_dict(a) -> dict:
    return {"id": a.pk, "code": a.code, "name": a.name, "group_id": a.group_id, "group": a.group.name,
            "nature": a.group.nature, "report_head": a.group.report_head, "kind": a.kind,
            "system_role": a.system_role, "party_id": a.party_id, "intercompany_entity_id": a.intercompany_entity_id,
            "is_active": a.is_active}


def voucher_dict(v: Voucher, lines: bool = False) -> dict:
    data = {"id": v.pk, "entity_id": v.entity_id, "number": v.number, "voucher_type": v.voucher_type,
            "date": v.date, "status": v.status, "narration": v.narration, "total": v.total,
            "source_type": v.source_type, "source_id": v.source_id, "source_event": v.source_event,
            "reversal_of_id": v.reversal_of_id, "posted_at": v.posted_at,
            "posted_by": v.posted_by.username if v.posted_by_id and v.posted_by else None,
            "created_by": v.created_by.username if v.created_by_id and v.created_by else None}
    if lines:
        data["lines"] = [{"line_no": ln.line_no, "account_id": ln.account_id, "account_code": ln.account.code,
                          "account": ln.account.name, "debit": ln.debit, "credit": ln.credit,
                          "narration": ln.narration, "trade_id": ln.trade_id, "cost_centre_id": ln.cost_centre_id}
                         for ln in v.lines.select_related("account")]
        reversed_by = getattr(v, "reversed_by", None) if v.status == "REVERSED" else None
        data["reversed_by_id"] = reversed_by.pk if reversed_by else None
    return data


def invoice_dict(inv: Invoice, lines: bool = False) -> dict:
    from apps.accounting.services.invoices import outstanding, payment_status, settled_amount
    data = {"id": inv.pk, "entity_id": inv.entity_id, "kind": inv.kind, "number": inv.number,
            "party_id": inv.party_id, "party": inv.party.name, "party_reference": inv.party_reference,
            "date": inv.date, "due_date": inv.due_date, "credit_days": inv.credit_days,
            "currency": inv.currency, "fx_rate": inv.fx_rate,
            "taxable_amount": inv.taxable_amount, "cgst": inv.cgst, "sgst": inv.sgst, "igst": inv.igst,
            "roundoff": inv.roundoff, "gross_amount": inv.gross_amount,
            "tds_section": inv.tds_section.code if inv.tds_section_id else None, "tds_rate": inv.tds_rate,
            "tds_amount": inv.tds_amount, "net_amount": inv.net_amount, "status": inv.status,
            "payment_status": payment_status(inv), "settled": settled_amount(inv), "outstanding": outstanding(inv),
            "trade_id": inv.trade_id, "against_invoice_id": inv.against_invoice_id, "voucher_id": inv.voucher_id,
            "voucher_number": inv.voucher.number if inv.voucher_id else None, "narration": inv.narration}
    if lines:
        data["lines"] = [{"line_no": ln.line_no, "account_id": ln.account_id, "account": ln.account.name,
                          "description": ln.description, "quantity": ln.quantity, "amount": ln.amount,
                          "gst_rate": ln.gst_rate, "cgst": ln.cgst, "sgst": ln.sgst, "igst": ln.igst,
                          "trade_id": ln.trade_id, "cost_centre_id": ln.cost_centre_id}
                         for ln in inv.lines.select_related("account")]
        data["settlements"] = [{"id": s.pk, "amount": s.amount, "voucher_id": s.voucher_id,
                                "voucher_number": s.voucher.number, "payment_id": s.payment_id,
                                "note_id": s.note_id, "is_active": s.is_active, "date": s.voucher.date}
                               for s in inv.settlements.select_related("voucher")]
    return data


def payment_dict(p: Payment) -> dict:
    from apps.accounting.services.payments import unallocated
    return {"id": p.pk, "entity_id": p.entity_id, "direction": p.direction, "party_id": p.party_id,
            "party": p.party.name, "bank_account_id": p.bank_account_id, "date": p.date, "amount": p.amount,
            "tds_amount": p.tds_amount, "mode": p.mode, "reference": p.reference, "status": p.status,
            "voucher_id": p.voucher_id, "voucher_number": p.voucher.number if p.voucher_id else None,
            "trade_payment_id": p.trade_payment_id, "unallocated": unallocated(p) if p.status == "POSTED" else None,
            "narration": p.narration}


def bank_dict(b: BankAccount) -> dict:
    from apps.accounting.selectors.ledger import account_balance
    return {"id": b.pk, "entity_id": b.entity_id, "account_id": b.account_id, "bank_name": b.bank_name,
            "account_number": b.account_number, "ifsc": b.ifsc, "is_cash": b.is_cash, "is_active": b.is_active,
            "book_balance": account_balance(b.account)}


def line_dict(ln: StatementLine) -> dict:
    from apps.accounting.services.banking import line_remaining
    return {"id": ln.pk, "bank_account_id": ln.bank_account_id, "import_id": ln.statement_import_id,
            "txn_date": ln.txn_date, "value_date": ln.value_date, "narration": ln.narration,
            "reference": ln.reference, "debit": ln.debit, "credit": ln.credit, "balance": ln.balance,
            "status": ln.status, "matched_amount": ln.matched_amount, "unmatched": line_remaining(ln),
            "matches": [{"id": m.pk, "voucher_id": m.voucher_id, "voucher_number": m.voucher.number,
                         "amount": m.amount, "method": m.method, "is_active": m.is_active,
                         "created_on": m.created_on} for m in ln.matches.select_related("voucher")]}
