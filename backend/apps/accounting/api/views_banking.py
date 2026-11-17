"""Banking API: bank accounts, statement upload, workbench, matching, suspense, reconciliation."""
from __future__ import annotations

from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from apps.accounting.models import Account, BankAccount, BankMatch, Invoice, StatementImport, StatementLine, SuspenseItem, Voucher
from apps.accounting.selectors.reports import suspense_register
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
