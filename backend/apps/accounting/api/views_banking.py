"""Banking API: bank accounts, statement upload, workbench, matching, suspense, reconciliation."""
from __future__ import annotations

from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from apps.accounting.models import (
    Account, BankAccount, BankMatch, Invoice, NarrationAlias, StatementImport, StatementLine, SuspenseItem, Voucher,
)
from apps.core.models import CompanyModel
from apps.accounting.selectors.reports import suspense_register
from apps.accounting.services import bank_proposals as proposals_svc
from apps.accounting.services import banking
from apps.accounting.services import payments as pay_svc
from apps.accounts.models import User

from .common import AccountingView, ApproverView, as_date, as_int, as_money, entity_from, ok, page, param
from .present import bank_dict, line_dict, voucher_dict


class BankAccountListView(ApproverView):
    def get(self, request):
        e = entity_from(request)
        return ok([bank_dict(b) for b in BankAccount.objects.filter(entity=e).select_related("account")])

    def post(self, request):
        e = entity_from(request)
        opening = param(request, "opening_balance")
        bank = pay_svc.create_bank_account(
            e, bank_name=param(request, "bank_name", required=True),
            account_number=param(request, "account_number", required=True), ifsc=param(request, "ifsc", "") or "",
            is_cash=str(param(request, "is_cash", "false")).lower() in ("1", "true", "yes"),
            opening_balance=as_money(opening, "opening_balance") if opening not in (None, "") else None,
            opening_date=as_date(param(request, "opening_date"), "opening_date", e.books_start_date),
            user=request.user)
        return ok(bank_dict(bank), status.HTTP_201_CREATED)


class StatementUploadView(AccountingView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, bank_id: int):
        imports = StatementImport.objects.filter(bank_account_id=bank_id)
        return ok([{"id": i.pk, "file_name": i.file_name, "format": i.file_format, "rows_total": i.rows_total,
                    "rows_new": i.rows_new, "rows_duplicate": i.rows_duplicate, "rows_rejected": i.rows_rejected,
                    "errors": i.errors, "column_mapping": i.column_mapping, "uploaded_on": i.created_on,
                    "uploaded_by": i.created_by.username if i.created_by else None}
                   for i in imports.select_related("created_by")])

    def post(self, request, bank_id: int):
        bank = BankAccount.objects.select_related("entity").get(pk=bank_id)
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "Attach a CSV or Excel statement."})
        if upload.size > banking.MAX_UPLOAD_BYTES:  # refuse before reading the body into memory
            raise ValidationError({"file": "Statement file is larger than 10 MB."})
        mapping = request.data.get("column_mapping")
        if isinstance(mapping, str) and mapping.strip():
            import json
            try:
                mapping = json.loads(mapping)
            except ValueError as exc:
                raise ValidationError({"column_mapping": "Must be JSON {field: header}."}) from exc
        result = banking.import_statement(bank, file_name=upload.name, content=upload.read(),
                                          column_mapping=mapping or None, user=request.user)
        st = result.statement_import
        return ok({"id": st.pk, "rows_total": st.rows_total, "rows_new": st.rows_new,
                   "rows_duplicate": st.rows_duplicate, "rows_rejected": st.rows_rejected, "errors": st.errors,
                   "column_mapping": st.column_mapping}, status.HTTP_201_CREATED)


class StatementLineListView(AccountingView):
    def get(self, request, bank_id: int):
        qs = StatementLine.objects.filter(bank_account_id=bank_id).order_by("-txn_date", "-id")
        if param(request, "status"):
            qs = qs.filter(status__in=str(param(request, "status")).split(","))
        if param(request, "start"):
            qs = qs.filter(txn_date__gte=as_date(param(request, "start"), "start"))
        if param(request, "end"):
            qs = qs.filter(txn_date__lte=as_date(param(request, "end"), "end"))
        if param(request, "search"):
            term = param(request, "search")
            qs = qs.filter(Q(narration__icontains=term) | Q(reference__icontains=term))  # UTR / cheque no. too
        return ok(page(request, qs, line_dict))


class LineCandidatesView(AccountingView):
    def get(self, request, line_id: int):
        line = StatementLine.objects.select_related("bank_account").get(pk=line_id)
        return ok({"line": line_dict(line),
                   "candidates": [{"voucher": voucher_dict(c.voucher), "unmatched": c.unmatched, "score": c.score,
                                   "signals": c.signals, "party": banking.party_name(c.voucher)}
                                  for c in banking.candidates_for(line)[:20]]})


class AutoMatchView(AccountingView):
    def post(self, request, bank_id: int):
        return ok(banking.auto_match(BankAccount.objects.get(pk=bank_id), user=request.user))


class ManualMatchView(AccountingView):
    def post(self, request, line_id: int):
        line = StatementLine.objects.get(pk=line_id)
        raw = request.data.get("allocations") or []
        allocations = [(Voucher.objects.get(pk=as_int(r.get("voucher_id"), "voucher_id")), as_money(r.get("amount")))
                       for r in raw]
        return ok(line_dict(banking.manual_match(line, allocations, user=request.user)))


class UnmatchView(AccountingView):
    def post(self, request, match_id: int):
        line = banking.unmatch(BankMatch.objects.get(pk=match_id), reason=param(request, "reason", required=True),
                               user=request.user)
        return ok(line_dict(line))


class SuspenseView(ApproverView):
    """GET: suspense register. POST {line_id, reason, owner_id?, follow_up_on?}: move a line to suspense (posts)."""

    def get(self, request):
        return ok(suspense_register(entity_from(request)))

    def post(self, request):
        line = StatementLine.objects.get(pk=as_int(param(request, "line_id", required=True), "line_id"))
        owner_id = param(request, "owner_id")
        follow = param(request, "follow_up_on")
        item = banking.move_to_suspense(
            line, reason=param(request, "reason", required=True),
            owner=User.objects.get(pk=as_int(owner_id, "owner_id")) if owner_id else request.user,
            follow_up_on=as_date(follow, "follow_up_on") if follow else None, user=request.user)
        return ok({"id": item.pk, "voucher_id": item.voucher_id, "status": item.status}, status.HTTP_201_CREATED)


class SuspenseResolveView(ApproverView):
    """POST {mode: reclassify, account_id, note, allocations?} or {mode: match, voucher_id, note}."""

    def post(self, request, item_id: int):
        item = SuspenseItem.objects.select_related("entity").get(pk=item_id)
        note = param(request, "note", required=True)
        if param(request, "mode", "reclassify") == "match":
            voucher = Voucher.objects.get(pk=as_int(param(request, "voucher_id", required=True), "voucher_id"))
            item = banking.resolve_suspense_by_match(item, voucher, note=note, user=request.user)
        else:
            target = Account.objects.get(pk=as_int(param(request, "account_id", required=True), "account_id"),
                                         entity=item.entity)
            allocations = [(Invoice.objects.get(pk=as_int(r.get("invoice_id"), "invoice_id"), entity=item.entity),
                            as_money(r.get("amount"))) for r in (request.data.get("allocations") or [])]
            when = param(request, "date")
            item = banking.reclassify_suspense(item, target=target, note=note, allocations=allocations,
                                               resolution_date=as_date(when, "date") if when else None,
                                               user=request.user)
        return ok({"id": item.pk, "status": item.status, "resolution_voucher_id": item.resolution_voucher_id})


class ReconciliationView(AccountingView):
    def get(self, request, bank_id: int):
        from django.utils import timezone
        bank = BankAccount.objects.select_related("account", "entity").get(pk=bank_id)
        return ok(banking.bank_reconciliation(bank, as_date(param(request, "as_of"), "as_of", timezone.localdate())))


# --- invoice proposals (propose -> approver confirms; see services/bank_proposals.py) ------------------

def _party(p) -> dict | None:
    return {"id": p.pk, "name": p.name, "gstin": p.gst_number} if p is not None else None


def proposal_dict(p) -> dict:
    ln = p.line
    return {
        "line": {"id": ln.pk, "txn_date": ln.txn_date, "narration": ln.narration, "reference": ln.reference,
                 "debit": ln.debit, "credit": ln.credit, "amount": ln.amount, "status": ln.status},
        "direction": p.direction, "counterparty": p.counterparty, "party": _party(p.party), "source": p.source,
        "score": round(p.score, 2), "confidence": p.confidence, "blocked": p.blocked or None,
        "options": [{**_party(o), "score": round(sc, 2)} for o, sc in p.options],
        "allocations": [{"invoice_id": a.invoice.pk, "number": a.invoice.number, "date": a.invoice.date,
                         "due_date": a.invoice.due_date, "outstanding": a.outstanding, "amount": a.amount}
                        for a in p.allocations],
        "advance": p.advance, "exact_bill": p.exact_bill, "existing_candidates": p.existing_candidates,
        "is_bulk": p.is_bulk,
    }


class BankProposalListView(ApproverView):
    """GET bank-accounts/<id>/proposals/?confidence=&direction=  Read-only proposals for unmatched lines."""

    def get(self, request, bank_id: int):
        bank = BankAccount.objects.select_related("entity").get(pk=bank_id)
        rows = proposals_svc.proposals_for(bank)
        summary = {level: sum(1 for p in rows if p.confidence == level) for level in ("high", "medium", "low", "none", "bulk")}
        if param(request, "confidence"):
            wanted = set(str(param(request, "confidence")).split(","))
            rows = [p for p in rows if p.confidence in wanted]
        if param(request, "direction"):
            rows = [p for p in rows if p.direction == param(request, "direction")]
        return ok({"bank_account_id": bank.pk, "summary": {**summary, "total": sum(summary.values())},
                   "proposals": [proposal_dict(p) for p in rows]})


class BankProposalConfirmView(ApproverView):
    """POST {items: [{line_id, party_id}]}  Books each line (receipt/payment, oldest bills first, excess advance)."""

    def post(self, request, bank_id: int):
        bank = BankAccount.objects.select_related("entity").get(pk=bank_id)
        raw = request.data.get("items") or []
        if not isinstance(raw, list) or not raw:
            raise ValidationError({"items": "Give at least one {line_id, party_id}."})
        items = [(as_int(r.get("line_id"), "line_id"), as_int(r.get("party_id"), "party_id")) for r in raw]
        return ok(proposals_svc.confirm_many(bank, items, user=request.user))


class LineProposalView(ApproverView):
    """GET statement-lines/<id>/proposal/?party_id=  Preview the allocation for a chosen party (read-only)."""

    def get(self, request, line_id: int):
        line = StatementLine.objects.select_related("bank_account__entity").get(pk=line_id)
        party = CompanyModel.objects.get(pk=as_int(param(request, "party_id"), "party_id")) \
            if param(request, "party_id") else None
        return ok(proposal_dict(proposals_svc.proposal_for(line, party)))


class NarrationAliasView(ApproverView):
    """GET narration-aliases/?entity=  learned narration -> party mappings; DELETE narration-aliases/<id>/."""

    def get(self, request):
        e = entity_from(request)
        qs = NarrationAlias.objects.filter(entity=e).select_related("party").order_by("key", "direction")
        return ok({"aliases": [{"id": a.pk, "key": a.key, "direction": a.direction, "party_id": a.party_id,
                                "party": a.party.name, "hits": a.hits, "modified_on": a.modified_on} for a in qs]})

    def delete(self, request, alias_id: int):
        proposals_svc.forget_alias(NarrationAlias.objects.select_related("entity").get(pk=alias_id), user=request.user)
        return ok({"deleted": alias_id})


class PartyBankLinesView(AccountingView):
    """GET parties/<party_id>/bank-lines/?entity=&direction=RECEIPT|PAYMENT&search=
    Unmatched bank transactions for the record-payment screen, ranked for the party (read-only)."""

    def get(self, request, party_id: int):
        e = entity_from(request)
        direction = param(request, "direction", required=True)
        if direction not in ("RECEIPT", "PAYMENT"):
            raise ValidationError({"direction": "RECEIPT or PAYMENT."})
        party = CompanyModel.objects.get(pk=party_id)
        rows = proposals_svc.party_bank_lines(e, party, direction, search=param(request, "search", "") or "")
        return ok({"lines": [{
            "id": r["line"].pk, "bank_account_id": r["line"].bank_account_id,
            "bank": f"{r['line'].bank_account.bank_name} {r['line'].bank_account.account_number}".strip(),
            "txn_date": r["line"].txn_date, "narration": r["line"].narration, "reference": r["line"].reference,
            "amount": r["line"].amount, "remaining": r["remaining"], "status": r["line"].status,
            "mode": r["mode"], "score": round(r["score"], 2), "source": r["source"],
        } for r in rows]})


class UndoProposalView(ApproverView):
    """POST bank-proposals/<payment_id>/undo/  Unmatch + reverse a confirmed proposal (line back to unmatched)."""

    def post(self, request, payment_id: int):
        from apps.accounting.models import Payment
        line = proposals_svc.undo_confirmation(Payment.objects.get(pk=payment_id), user=request.user)
        return ok({"line_id": line.pk, "status": line.status})


def _split_rows(raw) -> list:
    if not isinstance(raw, list) or not raw:
        raise ValidationError({"rows": "Give at least one {party_id, amount}."})
    parties = CompanyModel.objects.in_bulk({as_int(r.get("party_id"), "party_id") for r in raw})
    rows = []
    for r in raw:
        party = parties.get(as_int(r.get("party_id"), "party_id"))
        if party is None:
            raise ValidationError({"rows": f"Unknown party {r.get('party_id')}."})
        rows.append((party, as_money(r.get("amount"))))
    return rows


class LineSplitView(ApproverView):
    """POST statement-lines/<id>/split/ {rows:[{party_id, amount}], dry_run?}
    dry_run: the oldest-first bills per row (read-only). Otherwise books one payment/receipt per row and
    matches them all to the line; rows must add up to the line's unmatched amount."""

    def post(self, request, line_id: int):
        line = StatementLine.objects.select_related("bank_account__entity").get(pk=line_id)
        rows = _split_rows(request.data.get("rows"))
        if request.data.get("dry_run"):
            return ok({"rows": [{"party_id": r.party.pk, "party": r.party.name, "amount": r.amount, "advance": r.advance,
                                 "allocations": [{"invoice_id": a.invoice.pk, "number": a.invoice.number, "date": a.invoice.date,
                                                  "outstanding": a.outstanding, "amount": a.amount} for a in r.allocations]}
                                for r in proposals_svc.plan_split(line, rows)]})
        payments = proposals_svc.split_line(line, rows, user=request.user)
        return ok({"line_id": line.pk, "payments": [{"id": p.pk, "voucher": p.voucher.number, "party_id": p.party_id,
                                                     "party": p.party.name, "amount": p.amount} for p in payments]})

    def delete(self, request, line_id: int):
        line = proposals_svc.undo_split(StatementLine.objects.get(pk=line_id), user=request.user)
        return ok({"line_id": line.pk, "status": line.status})
